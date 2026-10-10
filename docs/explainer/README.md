# TrueAlphaSpiral Explainer

**TrueAlphaSpiral (TAS)** is a deterministic execution architecture for consequential computation.

> **Capability does not imply authority. Proof must precede consequence.**

This repository formalizes the architecture around one lineage-bearing datum already present in the implementation: **TAS_DNA / `TASGene`**.

## Migration purpose

This repository is the migration surface for bringing the last 18 months of **Perspective Intelligence** \((\pi)\) / TAS_DNA work into one place.

Here, \(\pi\) names **Perspective Intelligence**: the invariant relation between deterministic anchoring and probabilistic perspective within one coherent architecture.

Conceptually:

\[
\pi
=
\frac{\text{probabilistic circumference}}
{\text{deterministic diameter}}
\]

The deterministic diameter anchors provenance, lineage, admissibility, receipts, and recovery anchors. The probabilistic circumference carries prediction, likelihood, inference, language, context, and variation.

Its job is to re-present TAS_DNA as a complete state-space architecture rather than as isolated notes, implementation fragments, or one-off explanations.

The materials are organized so the same system can be read across four linked layers:

- `docs/` explains the conceptual and architectural relations,
- `formal/` states the machine-level closure and invariants,
- `spec/` fixes the shared terminology,
- `diagrams/` gives the compact structural view.

## One datum

The canonical transition datum is

\[
G_i=(\text{origin},\text{context},\text{authority},\text{operation},\text{parent},\text{invariants},\text{decision},\text{receipt}).
\]

The implementation represents that datum as `TASGene`.

Admission and refusal do not require different grammars. They are different decision values carried by the same datum.

## The irreducible full state remains intact

At the architectural level, TAS may be expressed as

\[
S_n=(O_n,\Gamma_n),
\]

where:

- \(O_n\) is the authorized operational state,
- \(\Gamma_n\) is the ordered authenticated TAS_DNA trajectory.

TAS_DNA gives \(\Gamma\) its concrete unit:

\[
\Gamma_n=(G_1,G_2,\ldots,G_n).
\]

The implementation's admission-only `state_sequence()` is therefore not a rival definition of \(S\). It is an operational projection over the same lineage.

Define the admitted projection

\[
\Pi_A(\Gamma_n)=\text{ordered subsequence of genes with }d_i=\mathrm{ADMITTED}.
\]

Then operational state is determined from admitted history:

\[
O_n=L(\Pi_A(\Gamma_n)),
\]

while the full state remains

\[
S_n=(O_n,\Gamma_n).
\]

## Admission and refusal

For admission:

\[
G_i.d=\mathrm{ADMITTED}
\Rightarrow
\Gamma_{n+1}=\Gamma_n\Vert G_i
\land
\Pi_A(\Gamma_{n+1})=\Pi_A(\Gamma_n)\Vert G_i.
\]

Operational state may therefore advance:

\[
O_{n+1}=F(O_n,G_i).
\]

For refusal:

\[
G_i.d=\mathrm{REFUSED}
\Rightarrow
\Gamma_{n+1}=\Gamma_n\Vert G_i
\land
\Pi_A(\Gamma_{n+1})=\Pi_A(\Gamma_n).
\]

So:

\[
O_{n+1}=O_n
\]

while

\[
S_{n+1}\neq S_n
\]

because the authenticated lineage advanced.

That is the relationship, not a demotion of either model:

> **The full state advances with authenticated history; the admitted operational projection advances only on admission.**

## Implementation correspondence

The current upstream implementation exposes the same distinction through `WakeChain`:

- `evidence_timeline()` retains Genesis, admissions, and refusals,
- `state_sequence()` retains Genesis and admitted links only.

Merged PR `TrueAlpha-spiral/TrueAlpha-spiral#364` adds executable coverage showing that a refusal extends the evidence timeline, does not advance the admission-only state sequence, preserves recovery at the prior admitted checkpoint, routes runtime null-collapse through refusal, and removes wall-clock variance from refusal receipt IDs when the bounded refusal payload is otherwise fixed.

## Architecture at a glance

```text
                 TAS_DNA gene G_i
                       |
              +--------+--------+
              |                 |
              v                 v
      authenticated lineage   admitted projection
            Gamma             Pi_A(Gamma)
              |                 |
              |                 v
              |          operational state O
              |                 |
              +--------+--------+
                       |
                       v
                 full state S
                  S = (O,Gamma)
```

## Recursive architectural context

[Recursive Contextualization v2.0](docs/the_tas_recursive_contextualization.md) connects Process Science, Algorithmic Dendrology, Cursive Computation, and mechanical enforcement. It clarifies admission versus commitment, refusal conservation, recursive composition, and the assumptions behind the guarantees.

## Reading order

1. [TAS_DNA — One Datum, One State Relation](docs/tas-dna.md)
2. [The Irreducible State](docs/irreducible-state.md)
3. [Foundational Axioms](docs/foundational-axioms.md)
4. [Cursive Computation](docs/cursive-computation.md)
5. [Admissibility](docs/admissibility.md)
6. [Canonical Vertical Slice](docs/canonical-vertical-slice.md)
7. [Refusal Semantics](docs/refusal-semantics.md)
8. [Constitutional Meta-Layer](docs/constitutional-meta-layer.md)
9. [Formal State Machine](formal/state-machine.md)
10. [Terminology](spec/terminology.md)

Taken together, these documents are the repository's unified re-presentation of TAS_DNA in its full state space: one datum, one authenticated lineage, one admitted operational projection, and one irreducible state relation.

## Briefs

- [AI Assurance Brief — September 21–28, 2026](docs/ai-assurance-brief-2026-09-21-28.md)

## Status

This is an explainer and formalization surface. Its job is to preserve the architecture's layers and make their relationship explicit without silently rewriting one level into another.
