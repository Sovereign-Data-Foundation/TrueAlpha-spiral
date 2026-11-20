"""Isolated deterministic primitives; not a conformance runner or system.

This module provides no authorization, signature verification, replay
protection, state transition, escrow release, or financial commit. In
particular, computed allocations are mathematical results, not permission to
transfer funds. A production gate would need independently trusted Ed25519
keys, actual proof verification and atomic nonce consumption with commit; a
production receipt must also bind the allocation digest.

The index is represented as lowercase SHA-256 hex. Receipt serialization
supports the integer-only interoperable JCS subset and rejects all floats.
Settlement uses unsigned 64-bit inputs and intermediate products, and raises
on invalid input or overflow. It does not evaluate gate status or issue a
settlement decision code.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Sequence


_MAX_U64 = (1 << 64) - 1
_MAX_SAFE_JSON_INT = (1 << 53) - 1
_RECEIPT_DOMAIN = b"TAS\x00ADMISSIBILITY-RECEIPT\x00v1\x00"


@dataclass(frozen=True)
class CapabilityEnvelope:
    issuer: str
    capability_id: str
    valid_from: int
    valid_until: int


def _nonempty_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a nonempty string")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{name} must contain Unicode scalar values") from exc
    return value


def _natural(value: object, name: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
    if value > _MAX_U64:
        raise OverflowError(f"{name} exceeds unsigned 64-bit range")
    return value


def derive_capability_key_index(cap: CapabilityEnvelope) -> str:
    """Return SHA256(0x02 || len32(issuer) || issuer || len32(id) || id)."""
    if not isinstance(cap, CapabilityEnvelope):
        raise TypeError("cap must be a CapabilityEnvelope")
    issuer = _nonempty_text(cap.issuer, "issuer").encode("utf-8")
    capability = _nonempty_text(cap.capability_id, "capability_id").encode("utf-8")
    if len(issuer) > 0xFFFFFFFF or len(capability) > 0xFFFFFFFF:
        raise OverflowError("UTF-8 component exceeds unsigned 32-bit length")
    return hashlib.sha256(
        b"\x02" + len(issuer).to_bytes(4, "big") + issuer
        + len(capability).to_bytes(4, "big") + capability
    ).hexdigest()


def deterministic_jcs_serialize(value: Any) -> bytes:
    """Return JCS UTF-8 bytes for the documented integer-only JSON subset."""
    def encode(item: Any, active: set[int]) -> str:
        if item is None:
            return "null"
        if type(item) is bool:
            return "true" if item else "false"
        if type(item) is int:
            if not -_MAX_SAFE_JSON_INT <= item <= _MAX_SAFE_JSON_INT:
                raise ValueError("JSON integer outside interoperable range")
            return str(item)
        if isinstance(item, float):
            raise TypeError("floating-point values are not supported")
        if isinstance(item, str):
            try:
                item.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise ValueError("invalid Unicode string") from exc
            return json.dumps(item, ensure_ascii=False)
        if isinstance(item, (list, dict)):
            identity = id(item)
            if identity in active:
                raise ValueError("cyclic JSON value")
            active.add(identity)
            try:
                if isinstance(item, list):
                    return "[" + ",".join(encode(v, active) for v in item) + "]"
                for key in item:
                    if not isinstance(key, str):
                        raise TypeError("JSON object keys must be strings")
                    encode(key, active)
                keys = sorted(item, key=lambda key: key.encode("utf-16be"))
                return "{" + ",".join(
                    encode(key, active) + ":" + encode(item[key], active)
                    for key in keys
                ) + "}"
            finally:
                active.remove(identity)
        raise TypeError("unsupported JSON value")

    return encode(value, set()).encode("utf-8")


def compute_jcs_receipt_digest(receipt: Any) -> str:
    """Hash the domain-prefixed JCS body; this does not bind absent fields."""
    return hashlib.sha256(_RECEIPT_DOMAIN + deterministic_jcs_serialize(receipt)).hexdigest()


@dataclass(frozen=True)
class SettlementSlice:
    artifact_id: str
    bps: int


@dataclass(frozen=True)
class Allocation:
    artifact_id: str
    amount: int


def _validate_slices(slices: Sequence[SettlementSlice]) -> None:
    if not isinstance(slices, (list, tuple)) or not slices:
        raise ValueError("slices must be a nonempty list or tuple")
    for item in slices:
        if not isinstance(item, SettlementSlice):
            raise TypeError("each slice must be a SettlementSlice")
        _nonempty_text(item.artifact_id, "artifact_id")
        if _natural(item.bps, "bps") > 10000:
            raise ValueError("bps exceeds 10000")
    if sum(item.bps for item in slices) != 10000:
        raise ValueError("slice basis points must sum to 10000")


def calculate_batch_allocations(pool: int, slices: Sequence[SettlementSlice]) -> tuple[Allocation, ...]:
    """Pure Hare–Niemeyer arithmetic; no gate, escrow or transfer is performed.

    Slices must be nonempty and sum to 10,000 basis points. Largest remainders
    receive residual units, with ties ordered by artifact_id (then input order
    for duplicate IDs). Results correspond to the original slice order.
    """
    pool = _natural(pool, "pool")
    _validate_slices(slices)
    for item in slices:
        if pool * item.bps > _MAX_U64:
            raise OverflowError("pool times bps exceeds unsigned 64-bit range")
    parts = [divmod(pool * item.bps, 10000) for item in slices]
    amounts = [part[0] for part in parts]
    dust = pool - sum(amounts)
    order = sorted(range(len(slices)), key=lambda i: (-parts[i][1], slices[i].artifact_id))
    for i in order[:dust]:
        amounts[i] += 1
    return tuple(Allocation(item.artifact_id, amount) for item, amount in zip(slices, amounts))


def allocation_digest(cvp_allocations: Sequence[SettlementSlice]) -> str:
    """SHA-256 of the JCS-normalized CVP basis-point allocation records.

    Records contain only ``artifact_id`` and ``bps`` in the supplied vector
    order. Receipts do not automatically bind this digest; no authority or
    state transition is implied.
    """
    _validate_slices(cvp_allocations)
    vector = [
        {"artifact_id": item.artifact_id, "bps": item.bps}
        for item in cvp_allocations
    ]
    return hashlib.sha256(deterministic_jcs_serialize(vector)).hexdigest()
