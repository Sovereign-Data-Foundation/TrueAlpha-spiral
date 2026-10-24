# The Irreducible State

## Definition

TrueAlphaSpiral defines state as the ordered pair

\[
S_n := (O_n,\Gamma_n)
\]

with:

- \(O_n\): protected operational state.
- \(\Gamma_n\): ordered authenticated lineage.

Neither coordinate is treated as disposable metadata. The pair is the state.

## Equality is not identity

Operational equality alone does not establish state identity:

\[
O_a = O_b
\centernot\implies
S_a=S_b
\]

If the lineages differ,

\[
\Gamma_a\neq\Gamma_b,
\]

then

\[
(O_a,\Gamma_a)\neq(O_b,\Gamma_b).
\]

This matters because future admissibility may depend on the authenticated path by which the present operational configuration was reached.

## Refusal theorem

Let \(x\) be an evaluated proposal that is refused. TAS preserves the protected operational state:

\[
O_{n+1}=O_n.
\]

But the refusal itself becomes authenticated evidence:

\[
\Gamma_{n+1}
=
\operatorname{Extend}(\Gamma_n,r^-_x),
\]

with parent binding

\[
\operatorname{parent}(r^-_x)
=
\operatorname{Tip}(\Gamma_n).
\]

Therefore:

\[
S_{n+1}
eq S_n.
\]

The architectural invariant is:

> **Refusal preserves operational state while advancing constitutive state.**

## Why an unordered set is insufficient

Writing lineage as

\[
\Gamma_{n+1}=\Gamma_n\cup\{r_x\}
\]

is too weak because set union does not encode order, ancestry, or authenticated parenthood.

TAS instead requires an append operation over an ordered lineage structure:

\[
\Gamma_{n+1}=\operatorname{Extend}(\Gamma_n,r_x).
\]

The extension is valid only when the new receipt binds to the authenticated current tip.

## Reconstruction

A stronger formulation makes the operational state reconstructible from well-formed lineage:

\[
L:\mathsf{WF}\to\mathcal O
\]

such that

\[
O=L(\Gamma).
\]

Under this model, \(O\) is not an independently authoritative memory object. It is the operational projection of an authenticated evidentiary trajectory.

## Markov property of the complete state

History dependence does not require an infinite external history variable if the relevant history is already contained in \(\Gamma\).

The complete state can therefore be Markovian even when \(O\) alone is not:

\[
P(S_{n+1}\mid S_n,S_{n-1},\ldots)
=
P(S_{n+1}\mid S_n).
\]

The point is not that history disappears. The point is that authenticated history has been internalized into the present state.
