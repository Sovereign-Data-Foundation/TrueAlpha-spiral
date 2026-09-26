"""Regression coverage for authenticated TASGene parent binding."""

from core.gene import TASGene
from core.wakechain import LinkKind, WakeChain


def _admitted(*, parent: str | None) -> TASGene:
    return TASGene.admit(
        origin="unit-test",
        context="test-context",
        authority="HumanAPIKey:test",
        operation="test-op",
        parent=parent,
        invariants=("P0",),
        receipt={"receipt_id": "admit", "admissible": True},
    )


def test_stale_gene_parent_is_refused_without_advancing_operational_state():
    chain = WakeChain.start(author="test")
    admitted = chain.append(_admitted(parent=None))
    state_before = chain.state_sequence()

    refusal = chain.append(_admitted(parent=None))

    assert refusal.kind == LinkKind.REFUSAL
    assert refusal.parent_hash == admitted.link_hash
    assert refusal.metadata["receipt"]["code"] == "STALE_PARENT"
    assert refusal.metadata["receipt"]["claimed_parent"] is None
    assert refusal.metadata["receipt"]["expected_parent"] == admitted.gene_id
    assert chain.state_sequence() == state_before
    assert chain.head == refusal
    assert chain.verify_integrity()
