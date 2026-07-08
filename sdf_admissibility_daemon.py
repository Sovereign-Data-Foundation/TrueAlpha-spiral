"""SDF Public Proof Surface v0.1 admissibility daemon.

The daemon witnesses the public proof surface for a proposed state transition
without retaining private substance. It verifies origin, authority, lineage,
consent, and receipt-generation invariants, then emits a canonical receipt.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4

REQUIRED_INVARIANTS = [
    "origin_integrity",
    "authority_match",
    "lineage_continuity",
    "consent_validity",
    "substance_privacy",
    "receipt_generation",
    "refusal_legibility",
]

DEFAULT_DENIED_CAPABILITIES = {
    "modify_private_state_without_consent",
    "execute_external_tool_without_receipt",
    "suppress_refusal_reason",
}


def canonical_json(value: Mapping[str, Any]) -> str:
    """Return deterministic JSON for hashing and receipt comparison."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_uri(value: Mapping[str, Any] | str) -> str:
    """Return a sha256: URI for canonical JSON or a string payload."""

    payload = canonical_json(value) if isinstance(value, Mapping) else value
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class AdmissibilityDaemon:
    """Deterministic runtime gate for proposed SDF state transitions."""

    def __init__(self, gate_name: str = "logOS_daemon_v0.1") -> None:
        self.gate_name = gate_name

    def evaluate(self, transition: Mapping[str, Any]) -> dict[str, Any]:
        """Accept or refuse a transition and emit a canonical forensic receipt."""

        candidate = deepcopy(dict(transition))
        failed = self._failed_invariants(candidate)
        accepted = not failed
        receipt = self._receipt(candidate, accepted, failed)
        receipt["receipt_hash"] = sha256_uri({k: v for k, v in receipt.items() if k != "receipt_hash"})
        return receipt

    def _failed_invariants(self, transition: Mapping[str, Any]) -> list[str]:
        failed: list[str] = []
        origin = transition.get("origin", {})
        authority = transition.get("authority", {})
        lineage = transition.get("lineage", {})
        privacy = transition.get("privacy", {})

        if not all(origin.get(field) for field in ("origin_id", "origin_type", "authority_source", "timestamp_utc", "nonce")):
            failed.append("origin_integrity")

        requested = set(transition.get("action_requested", []))
        scope = set(authority.get("authority_scope", []))
        denied = set(authority.get("denied_capabilities", [])) | DEFAULT_DENIED_CAPABILITIES
        if not requested or not requested.issubset(scope) or requested & denied:
            failed.append("authority_match")

        if not lineage.get("parent_hash") or lineage.get("parent_hash") != transition.get("expected_parent_hash"):
            failed.append("lineage_continuity")

        if authority.get("consent_required", True) and not transition.get("consent", {}).get("granted"):
            failed.append("consent_validity")

        if privacy.get("private_payload_storage") or privacy.get("reveal_private_content"):
            failed.append("substance_privacy")

        return failed

    def _receipt(self, transition: Mapping[str, Any], accepted: bool, failed: list[str]) -> dict[str, Any]:
        origin = transition.get("origin", {})
        lineage = transition.get("lineage", {})
        action = transition.get("action_requested", [])
        timestamp = transition.get("timestamp_utc") or origin.get("timestamp_utc") or _utc_now()
        base = {
            "receipt_id": transition.get("receipt_id") or f"sdf-{'exec' if accepted else 'refusal'}-{uuid4().hex[:12]}",
            "origin_id": origin.get("origin_id", "unknown_or_invalid"),
            "action_requested": action,
            "action_authorized": accepted,
            "state_changed": False,
            "parent_hash": lineage.get("parent_hash"),
            "transition_hash": sha256_uri(transition),
            "witness_hash": sha256_uri({"gate": self.gate_name, "failed_invariants": failed}),
            "timestamp_utc": timestamp,
        }
        if accepted:
            return {
                "receipt_type": "execution",
                **base,
                "admissibility_result": "accepted",
                "admissibility_gate": self.gate_name,
                "tools_invoked": transition.get("tools_invoked", []),
                "required_invariants": REQUIRED_INVARIANTS,
                "failed_invariants": [],
            }
        return {
            "receipt_type": "refusal",
            **base,
            "admissibility_result": "refused",
            "admissibility_gate": self.gate_name,
            "refusal_reason": "DENIED_AUTHORIZATION",
            "required_invariants": REQUIRED_INVARIANTS,
            "failed_invariants": failed,
        }


def evaluate_transition(transition: Mapping[str, Any]) -> dict[str, Any]:
    """Convenience wrapper using the default log(OS) daemon name."""

    return AdmissibilityDaemon().evaluate(transition)
