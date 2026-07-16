from pathlib import Path

from sdf_admissibility_daemon import (
    AdmissibilityDaemon, AuthoritySnapshot, SQLiteDecisionLedger, sha256_uri,
)


class Authority:
    def __init__(self, snapshot): self.snapshot = snapshot
    def resolve(self, **_): return self.snapshot
class Signatures:
    def verify(self, **kwargs): return kwargs["signature"] == b"valid"
class Scope:
    def permits(self, **kwargs): return kwargs["requested_operation"] == "read"
class Parents:
    def verify(self, **_): return True
class Signer:
    def sign(self, message): return {"node_id": "test-node", "signature": sha256_uri(message.hex())}


def envelope(**changes):
    value = {"credential_id":"steward-1", "authority_epoch":7, "authority_checkpoint_hash":"sha256:checkpoint", "issued_at":"2026-07-08T00:00:00Z", "nonce":"nonce-1", "requested_operation":"read", "candidate_hash":"sha256:candidate", "expected_state_parent_hash":"sha256:genesis"}
    value.update(changes)
    return value


def signed_envelope(**changes):
    value = envelope(**changes)
    value.setdefault("signature", b"valid".hex())
    return value


def daemon(tmp_path: Path):
    snapshot = AuthoritySnapshot("steward-1", 7, "sha256:checkpoint", b"key", "2026-07-01T00:00:00Z", "2026-07-17T00:00:00Z", "sha256:scope")
    return AdmissibilityDaemon(authority_resolver=Authority(snapshot), signature_verifier=Signatures(), scope_resolver=Scope(), ledger=SQLiteDecisionLedger(tmp_path / "ledger.db"), parent_verifier=Parents(), receipt_signer=Signer())


def test_authenticated_envelope_advances_both_heads(tmp_path):
    receipt = daemon(tmp_path).evaluate(signed_envelope(), current_time="2026-07-08T01:00:00Z")
    assert receipt["decision"] == "ADMITTED"
    assert (receipt["evidence_sequence"], receipt["state_sequence"]) == (1, 1)


def test_refusal_advances_evidence_but_not_state(tmp_path):
    receipt = daemon(tmp_path).evaluate(signed_envelope(requested_operation="write"), current_time="2026-07-08T01:00:00Z")
    assert receipt["decision"] == "REFUSED"
    assert (receipt["evidence_sequence"], receipt["state_sequence"]) == (1, 0)


def test_replay_is_idempotent_and_equivocation_cuts_off(tmp_path):
    instance = daemon(tmp_path)
    first = instance.evaluate(signed_envelope(), current_time="2026-07-08T01:00:00Z")
    retry = instance.evaluate(signed_envelope(), current_time="2026-07-08T01:00:00Z")
    assert retry["receipt_hash"] == first["receipt_hash"] and retry["replayed"]
    cutoff = instance.evaluate(signed_envelope(candidate_hash="sha256:other"), current_time="2026-07-08T01:00:00Z")
    assert cutoff["admissibility_result"] == "CUTOFF"


def test_malformed_raw_transport_is_not_a_receipt(tmp_path):
    assert daemon(tmp_path).evaluate_raw(b'{"a":1,"a":2}', current_time="2026-07-08T01:00:00Z") is None
    assert daemon(tmp_path).evaluate_raw(b'{"a":1.0}', current_time="2026-07-08T01:00:00Z") is None


def test_state_fork_cuts_off_after_prior_admission(tmp_path):
    instance = daemon(tmp_path)
    instance.evaluate(signed_envelope(), current_time="2026-07-08T01:00:00Z")
    result = instance.evaluate(signed_envelope(nonce="nonce-2"), current_time="2026-07-08T01:00:00Z")
    assert result["admissibility_result"] == "CUTOFF"


def test_invalid_signature_is_evidentiary_refusal_not_state_transition(tmp_path):
    receipt = daemon(tmp_path).evaluate(
        signed_envelope(signature="00"), current_time="2026-07-08T01:00:00Z"
    )
    assert receipt["decision"] == "REFUSED"
    assert "signature_validity" in receipt["failed_invariants"]
    assert receipt["state_sequence"] == 0


def test_wal_ledger_recovers_heads_after_restart(tmp_path):
    first = daemon(tmp_path).evaluate(signed_envelope(), current_time="2026-07-08T01:00:00Z")
    resumed = daemon(tmp_path).evaluate(
        signed_envelope(
            nonce="nonce-after-restart",
            expected_state_parent_hash=first["state_head_hash"],
        ),
        current_time="2026-07-08T01:00:00Z",
    )
    assert (resumed["evidence_sequence"], resumed["state_sequence"]) == (2, 2)
