"""Deterministic Replit boundary connector for TAS Pythonetics.

The connector is intentionally side-effect free for workspace state: it validates
payload density and manifest provenance, then returns auditable receipts that a
Replit workflow can persist or use to decide whether a workspace action is
admitted. Integrity failures engage an irreversible in-memory SentientLock so a
single connector instance cannot silently continue after witnessing a breach.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

DENSITY_THRESHOLD = 0.15
CONNECTOR_NAME = "replit"


class SovereignStructuralViolation(RuntimeError):
    """Raised when a connector payload fails deterministic TAS admission."""


@dataclass(frozen=True)
class ConnectorReceipt:
    """Immutable receipt emitted by the Replit connector gate."""

    connector: str
    admitted: bool
    payload_sha256: str
    manifest_sha256: str
    density: float
    reason: str
    timestamp: str
    locked: bool
    expected_manifest_sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a stable JSON-serializable receipt dictionary."""
        receipt = {
            "connector": self.connector,
            "admitted": self.admitted,
            "payload_sha256": self.payload_sha256,
            "manifest_sha256": self.manifest_sha256,
            "density": self.density,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "locked": self.locked,
        }
        if self.expected_manifest_sha256 is not None:
            receipt["expected_manifest_sha256"] = self.expected_manifest_sha256
        return receipt


def canonical_manifest_hash(manifest: Mapping[str, Any]) -> str:
    """Hash a manifest with deterministic key ordering and compact separators."""
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def character_shannon_entropy(payload: str) -> float:
    """Compute character-level Shannon entropy in bits per character."""
    if not payload:
        return 0.0

    counts = Counter(payload)
    length = len(payload)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def structural_density(payload: str) -> float:
    """Scale character entropy by payload footprint to expose padded repetition."""
    footprint = len(payload.encode("utf-8"))
    if footprint == 0:
        return 0.0
    return character_shannon_entropy(payload) / math.sqrt(footprint)


class ReplitConnector:
    """Admission gate for Replit-originated TAS workspace actions.

    A failed verification engages an irreversible lock on this connector
    instance. Callers should instantiate a fresh connector only after their own
    external ledger has persisted and reviewed the witness receipt.
    """

    def __init__(self, density_threshold: float = DENSITY_THRESHOLD) -> None:
        if density_threshold <= 0:
            raise ValueError("density_threshold must be positive")
        self.density_threshold = density_threshold
        self._locked = False
        self._witness_receipts: tuple[ConnectorReceipt, ...] = ()

    @property
    def locked(self) -> bool:
        """Return whether this connector has entered irreversible lock state."""
        return self._locked

    @property
    def witness_receipts(self) -> tuple[ConnectorReceipt, ...]:
        """Return immutable non-compliance receipts observed by this connector."""
        return self._witness_receipts

    def verify(self, payload: str, manifest: Mapping[str, Any], expected_manifest_hash: str) -> ConnectorReceipt:
        """Validate payload density and canonical manifest provenance.

        Raises:
            SovereignStructuralViolation: if the connector is already locked,
                the payload is structurally diluted, or the canonical manifest
                hash differs from the expected hash.
        """
        manifest_hash = canonical_manifest_hash(manifest)
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        density = structural_density(payload)

        if self._locked:
            receipt = self._receipt(
                False,
                payload_hash,
                manifest_hash,
                density,
                "connector_locked",
                expected_manifest_hash,
                locked=True,
            )
            raise SovereignStructuralViolation(json.dumps(receipt.to_dict(), sort_keys=True))

        if density < self.density_threshold:
            receipt = self._engage_sentient_lock(
                payload_hash,
                manifest_hash,
                density,
                "density_below_threshold",
                expected_manifest_hash,
            )
            raise SovereignStructuralViolation(json.dumps(receipt.to_dict(), sort_keys=True))

        if manifest_hash != expected_manifest_hash:
            receipt = self._engage_sentient_lock(
                payload_hash,
                manifest_hash,
                density,
                "manifest_hash_mismatch",
                expected_manifest_hash,
            )
            raise SovereignStructuralViolation(json.dumps(receipt.to_dict(), sort_keys=True))

        return self._receipt(True, payload_hash, manifest_hash, density, "admitted", expected_manifest_hash)

    def _engage_sentient_lock(
        self,
        payload_hash: str,
        manifest_hash: str,
        density: float,
        reason: str,
        expected_manifest_hash: str | None,
    ) -> ConnectorReceipt:
        """Freeze this connector and compile an immutable witness receipt."""
        self._locked = True
        receipt = self._receipt(
            False,
            payload_hash,
            manifest_hash,
            density,
            reason,
            expected_manifest_hash,
            locked=True,
        )
        self._witness_receipts = (*self._witness_receipts, receipt)
        return receipt

    @staticmethod
    def _receipt(
        admitted: bool,
        payload_hash: str,
        manifest_hash: str,
        density: float,
        reason: str,
        expected_manifest_hash: str | None,
        locked: bool = False,
    ) -> ConnectorReceipt:
        return ConnectorReceipt(
            connector=CONNECTOR_NAME,
            admitted=admitted,
            payload_sha256=payload_hash,
            manifest_sha256=manifest_hash,
            density=round(density, 12),
            reason=reason,
            timestamp=datetime.now(timezone.utc).isoformat(),
            locked=locked,
            expected_manifest_sha256=expected_manifest_hash,
        )
