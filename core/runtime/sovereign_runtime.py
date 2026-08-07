"""Sovereign execution runtime for TAS Initial Operating Capability."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
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
    """The append-only evidence and state ledger for the TAS IOC execution."""

    def __init__(self, genesis_parent_hash: str = "sha256:genesis") -> None:
        self.evidence_history: list[TASGene] = []
        self.state_history: list[TASGene] = []
        self.genesis_parent_hash = genesis_parent_hash
        self._state_head_hash = genesis_parent_hash
        self._last_wake_link = genesis_parent_hash

    @property
    def state_head_hash(self) -> str:
        return self._state_head_hash

    @property
    def last_wake_link(self) -> str:
        return self._last_wake_link

    def append(self, gene: TASGene) -> str:
        """Append a TASGene to the histories, validating parent linkage."""
        gene.constitutional_completeness_check()

        if gene.decision == "ADMITTED":
            if gene.parent != self._state_head_hash:
                raise SovereignStructuralViolation(
                    f"State linkage discontinuity: expected parent {self._state_head_hash}, "
                    f"got {gene.parent}"
                )
            self.state_history.append(gene)
            self._state_head_hash = gene.receipt.get("receipt_hash") or sha256_uri(gene.receipt)

        self.evidence_history.append(gene)

        # Compute new WakeLink (cryptographically chained)
        receipt_hash = gene.receipt.get("receipt_hash") or sha256_uri(gene.receipt)
        payload = f"{self._last_wake_link}:{receipt_hash}"
        self._last_wake_link = "sha256:" + hashlib.sha256(payload.encode()).hexdigest()
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
    ) -> None:
        self.verifier_public_key = verifier_public_key
        self.runtime_private_key = runtime_private_key
        self.state = genesis_state if genesis_state is not None else {"value": 0}
        self.wake_chain = WakeChain()

    def execute_action(self, obj: AdmissibilityObject) -> dict[str, Any]:
        """Verify the admissibility object, update the WakeChain, and execute state transition."""
        is_signature_valid = False
        if obj.signature:
            try:
                from cryptography.hazmat.primitives.asymmetric import ed25519
                pub_key = ed25519.Ed25519PublicKey.from_public_bytes(self.verifier_public_key)
                pub_key.verify(obj.signature, obj.receipt_hash.encode())
                is_signature_valid = True
            except Exception:
                is_signature_valid = False

        failed_checks = []
        if not is_signature_valid:
            failed_checks.append("signature_validity")
        if obj.revocation_result:
            failed_checks.append("authority_match")
        if obj.decision != "ADMITTED":
            failed_checks.append("scope_authorization")

        decision = "ADMITTED" if (not failed_checks and obj.decision == "ADMITTED") else "REFUSED"

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

            committed_body = {
                "decision": "COMMITTED",
                "operation": operation,
                "state_hash": sha256_uri(self.state),
                "state": dict(self.state),
                "wake_link": wake_link,
                "receipt_hash": obj.receipt_hash,
            }
            committed_message = b"SDF-TERMINAL-COMMITTED-V1\0" + canonical_json(committed_body).encode("utf-8")

            from cryptography.hazmat.primitives.asymmetric import ed25519
            priv_key = ed25519.Ed25519PrivateKey.from_private_bytes(self.runtime_private_key)
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
            refused_message = b"SDF-TERMINAL-REFUSED-V1\0" + canonical_json(refused_body).encode("utf-8")

            from cryptography.hazmat.primitives.asymmetric import ed25519
            priv_key = ed25519.Ed25519PrivateKey.from_private_bytes(self.runtime_private_key)
            signature = priv_key.sign(refused_message)

            return {
                **refused_body,
                "attestation": {
                    "node_id": "tas-runtime-01",
                    "signature": signature.hex(),
                },
            }
