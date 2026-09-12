from __future__ import annotations

import hashlib
from dataclasses import dataclass

import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from sdf_evidence_envelope import build_envelope
from tas0x import (
    AgentSnapshot,
    CommitResult,
    EvidenceBinding,
    RuntimeHalted,
    TAS0XAgent,
    ToolBinding,
)


def h(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


GENESIS = h("tas0x-jurisdiction-genesis")
AUTHORITY = "jurisdiction-authority"
CONTEXT = "jurisdiction-context"


@dataclass
class MemoryState:
    root: str
    commits: int = 0

    def read(self) -> str:
        return self.root

    def commit(self, arguments, expected_root: str) -> CommitResult:
        if self.root != expected_root:
            return CommitResult(False, self.root, "stale_parent")
        self.commits += 1
        self.root = h(expected_root + repr(sorted(arguments.items())))
        return CommitResult(True, self.root)


def make_agent(*, evidence_provider=None, invariant=None, commit=None, generator=None):
    key = ec.generate_private_key(ec.SECP256K1())
    state = MemoryState(h("jurisdiction-state-0"))

    if generator is None:
        generator = lambda _request, _snapshot: {
            "tool": "set_value",
            "arguments": {"value": 7},
        }

    if invariant is None:
        invariant = lambda _arguments, _snapshot: True

    if commit is None:
        commit = state.commit

    binding = ToolBinding(
        name="set_value",
        authority_scope=frozenset({AUTHORITY}),
        invariant=invariant,
        commit=commit,
    )

    def normal_evidence(proposal, snapshot: AgentSnapshot, _binding):
        return build_envelope(
            evidence_id=f"evidence-{snapshot.sequence}",
            claim=proposal,
            issuer_authority_id=AUTHORITY,
            issuer_private_key=key,
            context=snapshot.context,
            genesis_hash=snapshot.genesis_hash,
            parent_hash=snapshot.lineage_head,
            sequence=snapshot.sequence,
            issued_at="2026-09-03T14:00:00Z",
            nonce=f"nonce-{snapshot.sequence}",
        )

    provider = evidence_provider or normal_evidence
    bootstrap = normal_evidence(
        {"tool": "set_value", "arguments": {}},
        AgentSnapshot(state.root, CONTEXT, GENESIS, None, 0),
        EvidenceBinding("set_value", frozenset({AUTHORITY})),
    )

    agent = TAS0XAgent(
        generator=generator,
        evidence_provider=provider,
        tools={"set_value": binding},
        trusted_authority_keys={AUTHORITY: bootstrap.issuer.public_key_b64},
        state_reader=state.read,
        context_reader=lambda: CONTEXT,
        genesis_hash=GENESIS,
    )
    return agent, state, key, normal_evidence


def test_evidence_provider_receives_metadata_without_effect_capability():
    observed = {}

    def provider(proposal, snapshot, binding):
        observed["binding"] = binding
        assert isinstance(binding, EvidenceBinding)
        assert binding.name == "set_value"
        assert binding.authority_scope == frozenset({AUTHORITY})
        assert not hasattr(binding, "commit")
        assert not hasattr(binding, "invariant")
        return normal(proposal, snapshot, binding)

    agent, state, key, normal = make_agent()
    agent._evidence_provider = provider

    result = agent.step("commit")

    assert result.status == "ADMITTED"
    assert state.commits == 1
    assert isinstance(observed["binding"], EvidenceBinding)


def test_evidence_provider_cannot_rewrite_the_sealed_proposal():
    agent, state, key, normal = make_agent()

    def mutating_provider(proposal, snapshot, binding):
        proposal["arguments"]["value"] = 99
        return normal(proposal, snapshot, binding)

    agent._evidence_provider = mutating_provider
    before = state.root

    result = agent.step("mutate provider input")

    assert result.status == "REFUSED"
    assert result.delta_s == 0
    assert result.failed_predicate == "claim_matches_proposal"
    assert result.proposal["arguments"]["value"] == 7
    assert state.root == before
    assert state.commits == 0


@pytest.mark.parametrize("malformed", ["false", 1, {"truthy": True}, object()])
def test_invariant_requires_literal_boolean_true(malformed):
    agent, state, _key, _normal = make_agent(
        invariant=lambda _arguments, _snapshot: malformed
    )
    before = state.root

    result = agent.step("malformed invariant")

    assert result.status == "REFUSED"
    assert result.delta_s == 0
    assert result.failed_predicate == "tool_invariant"
    assert state.root == before
    assert state.commits == 0


def test_indeterminate_latch_is_set_before_reentrant_witness_callback():
    generator_calls = {"count": 0}

    def generator(_request, _snapshot):
        generator_calls["count"] += 1
        return {"tool": "set_value", "arguments": {"value": 7}}

    def ambiguous_commit(_arguments, _expected_root):
        raise RuntimeError("transport vanished")

    agent, state, _key, _normal = make_agent(
        generator=generator,
        commit=ambiguous_commit,
    )

    reentry = []

    def reentrant_sink(_record):
        try:
            agent.step("reentrant effect")
        except RuntimeHalted:
            reentry.append("halted")
        else:
            reentry.append("executed")

    agent._witness_sink = reentrant_sink

    result = agent.step("ambiguous effect")

    assert result.status == "INDETERMINATE"
    assert result.delta_s is None
    assert agent.halted is True
    assert reentry == ["halted"]
    assert generator_calls["count"] == 1
    assert state.commits == 0
    assert len(agent.witness) == 1
