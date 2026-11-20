"""Isolated deterministic primitives; not a conformance runner or system.

The cryptographic gate and SQLite escrow transition below use an explicitly
configured trust root and keys. They do not authorize external transfers or
establish key ownership, policy scope, root freshness, or production protocol
conformance. Computed allocations alone are not permission to transfer funds.

The index is represented as lowercase SHA-256 hex. Receipt serialization
supports the integer-only interoperable JCS subset and rejects all floats.
Settlement uses unsigned 64-bit inputs and intermediate products, and raises
on invalid input or overflow. It does not evaluate gate status or issue a
settlement decision code.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from typing import Any, Sequence

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from sdf_admissibility_daemon import SQLiteDecisionLedger


_MAX_U64 = (1 << 64) - 1
_MAX_SAFE_JSON_INT = (1 << 53) - 1
_RECEIPT_DOMAIN = b"TAS\x00ADMISSIBILITY-RECEIPT\x00v1\x00"
CAPABILITY_DOMAIN = b"TAS\x00CAPABILITY\x00v1\x00"
ESCROW_DOMAIN = b"TAS\x00ESCROW-RELEASE\x00v1\x00"
CONFIGURED_SMT_ROOT = "6155289196324fe02ff3e7bd5b8423237ebcfa686f0bb6c8fc8812c75a40974b"


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


@dataclass(frozen=True)
class TrustedGate:
    """Locally provisioned trust, never populated from a signed request.

    The default root is the specified anchor, not the result of the empty-tree
    recursion. A different root requires an independently trusted configuration.
    """
    issuer: str
    issuer_key: bytes
    adjudicator_key: bytes
    revocation_root: str = CONFIGURED_SMT_ROOT


@dataclass(frozen=True)
class SparseNonInclusionProof:
    # 256 sibling hashes, leaf-to-root; path bits are consumed least-significant first.
    siblings: tuple[str, ...]


@dataclass(frozen=True)
class EscrowLedger:
    r_gross: int
    r_legal: int
    r_infra: int
    r_dist: int
    liquid_sum: int
    escrow_sum: int
    escrow_bal: int


@dataclass(frozen=True)
class EscrowRequest:
    ledger_id: str
    nonce: str
    delta: int
    upheld: bool
    expected: EscrowLedger
    allocations: tuple[SettlementSlice, ...]


@dataclass(frozen=True)
class EscrowCommit:
    ledger: EscrowLedger
    receipt_hash: str


def _hex_hash(value: object) -> bytes:
    if type(value) is not str or len(value) != 64 or any(
        c not in "0123456789abcdef" for c in value
    ):
        raise ValueError("expected lowercase SHA-256 hex")
    return bytes.fromhex(value)


def _gate_config(config: TrustedGate) -> None:
    if type(config) is not TrustedGate:
        raise TypeError("trusted gate configuration required")
    _nonempty_text(config.issuer, "issuer")
    if (type(config.issuer_key) is not bytes or len(config.issuer_key) != 32
            or type(config.adjudicator_key) is not bytes or len(config.adjudicator_key) != 32
            or config.issuer_key == config.adjudicator_key):
        raise ValueError("two distinct Ed25519 public keys required")
    _hex_hash(config.revocation_root)


def _capability_body(cap: CapabilityEnvelope) -> dict[str, Any]:
    if type(cap) is not CapabilityEnvelope:
        raise TypeError("capability required")
    derive_capability_key_index(cap)
    start = _natural(cap.valid_from, "valid_from")
    end = _natural(cap.valid_until, "valid_until")
    if start > end:
        raise ValueError("invalid capability interval")
    return {"issuer": cap.issuer, "capability_id": cap.capability_id,
            "valid_from": start, "valid_until": end}


def _verify_signature(key: bytes, signature: bytes, domain: bytes, body: dict[str, Any]) -> None:
    if type(signature) is not bytes or len(signature) != 64:
        raise ValueError("invalid Ed25519 signature")
    Ed25519PublicKey.from_public_bytes(key).verify(
        signature, domain + deterministic_jcs_serialize(body)
    )


def capability_signing_payload(cap: CapabilityEnvelope) -> bytes:
    """Canonical bytes signed by the independently trusted issuer key."""
    return CAPABILITY_DOMAIN + deterministic_jcs_serialize(_capability_body(cap))


def _verify_non_inclusion(index: str, proof: SparseNonInclusionProof, root: str) -> bool:
    if type(proof) is not SparseNonInclusionProof or type(proof.siblings) is not tuple:
        raise ValueError("invalid sparse proof")
    if len(proof.siblings) != 256:
        raise ValueError("sparse proof must have 256 siblings")
    path = int.from_bytes(_hex_hash(index), "big")
    node = bytes(32)
    for level, sibling_hex in enumerate(proof.siblings):
        sibling = _hex_hash(sibling_hex)
        left, right = (sibling, node) if (path >> level) & 1 else (node, sibling)
        node = hashlib.sha256(b"\x01" + left + right).digest()
    return node == _hex_hash(root)


def eval_admission_gate(cap: CapabilityEnvelope, signature: bytes,
                        proof: SparseNonInclusionProof, *, trusted: TrustedGate,
                        now: int) -> bool:
    """Verify evidence only, not an admission or replay-safe state transition.

    Caller must independently supply trusted keys, current time and root. Proof
    format uses an all-zero absent leaf and 256 explicit leaf-to-root siblings.
    """
    try:
        _gate_config(trusted)
        body = _capability_body(cap)
        now = _natural(now, "now")
        if cap.issuer != trusted.issuer or not cap.valid_from <= now <= cap.valid_until:
            return False
        _verify_signature(trusted.issuer_key, signature, CAPABILITY_DOMAIN, body)
        return _verify_non_inclusion(derive_capability_key_index(cap), proof, trusted.revocation_root)
    except (TypeError, ValueError, OverflowError, InvalidSignature):
        return False


def _ledger_body(ledger: EscrowLedger) -> dict[str, int]:
    if type(ledger) is not EscrowLedger:
        raise TypeError("escrow ledger required")
    body = {name: _natural(getattr(ledger, name), name)
            for name in EscrowLedger.__dataclass_fields__}
    if any(value > _MAX_SAFE_JSON_INT for value in body.values()):
        raise ValueError("ledger outside JCS integer range")
    return body


def _release_body(request: EscrowRequest, cap: CapabilityEnvelope,
                  trusted: TrustedGate) -> dict[str, Any]:
    if type(request) is not EscrowRequest:
        raise TypeError("escrow request required")
    _nonempty_text(request.ledger_id, "ledger_id")
    _nonempty_text(request.nonce, "nonce")
    delta = _natural(request.delta, "delta")
    if delta == 0 or delta > _MAX_SAFE_JSON_INT or type(request.upheld) is not bool:
        raise ValueError("invalid escrow decision")
    if type(request.allocations) is not tuple:
        raise TypeError("allocations must be immutable")
    return {"ledger_id": request.ledger_id, "nonce": request.nonce,
            "delta": delta, "upheld": request.upheld,
            "expected": _ledger_body(request.expected),
            "allocation_digest": allocation_digest(request.allocations),
            "capability": _capability_body(cap), "revocation_root": trusted.revocation_root}


def escrow_signing_payload(request: EscrowRequest, cap: CapabilityEnvelope,
                           trusted: TrustedGate) -> bytes:
    """Canonical adjudicator signing bytes, including state and allocation digest."""
    _gate_config(trusted)
    return ESCROW_DOMAIN + deterministic_jcs_serialize(_release_body(request, cap, trusted))


def provision_escrow_ledger(ledger: SQLiteDecisionLedger, ledger_id: str,
                            initial: EscrowLedger) -> None:
    """Trusted administrative setup, create once; never use untrusted initial state."""
    if type(ledger) is not SQLiteDecisionLedger:
        raise TypeError("SQLiteDecisionLedger required")
    _nonempty_text(ledger_id, "ledger_id")
    payload = deterministic_jcs_serialize(_ledger_body(initial)).decode("utf-8")
    with closing(ledger._connect()) as connection, connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("CREATE TABLE IF NOT EXISTS tas_escrow_state "
                           "(ledger_id TEXT PRIMARY KEY, canonical_state TEXT NOT NULL)")
        connection.execute("INSERT INTO tas_escrow_state VALUES (?, ?)", (ledger_id, payload))
        connection.execute("COMMIT")


def release_escrow(request: EscrowRequest, cap: CapabilityEnvelope,
                   capability_signature: bytes, proof: SparseNonInclusionProof,
                   release_signature: bytes, *, trusted: TrustedGate, now: int,
                   ledger: SQLiteDecisionLedger) -> EscrowCommit | None:
    """Atomically consume the nonce and commit an internal SQLite ledger transition.

    A successful result is not an external transfer. Provisioning, key/clock/root
    freshness, scope, and any external effect must be controlled independently.
    Invalid input, stale state, replay, and database failure all fail closed.
    """
    try:
        if type(ledger) is not SQLiteDecisionLedger:
            return None
        if not eval_admission_gate(cap, capability_signature, proof, trusted=trusted, now=now):
            return None
        body = _release_body(request, cap, trusted)
        _verify_signature(trusted.adjudicator_key, release_signature, ESCROW_DOMAIN, body)
        state = request.expected
        delta = request.delta
        if delta > min(state.escrow_bal, state.escrow_sum, state.r_dist):
            return None
        fields = _ledger_body(state)
        fields["escrow_bal"] -= delta
        fields["escrow_sum"] -= delta
        if request.upheld:
            fields["r_dist"] -= delta
            fields["r_legal"] += delta
        else:
            fields["liquid_sum"] += delta
        result = EscrowLedger(**fields)
        next_payload = deterministic_jcs_serialize(_ledger_body(result)).decode("utf-8")
        expected_payload = deterministic_jcs_serialize(body["expected"]).decode("utf-8")
        receipt = {"type": "tas-escrow-release-v1", "request": body,
                   "result": _ledger_body(result), "evaluated_at": now,
                   "capability_signature": capability_signature.hex(),
                   "release_signature": release_signature.hex(),
                   "proof_siblings": list(proof.siblings)}
        receipt_hash = "sha256:" + compute_jcs_receipt_digest(receipt)
        replay_key = "tas-escrow-v1:" + hashlib.sha256(
            deterministic_jcs_serialize({"issuer": cap.issuer, "nonce": request.nonce})
        ).hexdigest()
        authorization_hash = "sha256:" + hashlib.sha256(
            ESCROW_DOMAIN + deterministic_jcs_serialize(body)
        ).hexdigest()
        with closing(ledger._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT canonical_state FROM tas_escrow_state WHERE ledger_id=?",
                                     (request.ledger_id,)).fetchone()
            if row is None or row[0] != expected_payload or connection.execute(
                "SELECT 1 FROM decision_receipts WHERE replay_key=?", (replay_key,)
            ).fetchone():
                connection.execute("ROLLBACK")
                return None
            evidence_seq, _, state_seq, state_head = connection.execute(
                "SELECT evidence_sequence,evidence_head_hash,state_sequence,state_head_hash "
                "FROM ledger_meta WHERE singleton=1"
            ).fetchone()
            connection.execute("UPDATE tas_escrow_state SET canonical_state=? WHERE ledger_id=?",
                               (next_payload, request.ledger_id))
            connection.execute("INSERT INTO decision_receipts VALUES (?,?,?,?,?,?,?,?)", (
                receipt_hash, evidence_seq + 1, state_seq + 1, replay_key,
                authorization_hash, state_head, 1, deterministic_jcs_serialize(receipt)))
            connection.execute(
                "UPDATE ledger_meta SET evidence_sequence=?,evidence_head_hash=?,"
                "state_sequence=?,state_head_hash=? WHERE singleton=1",
                (evidence_seq + 1, receipt_hash, state_seq + 1, receipt_hash))
            connection.execute("COMMIT")
        return EscrowCommit(result, receipt_hash)
    except (TypeError, ValueError, OverflowError, InvalidSignature, sqlite3.Error):
        return None
