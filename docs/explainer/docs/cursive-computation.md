# Cursive Computation

Cursive computation is the extension-only processing of lineage-bearing TAS_DNA genes.

The canonical datum is

\[
G_i=(o_i,c_i,a_i,x_i,p_i,\Phi_i,d_i,r_i).
\]

Each represented decision is appended to the ordered computational chronology. The distinction between admission and refusal is carried by the decision field, not by changing the data grammar.

## The cursive stroke

Let \(\mathcal G_n\) be the ordered gene chronology.

A represented decision extends it as

\[
\mathcal G_{n+1}=\mathcal G_n\Vert G_i.
\]

Parent binding preserves ancestry:

\[
p_i=\operatorname{Tip}(\mathcal G_n).
\]

The append is the cursive stroke: the next datum is joined to the prior lineage rather than replacing it.

## Admission stroke

For

\[
d_i=\mathrm{ADMITTED},
\]

the datum is retained in evidence and advances the authorized state sequence:

\[
\mathcal E_{n+1}=\mathcal E_n\Vert G_i,
\]

\[
S_{k+1}=F(S_k,G_i).
\]

## Refusal stroke

For

\[
d_i=\mathrm{REFUSED},
\]

the same datum grammar is retained in evidence while authorized state remains stationary:

\[
\mathcal E_{n+1}=\mathcal E_n\Vert G_i,
\]

\[
S_{k+1}=S_k.
\]

The refusal is therefore not absence of computation. It is an authenticated negative decision that remains in the process chronology without becoming the next authorized state.

## One chronology, two views

The upstream implementation exposes this directly:

- `WakeChain.evidence_timeline()` retains admissions and refusals.
- `WakeChain.state_sequence()` retains Genesis and admitted links only.

These are projections over the same lineage-bearing computational events, not competing definitions of state.

## Rebase is not rewrite

A stale candidate derived from an earlier authorized head cannot silently replace its parent claim with the current head. It must be re-derived against the new parent while preserving evidence of the prior attempt.

If candidate \(G_b\) was derived from head \(H_0\), but authorized state has advanced to \(H_1\), then a valid successor is a new datum:

\[
G'_b=\operatorname{Rebase}(G_b,H_1).
\]

The stale event is not erased from evidence.

## Cursive identity

The essential rule is:

> **Extension changes the record; admission changes authorized state.**

Cursive computation therefore preserves trajectory without requiring every recorded event to become consequential state.
