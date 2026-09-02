"""TAS[0X] agent runtime.

The generator may propose.  It may not authorize, attest, or commit.

TAS[0X] composes the existing TAS admissibility boundary into an agent loop:

    request -> proposal -> external evidence -> Y-knot -> compare-and-commit
                                      |                |
                                      +---- refusal ---+

Every terminal path is witnessable.  A model output never becomes authority
merely because the model emitted it.
"""

from __future__ import annotations

import hashlib
import json
import math
import threading
from dataclasses import dataclass
from typing import Any, Callable, FrozenSet, Mapping, Optional, Protocol

from sdf_evidence_envelope import SDFEvidenceEnvelope
from tas_admissibility import AdmissionReceipt, RefusalReceipt, admit_or_refuse

TAS0X_RECEIPT_DOMAIN = b"TAS-0X-TERMINAL-V1\x00"
TAS0X_AGENT_ID = "TAS[0X]"


class GeneratorPort(Protocol):
    """Probabilistic or deterministic proposal source.  No authority lives here."""

    def __call__(self, request: str, snapshot: "AgentSnapshot") -> Mapping[str, Any]: ...


class EvidencePort(Protocol):
    """Independent attestation source for a normalized proposal."""

    def __call__(
        self,
        proposal: Mapping[str, Any],
        snapshot: "AgentSnapshot",
        binding: "ToolBinding",
    ) -> SDFEvidenceEnvelope: ...


@dataclass(frozen=True)
class AgentSnapshot:
    """Read-only coordinates supplied to the generator and evidence source."""

    state_root: str
    context: str
    genesis_hash: str
    lineage_head: Optional[str]
    sequence: int


@dataclass(frozen=True)
class CommitResult:
    """Result of an atomic compare-and-commit operation.

    ``committed=False`` asserts that this agent transition produced no effect.
    ``committed=True`` requires ``state_root_after`` to be the published root of
    the committed protected state.
    """

    committed: bool
    state_root_after: str
    code: Optional[str] = None


InvariantCheck = Callable[[Mapping[str, Any], AgentSnapshot], bool]
CommitEffect = Callable[[Mapping[str, Any], str], CommitResult]


@dataclass(frozen=True)
class ToolBinding:
    """Externally configured effect binding.

    The proposal selects only ``name``.  It cannot select the authority scope,
    invariant, or commit function attached to that name.
    """

    name: str
    authority_scope: FrozenSet[str]
    invariant: InvariantCheck
    commit: CommitEffect

    def __post_init__(self) -> None:
        if not self.name or not isinstance(self.name, str):
            raise ValueError("tool binding name must be a non-empty string")
        if not self.authority_scope:
            raise ValueError("tool binding authority_scope must not be empty")


@dataclass(frozen=True)
class TAS0XResult:
    """One completed TAS[0X] cycle."""

    status: str
    delta_s: Optional[int]
    proposal: Optional[Mapping[str, Any]]
    state_root_before: str
    state_root_after: Optional[str]
    failed_predicate: Optional[str]
    terminal_hash: str
    sequence: int
    receipt: Mapping[str, Any]


class CommitConflict(RuntimeError):
    """Compare-and-commit proved that this transition did not commit."""

    def __init__(self, code: str, observed_root: str) -> None:
        super().__init__(code)
        self.code = code
        self.observed_root = observed_root


class CommitIndeterminate(RuntimeError):
    """Commit contract could not prove success or failure."""

    def __init__(self, code: str, observed_root: Optional[str] = None) -> None:
        super().__init__(code)
        self.code = code
        self.observed_root = observed_root


def _json_value(value: Any) -> Any:
    """Return a JSON-safe, type-preserving copy or fail closed."""

    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite JSON numbers are forbidden")
        return value
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("proposal object keys must be strings")
        return {str(key): _json_value(item) for key, item in value.items()}
    raise TypeError(f"proposal values must use JSON types, not {type(value).__name__}")


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        _json_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _hex64(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return value == value.lower()


def _terminal_hash(body: Mapping[str, Any]) -> str:
    return hashlib.sha256(TAS0X_RECEIPT_DOMAIN + _canonical_json(body)).hexdigest()


class TAS0XAgent:
    """Single-agent TAS effect mediator.

    Parameters are intentionally split by jurisdiction:

    * ``generator`` proposes JSON only.
    * ``evidence_provider`` attests the exact normalized proposal.
    * ``tools`` binds names to external authority scopes, invariants, and effects.
    * ``trusted_authority_keys`` is supplied independently of the proposal.
    * ``state_reader`` exposes the current protected-state root for CAS checks.
    * ``witness_sink`` receives every terminal receipt, including refusals.

    The agent serializes ``step`` calls with an RLock.  Cross-process atomicity
    remains the responsibility of each tool's compare-and-commit implementation.
    """

    def __init__(
        self,
        *,
        generator: GeneratorPort,
        evidence_provider: EvidencePort,
        tools: Mapping[str, ToolBinding],
        trusted_authority_keys: Mapping[str, str],
        state_reader: Callable[[], str],
        context_reader: Callable[[], str],
        genesis_hash: str,
        lineage_head: Optional[str] = None,
        sequence: int = 0,
        trusted_credential_keys: Mapping[str, tuple[str, str]] | None = None,
        witness_sink: Callable[[Mapping[str, Any]], None] | None = None,
    ) -> None:
        if not _hex64(genesis_hash):
            raise ValueError("genesis_hash must be a lowercase 64-char hex digest")
        if lineage_head is not None and not _hex64(lineage_head):
            raise ValueError("lineage_head must be None or a lowercase hex64 digest")
        if sequence < 0:
            raise ValueError("sequence must be non-negative")

        bindings = dict(tools)
        if set(bindings) != {binding.name for binding in bindings.values()}:
            raise ValueError("tool mapping keys must exactly match ToolBinding.name")

        self._generator = generator
        self._evidence_provider = evidence_provider
        self._tools = bindings
        self._trusted_authority_keys = dict(trusted_authority_keys)
        self._trusted_credential_keys = (
            None if trusted_credential_keys is None else dict(trusted_credential_keys)
        )
        self._state_reader = state_reader
        self._context_reader = context_reader
        self._genesis_hash = genesis_hash
        self._lineage_head = lineage_head
        self._sequence = sequence
        self._seen_nonces: set[str] = set()
        self._witness_sink = witness_sink
        self._witness: list[Mapping[str, Any]] = []
        self._witness_sink_errors: list[Mapping[str, str]] = []
        self._lock = threading.RLock()

    @property
    def lineage_head(self) -> Optional[str]:
        return self._lineage_head

    @property
    def sequence(self) -> int:
        return self._sequence

    @property
    def witness(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(self._witness)

    @property
    def witness_sink_errors(self) -> tuple[Mapping[str, str], ...]:
        """Best-effort sink failures; never allowed to erase a terminal result."""
        return tuple(self._witness_sink_errors)

    def snapshot(self) -> AgentSnapshot:
        state_root = self._state_reader()
        context = self._context_reader()
        if not _hex64(state_root):
            raise ValueError("state_reader must return a lowercase 64-char hex digest")
        if not isinstance(context, str) or not context:
            raise ValueError("context_reader must return a non-empty string")
        return AgentSnapshot(
            state_root=state_root,
            context=context,
            genesis_hash=self._genesis_hash,
            lineage_head=self._lineage_head,
            sequence=self._sequence,
        )

    def step(self, request: str) -> TAS0XResult:
        """Run exactly one proposal/evidence/admission/commit cycle."""

        with self._lock:
            snapshot = self.snapshot()

            try:
                proposal = self._normalize_proposal(self._generator(request, snapshot))
            except Exception as exc:
                return self._local_terminal(
                    status="REFUSED",
                    delta_s=0,
                    snapshot=snapshot,
                    proposal=None,
                    failed_predicate="generator_output",
                    detail_code=type(exc).__name__,
                    state_root_after=snapshot.state_root,
                )

            binding = self._tools.get(proposal["tool"])
            if binding is None:
                return self._local_terminal(
                    status="REFUSED",
                    delta_s=0,
                    snapshot=snapshot,
                    proposal=proposal,
                    failed_predicate="known_tool",
                    detail_code="unknown_tool",
                    state_root_after=snapshot.state_root,
                )

            try:
                envelope = self._evidence_provider(proposal, snapshot, binding)
            except Exception as exc:
                return self._local_terminal(
                    status="REFUSED",
                    delta_s=0,
                    snapshot=snapshot,
                    proposal=proposal,
                    failed_predicate="evidence_available",
                    detail_code=type(exc).__name__,
                    state_root_after=snapshot.state_root,
                )

            lineage_ok = self._lineage_guard(envelope, snapshot)
            invariant_ok = self._safe_tool_invariant(
                binding, proposal["arguments"], snapshot
            )

            def combined_invariant(_proposal: Any, _state_root: str) -> bool:
                return lineage_ok and invariant_ok

            def apply_transition(_proposal: Any, expected_root: str) -> str:
                return self._compare_and_commit(
                    binding, proposal["arguments"], expected_root
                )

            try:
                outcome = admit_or_refuse(
                    proposal=proposal,
                    envelope=envelope,
                    state_root=snapshot.state_root,
                    authority_scope=binding.authority_scope,
                    current_context=snapshot.context,
                    seen_nonces=self._seen_nonces,
                    invariant_check=combined_invariant,
                    apply_transition=apply_transition,
                    trusted_authority_keys=self._trusted_authority_keys,
                    trusted_credential_keys=self._trusted_credential_keys,
                )
            except CommitConflict as exc:
                self._seen_nonces.add(envelope.nonce)
                return self._local_terminal(
                    status="CONFLICT",
                    delta_s=0,
                    snapshot=snapshot,
                    proposal=proposal,
                    failed_predicate="compare_and_commit",
                    detail_code=exc.code,
                    state_root_after=exc.observed_root,
                    evidence_id=envelope.evidence_id,
                    nonce=envelope.nonce,
                )
            except CommitIndeterminate as exc:
                self._seen_nonces.add(envelope.nonce)
                return self._local_terminal(
                    status="INDETERMINATE",
                    delta_s=None,
                    snapshot=snapshot,
                    proposal=proposal,
                    failed_predicate="commit_proof",
                    detail_code=exc.code,
                    state_root_after=exc.observed_root,
                    evidence_id=envelope.evidence_id,
                    nonce=envelope.nonce,
                )
            except Exception as exc:
                self._seen_nonces.add(envelope.nonce)
                return self._local_terminal(
                    status="INDETERMINATE",
                    delta_s=None,
                    snapshot=snapshot,
                    proposal=proposal,
                    failed_predicate="commit_proof",
                    detail_code=type(exc).__name__,
                    state_root_after=self._safe_read_state_root(),
                    evidence_id=envelope.evidence_id,
                    nonce=envelope.nonce,
                )

            if isinstance(outcome, AdmissionReceipt):
                status = "ADMITTED"
                state_root_after: Optional[str] = outcome.state_root_after
                failed_predicate = None
            elif isinstance(outcome, RefusalReceipt):
                status = "REFUSED"
                state_root_after = outcome.state_root
                failed_predicate = outcome.failed_predicate
                if failed_predicate == "invariant_pass":
                    if not lineage_ok and not invariant_ok:
                        failed_predicate = "lineage_and_tool_invariant"
                    elif not lineage_ok:
                        failed_predicate = "lineage_anchor"
                    elif not invariant_ok:
                        failed_predicate = "tool_invariant"
            else:
                return self._local_terminal(
                    status="INDETERMINATE",
                    delta_s=None,
                    snapshot=snapshot,
                    proposal=proposal,
                    failed_predicate="unknown_admission_outcome",
                    detail_code=type(outcome).__name__,
                    state_root_after=self._safe_read_state_root(),
                    evidence_id=envelope.evidence_id,
                    nonce=envelope.nonce,
                )

            body = {
                "agent": TAS0X_AGENT_ID,
                "status": status,
                "delta_s": outcome.delta_s,
                "sequence": snapshot.sequence,
                "proposal": proposal,
                "evidence_id": outcome.evidence_id,
                "verdict_receipt_hash": outcome.verdict.receipt_hash,
                "boundary_lineage_hash": outcome.lineage_evidence_hash,
                "state_root_before": snapshot.state_root,
                "state_root_after": state_root_after,
                "failed_predicate": failed_predicate,
                "parent_terminal_hash": snapshot.lineage_head,
            }
            terminal_hash = self._record_terminal(body)
            receipt = {**body, "terminal_hash": terminal_hash}
            return TAS0XResult(
                status=status,
                delta_s=outcome.delta_s,
                proposal=proposal,
                state_root_before=snapshot.state_root,
                state_root_after=state_root_after,
                failed_predicate=failed_predicate,
                terminal_hash=terminal_hash,
                sequence=snapshot.sequence,
                receipt=receipt,
            )

    def _normalize_proposal(self, proposal: Mapping[str, Any]) -> Mapping[str, Any]:
        normalized = _json_value(proposal)
        if not isinstance(normalized, dict):
            raise TypeError("generator must return a JSON object")
        tool = normalized.get("tool")
        arguments = normalized.get("arguments")
        if not isinstance(tool, str) or not tool:
            raise ValueError("proposal.tool must be a non-empty string")
        if not isinstance(arguments, dict):
            raise TypeError("proposal.arguments must be a JSON object")
        return normalized

    def _lineage_guard(
        self, envelope: SDFEvidenceEnvelope, snapshot: AgentSnapshot
    ) -> bool:
        lineage = envelope.lineage
        if lineage.genesis_hash != snapshot.genesis_hash:
            return False
        if lineage.sequence != snapshot.sequence:
            return False
        if snapshot.sequence == 0:
            return snapshot.lineage_head is None and lineage.parent_hash is None
        return lineage.parent_hash == snapshot.lineage_head

    @staticmethod
    def _safe_tool_invariant(
        binding: ToolBinding,
        arguments: Mapping[str, Any],
        snapshot: AgentSnapshot,
    ) -> bool:
        try:
            return bool(binding.invariant(arguments, snapshot))
        except Exception:
            return False

    def _compare_and_commit(
        self,
        binding: ToolBinding,
        arguments: Mapping[str, Any],
        expected_root: str,
    ) -> str:
        observed_before = self._safe_read_state_root()
        if observed_before is None:
            raise CommitIndeterminate("state_unreadable_before_commit")
        if observed_before != expected_root:
            raise CommitConflict("stale_parent", observed_before)

        try:
            result = binding.commit(arguments, expected_root)
        except CommitConflict:
            raise
        except Exception as exc:
            raise CommitIndeterminate(
                type(exc).__name__, self._safe_read_state_root()
            ) from exc

        if not isinstance(result, CommitResult):
            raise CommitIndeterminate(
                "invalid_commit_result", self._safe_read_state_root()
            )

        observed_after = self._safe_read_state_root()
        if observed_after is None:
            raise CommitIndeterminate("state_unreadable_after_commit")

        if not result.committed:
            if observed_after != observed_before:
                raise CommitIndeterminate("conflict_mutated_state", observed_after)
            raise CommitConflict(result.code or "commit_rejected", observed_after)

        if not _hex64(result.state_root_after):
            raise CommitIndeterminate("invalid_state_root_after", observed_after)
        if observed_after != result.state_root_after:
            raise CommitIndeterminate("commit_root_not_published", observed_after)
        return result.state_root_after

    def _safe_read_state_root(self) -> Optional[str]:
        try:
            root = self._state_reader()
        except Exception:
            return None
        return root if _hex64(root) else None

    def _local_terminal(
        self,
        *,
        status: str,
        delta_s: Optional[int],
        snapshot: AgentSnapshot,
        proposal: Optional[Mapping[str, Any]],
        failed_predicate: str,
        detail_code: str,
        state_root_after: Optional[str],
        evidence_id: Optional[str] = None,
        nonce: Optional[str] = None,
    ) -> TAS0XResult:
        body = {
            "agent": TAS0X_AGENT_ID,
            "status": status,
            "delta_s": delta_s,
            "sequence": snapshot.sequence,
            "proposal": proposal,
            "evidence_id": evidence_id,
            "nonce": nonce,
            "state_root_before": snapshot.state_root,
            "state_root_after": state_root_after,
            "failed_predicate": failed_predicate,
            "detail_code": detail_code,
            "parent_terminal_hash": snapshot.lineage_head,
        }
        terminal_hash = self._record_terminal(body)
        receipt = {**body, "terminal_hash": terminal_hash}
        return TAS0XResult(
            status=status,
            delta_s=delta_s,
            proposal=proposal,
            state_root_before=snapshot.state_root,
            state_root_after=state_root_after,
            failed_predicate=failed_predicate,
            terminal_hash=terminal_hash,
            sequence=snapshot.sequence,
            receipt=receipt,
        )

    def _record_terminal(self, body: Mapping[str, Any]) -> str:
        terminal_hash = _terminal_hash(body)
        record = {**body, "terminal_hash": terminal_hash}
        self._witness.append(record)
        self._lineage_head = terminal_hash
        self._sequence += 1
        if self._witness_sink is not None:
            try:
                self._witness_sink(record)
            except Exception as exc:
                self._witness_sink_errors.append(
                    {"terminal_hash": terminal_hash, "error": type(exc).__name__}
                )
        return terminal_hash
