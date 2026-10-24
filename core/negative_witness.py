"""Deterministic ingestion of historical failures as negative witnesses.

Negative witnesses are evidence about a known failure pattern.  They never
assert that an arbitrary claim is false and never authorize a state transition.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


DOMAIN = b"TAS-NEGATIVE-WITNESS-V1\0"
GENESIS = "sha256:" + "0" * 64
HASH_PREFIX = "sha256:"
FAILURE_CLASSES = frozenset(
    {"UNTRACEABLE_GENERATION", "WITNESS_FABRICATION", "AUTHORITY_DISCONTINUITY", "STALE_EVIDENCE"}
)


def canonical_json(value: Mapping[str, Any]) -> bytes:
    """Return the canonical UTF-8 representation used by signatures and hashes."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def content_hash(value: Mapping[str, Any]) -> str:
    return HASH_PREFIX + hashlib.sha256(canonical_json(value)).hexdigest()


def _is_hash(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith(HASH_PREFIX):
        return False
    digest = value[len(HASH_PREFIX) :]
    return len(digest) == 64 and all(character in "0123456789abcdef" for character in digest)


def _parse_utc(value: str) -> datetime:
    if not value.endswith("Z"):
        raise ValueError("timestamp must use UTC Z notation")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    if parsed.tzinfo != timezone.utc:
        raise ValueError("timestamp must be UTC")
    return parsed


@dataclass(frozen=True)
class WitnessAttestation:
    principal_id: str
    key_id: str
    signed_at: str
    signature: bytes


@dataclass(frozen=True)
class NegativeWitness:
    witness_id: str
    failure_class: str
    observed_at: str
    source_artifact_hash: str
    evidence_hashes: tuple[str, ...]
    pattern_digest: str
    description: str
    attestations: tuple[WitnessAttestation, ...]
    schema_version: str = "1.0"

    def signed_payload(self) -> dict[str, Any]:
        """Return exactly the fields jointly signed by each attestor."""
        return {
            "description": self.description,
            "evidence_hashes": list(self.evidence_hashes),
            "failure_class": self.failure_class,
            "observed_at": self.observed_at,
            "pattern_digest": self.pattern_digest,
            "schema_version": self.schema_version,
            "source_artifact_hash": self.source_artifact_hash,
        }


@dataclass(frozen=True)
class IngestionReceipt:
    decision: str
    reason_code: str | None
    witness_id: str
    prior_registry_digest: str
    registry_digest: str


class ChallengeRegistry:
    """Append-only registry whose digest binds order, witness, and prior head."""

    def __init__(self) -> None:
        self._witnesses: dict[str, NegativeWitness] = {}
        self._revoked: set[str] = set()
        self._head = GENESIS

    @property
    def digest(self) -> str:
        return self._head

    def snapshot(self) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
        return self._head, tuple(self._witnesses), tuple(sorted(self._revoked))

    def ingest(
        self,
        witness: NegativeWitness,
        authority_snapshot: Mapping[str, bytes],
        *,
        minimum_distinct_principals: int = 2,
    ) -> IngestionReceipt:
        """Validate and append a witness, or return a non-mutating refusal."""
        prior = self._head
        if witness.witness_id in self._witnesses:
            return IngestionReceipt("REFUSED", "WITNESS_INVALID", witness.witness_id, prior, prior)
        reason = self._validate(witness, authority_snapshot, minimum_distinct_principals)
        if reason is not None:
            return IngestionReceipt("REFUSED", reason, witness.witness_id, prior, prior)

        entry = {
            "event": "NEGATIVE_WITNESS_ADMITTED",
            "prior_registry_digest": prior,
            "witness_id": witness.witness_id,
        }
        self._head = content_hash(entry)
        self._witnesses[witness.witness_id] = witness
        return IngestionReceipt("ADMITTED", None, witness.witness_id, prior, self._head)

    def revoke(self, witness_id: str) -> str:
        """Deactivate, but never erase, an admitted witness and advance the head."""
        if witness_id not in self._witnesses:
            raise KeyError(witness_id)
        if witness_id in self._revoked:
            return self._head
        self._head = content_hash(
            {"event": "NEGATIVE_WITNESS_REVOKED", "prior_registry_digest": self._head, "witness_id": witness_id}
        )
        self._revoked.add(witness_id)
        return self._head

    def is_active(self, witness_id: str, snapshot_digest: str) -> bool:
        """Query only the current, explicitly named snapshot (no implicit latest)."""
        if snapshot_digest != self._head:
            raise ValueError("challenge registry snapshot mismatch")
        return witness_id in self._witnesses and witness_id not in self._revoked

    @staticmethod
    def _validate(
        witness: NegativeWitness,
        authority_snapshot: Mapping[str, bytes],
        minimum_distinct_principals: int,
    ) -> str | None:
        try:
            if minimum_distinct_principals < 1:
                raise ValueError("minimum distinct principals must be positive")
            if witness.schema_version != "1.0" or witness.failure_class not in FAILURE_CLASSES:
                return "WITNESS_INVALID"
            _parse_utc(witness.observed_at)
            if not witness.description.strip() or not witness.evidence_hashes:
                return "WITNESS_INVALID"
            if len(set(witness.evidence_hashes)) != len(witness.evidence_hashes):
                return "WITNESS_INVALID"
            if not all(_is_hash(value) for value in (witness.source_artifact_hash, witness.pattern_digest)):
                return "WITNESS_INVALID"
            if not all(_is_hash(value) for value in witness.evidence_hashes):
                return "WITNESS_INVALID"
            payload = witness.signed_payload()
            expected_id = content_hash(payload)
            if witness.witness_id != expected_id:
                return "WITNESS_INVALID"

            principals: set[str] = set()
            key_ids: set[str] = set()
            message = DOMAIN + canonical_json(payload)
            for attestation in witness.attestations:
                _parse_utc(attestation.signed_at)
                if attestation.principal_id in principals or attestation.key_id in key_ids:
                    return "AUTHORITY_CONTINUITY_FAILURE"
                public_key = authority_snapshot.get(attestation.key_id)
                if public_key is None:
                    return "AUTHORITY_CONTINUITY_FAILURE"
                Ed25519PublicKey.from_public_bytes(public_key).verify(attestation.signature, message)
                principals.add(attestation.principal_id)
                key_ids.add(attestation.key_id)
            if len(principals) < minimum_distinct_principals:
                return "AUTHORITY_CONTINUITY_FAILURE"
        except (TypeError, ValueError):
            return "WITNESS_INVALID"
        except Exception:
            return "AUTHORITY_CONTINUITY_FAILURE"
        return None
