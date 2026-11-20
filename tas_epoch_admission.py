"""Stateless, computed epoch admission; this does not establish real-world authority.

The caller independently provisions the issuer key, minimum epoch and root,
and supplies a reliable current time and cache age in nonnegative integer
seconds. The signed maximum freshness constrains that supplied age; this gate
cannot establish that the age is truthful. The capability is not signed here:
its authorization must be established separately. No replay protection, root
distribution or key ownership is provided here.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from enum import IntEnum

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from tas_conformance_harness import (
    CapabilityEnvelope,
    _RECEIPT_DOMAIN,
    derive_capability_key_index,
    deterministic_jcs_serialize,
)


SUITE = "OURSPACE-SMT-SHA256-V1"
_MAX_JSON_INT = (1 << 53) - 1
_ZERO = bytes(32)


class GateStatus(IntEnum):
    VERIFIED = 2000
    INVALID = 4101
    UNVERIFIED = 4102
    REVOKED = 4103
    EXPIRED = 4104
    INDETERMINATE = 4105

    def __bool__(self) -> bool:
        raise TypeError("compare GateStatus explicitly; it is not a boolean")


AdmissionStatus = GateStatus


@dataclass(frozen=True)
class Epoch:
    epoch: int
    issuer: str
    valid_from: int
    valid_until: int
    root: str
    suite: str
    max_freshness_seconds: int


@dataclass(frozen=True)
class TrustedEpoch:
    """Local configuration, not supplied by the signed evidence."""

    issuer: str
    issuer_key: bytes
    minimum_epoch: int
    root: str


@dataclass(frozen=True)
class SparseProof:
    """Lowercase hex index, leaf and 256 leaf-to-root sibling hashes."""

    index: str
    leaf: str
    siblings: tuple[str, ...]


@dataclass(frozen=True)
class AdmissionEvidence:
    epoch: Epoch | None
    signature: bytes | None
    capability: CapabilityEnvelope | None
    proof: SparseProof | None


def _integer(value: object) -> bool:
    return type(value) is int and 0 <= value <= _MAX_JSON_INT


def _text(value: object) -> bool:
    if type(value) is not str or not value:
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _hash(value: object) -> bytes:
    if type(value) is not str or len(value) != 64 or any(
        char not in "0123456789abcdef" for char in value
    ):
        raise ValueError("expected lowercase 32-byte hex")
    return bytes.fromhex(value)


def _epoch_body(epoch: Epoch) -> dict[str, object]:
    if type(epoch) is not Epoch:
        raise TypeError("expected Epoch")
    if (not _integer(epoch.epoch) or not _text(epoch.issuer)
            or not _integer(epoch.valid_from) or not _integer(epoch.valid_until)
            or epoch.valid_from > epoch.valid_until or not _text(epoch.root)
            or not _text(epoch.suite) or not _integer(epoch.max_freshness_seconds)):
        raise ValueError("invalid epoch fields")
    return {
        "epoch": epoch.epoch,
        "issuer": epoch.issuer,
        "valid_from": epoch.valid_from,
        "valid_until": epoch.valid_until,
        "root": epoch.root,
        "suite": epoch.suite,
        "max_freshness_seconds": epoch.max_freshness_seconds,
    }


def epoch_signing_payload(epoch: Epoch) -> bytes:
    """Return the domain-prefixed canonical complete epoch payload."""
    return _RECEIPT_DOMAIN + deterministic_jcs_serialize(_epoch_body(epoch))


def sign_epoch(epoch: Epoch, private_key: Ed25519PrivateKey) -> bytes:
    """Sign the canonical payload with the issuer's Ed25519 private key."""
    return private_key.sign(epoch_signing_payload(epoch))


def _trusted(config: object) -> bool:
    if (type(config) is not TrustedEpoch or not _text(config.issuer)
            or type(config.issuer_key) is not bytes or len(config.issuer_key) != 32
            or not _integer(config.minimum_epoch)):
        return False
    try:
        _hash(config.root)
        Ed25519PublicKey.from_public_bytes(config.issuer_key)
    except (TypeError, ValueError):
        return False
    return True


def _proof_root(proof: SparseProof) -> bytes:
    if type(proof) is not SparseProof or type(proof.siblings) is not tuple:
        raise ValueError("invalid sparse proof")
    index = _hash(proof.index)
    leaf = _hash(proof.leaf)
    if len(proof.siblings) != 256:
        raise ValueError("sparse proof must have 256 siblings")
    node = _ZERO if leaf == _ZERO else hashlib.sha256(b"\x00" + index + leaf).digest()
    path = int.from_bytes(index, "big")
    for level, sibling_hex in enumerate(proof.siblings):
        sibling = _hash(sibling_hex)
        left, right = (sibling, node) if (path >> level) & 1 else (node, sibling)
        node = hashlib.sha256(b"\x01" + left + right).digest()
    return node


def evaluate_epoch_admission(
    evidence: AdmissionEvidence | None,
    *,
    trusted: TrustedEpoch | None,
    now: int,
    cached_age: int,
) -> GateStatus:
    """Evaluate in missing, authority, signature/epoch, time, proof order.

    Interval endpoints and freshness limits are inclusive. Malformed local
    time/cache inputs fail closed as EXPIRED. A nonzero leaf is REVOKED only
    after the entire proof has been checked against the independently trusted
    and signed root. The capability's time interval is checked, but its
    signature and authorization are outside this gate. Always compare the
    returned status explicitly with GateStatus.VERIFIED.
    """
    if evidence is None:
        return AdmissionStatus.UNVERIFIED
    if type(evidence) is not AdmissionEvidence:
        return AdmissionStatus.INVALID
    if any(value is None for value in (
        evidence.epoch, evidence.signature, evidence.capability, evidence.proof
    )):
        return AdmissionStatus.UNVERIFIED
    if not _trusted(trusted):
        return AdmissionStatus.INDETERMINATE

    epoch = evidence.epoch
    try:
        payload = epoch_signing_payload(epoch)
        if (type(evidence.signature) is not bytes or len(evidence.signature) != 64
                or epoch.issuer != trusted.issuer or epoch.epoch < trusted.minimum_epoch
                or epoch.suite != SUITE):
            return AdmissionStatus.INVALID
        Ed25519PublicKey.from_public_bytes(trusted.issuer_key).verify(
            evidence.signature, payload
        )
    except (InvalidSignature, TypeError, ValueError, OverflowError):
        return AdmissionStatus.INVALID

    if (not _integer(now) or not _integer(cached_age)
            or not epoch.valid_from <= now <= epoch.valid_until
            or cached_age > epoch.max_freshness_seconds):
        return AdmissionStatus.EXPIRED

    cap = evidence.capability
    if (type(cap) is not CapabilityEnvelope or not _integer(cap.valid_from)
            or not _integer(cap.valid_until) or cap.valid_from > cap.valid_until):
        return AdmissionStatus.INVALID
    if not cap.valid_from <= now <= cap.valid_until:
        return AdmissionStatus.EXPIRED

    try:
        if (type(evidence.capability) is not CapabilityEnvelope
                or evidence.capability.issuer != trusted.issuer
                or type(evidence.proof) is not SparseProof
                or evidence.proof.index != derive_capability_key_index(evidence.capability)):
            return AdmissionStatus.INVALID
        signed_root = _hash(epoch.root)
        trusted_root = _hash(trusted.root)
        calculated_root = _proof_root(evidence.proof)
        if (not hmac.compare_digest(signed_root, trusted_root)
                or not hmac.compare_digest(calculated_root, trusted_root)):
            return AdmissionStatus.INVALID
        return (AdmissionStatus.REVOKED if _hash(evidence.proof.leaf) != _ZERO
                else AdmissionStatus.VERIFIED)
    except (TypeError, ValueError, OverflowError):
        return AdmissionStatus.INVALID
