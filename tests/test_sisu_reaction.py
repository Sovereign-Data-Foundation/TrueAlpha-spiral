import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "formal" / "python"))

from sisu_reaction import (  # noqa: E402
    ArtifactFinancialState, AssetBuckets, AdmissionGateState as G, DisputeState,
    FinancialAction as A, FinancialState, OperationalState, SystemState,
    eval_admission_gate_multisig, run_actions, system_step, total_value,
)


def _fs():
    return FinancialState((ArtifactFinancialState(1, balances=AssetBuckets(10, 5)),
                           ArtifactFinancialState(2, balances=AssetBuckets(3, 0))), 7)


def test_multisig_quorum():
    f = lambda ap, th=2, **k: eval_admission_gate_multisig(
        k.get("e", True), True, False, [1, 2, 3], ap, th)
    assert f([1, 2]) is G.VERIFIED
    assert f([1, 1, 9]) is G.INDETERMINATE
    assert f([1, 2], th=0) is G.INDETERMINATE
    assert f([1, 2], e=False) is G.UNVERIFIED


def test_value_preserved_by_conservative_sequence():
    seq = [A("triggerDispute", 1), A("resolveForfeited", 1), A("resolveExonerated", 2)]
    out = run_actions(seq, _fs())
    assert total_value(out) == total_value(_fs())
    assert out.treasury == 12

def test_forfeit_moves_escrow_to_treasury():
    out = run_actions([A("triggerDispute", 1), A("resolveForfeited", 1)], _fs())
    assert out.treasury == 12 and out.artifacts[0].dispute is DisputeState.FORFEITED


def test_royalty_mints_and_fail_closed():
    s = SystemState(OperationalState(4, (1,)), _fs())
    n = system_step(False, A("accrueRoyalty", 2, 9), s)
    assert n.op_state == s.op_state and total_value(n.fin_state) == total_value(s.fin_state) + 9
    assert system_step(True, A("triggerDispute", 1), s).op_state.execution_count == 5
