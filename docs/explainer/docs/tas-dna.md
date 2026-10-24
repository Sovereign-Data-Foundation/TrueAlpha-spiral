# TAS_DNA — One Datum, One State Relation

TAS_DNA is the canonical lineage-bearing transition datum.

The current implementation represents it as

\[
G_i=(o_i,c_i,a_i,x_i,p_i,\Phi_i,d_i,r_i),
\]

with fields for origin, context, authority, operation, parent, invariants, decision, and receipt.

The purpose of formalizing TAS_DNA is not to replace any existing state model. It is to connect them precisely.

## 1. TAS_DNA is the unit of lineage

Let

\[
\Gamma_n=(G_1,G_2,\ldots,G_n)
\]

be the ordered authenticated TAS_DNA trajectory.

Each represented admission or refusal extends that lineage:

\[
\Gamma_{n+1}=\Gamma_n\Vert G_i.
\]

Admission and refusal therefore share the same constitutional data grammar.

## 2. The full state

The architectural state remains

\[
S_n=(O_n,\Gamma_n),
\]

where \(O_n\) is authorized operational state and \(\Gamma_n\) is authenticated lineage.

Nothing in TAS_DNA replaces this pair. TAS_DNA supplies the concrete datum from which \(\Gamma\) is built.

## 3. The admitted projection

Define

\[
\Pi_A(\Gamma_n)
\]

as the ordered subsequence of TAS_DNA genes whose decision is `ADMITTED`.

The implementation's `WakeChain.state_sequence()` corresponds to this admitted projection, while `WakeChain.evidence_timeline()` corresponds to the broader chronology that contains admissions and refusals.

Operational state can then be written as a deterministic reconstruction from admitted history:

\[
O_n=L(\Pi_A(\Gamma_n)).
\]

This makes the relationship explicit:

\[
\boxed{
S_n=\bigl(L(\Pi_A(\Gamma_n)),\Gamma_n\bigr)
}
\]

TAS_DNA is therefore the datum that binds operational state and authenticated history into one formal picture.

## 4. Admission

For admitted gene \(G_i\):

\[
d_i=\mathrm{ADMITTED}.
\]

Then

\[
\Gamma_{n+1}=\Gamma_n\Vert G_i
\]

and

\[
\Pi_A(\Gamma_{n+1})=\Pi_A(\Gamma_n)\Vert G_i.
\]

So the authorized operational projection advances:

\[
O_{n+1}=F(O_n,G_i).
\]

The full state advances because both its lineage and operational coordinates may change.

## 5. Refusal

For refused gene \(G_i\):

\[
d_i=\mathrm{REFUSED}.
\]

Then

\[
\Gamma_{n+1}=\Gamma_n\Vert G_i
\]

but

\[
\Pi_A(\Gamma_{n+1})=\Pi_A(\Gamma_n).
\]

Therefore:

\[
O_{n+1}=O_n
\]

while

\[
S_{n+1}=(O_n,\Gamma_n\Vert G_i)\neq(O_n,\Gamma_n)=S_n.
\]

This gives the exact relationship between the two statements that otherwise look contradictory:

- **the implementation's admitted state sequence does not advance on refusal**, and
- **the full constitutive state does advance because authenticated lineage advances**.

Both remain intact.

## 6. Recovery

Let

\[
\operatorname{Tip}_A(\Gamma_n)=\operatorname{Tip}(\Pi_A(\Gamma_n))
\]

be the latest admitted gene.

For refusal, recovery remains anchored to that admitted tip:

\[
\operatorname{RecoveryAnchor}(G_i)=\operatorname{Tip}_A(\Gamma_n).
\]

The refused gene remains in \(\Gamma\) without becoming the authorized recovery checkpoint.

## 7. Self-similarity

The TAS_DNA claim is preserved at both levels:

> **The same constitutional datum carries origin, authority, invariants, decision, and receipt through both successful and refused transitions.**

The admitted projection decides what may become consequential operational state. The full lineage records what actually occurred at the execution boundary.

## 8. Formal closure

The minimal closure is:

\[
\boxed{
\Gamma_{n+1}=\Gamma_n\Vert G_i
}
\]

with

\[
\boxed{
O_{n+1}=
\begin{cases}
F(O_n,G_i), & d_i=\mathrm{ADMITTED},\\[4pt]
O_n, & d_i=\mathrm{REFUSED}.
\end{cases}}
\]

and therefore

\[
\boxed{
S_{n+1}=(O_{n+1},\Gamma_{n+1}).
}
\]

One datum. One lineage. One irreducible state relation.

## Source correspondence

This formalization aligns:

- `core/gene.py` — `TASGene` as the canonical minimal transition unit,
- `core/wakechain.py` — evidence timeline and admission-only state sequence,
- `docs/specs/intelligent_self_similar_design.md` — the two simultaneous histories and TAS_DNA gene,
- merged PR `TrueAlpha-spiral/TrueAlpha-spiral#364` — executable refusal-path behavior.
