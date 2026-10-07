from dataclasses import replace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.negative_witness import (
    DOMAIN,
    ChallengeRegistry,
    NegativeWitness,
    WitnessAttestation,
    canonical_json,
    content_hash,
)


def _hash(character: str) -> str:
    return "sha256:" + character * 64


def _witness(keys, *, duplicate_principal=False):
    unsigned = NegativeWitness(
        witness_id="",
        failure_class="UNTRACEABLE_GENERATION",
        observed_at="2026-10-07T12:00:00Z",
        source_artifact_hash=_hash("a"),
        evidence_hashes=(_hash("b"),),
        pattern_digest=_hash("c"),
        description="Generated assertion has no attributable source.",
        attestations=(),
    )
    payload = unsigned.signed_payload()
    message = DOMAIN + canonical_json(payload)
    attestations = tuple(
        WitnessAttestation(
            principal_id="principal:one" if duplicate_principal else f"principal:{index}",
            key_id=f"key:{index}",
            signed_at="2026-10-07T12:01:00Z",
            signature=key.sign(message),
        )
        for index, key in enumerate(keys)
    )
    return replace(unsigned, witness_id=content_hash(payload), attestations=attestations)


def test_admits_two_party_attested_failure_and_binds_registry_head():
    keys = [Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()]
    authority = {f"key:{index}": key.public_key().public_bytes_raw() for index, key in enumerate(keys)}
    registry = ChallengeRegistry()

    receipt = registry.ingest(_witness(keys), authority)

    assert receipt.decision == "ADMITTED"
    assert receipt.reason_code is None
    assert receipt.registry_digest != receipt.prior_registry_digest
    assert registry.is_active(receipt.witness_id, receipt.registry_digest)


def test_tampered_payload_is_refused_without_registry_mutation():
    keys = [Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()]
    authority = {f"key:{index}": key.public_key().public_bytes_raw() for index, key in enumerate(keys)}
    registry = ChallengeRegistry()
    witness = replace(_witness(keys), description="tampered after signing")

    receipt = registry.ingest(witness, authority)

    assert receipt.decision == "REFUSED"
    assert receipt.reason_code == "WITNESS_INVALID"
    assert receipt.registry_digest == receipt.prior_registry_digest


def test_duplicate_principals_do_not_satisfy_threshold():
    keys = [Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()]
    authority = {f"key:{index}": key.public_key().public_bytes_raw() for index, key in enumerate(keys)}

    receipt = ChallengeRegistry().ingest(_witness(keys, duplicate_principal=True), authority)

    assert receipt.reason_code == "AUTHORITY_CONTINUITY_FAILURE"


def test_revocation_is_append_only_and_snapshot_bound():
    keys = [Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()]
    authority = {f"key:{index}": key.public_key().public_bytes_raw() for index, key in enumerate(keys)}
    registry = ChallengeRegistry()
    admitted = registry.ingest(_witness(keys), authority)

    revoked_head = registry.revoke(admitted.witness_id)

    assert revoked_head != admitted.registry_digest
    assert not registry.is_active(admitted.witness_id, revoked_head)
    with pytest.raises(ValueError, match="snapshot mismatch"):
        registry.is_active(admitted.witness_id, admitted.registry_digest)


def test_replay_is_refused_without_advancing_registry():
    keys = [Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()]
    authority = {f"key:{index}": key.public_key().public_bytes_raw() for index, key in enumerate(keys)}
    registry = ChallengeRegistry()
    witness = _witness(keys)
    admitted = registry.ingest(witness, authority)

    replay = registry.ingest(witness, authority)

    assert replay.decision == "REFUSED"
    assert replay.reason_code == "WITNESS_INVALID"
    assert replay.registry_digest == admitted.registry_digest
