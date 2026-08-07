"""Sovereign execution runtime for TAS Initial Operating Capability."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Set, Sequence


class SovereignStructuralViolation(RuntimeError):
    """Raised when an operation or linkage fails deterministic TAS admission."""


def canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_uri(value: Mapping[str, Any] | str) -> str:
    payload = canonical_json(value) if isinstance(value, Mapping) else value
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True)
class AdmissibilityObject:
    credential_id: str
    scope: str
    authority_snapshot: Any
    context_snapshot_hash: str
    candidate_hash: str
    parent_receipt: str | None
    revocation_result: bool
    invariant_results: dict[str, Any]
    closed_admitted_action_set: Set[str]
    decision: str  # "ADMITTED" or "REFUSED"
    receipt_hash: str
    signature: bytes

    def compute_receipt_hash(self) -> str:
        """Recompute the receipt_hash mechanically from all fields of the AdmissibilityObject.

        This guarantees that no field of the object can be modified without altering the receipt_hash,
        preventing any substitution gaps.
        """
        body = {
            "credential_id": self.credential_id,
            "scope": self.scope,
            "authority_snapshot": {
                "credential_id": getattr(
                    self.authority_snapshot,
                    "credential_id",
                    self.authority_snapshot.get("credential_id")
                    if isinstance(self.authority_snapshot, dict)
                    else "",
                ),
                "authority_epoch": getattr(
                    self.authority_snapshot,
                    "authority_epoch",
                    self.authority_snapshot.get("authority_epoch")
                    if isinstance(self.authority_snapshot, dict)
                    else 0,
                ),
                "authority_checkpoint_hash": getattr(
                    self.authority_snapshot,
                    "authority_checkpoint_hash",
                    self.authority_snapshot.get("authority_checkpoint_hash")
                    if isinstance(self.authority_snapshot, dict)
                    else "",
                ),
                "revoked": getattr(
                    self.authority_snapshot,
                    "revoked",
                    self.authority_snapshot.get("revoked")
                    if isinstance(self.authority_snapshot, dict)
                    else False,
                ),
            }
            if self.authority_snapshot
            else None,
            "context_snapshot_hash": self.context_snapshot_hash,
            "candidate_hash": self.candidate_hash,
            "parent_receipt": self.parent_receipt,
            "revocation_result": self.revocation_result,
            "invariant_results": self.invariant_results,
            "closed_admitted_action_set": sorted(list(self.closed_admitted_action_set)),
            "decision": self.decision,
        }
        return sha256_uri(body)


@dataclass(frozen=True)
class TASGene:
    origin: str
    context: str
    authority: str
    operation: str
    parent: str
    invariants: dict[str, Any]
    decision: str
    receipt: dict[str, Any]

    @classmethod
    def admitted(
        cls,
        origin: str,
        context: str,
        authority: str,
        operation: str,
        parent: str,
        invariants: dict[str, Any],
        receipt: dict[str, Any],
    ) -> TASGene:
        return cls(
            origin=origin,
            context=context,
            authority=authority,
            operation=operation,
            parent=parent,
            invariants=invariants,
            decision="ADMITTED",
            receipt=receipt,
        )

    @classmethod
    def refused(
        cls,
        origin: str,
        context: str,
        authority: str,
        operation: str,
        parent: str,
        invariants: dict[str, Any],
        receipt: dict[str, Any],
    ) -> TASGene:
        return cls(
            origin=origin,
            context=context,
            authority=authority,
            operation=operation,
            parent=parent,
            invariants=invariants,
            decision="REFUSED",
            receipt=receipt,
        )

    def constitutional_completeness_check(self) -> bool:
        """Enforce constitutional completeness check of TASGene."""
        if not self.origin:
            raise ValueError("TASGene: origin is required")
        if not self.context:
            raise ValueError("TASGene: context is required")
        if not self.authority:
            raise ValueError("TASGene: authority is required")
        if not self.operation:
            raise ValueError("TASGene: operation is required")
        if not self.parent:
            raise ValueError("TASGene: parent is required")
        if not isinstance(self.invariants, dict):
            raise ValueError("TASGene: invariants must be a dictionary")
        if self.decision not in ("ADMITTED", "REFUSED"):
            raise ValueError("TASGene: decision must be ADMITTED or REFUSED")
        if not isinstance(self.receipt, dict) or not self.receipt:
            raise ValueError("TASGene: receipt must be a non-empty dict")
        return True


class WakeChain:
    """The WAL SQLite-backed append-only evidence and state ledger."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        genesis_parent_hash: str = "sha256:genesis",
    ) -> None:
        self.db_path = str(db_path) if db_path is not None else None
        self.genesis_parent_hash = genesis_parent_hash
        self.evidence_history: list[TASGene] = []
        self.state_history: list[TASGene] = []

        self._state_head_hash = genesis_parent_hash
        self._last_wake_link = genesis_parent_hash

        if self.db_path:
            with self._connect() as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS wake_meta (
                        singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                        state_head_hash TEXT NOT NULL,
                        last_wake_link TEXT NOT NULL
                    );
                    INSERT OR IGNORE INTO wake_meta VALUES (1, 'sha256:genesis', 'sha256:genesis');

                    CREATE TABLE IF NOT EXISTS wake_genes (
                        receipt_hash TEXT PRIMARY KEY,
                        origin TEXT NOT NULL,
                        context TEXT NOT NULL,
                        authority TEXT NOT NULL,
                        operation TEXT NOT NULL,
                        parent TEXT NOT NULL,
                        invariants TEXT NOT NULL,
                        decision TEXT NOT NULL CHECK (decision IN ('ADMITTED', 'REFUSED')),
                        receipt TEXT NOT NULL,
                        sequence_id INTEGER NOT NULL UNIQUE
                    );
                """)
                # Load state
                meta = conn.execute(
                    "SELECT state_head_hash, last_wake_link FROM wake_meta WHERE singleton=1"
                ).fetchone()
                self._state_head_hash = meta[0]
                self._last_wake_link = meta[1]

                # Load genes sorted by sequence_id
                genes = conn.execute(
                    "SELECT origin, context, authority, operation, parent, invariants, decision, receipt "
                    "FROM wake_genes ORDER BY sequence_id ASC"
                ).fetchall()
                for row in genes:
                    gene = TASGene(
                        origin=row[0],
                        context=row[1],
                        authority=row[2],
                        operation=row[3],
                        parent=row[4],
                        invariants=json.loads(row[5]),
                        decision=row[6],
                        receipt=json.loads(row[7]),
                    )
                    self.evidence_history.append(gene)
                    if gene.decision == "ADMITTED":
                        self.state_history.append(gene)

    def _connect(self) -> sqlite3.Connection:
        if not self.db_path:
            raise ValueError("No database path configured for this WakeChain instance.")
        return sqlite3.connect(self.db_path, isolation_level=None, timeout=10)

    @property
    def state_head_hash(self) -> str:
        return self._state_head_hash

    @property
    def last_wake_link(self) -> str:
        return self._last_wake_link

    def append(self, gene: TASGene) -> str:
        """Append a TASGene to the histories, validating parent linkage and persisting if database exists."""
        gene.constitutional_completeness_check()

        if gene.decision == "ADMITTED":
            if gene.parent != self._state_head_hash:
                raise SovereignStructuralViolation(
                    f"State linkage discontinuity: expected parent {self._state_head_hash}, "
                    f"got {gene.parent}"
                )
            self.state_history.append(gene)
            self._state_head_hash = (
                gene.receipt.get("receipt_hash") or sha256_uri(gene.receipt)
            )

        self.evidence_history.append(gene)

        # Compute new WakeLink (cryptographically chained)
        receipt_hash = gene.receipt.get("receipt_hash") or sha256_uri(gene.receipt)
        payload = f"{self._last_wake_link}:{receipt_hash}"
        self._last_wake_link = (
            "sha256:" + hashlib.sha256(payload.encode()).hexdigest()
        )

        # Persist if database is configured
        if self.db_path:
            with self._connect() as conn:
                try:
                    conn.execute("BEGIN IMMEDIATE")
                    max_seq = conn.execute(
                        "SELECT COALESCE(MAX(sequence_id), 0) FROM wake_genes"
                    ).fetchone()[0]
                    next_seq = max_seq + 1

                    conn.execute(
                        "INSERT INTO wake_genes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            receipt_hash,
                            gene.origin,
                            gene.context,
                            gene.authority,
                            gene.operation,
                            gene.parent,
                            json.dumps(gene.invariants, sort_keys=True),
                            gene.decision,
                            json.dumps(gene.receipt, sort_keys=True),
                            next_seq,
                        ),
                    )
                    conn.execute(
                        "UPDATE wake_meta SET state_head_hash=?, last_wake_link=? WHERE singleton=1",
                        (self._state_head_hash, self._last_wake_link),
                    )
                    conn.execute("COMMIT")
                except Exception:
                    conn.execute("ROLLBACK")
                    raise

        return self._last_wake_link


class SovereignRuntime:
    """A bounded runtime that consumes verifier-produced admissibility objects,

    routes them through TASGene and WakeChain, and executes narrow deterministic
    operations to transition the protected state.
    """

    def __init__(
        self,
        verifier_public_key: bytes,
        runtime_private_key: bytes,
        genesis_state: dict[str, Any] | None = None,
        db_path: str | Path | None = None,
    ) -> None:
        self.verifier_public_key = verifier_public_key
        self.runtime_private_key = runtime_private_key
        self.db_path = str(db_path) if db_path is not None else None

        self.state = genesis_state if genesis_state is not None else {"value": 0}

        if self.db_path:
            with sqlite3.connect(
                self.db_path, isolation_level=None, timeout=10
            ) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS runtime_state (
                        singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                        state_json TEXT NOT NULL
                    )
                """)
                row = conn.execute(
                    "SELECT state_json FROM runtime_state WHERE singleton=1"
                ).fetchone()
                if row:
                    self.state = json.loads(row[0])
                else:
                    conn.execute(
                        "INSERT INTO runtime_state VALUES (1, ?)",
                        (json.dumps(self.state, sort_keys=True),),
                    )

        self.wake_chain = WakeChain(db_path=db_path)

    def _persist_state(self) -> None:
        if self.db_path:
            with sqlite3.connect(
                self.db_path, isolation_level=None, timeout=10
            ) as conn:
                conn.execute(
                    "UPDATE runtime_state SET state_json=? WHERE singleton=1",
                    (json.dumps(self.state, sort_keys=True),),
                )

    def execute_action(self, obj: AdmissibilityObject) -> dict[str, Any]:
        """Verify the admissibility object, update the WakeChain, and execute state transition."""
        recomputed_hash = obj.compute_receipt_hash()

        is_signature_valid = False
        failed_checks = []

        if obj.receipt_hash != recomputed_hash:
            failed_checks.append("binding_integrity")

        if obj.signature:
            try:
                from cryptography.hazmat.primitives.asymmetric import ed25519

                pub_key = ed25519.Ed25519PublicKey.from_public_bytes(
                    self.verifier_public_key
                )
                pub_key.verify(obj.signature, obj.receipt_hash.encode())
                is_signature_valid = True
            except Exception:
                is_signature_valid = False

        if not is_signature_valid:
            failed_checks.append("signature_validity")
        if obj.revocation_result:
            failed_checks.append("authority_match")
        if obj.decision != "ADMITTED":
            failed_checks.append("scope_authorization")

        # Enforce exact membership in closed_admitted_action_set
        if obj.scope not in obj.closed_admitted_action_set:
            failed_checks.append("scope_authorization")

        decision = (
            "ADMITTED"
            if (not failed_checks and obj.decision == "ADMITTED")
            else "REFUSED"
        )

        origin = obj.candidate_hash
        context = obj.context_snapshot_hash
        authority = obj.credential_id
        operation = obj.scope
        parent = obj.parent_receipt or "sha256:genesis"
        invariants = {
            "failed_checks": failed_checks,
            "invariant_results": obj.invariant_results,
        }

        receipt_dict = {
            "receipt_hash": obj.receipt_hash,
            "decision": decision,
            "expected_state_parent_hash": parent,
            "failed_checks": failed_checks,
        }

        if decision == "ADMITTED":
            gene = TASGene.admitted(
                origin=origin,
                context=context,
                authority=authority,
                operation=operation,
                parent=parent,
                invariants=invariants,
                receipt=receipt_dict,
            )

            wake_link = self.wake_chain.append(gene)

            if operation == "increment":
                self.state["value"] = self.state.get("value", 0) + 1
            else:
                self.state[operation] = "updated"

            # Persist the state transition durably
            self._persist_state()

            committed_body = {
                "decision": "COMMITTED",
                "operation": operation,
                "state_hash": sha256_uri(self.state),
                "state": dict(self.state),
                "wake_link": wake_link,
                "receipt_hash": obj.receipt_hash,
            }
            committed_message = (
                b"SDF-TERMINAL-COMMITTED-V1\0"
                + canonical_json(committed_body).encode("utf-8")
            )

            from cryptography.hazmat.primitives.asymmetric import ed25519

            priv_key = ed25519.Ed25519PrivateKey.from_private_bytes(
                self.runtime_private_key
            )
            signature = priv_key.sign(committed_message)

            return {
                **committed_body,
                "attestation": {
                    "node_id": "tas-runtime-01",
                    "signature": signature.hex(),
                },
            }

        else:
            gene = TASGene.refused(
                origin=origin,
                context=context,
                authority=authority,
                operation=operation,
                parent=parent,
                invariants=invariants,
                receipt=receipt_dict,
            )

            wake_link = self.wake_chain.append(gene)

            refused_body = {
                "decision": "REFUSED",
                "operation": operation,
                "state_hash": sha256_uri(self.state),
                "state": dict(self.state),
                "wake_link": wake_link,
                "receipt_hash": obj.receipt_hash,
                "failures": failed_checks,
            }
            refused_message = (
                b"SDF-TERMINAL-REFUSED-V1\0"
                + canonical_json(refused_body).encode("utf-8")
            )

            from cryptography.hazmat.primitives.asymmetric import ed25519

            priv_key = ed25519.Ed25519PrivateKey.from_private_bytes(
                self.runtime_private_key
            )
            signature = priv_key.sign(refused_message)

            return {
                **refused_body,
                "attestation": {
                    "node_id": "tas-runtime-01",
                    "signature": signature.hex(),
                },
            }
