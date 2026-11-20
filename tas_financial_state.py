"""Local Q_F escrow machine; no epoch gate, transfers, or Lean integration.

Provisioning is a privileged local operation, not a settlement authorization.
Protect the database, its backups and the configured tribunal key from rollback
or replacement. Replay protection is confined to this database; independently
deployed databases must use distinct, never-reused machine IDs.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Sequence

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from tas_conformance_harness import (
    Allocation, SettlementSlice, allocation_digest, calculate_batch_allocations,
    deterministic_jcs_serialize,
)

MAX_U64 = (1 << 64) - 1
TRIBUNAL_DOMAIN = b"TAS\x00Q_F-TRIBUNAL\x00v1\x00"
RECEIPT_DOMAIN = b"TAS\x00Q_F-RECEIPT\x00v1\x00"


class ReleaseStatus(IntEnum):
    RELEASED = 2000
    FORGED = 4401
    MISSING_ALLOCATION = 4402
    REPLAY = 4403
    ALREADY_RESOLVED = 4404
    DISPUTE_MISMATCH = 4405
    CVP_MISMATCH = 4406

    def __bool__(self) -> bool:
        raise TypeError("compare ReleaseStatus explicitly")


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value:
        raise ValueError(f"{name} must be a nonempty string")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{name} must contain Unicode scalar values") from exc
    return value


def _u64(value: object, name: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
    if value > MAX_U64:
        raise OverflowError(f"{name} exceeds uint64")
    return value


def _sum(*values: int) -> int:
    result = 0
    for value in values:
        result += _u64(value, "amount")
        if result > MAX_U64:
            raise OverflowError("uint64 addition overflow")
    return result


def _digest(value: object) -> str:
    if (type(value) is not str or len(value) != 64
            or any(c not in "0123456789abcdef" for c in value)):
        raise ValueError("dispute_digest must be lowercase SHA-256 hex")
    return value


@dataclass(frozen=True)
class Share:
    artifact_id: str
    bps: int
    contested: bool


@dataclass(frozen=True)
class BatchSettlement:
    settled: tuple[Allocation, ...]
    escrow: tuple[Allocation, ...]


def calculate_batch_settlement(pool: int, shares: Sequence[Share]) -> BatchSettlement:
    """Compute only; no gate status, database write, or transfer is implied.

    Outputs head-cons each ranked payment, i.e. reverse remainder/ID ranking
    within each partition. Duplicate IDs are rejected, even across partitions.
    """
    if not isinstance(shares, (list, tuple)) or not shares:
        raise ValueError("shares must be a nonempty list or tuple")
    for share in shares:
        if type(share) is not Share or type(share.contested) is not bool:
            raise TypeError("expected Share with boolean contested")
        _text(share.artifact_id, "artifact_id")
    if len({s.artifact_id for s in shares}) != len(shares):
        raise ValueError("duplicate artifact_id")
    slices = [SettlementSlice(s.artifact_id, s.bps) for s in shares]
    allocations = calculate_batch_allocations(pool, slices)
    ranked = sorted(range(len(shares)),
                    key=lambda i: (-(pool * shares[i].bps % 10000),
                                   shares[i].artifact_id))
    settled, escrow = [], []
    for i in ranked:
        (escrow if shares[i].contested else settled).append(allocations[i])
    return BatchSettlement(tuple(reversed(settled)), tuple(reversed(escrow)))


@dataclass(frozen=True)
class EscrowAllocation:
    allocation_id: str
    amount: int
    dispute_digest: str


@dataclass(frozen=True)
class TribunalToken:
    machine_id: str
    nonce: str
    allocation_id: str
    verdict: str
    dispute_digest: str
    cvp_allocation_digest: str


def tribunal_signing_payload(token: TribunalToken) -> bytes:
    if type(token) is not TribunalToken:
        raise TypeError("expected TribunalToken")
    _text(token.machine_id, "machine_id")
    _text(token.nonce, "nonce")
    _text(token.allocation_id, "allocation_id")
    if type(token.verdict) is not str or token.verdict not in ("upheld", "exonerated"):
        raise ValueError("invalid verdict")
    _digest(token.dispute_digest)
    _digest(token.cvp_allocation_digest)
    return TRIBUNAL_DOMAIN + deterministic_jcs_serialize({
        "machine_id": token.machine_id, "nonce": token.nonce,
        "allocation_id": token.allocation_id, "verdict": token.verdict,
        "dispute_digest": token.dispute_digest,
        "cvp_allocation_digest": token.cvp_allocation_digest,
    })


@dataclass(frozen=True)
class FinancialState:
    r_gross: int
    r_legal: int
    r_infra: int
    r_dist: int
    liquid_sum: int
    escrow_sum: int
    escrow_bal: int


@dataclass(frozen=True)
class ReleaseResult:
    status: ReleaseStatus
    state: FinancialState | None = None
    receipt_hash: str | None = None


class FinancialMachine:
    """SQLite-backed local machine, with separately provisioned Ed25519 key.

    Use a single database per machine. The constructor pins both the external
    key and machine ID; supplying different trust configuration fails closed.
    Callers must restrict provisioning and database access to trusted operators.
    """

    def __init__(self, path: str | Path, *, machine_id: str, tribunal_key: bytes):
        self.path = str(path)
        if not self.path or self.path == ":memory:" or self.path.startswith("file:"):
            raise ValueError("a persistent SQLite file path is required")
        self.machine_id = _text(machine_id, "machine_id")
        if type(tribunal_key) is not bytes or len(tribunal_key) != 32:
            raise ValueError("trusted tribunal key must be 32 raw bytes")
        self.key = Ed25519PublicKey.from_public_bytes(tribunal_key)
        with closing(self._connect()) as db:
            if db.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() != "wal":
                raise RuntimeError("SQLite WAL mode unavailable")
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute("CREATE TABLE IF NOT EXISTS qf_config "
                           "(singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
                           "machine_id TEXT NOT NULL, tribunal_key BLOB NOT NULL)")
                db.execute("CREATE TABLE IF NOT EXISTS qf_state "
                           "(singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
                           "r_gross TEXT NOT NULL, r_legal TEXT NOT NULL, r_infra TEXT NOT NULL, "
                           "r_dist TEXT NOT NULL, liquid_sum TEXT NOT NULL, "
                           "escrow_sum TEXT NOT NULL, escrow_bal TEXT NOT NULL)")
                db.execute("CREATE TABLE IF NOT EXISTS qf_allocations "
                           "(allocation_id TEXT PRIMARY KEY, amount TEXT NOT NULL, "
                           "dispute_digest TEXT NOT NULL, status TEXT NOT NULL "
                           "CHECK(status IN ('escrow', 'exonerated', 'forfeited')))")
                db.execute("CREATE TABLE IF NOT EXISTS qf_cvp "
                           "(singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
                           "canonical_allocations BLOB NOT NULL, digest TEXT NOT NULL)")
                db.execute("CREATE TABLE IF NOT EXISTS qf_receipts "
                           "(nonce TEXT PRIMARY KEY, receipt_hash TEXT UNIQUE NOT NULL, "
                           "canonical_receipt BLOB NOT NULL)")
                row = db.execute("SELECT machine_id, tribunal_key FROM qf_config").fetchone()
                if row is None:
                    db.execute("INSERT INTO qf_config VALUES (1, ?, ?)",
                               (self.machine_id, tribunal_key))
                elif row != (self.machine_id, tribunal_key):
                    raise ValueError("machine ID or trusted tribunal key mismatch")
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        db.execute("PRAGMA busy_timeout=30000")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def provision(self, allocations: Sequence[EscrowAllocation], *,
                  cvp_allocations: Sequence[SettlementSlice],
                  liquid_sum: int = 0, r_legal: int = 0, r_infra: int = 0) -> FinancialState:
        """One-time trusted bootstrap, including independently supplied CVP.

        The CVP vector is committed to tokens/receipts but is not evidence that
        the provisioned escrow amounts came from that vector or an external gate.
        """
        if not isinstance(allocations, (list, tuple)):
            raise TypeError("allocations must be a list or tuple")
        for item in allocations:
            if type(item) is not EscrowAllocation:
                raise TypeError("expected EscrowAllocation")
            _text(item.allocation_id, "allocation_id")
            _u64(item.amount, "amount")
            _digest(item.dispute_digest)
        if len({a.allocation_id for a in allocations}) != len(allocations):
            raise ValueError("duplicate allocation_id")
        if not isinstance(cvp_allocations, (list, tuple)):
            raise TypeError("cvp_allocations must be a list or tuple")
        cvp = tuple(cvp_allocations)
        if any(type(s) is not SettlementSlice for s in cvp):
            raise TypeError("expected SettlementSlice")
        for item in cvp:
            _text(item.artifact_id, "CVP artifact_id")
            _u64(item.bps, "CVP bps")
        if len({s.artifact_id for s in cvp}) != len(cvp):
            raise ValueError("duplicate CVP artifact_id")
        cvp_hash = allocation_digest(cvp)
        cvp_canonical = deterministic_jcs_serialize(
            [{"artifact_id": s.artifact_id, "bps": s.bps} for s in cvp]
        )
        escrow = _sum(*(a.amount for a in allocations))
        dist = _sum(liquid_sum, escrow)
        gross = _sum(r_legal, r_infra, dist)
        if gross * 1500 > MAX_U64:
            raise OverflowError("r_gross times 1500 exceeds uint64")
        state = FinancialState(gross, r_legal, r_infra, dist, liquid_sum, escrow, escrow)
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                if db.execute("SELECT 1 FROM qf_state").fetchone():
                    raise ValueError("machine already provisioned")
                db.execute("INSERT INTO qf_state VALUES (1, ?, ?, ?, ?, ?, ?, ?)",
                           tuple(str(v) for v in state.__dict__.values()))
                db.executemany("INSERT INTO qf_allocations VALUES (?, ?, ?, 'escrow')",
                               [(a.allocation_id, str(a.amount), a.dispute_digest)
                                for a in allocations])
                db.execute("INSERT INTO qf_cvp VALUES (1, ?, ?)", (cvp_canonical, cvp_hash))
                self._state(db)
                db.commit()
            except BaseException:
                db.rollback()
                raise
        return state

    def _state(self, db: sqlite3.Connection) -> FinancialState:
        row = db.execute("SELECT r_gross, r_legal, r_infra, r_dist, liquid_sum, "
                         "escrow_sum, escrow_bal FROM qf_state WHERE singleton=1").fetchone()
        if row is None:
            raise ValueError("machine not provisioned")
        try:
            values = tuple(_u64(int(value), "state") for value in row)
            if any(str(value) != original for value, original in zip(values, row)):
                raise ValueError("noncanonical state")
            state = FinancialState(*values)
            if state.r_gross * 1500 > MAX_U64:
                raise ValueError("r_gross times 1500 exceeds uint64")
            self._cvp_digest(db)
            pending = _sum(*(int(r[0]) for r in db.execute(
                "SELECT amount FROM qf_allocations WHERE status='escrow'")))
            if (_sum(state.r_legal, state.r_infra, state.r_dist) != state.r_gross
                    or _sum(state.liquid_sum, state.escrow_sum) != state.r_dist
                    or state.escrow_sum != state.escrow_bal
                    or pending != state.escrow_sum):
                raise ValueError("state conservation failure")
            return state
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("invalid persisted financial state") from exc

    def _cvp_digest(self, db: sqlite3.Connection) -> str:
        row = db.execute("SELECT canonical_allocations, digest FROM qf_cvp "
                         "WHERE singleton=1").fetchone()
        if row is None:
            raise ValueError("missing provisioned CVP")
        canonical, digest = row
        try:
            vector = json.loads(canonical)
            if type(vector) is not list:
                raise ValueError("invalid CVP vector")
            slices = []
            for record in vector:
                if type(record) is not dict or set(record) != {"artifact_id", "bps"}:
                    raise ValueError("invalid CVP record")
                if type(record["artifact_id"]) is not str:
                    raise ValueError("invalid CVP artifact_id")
                slices.append(SettlementSlice(record["artifact_id"], record["bps"]))
            if len({s.artifact_id for s in slices}) != len(slices):
                raise ValueError("duplicate CVP artifact_id")
            _digest(digest)
            if (type(canonical) is not bytes
                    or deterministic_jcs_serialize(vector) != canonical
                    or allocation_digest(slices) != digest):
                raise ValueError("invalid CVP commitment")
            return digest
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("invalid provisioned CVP") from exc

    def state(self) -> FinancialState:
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            try:
                state = self._state(db)
                db.commit()
                return state
            except BaseException:
                db.rollback()
                raise

    def release(self, token: TribunalToken, signature: bytes) -> ReleaseResult:
        """Verify first, then atomically consume nonce, resolve and receipt."""
        try:
            payload = tribunal_signing_payload(token)
            if (token.machine_id != self.machine_id or type(signature) is not bytes
                    or len(signature) != 64):
                return ReleaseResult(ReleaseStatus.FORGED)
            self.key.verify(signature, payload)
        except (InvalidSignature, TypeError, ValueError, OverflowError):
            return ReleaseResult(ReleaseStatus.FORGED)
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                state = self._state(db)
                cvp_hash = self._cvp_digest(db)
                if db.execute("SELECT 1 FROM qf_receipts WHERE nonce=?", (token.nonce,)).fetchone():
                    db.rollback()
                    return ReleaseResult(ReleaseStatus.REPLAY)
                if token.cvp_allocation_digest != cvp_hash:
                    db.rollback()
                    return ReleaseResult(ReleaseStatus.CVP_MISMATCH)
                row = db.execute("SELECT amount, dispute_digest, status FROM qf_allocations "
                                 "WHERE allocation_id=?", (token.allocation_id,)).fetchone()
                if row is None:
                    db.rollback()
                    return ReleaseResult(ReleaseStatus.MISSING_ALLOCATION)
                amount_text, digest, status = row
                if digest != token.dispute_digest:
                    db.rollback()
                    return ReleaseResult(ReleaseStatus.DISPUTE_MISMATCH)
                if status != "escrow":
                    db.rollback()
                    return ReleaseResult(ReleaseStatus.ALREADY_RESOLVED)
                amount = _u64(int(amount_text), "allocation amount")
                if str(amount) != amount_text or amount > state.escrow_sum:
                    raise ValueError("invalid allocation amount")
                upheld = token.verdict == "upheld"
                next_state = FinancialState(
                    state.r_gross, _sum(state.r_legal, amount) if upheld else state.r_legal,
                    state.r_infra, state.r_dist - amount if upheld else state.r_dist,
                    state.liquid_sum if upheld else _sum(state.liquid_sum, amount),
                    state.escrow_sum - amount, state.escrow_bal - amount,
                )
                db.execute("UPDATE qf_allocations SET status=? WHERE allocation_id=?",
                           ("forfeited" if upheld else "exonerated", token.allocation_id))
                db.execute("UPDATE qf_state SET r_gross=?, r_legal=?, r_infra=?, r_dist=?, "
                           "liquid_sum=?, escrow_sum=?, escrow_bal=? WHERE singleton=1",
                           tuple(str(v) for v in next_state.__dict__.values()))
                self._state(db)
                receipt = {"machine_id": token.machine_id, "nonce": token.nonce,
                           "allocation_id": token.allocation_id, "verdict": token.verdict,
                           "dispute_digest": token.dispute_digest, "amount": str(amount),
                           "cvp_allocation_digest": cvp_hash,
                           "tribunal_signature": signature.hex(),
                           "state": {k: str(v) for k, v in next_state.__dict__.items()}}
                canonical = deterministic_jcs_serialize(receipt)
                receipt_hash = hashlib.sha256(RECEIPT_DOMAIN + canonical).hexdigest()
                db.execute("INSERT INTO qf_receipts VALUES (?, ?, ?)",
                           (token.nonce, receipt_hash, canonical))
                db.commit()
                return ReleaseResult(ReleaseStatus.RELEASED, next_state, receipt_hash)
            except BaseException:
                db.rollback()
                raise
