"""Cryptographic evidence and atomic internal escrow transition tests."""

import hashlib
import json
import sqlite3
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sdf_admissibility_daemon import SQLiteDecisionLedger
from tas_conformance_harness import (
    CAPABILITY_DOMAIN,
    CONFIGURED_SMT_ROOT,
    CapabilityEnvelope,
    EscrowLedger,
    EscrowRequest,
    SettlementSlice,
    SparseNonInclusionProof,
    TrustedGate,
    allocation_digest,
    capability_signing_payload,
    compute_jcs_receipt_digest,
    derive_capability_key_index,
    deterministic_jcs_serialize,
    escrow_signing_payload,
    eval_admission_gate,
    provision_escrow_ledger,
    release_escrow,
)


def public_bytes(key):
    return key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )


class CryptoTests(unittest.TestCase):
    def setUp(self):
        self.issuer = Ed25519PrivateKey.from_private_bytes(b"\x01" * 32)
        self.adjudicator = Ed25519PrivateKey.from_private_bytes(b"\x02" * 32)
        self.cap = CapabilityEnvelope("issuer", "capability", 10, 20)
        self.proof = SparseNonInclusionProof(tuple(
            hashlib.sha256(f"sibling-{i}".encode()).hexdigest() for i in range(256)
        ))
        node = bytes(32)
        path = int(derive_capability_key_index(self.cap), 16)
        for i, sibling in enumerate(self.proof.siblings):
            sibling = bytes.fromhex(sibling)
            node = hashlib.sha256(
                b"\x01" + (sibling + node if path & (1 << i) else node + sibling)
            ).digest()
        self.trusted = TrustedGate(
            "issuer", public_bytes(self.issuer), public_bytes(self.adjudicator), node.hex()
        )
        self.cap_sig = self.issuer.sign(capability_signing_payload(self.cap))
        self.initial = EscrowLedger(100, 10, 10, 80, 30, 50, 50)
        self.request = EscrowRequest(
            "ledger", "nonce-1", 5, True, self.initial, (SettlementSlice("a", 10000),)
        )
        # A shared in-memory SQLite database keeps all operations in memory.
        self.uri = f"file:tas-{uuid.uuid4().hex}?mode=memory&cache=shared"
        self.anchor = sqlite3.connect(self.uri, uri=True)
        self.ledger = SQLiteDecisionLedger(self.uri)
        provision_escrow_ledger(self.ledger, "ledger", self.initial)

    def tearDown(self):
        self.anchor.close()

    def sign_release(self, request=None):
        return self.adjudicator.sign(
            escrow_signing_payload(request or self.request, self.cap, self.trusted)
        )

    def release(self, request=None, cap_sig=None, proof=None, release_sig=None,
                trusted=None, now=15):
        request = request or self.request
        return release_escrow(
            request, self.cap, self.cap_sig if cap_sig is None else cap_sig,
            self.proof if proof is None else proof,
            self.sign_release(request) if release_sig is None else release_sig,
            trusted=self.trusted if trusted is None else trusted, now=now,
            ledger=self.ledger,
        )

    def test_gate_requires_signatures_trusted_keys_time_and_real_proof(self):
        gate = lambda cap, sig, proof, trust, now: eval_admission_gate(
            cap, sig, proof, trusted=trust, now=now
        )
        self.assertTrue(gate(self.cap, self.cap_sig, self.proof, self.trusted, 10))
        self.assertTrue(gate(self.cap, self.cap_sig, self.proof, self.trusted, 20))
        for sig in (b"", b"\x00" * 64, self.cap_sig[:-1], None, True,
                    self.issuer.sign(b"wrong" + capability_signing_payload(self.cap))):
            self.assertFalse(gate(self.cap, sig, self.proof, self.trusted, 15))
        self.assertFalse(gate(replace(self.cap, capability_id="other"), self.cap_sig,
                              self.proof, self.trusted, 15))
        self.assertFalse(gate(self.cap, self.cap_sig, self.proof, self.trusted, 21))
        self.assertFalse(gate(self.cap, self.cap_sig, self.proof, self.trusted, True))
        self.assertFalse(gate(self.cap, self.cap_sig, True, self.trusted, 15))
        self.assertFalse(gate(self.cap, self.cap_sig, replace(
            self.proof, siblings=("00" * 32,) + self.proof.siblings[1:]
        ), self.trusted, 15))
        self.assertFalse(gate(self.cap, self.cap_sig, replace(
            self.proof, siblings=self.proof.siblings[:-1]
        ), self.trusted, 15))
        self.assertFalse(gate(self.cap, self.cap_sig, self.proof, replace(
            self.trusted, issuer_key=public_bytes(self.adjudicator)
        ), 15))
        self.assertFalse(gate(self.cap, self.cap_sig, self.proof, replace(
            self.trusted, issuer_key=public_bytes(Ed25519PrivateKey.generate())
        ), 15))

    def test_anchor_is_configured_not_empty_tree_recursion(self):
        node = bytes(32)
        defaults = []
        for _ in range(256):
            defaults.append(node.hex())
            node = hashlib.sha256(b"\x01" + node + node).digest()
        self.assertEqual(node.hex(), "6155289130893872355eac98042d22aefa2c2e708bea169402760e3b55f9a2dc")
        self.assertEqual(TrustedGate("i", b"a" * 32, b"b" * 32).revocation_root,
                         CONFIGURED_SMT_ROOT)
        self.assertNotEqual(node.hex(), CONFIGURED_SMT_ROOT)
        self.assertFalse(eval_admission_gate(
            self.cap, self.cap_sig, SparseNonInclusionProof(tuple(defaults)),
            trusted=replace(self.trusted, revocation_root=CONFIGURED_SMT_ROOT), now=15
        ))
        self.assertTrue(eval_admission_gate(
            self.cap, self.cap_sig, SparseNonInclusionProof(tuple(defaults)),
            trusted=replace(self.trusted, revocation_root=node.hex()), now=15
        ))

    def test_commit_is_atomic_replay_safe_and_receipt_binds_allocation(self):
        result = self.release()
        self.assertEqual(result.ledger, EscrowLedger(100, 15, 10, 75, 30, 45, 45))
        self.assertEqual(self.request.expected, self.initial)
        with self.assertRaises(FrozenInstanceError):
            result.ledger.r_legal = 0
        self.assertIsNone(self.release())
        with self.ledger._connect() as con:
            payload = con.execute("SELECT canonical_receipt FROM decision_receipts").fetchone()[0]
            receipt = json.loads(payload)
            self.assertEqual(receipt["request"]["allocation_digest"],
                             allocation_digest(self.request.allocations))
            self.assertEqual(result.receipt_hash, "sha256:" + compute_jcs_receipt_digest(receipt))
            self.assertEqual(con.execute(
                "SELECT evidence_sequence, state_sequence FROM ledger_meta"
            ).fetchone(), (1, 1))
        next_request = replace(self.request, expected=result.ledger)
        self.assertIsNone(self.release(next_request))
        appended = self.ledger.append_decision_once(
            replay_key="daemon-test", authorization_hash="sha256:authorization",
            receipt_hash="sha256:next", receipt={"decision": "ADMITTED"},
            expected_state_parent_hash=result.receipt_hash, advances_state_lineage=True,
        )
        self.assertEqual((appended.evidence_sequence, appended.state_sequence), (2, 2))
        second = self.release(replace(next_request, nonce="nonce-2"))
        self.assertIsNotNone(second)
        with self.ledger._connect() as con:
            self.assertEqual(con.execute(
                "SELECT expected_state_parent_hash FROM decision_receipts WHERE receipt_hash=?",
                (second.receipt_hash,)
            ).fetchone()[0], "sha256:next")

    def test_changed_request_wrong_key_and_invalid_inputs_refuse(self):
        signature = self.sign_release()
        changed = replace(self.request, delta=6)
        self.assertIsNone(self.release(changed, release_sig=signature))
        self.assertIsNone(self.release(replace(self.request, allocations=(SettlementSlice("b", 10000),)),
                                       release_sig=signature))
        for sig in (b"", b"\0" * 63, b"\0" * 64, True,
                    self.issuer.sign(escrow_signing_payload(self.request, self.cap, self.trusted))):
            self.assertIsNone(self.release(release_sig=sig))
        self.assertIsNone(self.release(cap_sig=True))
        self.assertIsNone(self.release(proof=True))
        self.assertIsNone(self.release(now=21))
        self.assertIsNone(self.release(replace(self.request, delta=51)))
        self.assertIsNone(self.release(replace(self.request, expected=replace(self.initial, escrow_bal=49))))
        with self.ledger._connect() as con:
            self.assertEqual(con.execute("SELECT count(*) FROM decision_receipts").fetchone()[0], 0)

    def test_dismissed_and_stale_state(self):
        req = replace(self.request, upheld=False)
        result = self.release(req)
        self.assertEqual(result.ledger, EscrowLedger(100, 10, 10, 80, 35, 45, 45))
        self.assertIsNone(self.release(replace(req, nonce="new")))

    def test_database_failure_rolls_back_state_and_nonce(self):
        with self.ledger._connect() as con:
            con.execute("CREATE TRIGGER reject_receipt BEFORE INSERT ON decision_receipts "
                        "BEGIN SELECT RAISE(ABORT, 'injected'); END")
        self.assertIsNone(self.release())
        with self.ledger._connect() as con:
            self.assertEqual(con.execute("SELECT canonical_state FROM tas_escrow_state").fetchone()[0],
                             deterministic_jcs_serialize(self.request.expected.__dict__).decode())
            self.assertEqual(con.execute("SELECT count(*) FROM decision_receipts").fetchone()[0], 0)
            con.execute("DROP TRIGGER reject_receipt")
        self.assertIsNotNone(self.release())

    def test_racing_same_nonce_has_at_most_one_commit(self):
        barrier = threading.Barrier(2)
        sig = self.sign_release()
        def run():
            barrier.wait()
            return self.release(release_sig=sig)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: run(), range(2)))
        self.assertEqual(sum(r is not None for r in results), 1)
        with self.ledger._connect() as con:
            self.assertEqual(con.execute("SELECT count(*) FROM decision_receipts").fetchone()[0], 1)

    def test_domain_and_jcs(self):
        payload = capability_signing_payload(self.cap)
        self.assertEqual(payload, CAPABILITY_DOMAIN + deterministic_jcs_serialize({
            "capability_id": "capability", "issuer": "issuer", "valid_from": 10, "valid_until": 20
        }))


if __name__ == "__main__":
    unittest.main()
