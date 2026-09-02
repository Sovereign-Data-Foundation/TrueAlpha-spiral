from __future__ import annotations

import hashlib
from dataclasses import dataclass

from cryptography.hazmat.primitives.asymmetric import ec

from sdf_evidence_envelope import build_envelope
from tas0x import AgentSnapshot, CommitResult, TAS0XAgent, ToolBinding


def h(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


GENESIS = h("tas0x-genesis")
AUTHORITY = "test-authority"
CONTEXT = "test-context"


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
        self.root = hashlib.sha256(
            (expected_root + repr(sorted(arguments.items()))).encode()
        ).hexdigest()
        return CommitResult(True, self.root)


def make_harness(*, invariant=lambda _args, _snapshot: True, generator=None):
    key = ec.generate_private_key(ec.SECP256K1())
    state = MemoryState(h("state-0"))

    if generator is None:
        generator = lambda _request, _snapshot: {
            "tool": "set_value",
            "arguments": {"value": 7},
            "reason": "test proposal",
        }

    def evidence_provider(proposal, snapshot: AgentSnapshot, _binding):
        return build_envelope(
            evidence_id=f"evidence-{snapshot.sequence}",
            claim=proposal,
            issuer_authority_id=AUTHORITY,
            issuer_private_key=key,
            context=snapshot.context,
            genesis_hash=snapshot.genesis_hash,
            parent_hash=snapshot.lineage_head,
            sequence=snapshot.sequence,
            issued_at="2026-09-02T12:00:00Z",
            nonce=f"nonce-{snapshot.sequence}",
        )

    binding = ToolBinding(
        name="set_value",
        authority_scope=frozenset({AUTHORITY}),
        invariant=invariant,
        commit=state.commit,
    )

    bootstrap = evidence_provider(
        {"tool": "set_value", "arguments": {}},
        AgentSnapshot(state.root, CONTEXT, GENESIS, None, 0),
        binding,
    )

    agent = TAS0XAgent(
        generator=generator,
        evidence_provider=evidence_provider,
        tools={binding.name: binding},
        trusted_authority_keys={AUTHORITY: bootstrap.issuer.public_key_b64},
        state_reader=state.read,
        context_reader=lambda: CONTEXT,
        genesis_hash=GENESIS,
    )
    return agent, state, key


def test_admission_commits_only_after_all_predicates_pass():
    agent, state, _ = make_harness()
    before = state.root

    result = agent.step("set the value")

    assert result.status == "ADMITTED"
    assert result.delta_s == 1
    assert state.commits == 1
    assert state.root != before
    assert result.state_root_after == state.root
    assert agent.lineage_head == result.terminal_hash
    assert agent.sequence == 1
    assert len(agent.witness) == 1


def test_failed_tool_invariant_refuses_without_commit():
    agent, state, _ = make_harness(invariant=lambda _args, _snapshot: False)
    before = state.root

    result = agent.step("set the value")

    assert result.status == "REFUSED"
    assert result.delta_s == 0
    assert result.failed_predicate == "tool_invariant"
    assert state.commits == 0
    assert state.root == before
    assert len(agent.witness) == 1


def test_generator_cannot_self_authorize_unknown_tool():
    generator = lambda _request, _snapshot: {
        "tool": "root_shell",
        "arguments": {"authority_id": AUTHORITY},
    }
    agent, state, _ = make_harness(generator=generator)

    result = agent.step("do it")

    assert result.status == "REFUSED"
    assert result.delta_s == 0
    assert result.failed_predicate == "known_tool"
    assert state.commits == 0


def test_external_authority_scope_cannot_be_minted_by_proposal():
    key = ec.generate_private_key(ec.SECP256K1())
    state = MemoryState(h("state-authority"))
    evil = "proposal-selected-authority"

    def generator(_request, _snapshot):
        return {
            "tool": "set_value",
            "arguments": {"value": 9},
            "authority_id": evil,
        }

    def evidence_provider(proposal, snapshot, _binding):
        return build_envelope(
            evidence_id="evil-evidence",
            claim=proposal,
            issuer_authority_id=evil,
            issuer_private_key=key,
            context=snapshot.context,
            genesis_hash=snapshot.genesis_hash,
            parent_hash=snapshot.lineage_head,
            sequence=snapshot.sequence,
            issued_at="2026-09-02T12:00:00Z",
            nonce="evil-nonce",
        )

    probe = evidence_provider(
        {"tool": "set_value", "arguments": {}},
        AgentSnapshot(state.root, CONTEXT, GENESIS, None, 0),
        None,
    )
    binding = ToolBinding(
        name="set_value",
        authority_scope=frozenset({AUTHORITY}),
        invariant=lambda _args, _snapshot: True,
        commit=state.commit,
    )
    agent = TAS0XAgent(
        generator=generator,
        evidence_provider=evidence_provider,
        tools={"set_value": binding},
        trusted_authority_keys={evil: probe.issuer.public_key_b64},
        state_reader=state.read,
        context_reader=lambda: CONTEXT,
        genesis_hash=GENESIS,
    )

    result = agent.step("self-authorize")

    assert result.status == "REFUSED"
    assert result.failed_predicate == "scope_covered"
    assert state.commits == 0


def test_lineage_parent_mismatch_refuses_before_effect():
    agent, state, key = make_harness()
    first = agent.step("first")
    assert first.status == "ADMITTED"
    commits_before = state.commits

    def bad_evidence(proposal, snapshot, _binding):
        return build_envelope(
            evidence_id="bad-lineage",
            claim=proposal,
            issuer_authority_id=AUTHORITY,
            issuer_private_key=key,
            context=snapshot.context,
            genesis_hash=snapshot.genesis_hash,
            parent_hash=h("alternate-history"),
            sequence=snapshot.sequence,
            issued_at="2026-09-02T12:01:00Z",
            nonce="bad-lineage-nonce",
        )

    agent._evidence_provider = bad_evidence
    result = agent.step("second")

    assert result.status == "REFUSED"
    assert result.delta_s == 0
    assert result.failed_predicate == "lineage_anchor"
    assert state.commits == commits_before


def test_stale_snapshot_never_commits_agent_effect():
    agent, state, _ = make_harness()
    original_provider = agent._evidence_provider

    def racing_provider(proposal, snapshot, binding):
        envelope = original_provider(proposal, snapshot, binding)
        state.root = h("concurrent-writer")
        return envelope

    agent._evidence_provider = racing_provider
    result = agent.step("race")

    assert result.status == "CONFLICT"
    assert result.delta_s == 0
    assert result.failed_predicate == "compare_and_commit"
    assert state.commits == 0
    assert result.state_root_after == state.root


def test_unprovable_commit_halts_as_indeterminate_not_success():
    agent, state, _ = make_harness()

    def ambiguous_commit(_arguments, _expected_root):
        raise RuntimeError("transport vanished")

    old = agent._tools["set_value"]
    agent._tools["set_value"] = ToolBinding(
        name=old.name,
        authority_scope=old.authority_scope,
        invariant=old.invariant,
        commit=ambiguous_commit,
    )

    result = agent.step("ambiguous")

    assert result.status == "INDETERMINATE"
    assert result.delta_s is None
    assert result.failed_predicate == "commit_proof"
    assert state.commits == 0
    assert len(agent.witness) == 1


def test_refusal_advances_evidentiary_lineage_without_state_change():
    agent, state, _ = make_harness(invariant=lambda _args, _snapshot: False)
    before = state.root

    r1 = agent.step("refuse one")
    r2 = agent.step("refuse two")

    assert r1.status == r2.status == "REFUSED"
    assert state.root == before
    assert r2.receipt["parent_terminal_hash"] == r1.terminal_hash
    assert r1.sequence == 0
    assert r2.sequence == 1
    assert agent.sequence == 2


def test_witness_sink_failure_does_not_erase_terminal_result():
    def broken_sink(_record):
        raise OSError("ledger unavailable")

    agent, state, _ = make_harness()
    agent._witness_sink = broken_sink

    result = agent.step("commit despite witness mirror outage")

    assert result.status == "ADMITTED"
    assert result.delta_s == 1
    assert state.commits == 1
    assert agent.lineage_head == result.terminal_hash
    assert agent.sequence == 1
    assert len(agent.witness) == 1
    assert agent.witness_sink_errors == (
        {"terminal_hash": result.terminal_hash, "error": "OSError"},
    )
