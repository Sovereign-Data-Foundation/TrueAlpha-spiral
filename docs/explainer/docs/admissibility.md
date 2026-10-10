# Admissibility

Admissibility is the deterministic boundary between proposal and consequence.

## Predicate

A compact TAS formulation is:

\[
\operatorname{Adm}(e)
=
\operatorname{Auth}(e)
\wedge
\operatorname{Authority}(e)
\wedge
\operatorname{Scope}(e)
\wedge
\operatorname{Invariant}(e)
\wedge
\operatorname{Fresh}(e).
\]

A candidate transition is consequentially admitted only if every required predicate evaluates true.

## Proposal is not permission

A model, agent, process, or user-facing system may construct a candidate effect. That candidate remains in proposal space until the admissibility boundary verifies it against the current authenticated state.

\[
\text{Proposal} \neq \text{Authority}
\]

and

\[
\text{Capability} \neq \text{Permission}.
\]

## Recompute, do not trust

The verifier should recompute predicates from authenticated evidence rather than accept self-asserted claims from the proposer.

For example, a candidate that claims a parent head, scope, or policy version is admissible only if those claims agree with independently resolved current state.

## Operational consequence

Operational mutation is narrower than total state advancement:

\[
\Delta O\neq0
\iff
\operatorname{Adm}(S,x)=1
\]

for an effectful proposal.

A refusal may still advance lineage even though no protected operational mutation occurs.

## Complete mediation

The admissibility gate is meaningful only if all consequential effect paths cross it.

\[
\forall e\in E,
\neg\mathbb A(e)
\Rightarrow
\neg\mathbb C(e).
\]

Any unmediated side channel that can mutate protected state without satisfying the gate violates the architecture.

## Freshness and stale parents

A candidate derived from stale state is not silently upgraded to the current state. Parent identity must match the authenticated head, or the candidate is refused and must be re-derived.

This prevents a valid proof about an old state from being reused as if it were a valid proof about the present state.

## Witnessing

Some TAS formulations separate geometric or structural validity from witness resolution. In that form a crossing condition may require both:

\[
Y(x)=1
\quad\land\quad
W(x)=1.
\]

The exact witness mechanism is implementation-specific, but the architectural rule remains the same: consequence occurs only after all required proof conditions resolve successfully.
