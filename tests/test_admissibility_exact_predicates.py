from __future__ import annotations

import hashlib

import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from sdf_evidence_envelope import build_envelope, verify_evidence
from tas_admissibility import AdmissionReceipt, RefusalReceipt, admit_or_refuse


GENESIS = "a" * 64
STATE_ROOT = "c" * 64
AUTHORITY = "auth:exact"
CONTEXT = "ctx:exact:v1"


def make_envelope(claim, *, nonce="nonce-exact"):
    key = ec.generate_private_key(ec.SECP256K1())
    envelope = build_envelope(
        evidence_id="ev:exact",
        claim=claim,
        issuer_authority_id=AUTHORITY,
        issuer_private_key=key,
        context=CONTEXT,
        genesis_hash=GENESIS,
        parent_hash=None,
        sequence=0,
        issued_at="2026-09-03T19:00:00Z",
        nonce=nonce,
    )
    return envelope


def trusted_keys(envelope):
    return {envelope.issuer.authority_id: envelope.issuer.public_key_b64}


@pytest.mark.parametrize("truthy_non_bool", [1, "true", "false", [1], {"ok": True}])
def test_verify_evidence_requires_literal_boolean_true(truthy_non_bool):
    envelope = make_envelope({"op": "write"})

    verdict = verify_evidence(
        envelope,
        authority_scope=frozenset({AUTHORITY}),
        current_context=CONTEXT,
        seen_nonces=set(),
        invariant_pass=truthy_non_bool,
        trusted_authority_keys=trusted_keys(envelope),
    )

    assert verdict.admissible is False
    assert verdict.invariant_pass is False
    assert verdict.failed_predicate == "invariant_pass"
    assert verdict.delta_s() == 0


@pytest.mark.parametrize(
    ("signed_value", "proposal_value"),
    [(True, 1), (False, 0)],
)
def test_admit_or_refuse_uses_type_exact_claim_identity(signed_value, proposal_value):
    envelope = make_envelope({"value": signed_value})
    effects = []

    def apply_transition(proposal, state_root):
        effects.append(proposal)
        return hashlib.sha256((state_root + repr(proposal)).encode()).hexdigest()

    outcome = admit_or_refuse(
        proposal={"value": proposal_value},
        envelope=envelope,
        state_root=STATE_ROOT,
        authority_scope=frozenset({AUTHORITY}),
        current_context=CONTEXT,
        seen_nonces=set(),
        invariant_check=lambda _proposal, _state_root: True,
        apply_transition=apply_transition,
        trusted_authority_keys=trusted_keys(envelope),
    )

    assert isinstance(outcome, RefusalReceipt)
    assert outcome.delta_s == 0
    assert outcome.failed_predicate == "claim_matches_proposal"
    assert effects == []


@pytest.mark.parametrize("truthy_non_bool", [1, "true", "false", {"ok": True}])
def test_admit_or_refuse_rejects_truthy_non_boolean_invariant(truthy_non_bool):
    proposal = {"op": "write"}
    envelope = make_envelope(proposal)
    effects = []

    def apply_transition(candidate, state_root):
        effects.append(candidate)
        return hashlib.sha256((state_root + repr(candidate)).encode()).hexdigest()

    outcome = admit_or_refuse(
        proposal=proposal,
        envelope=envelope,
        state_root=STATE_ROOT,
        authority_scope=frozenset({AUTHORITY}),
        current_context=CONTEXT,
        seen_nonces=set(),
        invariant_check=lambda _proposal, _state_root: truthy_non_bool,
        apply_transition=apply_transition,
        trusted_authority_keys=trusted_keys(envelope),
    )

    assert isinstance(outcome, RefusalReceipt)
    assert outcome.delta_s == 0
    assert outcome.failed_predicate == "invariant_pass"
    assert effects == []


def test_literal_true_still_admits_exact_claim():
    proposal = {"op": "write", "value": 1}
    envelope = make_envelope(proposal)

    outcome = admit_or_refuse(
        proposal=proposal,
        envelope=envelope,
        state_root=STATE_ROOT,
        authority_scope=frozenset({AUTHORITY}),
        current_context=CONTEXT,
        seen_nonces=set(),
        invariant_check=lambda _proposal, _state_root: True,
        apply_transition=lambda candidate, state_root: hashlib.sha256(
            (state_root + repr(candidate)).encode()
        ).hexdigest(),
        trusted_authority_keys=trusted_keys(envelope),
    )

    assert isinstance(outcome, AdmissionReceipt)
    assert outcome.delta_s == 1
    assert outcome.verdict.invariant_pass is True
