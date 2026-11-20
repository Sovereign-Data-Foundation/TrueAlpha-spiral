import hashlib
import json
import os
import shutil
import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tas_conformance_harness import Allocation, SettlementSlice, allocation_digest
from tas_financial_state import (
    MAX_U64, RECEIPT_DOMAIN, BatchSettlement, EscrowAllocation, FinancialMachine,
    FinancialState, ReleaseStatus, Share, TribunalToken, calculate_batch_settlement,
    tribunal_signing_payload,
)

CVP = (SettlementSlice("a", 6000), SettlementSlice("b", 4000))
CVP_DIGEST = allocation_digest(CVP)


@pytest.fixture
def env():
    directory = Path(".qf-test-" + uuid.uuid4().hex)
    directory.mkdir()
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    machine = FinancialMachine(directory / "ledger.sqlite", machine_id="machine-1",
                               tribunal_key=public)
    try:
        yield directory, key, public, machine
    finally:
        shutil.rmtree(directory)


def token(allocation_id="a", nonce="nonce-1", verdict="exonerated", digest="ab" * 32):
    return TribunalToken("machine-1", nonce, allocation_id, verdict, digest, CVP_DIGEST)


def sign(key, message):
    return key.sign(tribunal_signing_payload(message))


def provision(machine):
    return machine.provision(
        [EscrowAllocation("a", 30, "ab" * 32),
         EscrowAllocation("b", 20, "cd" * 32)],
        cvp_allocations=CVP, liquid_sum=20, r_legal=10, r_infra=5,
    )


def test_exonerated_and_forfeited_conserve_and_receipt_binds(env):
    directory, key, _, machine = env
    assert provision(machine) == FinancialState(85, 10, 5, 70, 20, 50, 50)
    first = token()
    result = machine.release(first, sign(key, first))
    assert result.status == ReleaseStatus.RELEASED
    assert result.state == FinancialState(85, 10, 5, 70, 50, 20, 20)
    with sqlite3.connect(directory / "ledger.sqlite") as db:
        stored_hash, raw = db.execute(
            "SELECT receipt_hash, canonical_receipt FROM qf_receipts"
        ).fetchone()
        receipt = json.loads(raw)
        assert receipt["dispute_digest"] == first.dispute_digest
        assert receipt["allocation_id"] == first.allocation_id
        assert receipt["cvp_allocation_digest"] == CVP_DIGEST
        key.public_key().verify(bytes.fromhex(receipt["tribunal_signature"]),
                                tribunal_signing_payload(first))
        assert result.receipt_hash == stored_hash == hashlib.sha256(
            RECEIPT_DOMAIN + raw
        ).hexdigest()
    second = token("b", "nonce-2", "upheld", "cd" * 32)
    result = machine.release(second, sign(key, second))
    assert result.state == FinancialState(85, 30, 5, 50, 50, 0, 0)
    assert machine.state() == result.state
    for allocation, digest in [("a", "ab" * 32), ("b", "cd" * 32)]:
        again = token(allocation, "fresh-" + allocation, "exonerated", digest)
        assert machine.release(again, sign(key, again)).status == ReleaseStatus.ALREADY_RESOLVED


def test_signature_tampering_missing_id_and_dispute_binding(env):
    directory, key, public, machine = env
    provision(machine)
    original = token()
    signature = sign(key, original)
    for changed in (
        replace(original, machine_id="other"), replace(original, nonce="other"),
        replace(original, allocation_id="b"), replace(original, verdict="upheld"),
        replace(original, dispute_digest="cd" * 32),
        replace(original, cvp_allocation_digest="01" * 32),
    ):
        assert machine.release(changed, signature).status == ReleaseStatus.FORGED
    wrong = Ed25519PrivateKey.generate()
    for sig in (sign(wrong, original), b"", b"\0" * 64, None, True):
        assert machine.release(original, sig).status == ReleaseStatus.FORGED
    missing = replace(original, allocation_id="missing")
    assert machine.release(missing, sign(key, missing)).status == ReleaseStatus.MISSING_ALLOCATION
    mismatch = replace(original, dispute_digest="ef" * 32)
    assert machine.release(mismatch, sign(key, mismatch)).status == ReleaseStatus.DISPUTE_MISMATCH
    mismatch = replace(original, cvp_allocation_digest="ef" * 32)
    assert machine.release(mismatch, sign(key, mismatch)).status == ReleaseStatus.CVP_MISMATCH
    assert machine.state() == FinancialState(85, 10, 5, 70, 20, 50, 50)
    with pytest.raises(ValueError):
        FinancialMachine(directory / "ledger.sqlite", machine_id="machine-1",
                         tribunal_key=wrong.public_key().public_bytes(
                             serialization.Encoding.Raw, serialization.PublicFormat.Raw))
    with pytest.raises(ValueError):
        FinancialMachine(directory / "ledger.sqlite", machine_id="different", tribunal_key=public)


def test_global_nonce_replay_and_race(env):
    directory, key, public, machine = env
    provision(machine)
    message = token()
    signature = sign(key, message)
    barrier = threading.Barrier(2)

    def run(_):
        instance = FinancialMachine(directory / "ledger.sqlite", machine_id="machine-1",
                                    tribunal_key=public)
        barrier.wait()
        return instance.release(message, signature).status

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(run, range(2)))
    assert sorted(outcomes) == [ReleaseStatus.RELEASED, ReleaseStatus.REPLAY]
    changed = token("b", message.nonce, "upheld", "cd" * 32)
    assert machine.release(changed, sign(key, changed)).status == ReleaseStatus.REPLAY
    assert machine.release(message, b"\0" * 64).status == ReleaseStatus.FORGED
    with sqlite3.connect(directory / "ledger.sqlite") as db:
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert db.execute("SELECT COUNT(*) FROM qf_receipts").fetchone()[0] == 1
    assert machine.state() == FinancialState(85, 10, 5, 70, 50, 20, 20)


def test_atomic_rollback_and_retry(env):
    directory, key, _, machine = env
    before = provision(machine)
    message = token()
    signature = sign(key, message)
    with sqlite3.connect(directory / "ledger.sqlite") as db:
        db.execute("CREATE TRIGGER reject_receipt BEFORE INSERT ON qf_receipts "
                   "BEGIN SELECT RAISE(ABORT, 'injected'); END")
    with pytest.raises(sqlite3.IntegrityError):
        machine.release(message, signature)
    assert machine.state() == before
    with sqlite3.connect(directory / "ledger.sqlite") as db:
        assert db.execute("SELECT status FROM qf_allocations WHERE allocation_id='a'").fetchone() == ("escrow",)
        assert db.execute("SELECT COUNT(*) FROM qf_receipts").fetchone()[0] == 0
        db.execute("DROP TRIGGER reject_receipt")
    assert machine.release(message, signature).status == ReleaseStatus.RELEASED


def test_distinct_nonce_race_does_not_double_resolve(env):
    _, key, _, machine = env
    before = provision(machine)
    barrier = threading.Barrier(2)
    messages = [token(nonce="one"), token(nonce="two", verdict="upheld")]

    def run(message):
        signature = sign(key, message)
        barrier.wait()
        return machine.release(message, signature)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, messages))
    assert sorted(result.status for result in results) == [
        ReleaseStatus.RELEASED, ReleaseStatus.ALREADY_RESOLVED
    ]
    state = machine.state()
    assert state.r_gross == before.r_gross
    assert state.escrow_sum == state.escrow_bal == 20
    assert state.r_legal + state.r_infra + state.r_dist == state.r_gross
    assert state.liquid_sum + state.escrow_sum == state.r_dist


def test_corrupt_state_fails_closed(env):
    directory, key, _, machine = env
    provision(machine)
    with sqlite3.connect(directory / "ledger.sqlite") as db:
        db.execute("UPDATE qf_state SET escrow_bal='1'")
    message = token()
    with pytest.raises(ValueError, match="invalid persisted"):
        machine.release(message, sign(key, message))
    with sqlite3.connect(directory / "ledger.sqlite") as db:
        assert db.execute("SELECT COUNT(*) FROM qf_receipts").fetchone()[0] == 0
        assert db.execute("SELECT status FROM qf_allocations WHERE allocation_id='a'").fetchone() == ("escrow",)


def test_uint64_duplicates_and_single_provision(env):
    _, key, _, machine = env
    with pytest.raises(ValueError, match="duplicate"):
        machine.provision([EscrowAllocation("a", 1, "ab" * 32)] * 2, cvp_allocations=CVP)
    for amount, error in [(True, TypeError), (-1, ValueError), (MAX_U64 + 1, OverflowError)]:
        with pytest.raises(error):
            machine.provision([EscrowAllocation("a", amount, "ab" * 32)], cvp_allocations=CVP)
    with pytest.raises(OverflowError):
        machine.provision([EscrowAllocation("a", MAX_U64, "ab" * 32)], cvp_allocations=CVP, liquid_sum=1)
    with pytest.raises(ValueError):
        machine.provision([EscrowAllocation("a", 1, "bad")], cvp_allocations=CVP)
    with pytest.raises(ValueError, match="duplicate CVP"):
        machine.provision([], cvp_allocations=[SettlementSlice("a", 5000)] * 2)
    limit = MAX_U64 // 1500
    with pytest.raises(OverflowError, match="1500"):
        machine.provision([EscrowAllocation("a", limit + 1, "ab" * 32)], cvp_allocations=CVP)
    assert machine.provision([EscrowAllocation("a", limit, "ab" * 32)], cvp_allocations=CVP).r_gross == limit
    with pytest.raises(ValueError, match="already provisioned"):
        machine.provision([], cvp_allocations=CVP)
    message = token()
    assert machine.release(message, sign(key, message)).state.liquid_sum == limit


def test_batch_is_pure_ranked_head_cons_and_ties(env):
    _, _, _, machine = env
    shares = [Share("z", 2500, False), Share("a", 2500, False),
              Share("c", 2500, True), Share("b", 2500, True)]
    assert calculate_batch_settlement(2, shares) == BatchSettlement(
        (Allocation("z", 0), Allocation("a", 1)),
        (Allocation("c", 0), Allocation("b", 1)),
    )
    assert calculate_batch_settlement(2, list(reversed(shares))) == calculate_batch_settlement(2, shares)
    with pytest.raises(ValueError, match="not provisioned"):
        machine.state()
    with pytest.raises(ValueError, match="duplicate"):
        calculate_batch_settlement(2, [Share("a", 5000, True), Share("a", 5000, False)])
    with pytest.raises(TypeError):
        calculate_batch_settlement(2, [Share("a", 10000, 1)])
    with pytest.raises(OverflowError):
        calculate_batch_settlement(MAX_U64, [Share("a", 10000, False)])
    with pytest.raises(ValueError):
        calculate_batch_settlement(1, [Share("a", 9999, False)])


def test_token_canonical_payload_and_validation():
    message = token()
    payload = tribunal_signing_payload(message)
    assert payload.endswith(
        b'{"allocation_id":"a","cvp_allocation_digest":"' + CVP_DIGEST.encode()
        + b'","dispute_digest":"' + b"ab" * 32
        + b'","machine_id":"machine-1","nonce":"nonce-1","verdict":"exonerated"}'
    )
    for invalid in (replace(message, nonce=""), replace(message, verdict="other"),
                    replace(message, dispute_digest="AB" * 32)):
        with pytest.raises(ValueError):
            tribunal_signing_payload(invalid)


def test_adversarial_verdict_subclass_rejected(env):
    _, key, _, machine = env
    before = provision(machine)

    class DeceptiveVerdict(str):
        def __eq__(self, other):
            return True

    message = token()
    forged = replace(message, verdict=DeceptiveVerdict("exonerated"))
    assert machine.release(forged, sign(key, message)).status == ReleaseStatus.FORGED
    with pytest.raises(ValueError):
        tribunal_signing_payload(forged)
    assert machine.state() == before


def test_persisted_gross_overflow_and_cvp_corruption_fail_closed(env):
    directory, key, _, machine = env
    provision(machine)
    message = token()
    signature = sign(key, message)
    with sqlite3.connect(directory / "ledger.sqlite") as db:
        db.execute("UPDATE qf_state SET r_gross=?", (str(MAX_U64 // 1500 + 1),))
    with pytest.raises(ValueError, match="invalid persisted"):
        machine.release(message, signature)
    with sqlite3.connect(directory / "ledger.sqlite") as db:
        db.execute("UPDATE qf_state SET r_gross='85'")
        db.execute("UPDATE qf_cvp SET digest=?", ("00" * 32,))
    with pytest.raises(ValueError, match="invalid persisted"):
        machine.release(message, signature)
    with sqlite3.connect(directory / "ledger.sqlite") as db:
        assert db.execute("SELECT COUNT(*) FROM qf_receipts").fetchone()[0] == 0


def test_relative_path_survives_cwd_change(env, monkeypatch):
    directory, key, public, _ = env
    original = Path.cwd()
    root = directory.resolve()
    (root / "other").mkdir()
    try:
        monkeypatch.chdir(root)
        machine = FinancialMachine("relative.sqlite", machine_id="machine-1", tribunal_key=public)
        before = provision(machine)
        monkeypatch.chdir(root / "other")
        decoy = FinancialMachine("relative.sqlite", machine_id="machine-2", tribunal_key=public)
        decoy_before = provision(decoy)
        assert machine.state() == before
        message = token()
        assert machine.release(message, sign(key, message)).status == ReleaseStatus.RELEASED
        assert decoy.state() == decoy_before
        assert Path(machine.path) == root / "relative.sqlite"
    finally:
        monkeypatch.chdir(original)


@pytest.mark.parametrize("changed", ["machine_id", "tribunal_key"])
def test_replaced_database_fails_closed_in_each_transaction(env, changed):
    directory, key, public, machine = env
    provision(machine)
    other_key = Ed25519PrivateKey.generate()
    other_public = other_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    replacement_path = directory / "replacement.sqlite"
    replacement = FinancialMachine(
        replacement_path,
        machine_id="machine-2" if changed == "machine_id" else "machine-1",
        tribunal_key=other_public if changed == "tribunal_key" else public,
    )
    replacement_before = provision(replacement)
    original_path = directory / "ledger.sqlite"
    for path in (original_path, replacement_path):
        with sqlite3.connect(path) as db:
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()
    os.replace(replacement_path, original_path)
    message = token()
    for operation in (
        lambda: machine.state(),
        lambda: machine.provision([], cvp_allocations=CVP),
        lambda: machine.release(message, sign(key, message)),
    ):
        with pytest.raises(ValueError, match="machine ID or trusted tribunal key mismatch"):
            operation()
    with sqlite3.connect(original_path) as db:
        assert db.execute("SELECT COUNT(*) FROM qf_receipts").fetchone()[0] == 0
        assert db.execute("SELECT status FROM qf_allocations WHERE allocation_id='a'").fetchone() == ("escrow",)
        assert db.execute("SELECT r_gross FROM qf_state").fetchone() == (str(replacement_before.r_gross),)
