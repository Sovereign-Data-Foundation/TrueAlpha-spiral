from __future__ import annotations

import hashlib

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.runtime.unified_verifier import (
    ExecutionCandidate, HumanAuthorization, LineageTimeline, OperationalState,
    SovereignViolation, UniversalVerifierKernel,
)


def candidate(parent: bytes, action: str = "write") -> ExecutionCandidate:
    parameters = b'{"new":"state"}'
    return ExecutionCandidate(action, hashlib.sha256(parameters).digest(), parameters, parent)


def authorization(key: Ed25519PrivateKey, item: ExecutionCandidate, scopes=frozenset({"write"})) -> HumanAuthorization:
    unsigned = HumanAuthorization(key.public_key().public_bytes_raw(), scopes, b"x" * 64, 7)
    return HumanAuthorization(unsigned.identity_key, scopes, key.sign(UniversalVerifierKernel.authorization_payload(unsigned, item)), 7)


def initial():
    state = OperationalState(b"a" * 32, frozenset({"write", "read"}))
    return state, LineageTimeline(b"g" * 32, 4)


def test_verified_transition_mutates_state_and_advances_evidence() -> None:
    state, lineage = initial()
    item = candidate(lineage.parent_receipt_hash)
    key = Ed25519PrivateKey.generate()
    changed = OperationalState(b"b" * 32, frozenset({"write"}))
    next_state, next_lineage, receipt = UniversalVerifierKernel.process_transition(
        state, lineage, authorization(key, item), item, set(), lambda *_: changed
    )
    assert next_state == changed
    assert receipt.admission_gate_passed is True
    assert receipt.resulting_state_hash == UniversalVerifierKernel.compute_state_digest(changed)
    assert next_lineage.sequence_number == 5
    assert next_lineage.parent_receipt_hash == UniversalVerifierKernel.compute_receipt_digest(receipt)


def test_invalid_authority_freezes_state_without_calling_simulation_and_records_refusal() -> None:
    state, lineage = initial()
    item = candidate(lineage.parent_receipt_hash)
    key = Ed25519PrivateKey.generate()
    calls = 0

    def simulation(*_):
        nonlocal calls
        calls += 1
        return OperationalState(b"b" * 32, frozenset({"write"}))

    next_state, next_lineage, receipt = UniversalVerifierKernel.process_transition(
        state, lineage, authorization(key, item, frozenset()), item, set(), simulation
    )
    assert calls == 0
    assert next_state == state
    assert receipt.violation_recorded == SovereignViolation.SCOPE_EXCEEDED.value
    assert receipt.resulting_state_hash is None
    assert next_lineage.sequence_number == lineage.sequence_number + 1
    assert next_lineage.parent_receipt_hash != lineage.parent_receipt_hash


def test_lineage_gap_and_capability_expansion_are_refused() -> None:
    state, lineage = initial()
    key = Ed25519PrivateKey.generate()
    gap = candidate(b"z" * 32)
    _, _, refused = UniversalVerifierKernel.process_transition(state, lineage, authorization(key, gap), gap, set(), lambda *_: state)
    assert refused.violation_recorded == SovereignViolation.LINEAGE_DISCONTINUITY.value

    item = candidate(lineage.parent_receipt_hash)
    _, _, refused = UniversalVerifierKernel.process_transition(
        state, lineage, authorization(key, item), item, set(), lambda *_: OperationalState(b"b" * 32, frozenset({"write", "admin"}))
    )
    assert refused.violation_recorded == SovereignViolation.SCOPE_EXCEEDED.value
