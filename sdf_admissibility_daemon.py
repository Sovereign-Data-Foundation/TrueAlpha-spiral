"""SDF Public Proof Surface v0.2 admissibility daemon.

The daemon is a deterministic gate for well-formed proposed state transitions.
Malformed transport is rejected at ingress; well-formed authorization failures
receive a canonical refusal receipt.  A ledger atomically consumes authorization
nonces so a signed authorization cannot be replayed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Protocol

REQUIRED_INVARIANTS = [
    "origin_integrity", "authority_match", "scope_authorization",
    "lineage_continuity", "consent_validity", "substance_privacy",
    "receipt_generation", "refusal_legibility",
]
DEFAULT_DENIED_CAPABILITIES = {
    "modify_private_state_without_consent", "execute_external_tool_without_receipt",
    "suppress_refusal_reason",
}


class CanonicalJSONError(ValueError):
    """Raised when a raw payload cannot be used as a canonical transition."""


class ReplayConflictError(RuntimeError):
    """Raised when one nonce is presented with conflicting authorization data."""


@dataclass(frozen=True)
class DurableAppendResult:
    receipt_hash: str
    ledger_sequence: int
    ledger_head_hash: str
    replayed: bool


class DecisionLedger(Protocol):
    """Durable ledger contract. Implementations must atomically consume replay keys."""

    def append_decision_once(
        self, *, replay_key: str, authorization_hash: str, receipt_hash: str,
        receipt: Mapping[str, Any], parent_hash: str | None,
    ) -> DurableAppendResult: ...

    def get_receipt(self, receipt_hash: str) -> Mapping[str, Any] | None: ...


class InMemoryDecisionLedger:
    """Development-only ledger with the same atomic replay semantics as production."""

    def __init__(self) -> None:
        self._receipts: dict[str, dict[str, Any]] = {}
        self._replays: dict[str, tuple[str, DurableAppendResult]] = {}
        self._head_hash = "sha256:genesis"
        self._sequence = 0

    def append_decision_once(self, *, replay_key: str, authorization_hash: str,
                             receipt_hash: str, receipt: Mapping[str, Any],
                             parent_hash: str | None) -> DurableAppendResult:
        existing = self._replays.get(replay_key)
        if existing:
            old_authorization, result = existing
            if old_authorization != authorization_hash:
                raise ReplayConflictError("nonce replay conflicts with prior authorization")
            return DurableAppendResult(result.receipt_hash, result.ledger_sequence,
                                       result.ledger_head_hash, True)
        if parent_hash is not None and parent_hash != "sha256:genesis" and parent_hash not in self._receipts:
            raise ValueError("parent receipt is unavailable")
        self._sequence += 1
        self._head_hash = receipt_hash
        result = DurableAppendResult(receipt_hash, self._sequence, self._head_hash, False)
        self._receipts[receipt_hash] = dict(receipt)
        self._replays[replay_key] = (authorization_hash, result)
        return result

    def get_receipt(self, receipt_hash: str) -> Mapping[str, Any] | None:
        return self._receipts.get(receipt_hash)


def _no_duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CanonicalJSONError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_canonical_json(raw: bytes | str) -> Mapping[str, Any]:
    """Parse a transition without duplicate keys or floating point values."""
    try:
        value = json.loads(raw, object_pairs_hook=_no_duplicate_object)
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CanonicalJSONError("invalid JSON transport") from exc
    if not isinstance(value, Mapping):
        raise CanonicalJSONError("top-level JSON value must be an object")
    def reject_floats(item: Any) -> None:
        if isinstance(item, float):
            raise CanonicalJSONError("TAS-CJSON-1 does not permit floating-point values")
        if isinstance(item, Mapping):
            for nested in item.values(): reject_floats(nested)
        elif isinstance(item, list):
            for nested in item: reject_floats(nested)
    reject_floats(value)
    return value


def canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_uri(value: Mapping[str, Any] | str) -> str:
    payload = canonical_json(value) if isinstance(value, Mapping) else value
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_rfc3339(value: Any) -> datetime:
    if not isinstance(value, str): raise ValueError("RFC 3339 timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None: raise ValueError("RFC 3339 timezone is required")
    return parsed.astimezone(timezone.utc)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class AdmissibilityDaemon:
    """Fail-closed admission gate with atomic nonce consumption."""

    def __init__(
        self,
        gate_name: str = "logOS_daemon_v0.2",
        ledger: DecisionLedger | None = None,
        parent_verifier: Callable[[str, Mapping[str, Any]], bool] | None = None,
    ) -> None:
        self.gate_name = gate_name
        self.ledger = ledger or InMemoryDecisionLedger()
        self.parent_verifier = parent_verifier or self._verify_parent_hash

    def evaluate_raw(self, raw: bytes | str, *, current_time: str | None = None) -> dict[str, Any] | None:
        """Reject malformed transport without signing or persisting it."""
        try:
            transition = parse_canonical_json(raw)
        except CanonicalJSONError:
            return None
        return self.evaluate(transition, current_time=current_time)

    def evaluate(self, transition: Mapping[str, Any], *, current_time: str | None = None) -> dict[str, Any]:
        candidate = dict(transition)
        failed = self._failed_invariants(candidate, current_time)
        receipt = self._receipt(candidate, not failed, failed)
        receipt_hash = sha256_uri(receipt)
        receipt["receipt_hash"] = receipt_hash
        try:
            result = self.ledger.append_decision_once(
                replay_key=self._replay_key(candidate), authorization_hash=sha256_uri(candidate),
                receipt_hash=receipt_hash, receipt=receipt,
                parent_hash=candidate.get("lineage", {}).get("parent_hash") if not failed else None,
            )
        except (ReplayConflictError, ValueError):
            return self._cutoff(receipt, "LINEAGE_OR_REPLAY_INVALID")
        # The signed/hashable receipt is immutable after append.  The durable
        # acknowledgement is retained by the ledger, not injected into it.
        return receipt

    def _replay_key(self, transition: Mapping[str, Any]) -> str:
        origin, authority = transition.get("origin", {}), transition.get("authority", {})
        return sha256_uri({"credential_id": authority.get("credential_id", origin.get("authority_source")),
                           "authority_epoch": authority.get("authority_epoch"),
                           "checkpoint_hash": authority.get("authority_checkpoint_hash"),
                           "nonce": origin.get("nonce")})

    def _failed_invariants(self, transition: Mapping[str, Any], current_time: str | None) -> list[str]:
        failed: list[str] = []
        origin, authority = transition.get("origin", {}), transition.get("authority", {})
        lineage, privacy = transition.get("lineage", {}), transition.get("privacy", {})
        if not all(origin.get(field) for field in ("origin_id", "origin_type", "authority_source", "timestamp_utc", "nonce", "issued_at")):
            failed.append("origin_integrity")
        try:
            issued_at = parse_rfc3339(origin.get("issued_at"))
            now = parse_rfc3339(current_time) if current_time else datetime.now(timezone.utc)
            valid_until = parse_rfc3339(authority.get("valid_until", authority.get("expires_at")))
            if not issued_at <= now < valid_until: failed.append("authority_match")
        except ValueError:
            failed.append("authority_match")
        requested, scope = set(transition.get("action_requested", [])), set(authority.get("authority_scope", []))
        denied = set(authority.get("denied_capabilities", [])) | DEFAULT_DENIED_CAPABILITIES
        if not requested or not requested.issubset(scope) or requested & denied: failed.append("authority_match")
        policy = set(authority.get("scope_policy", []))
        if not policy or not requested.issubset(policy): failed.append("scope_authorization")
        if not lineage.get("parent_hash") or lineage.get("parent_hash") != transition.get("expected_parent_hash"):
            failed.append("lineage_continuity")
        elif lineage.get("parent_hash") != "sha256:genesis":
            parent = self.ledger.get_receipt(lineage["parent_hash"])
            if parent is None or not self.parent_verifier(lineage["parent_hash"], parent):
                failed.append("lineage_continuity")
        if authority.get("consent_required", True) and not transition.get("consent", {}).get("granted"):
            failed.append("consent_validity")
        if privacy.get("private_payload_storage") or privacy.get("reveal_private_content"):
            failed.append("substance_privacy")
        return failed

    @staticmethod
    def _verify_parent_hash(parent_hash: str, parent: Mapping[str, Any]) -> bool:
        """Verify a locally stored parent's canonical receipt hash.

        Production nodes should inject a verifier that additionally resolves the
        trusted gatekeeper key and verifies its signature against a checkpoint.
        """
        candidate = {key: value for key, value in parent.items() if key != "receipt_hash"}
        return parent.get("receipt_hash") == parent_hash and sha256_uri(candidate) == parent_hash

    def _receipt(self, transition: Mapping[str, Any], accepted: bool, failed: list[str]) -> dict[str, Any]:
        origin, lineage = transition.get("origin", {}), transition.get("lineage", {})
        base = {"receipt_id": transition.get("receipt_id") or "sdf-decision-" + sha256_uri(transition)[7:19],
                "origin_id": origin.get("origin_id", "unknown_or_invalid"),
                "action_requested": transition.get("action_requested", []), "action_authorized": accepted,
                "state_changed": False, "parent_hash": lineage.get("parent_hash"),
                "transition_hash": sha256_uri(transition),
                "witness_hash": sha256_uri({"gate": self.gate_name, "failed_invariants": failed}),
                "timestamp_utc": transition.get("timestamp_utc") or origin.get("timestamp_utc") or _utc_now()}
        if accepted:
            return {"receipt_type": "execution", **base, "admissibility_result": "accepted",
                    "admissibility_gate": self.gate_name, "tools_invoked": transition.get("tools_invoked", []),
                    "required_invariants": REQUIRED_INVARIANTS, "failed_invariants": []}
        return {"receipt_type": "refusal", **base, "admissibility_result": "refused",
                "admissibility_gate": self.gate_name, "refusal_reason": "DENIED_AUTHORIZATION",
                "required_invariants": REQUIRED_INVARIANTS, "failed_invariants": failed}

    def _cutoff(self, receipt: dict[str, Any], reason: str) -> dict[str, Any]:
        return {**receipt, "receipt_type": "cutoff", "admissibility_result": "CUTOFF",
                "action_authorized": False, "state_changed": False, "durable_receipt": False,
                "cutoff_reason": reason}


def evaluate_transition(transition: Mapping[str, Any]) -> dict[str, Any]:
    return AdmissibilityDaemon().evaluate(transition)
