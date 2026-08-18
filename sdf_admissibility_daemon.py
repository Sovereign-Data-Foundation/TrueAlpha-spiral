"""Authenticated SDF admissibility gate and evidence/state ledger contracts."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol


class CanonicalJSONError(ValueError): pass
class ReplayConflictError(RuntimeError): pass
class StateForkError(RuntimeError): pass
class LedgerUnavailableError(RuntimeError): pass


def canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_uri(value: Mapping[str, Any] | str) -> str:
    payload = canonical_json(value) if isinstance(value, Mapping) else value
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value: raise CanonicalJSONError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def parse_canonical_json(raw: bytes | str) -> Mapping[str, Any]:
    try: value = json.loads(raw, object_pairs_hook=_object_without_duplicates)
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc: raise CanonicalJSONError("invalid JSON") from exc
    def validate(item: Any) -> None:
        if isinstance(item, float): raise CanonicalJSONError("TAS-CJSON-1 forbids floating-point values")
        if isinstance(item, Mapping):
            for nested in item.values(): validate(nested)
        elif isinstance(item, list):
            for nested in item: validate(nested)
    if not isinstance(value, Mapping): raise CanonicalJSONError("top-level value must be an object")
    validate(value)
    return value


def parse_rfc3339(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None: raise ValueError("timestamp timezone is required")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class AuthoritySnapshot:
    credential_id: str
    authority_epoch: int
    authority_checkpoint_hash: str
    public_key: bytes
    valid_from: str
    valid_until: str
    scope_policy_hash: str
    revoked: bool = False


class AuthorityResolver(Protocol):
    def resolve(self, *, credential_id: str, authority_checkpoint_hash: str, authority_epoch: int) -> AuthoritySnapshot | None: ...


class SignatureVerifier(Protocol):
    def verify(self, *, public_key: bytes, message: bytes, signature: bytes) -> bool: ...


class ScopePolicyResolver(Protocol):
    def permits(self, *, policy_hash: str, requested_operation: str, candidate_hash: str) -> bool: ...


class ParentVerifier(Protocol):
    def verify(self, *, receipt_hash: str, authority_checkpoint_hash: str) -> bool: ...


class ReceiptSigner(Protocol):
    def sign(self, message: bytes) -> Mapping[str, str]: ...


@dataclass(frozen=True)
class DurableAppendResult:
    receipt_hash: str
    evidence_sequence: int
    evidence_head_hash: str
    state_sequence: int
    state_head_hash: str
    replayed: bool


class DecisionLedger(Protocol):
    def append_decision_once(
        self, *, replay_key: str, authorization_hash: str, receipt_hash: str,
        receipt: Mapping[str, Any], expected_state_parent_hash: str | None,
        advances_state_lineage: bool,
    ) -> DurableAppendResult: ...


class SQLiteDecisionLedger:
    """WAL-backed ledger with atomic replay detection and independent state history."""
    def __init__(self, database: str | Path) -> None:
        self.database = str(database)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS ledger_meta (
                  singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                  evidence_sequence INTEGER NOT NULL, evidence_head_hash TEXT NOT NULL,
                  state_sequence INTEGER NOT NULL, state_head_hash TEXT NOT NULL
                );
                INSERT OR IGNORE INTO ledger_meta VALUES (1, 0, 'sha256:genesis', 0, 'sha256:genesis');
                CREATE TABLE IF NOT EXISTS decision_receipts (
                  receipt_hash TEXT PRIMARY KEY, evidence_sequence INTEGER NOT NULL UNIQUE,
                  state_sequence INTEGER, replay_key TEXT NOT NULL UNIQUE,
                  authorization_hash TEXT NOT NULL, expected_state_parent_hash TEXT,
                  advances_state_lineage INTEGER NOT NULL CHECK (advances_state_lineage IN (0,1)),
                  canonical_receipt BLOB NOT NULL
                );
            """)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database, isolation_level=None, timeout=10)

    def append_decision_once(self, *, replay_key: str, authorization_hash: str, receipt_hash: str,
                             receipt: Mapping[str, Any], expected_state_parent_hash: str | None,
                             advances_state_lineage: bool) -> DurableAppendResult:
        payload = canonical_json(receipt).encode()
        with self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                old = connection.execute("SELECT receipt_hash, authorization_hash FROM decision_receipts WHERE replay_key=?", (replay_key,)).fetchone()
                if old:
                    if old[1] != authorization_hash: raise ReplayConflictError("replay key equivocation")
                    result = self._result(connection, old[0], True)
                    connection.execute("COMMIT")
                    return result
                evidence_sequence, evidence_head, state_sequence, state_head = connection.execute(
                    "SELECT evidence_sequence,evidence_head_hash,state_sequence,state_head_hash FROM ledger_meta WHERE singleton=1").fetchone()
                if advances_state_lineage and expected_state_parent_hash != state_head:
                    raise StateForkError("state parent does not match current state head")
                next_evidence, next_state = evidence_sequence + 1, state_sequence + int(advances_state_lineage)
                connection.execute("INSERT INTO decision_receipts VALUES (?,?,?,?,?,?,?,?)", (
                    receipt_hash, next_evidence, next_state if advances_state_lineage else None, replay_key,
                    authorization_hash, expected_state_parent_hash, int(advances_state_lineage), payload))
                connection.execute("UPDATE ledger_meta SET evidence_sequence=?,evidence_head_hash=?,state_sequence=?,state_head_hash=? WHERE singleton=1", (
                    next_evidence, receipt_hash, next_state, receipt_hash if advances_state_lineage else state_head))
                connection.execute("COMMIT")
                return DurableAppendResult(receipt_hash, next_evidence, receipt_hash, next_state,
                                           receipt_hash if advances_state_lineage else state_head, False)
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def _result(self, connection: sqlite3.Connection, receipt_hash: str, replayed: bool) -> DurableAppendResult:
        receipt = connection.execute("SELECT evidence_sequence FROM decision_receipts WHERE receipt_hash=?", (receipt_hash,)).fetchone()
        meta = connection.execute("SELECT evidence_sequence,evidence_head_hash,state_sequence,state_head_hash FROM ledger_meta WHERE singleton=1").fetchone()
        return DurableAppendResult(receipt_hash, receipt[0], meta[1], meta[2], meta[3], replayed)


class AdmissibilityDaemon:
    """Turn a signed authorization envelope into one durable admission decision.

    Authority is resolved from a trusted checkpoint.  Envelope authority fields
    select the snapshot; they do not grant authority by themselves.
    """

    _REQUIRED_FIELDS = frozenset({
        "credential_id", "authority_epoch", "authority_checkpoint_hash",
        "issued_at", "nonce", "requested_operation", "candidate_hash",
        "signature", "expected_state_parent_hash",
    })

    def __init__(
        self,
        *,
        authority_resolver: AuthorityResolver,
        signature_verifier: SignatureVerifier,
        scope_resolver: ScopePolicyResolver,
        ledger: DecisionLedger,
        parent_verifier: ParentVerifier,
        receipt_signer: ReceiptSigner,
    ) -> None:
        self.authority_resolver = authority_resolver
        self.signature_verifier = signature_verifier
        self.scope_resolver = scope_resolver
        self.ledger = ledger
        self.parent_verifier = parent_verifier
        self.receipt_signer = receipt_signer

    def evaluate_raw(
        self, raw: bytes | str, *, current_time: str
    ) -> dict[str, Any] | None:
        """Drop malformed transport without signing or allocating ledger space."""
        try:
            envelope = parse_canonical_json(raw)
        except CanonicalJSONError:
            return None
        return self.evaluate(envelope, current_time=current_time)

    def evaluate(
        self, envelope: Mapping[str, Any], *, current_time: str
    ) -> dict[str, Any]:
        """Persist an admitted decision or a well-formed refusal.

        CUTOFF means that durable append could not safely establish replay or
        state-lineage semantics; callers must not execute in that case.
        """
        errors = self._envelope_errors(envelope)
        if errors:
            return self._persist_refusal(envelope, errors)

        snapshot = self.authority_resolver.resolve(
            credential_id=envelope["credential_id"],
            authority_epoch=envelope["authority_epoch"],
            authority_checkpoint_hash=envelope["authority_checkpoint_hash"],
        )
        if snapshot is None or not self._matches_snapshot(envelope, snapshot):
            return self._persist_refusal(envelope, ["authority_match"])

        failures = self._authorization_failures(envelope, snapshot, current_time)
        expected_parent = envelope["expected_state_parent_hash"]
        if expected_parent != "sha256:genesis" and not self.parent_verifier.verify(
            receipt_hash=expected_parent,
            authority_checkpoint_hash=snapshot.authority_checkpoint_hash,
        ):
            failures.append("lineage_continuity")

        receipt = self._receipt(envelope, snapshot, failures)
        return self._append(
            receipt=receipt,
            replay_key=self._replay_key(snapshot, envelope["nonce"]),
            authorization_hash=sha256_uri(envelope),
            expected_state_parent_hash=expected_parent,
            advances_state_lineage=not failures,
        )

    def _envelope_errors(self, envelope: Mapping[str, Any]) -> list[str]:
        if not self._REQUIRED_FIELDS.issubset(envelope):
            return ["envelope_integrity"]
        if (
            not isinstance(envelope["credential_id"], str)
            or not isinstance(envelope["authority_epoch"], int)
            or isinstance(envelope["authority_epoch"], bool)
            or not isinstance(envelope["authority_checkpoint_hash"], str)
            or not isinstance(envelope["issued_at"], str)
            or not isinstance(envelope["nonce"], str)
            or not envelope["nonce"]
            or not isinstance(envelope["requested_operation"], str)
            or not isinstance(envelope["candidate_hash"], str)
            or not isinstance(envelope["signature"], str)
            or not isinstance(envelope["expected_state_parent_hash"], str)
        ):
            return ["envelope_integrity"]
        return []

    @staticmethod
    def _matches_snapshot(
        envelope: Mapping[str, Any], snapshot: AuthoritySnapshot
    ) -> bool:
        return (
            snapshot.credential_id == envelope["credential_id"]
            and snapshot.authority_epoch == envelope["authority_epoch"]
            and snapshot.authority_checkpoint_hash
            == envelope["authority_checkpoint_hash"]
        )

    def _authorization_failures(
        self,
        envelope: Mapping[str, Any],
        snapshot: AuthoritySnapshot,
        current_time: str,
    ) -> list[str]:
        failures: list[str] = []
        try:
            now = parse_rfc3339(current_time)
            issued_at = parse_rfc3339(envelope["issued_at"])
            valid_from = parse_rfc3339(snapshot.valid_from)
            valid_until = parse_rfc3339(snapshot.valid_until)
            if snapshot.revoked or not valid_from <= issued_at <= now < valid_until:
                failures.append("authority_match")
        except (TypeError, ValueError):
            failures.append("authority_match")

        unsigned = {key: value for key, value in envelope.items() if key != "signature"}
        try:
            signature = bytes.fromhex(envelope["signature"])
        except ValueError:
            signature = b""
        message = b"SDF-AUTH-V1\0" + canonical_json(unsigned).encode("utf-8")
        if not self.signature_verifier.verify(
            public_key=snapshot.public_key,
            message=message,
            signature=signature,
        ):
            failures.append("signature_validity")

        if not self.scope_resolver.permits(
            policy_hash=snapshot.scope_policy_hash,
            requested_operation=envelope["requested_operation"],
            candidate_hash=envelope["candidate_hash"],
        ):
            failures.append("scope_authorization")
        return failures

    def _persist_refusal(
        self, envelope: Mapping[str, Any], failures: list[str]
    ) -> dict[str, Any]:
        receipt = self._receipt(envelope, None, failures)
        return self._append(
            receipt=receipt,
            replay_key=sha256_uri({"invalid_transition_hash": sha256_uri(envelope)}),
            authorization_hash=sha256_uri(envelope),
            expected_state_parent_hash=None,
            advances_state_lineage=False,
        )

    def _append(
        self,
        *,
        receipt: Mapping[str, Any],
        replay_key: str,
        authorization_hash: str,
        expected_state_parent_hash: str | None,
        advances_state_lineage: bool,
    ) -> dict[str, Any]:
        try:
            result = self.ledger.append_decision_once(
                replay_key=replay_key,
                authorization_hash=authorization_hash,
                receipt_hash=receipt["receipt_hash"],
                receipt=receipt,
                expected_state_parent_hash=expected_state_parent_hash,
                advances_state_lineage=advances_state_lineage,
            )
        except (ReplayConflictError, StateForkError):
            return {
                "admissibility_result": "CUTOFF",
                "cutoff_reason": "REPLAY_OR_STATE_FORK",
                "durable_receipt": False,
            }
        except (LedgerUnavailableError, sqlite3.Error):
            return {
                "admissibility_result": "CUTOFF",
                "cutoff_reason": "LEDGER_UNAVAILABLE",
                "durable_receipt": False,
            }
        return {
            **receipt,
            "durable_receipt": True,
            "evidence_sequence": result.evidence_sequence,
            "evidence_head_hash": result.evidence_head_hash,
            "state_sequence": result.state_sequence,
            "state_head_hash": result.state_head_hash,
            "replayed": result.replayed,
        }

    @staticmethod
    def _replay_key(snapshot: AuthoritySnapshot, nonce: str) -> str:
        return sha256_uri({
            "credential_id": snapshot.credential_id,
            "authority_epoch": snapshot.authority_epoch,
            "checkpoint_hash": snapshot.authority_checkpoint_hash,
            "nonce": nonce,
        })

    def _receipt(
        self,
        envelope: Mapping[str, Any],
        snapshot: AuthoritySnapshot | None,
        failures: list[str],
    ) -> dict[str, Any]:
        body = {
            "transition_hash": sha256_uri(envelope),
            "authority_checkpoint_hash": (
                snapshot.authority_checkpoint_hash
                if snapshot is not None
                else envelope.get("authority_checkpoint_hash")
            ),
            "expected_state_parent_hash": envelope.get("expected_state_parent_hash"),
            "decision": "REFUSED" if failures else "ADMITTED",
            "failed_invariants": failures,
        }
        message = b"SDF-RECEIPT-V1\0" + canonical_json(body).encode("utf-8")
        receipt = {**body, "attestation": dict(self.receipt_signer.sign(message))}
        return {**receipt, "receipt_hash": sha256_uri(receipt)}
