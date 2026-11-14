"""Python bindings mirroring formal/lean/SISU_Reaction.lean (fail-closed gate,
multi-sig quorum, financial state machine, value accounting)."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Iterable, List, Tuple


class AdmissionGateState(Enum):
    VERIFIED = "VERIFIED"
    INVALID = "INVALID"
    UNVERIFIED = "UNVERIFIED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    INDETERMINATE = "INDETERMINATE"


class DisputeState(Enum):
    CLEAR = "CLEAR"
    DISPUTED = "DISPUTED"
    EXONERATED = "EXONERATED"
    FORFEITED = "FORFEITED"


@dataclass(frozen=True)
class AssetBuckets:
    liquid: int = 0
    escrow: int = 0


@dataclass(frozen=True)
class ArtifactFinancialState:
    id: int
    dispute: DisputeState = DisputeState.CLEAR
    basis_points: int = 0
    balances: AssetBuckets = field(default_factory=AssetBuckets)


@dataclass(frozen=True)
class FinancialState:
    artifacts: Tuple[ArtifactFinancialState, ...] = ()
    treasury: int = 0


@dataclass(frozen=True)
class OperationalState:
    execution_count: int = 0
    active_lineage: Tuple[int, ...] = ()


@dataclass(frozen=True)
class SystemState:
    op_state: OperationalState
    fin_state: FinancialState


@dataclass(frozen=True)
class FinancialAction:
    kind: str  # triggerDispute | resolveExonerated | resolveForfeited | accrueRoyalty
    artifact_id: int
    amount: int = 0

    _KINDS = ("triggerDispute", "resolveExonerated", "resolveForfeited", "accrueRoyalty")

    def __post_init__(self) -> None:
        if self.kind not in self._KINDS:
            raise ValueError(f"unknown action kind: {self.kind}")
        if self.amount < 0 or self.artifact_id < 0:
            raise ValueError("ids and amounts must be non-negative")

    @property
    def is_conservative(self) -> bool:
        return self.kind != "accrueRoyalty"


def eval_admission_gate(has_evidence: bool, smt_valid: bool, is_revoked: bool) -> AdmissionGateState:
    if not has_evidence:
        return AdmissionGateState.UNVERIFIED
    if not smt_valid:
        return AdmissionGateState.INVALID
    if is_revoked:
        return AdmissionGateState.REVOKED
    return AdmissionGateState.VERIFIED


def quorum_count(authorized: Iterable[int], approvals: Iterable[int]) -> int:
    """Count over the authorized list so duplicate approvals cannot inflate quorum."""
    approved = set(approvals)
    return sum(1 for s in authorized if s in approved)


def eval_admission_gate_multisig(
    has_evidence: bool,
    smt_valid: bool,
    is_revoked: bool,
    authorized: List[int],
    approvals: List[int],
    threshold: int,
) -> AdmissionGateState:
    base = eval_admission_gate(has_evidence, smt_valid, is_revoked)
    if base is not AdmissionGateState.VERIFIED:
        return base
    if 0 < threshold <= quorum_count(authorized, approvals):
        return AdmissionGateState.VERIFIED
    return AdmissionGateState.INDETERMINATE


def transition_financial_state(action: FinancialAction, fs: FinancialState) -> FinancialState:
    arts = fs.artifacts
    aid = action.artifact_id
    if action.kind == "triggerDispute":
        return replace(fs, artifacts=tuple(
            replace(a, dispute=DisputeState.DISPUTED)
            if a.id == aid and a.dispute is DisputeState.CLEAR else a for a in arts))
    if action.kind == "resolveExonerated":
        return replace(fs, artifacts=tuple(
            replace(a, dispute=DisputeState.EXONERATED,
                    balances=AssetBuckets(a.balances.liquid + a.balances.escrow, 0))
            if a.id == aid and a.dispute is DisputeState.DISPUTED else a for a in arts))
    if action.kind == "resolveForfeited":
        hit = lambda a: a.id == aid and a.dispute is DisputeState.DISPUTED  # noqa: E731
        slashed = sum(a.balances.escrow for a in arts if hit(a))
        return FinancialState(
            artifacts=tuple(
                replace(a, dispute=DisputeState.FORFEITED,
                        balances=replace(a.balances, escrow=0)) if hit(a) else a
                for a in arts),
            treasury=fs.treasury + slashed)
    out = []
    for a in arts:
        if a.id == aid:
            if a.dispute is DisputeState.DISPUTED:
                a = replace(a, balances=replace(a.balances, escrow=a.balances.escrow + action.amount))
            else:
                a = replace(a, balances=replace(a.balances, liquid=a.balances.liquid + action.amount))
        out.append(a)
    return replace(fs, artifacts=tuple(out))


def total_value(fs: FinancialState) -> int:
    return sum(a.balances.liquid + a.balances.escrow for a in fs.artifacts) + fs.treasury


def run_actions(actions: Iterable[FinancialAction], fs: FinancialState) -> FinancialState:
    for a in actions:
        fs = transition_financial_state(a, fs)
    return fs


def system_step(gate_verified: bool, action: FinancialAction, sys: SystemState) -> SystemState:
    """Fail-closed: an unverified gate freezes operational state; financial state still updates."""
    op = sys.op_state if not gate_verified else replace(
        sys.op_state, execution_count=sys.op_state.execution_count + 1)
    return SystemState(op_state=op, fin_state=transition_financial_state(action, sys.fin_state))
