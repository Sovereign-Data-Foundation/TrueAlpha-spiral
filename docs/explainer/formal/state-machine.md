# Formal State Machine

This document preserves both the architectural full-state model and the implementation's admission-only state sequence by relating them through TAS_DNA.

## 1. Canonical transition datum

Let

\[
G_i=(o_i,c_i,a_i,x_i,p_i,\Phi_i,d_i,r_i)
\]

with

\[
d_i\in\{\mathrm{ADMITTED},\mathrm{REFUSED},\mathrm{PENDING}\}.
\]

`TASGene` is the current implementation of this TAS_DNA datum.

## 2. Authenticated lineage

Let

\[
\Gamma_n=(G_1,G_2,\ldots,G_n)
\]

be the ordered authenticated TAS_DNA trajectory.

Every successfully represented admission or refusal extends lineage:

\[
\Gamma_{n+1}=\Gamma_n\Vert G_i.
\]

## 3. Admitted projection

Define

\[
\Pi_A(\Gamma_n)
\]

as the ordered subsequence of genes satisfying

\[
d_i=\mathrm{ADMITTED}.
\]

The current implementation's `WakeChain.state_sequence()` corresponds to this admitted projection.

The broader `WakeChain.evidence_timeline()` corresponds to the chronology containing admissions and refusals.

## 4. Operational reconstruction

Let

\[
L:\Pi_A(\Gamma)\to\mathcal O
\]

reconstruct authorized operational state from admitted history.

Then

\[
O_n=L(\Pi_A(\Gamma_n)).
\]

This allows the implementation's admission-only progression and the architectural full state to coexist without contradiction.

## 5. Irreducible full state

Define

\[
S_n=(O_n,\Gamma_n).
\]

Substituting the operational reconstruction gives

\[
\boxed{
S_n=\bigl(L(\Pi_A(\Gamma_n)),\Gamma_n\bigr).
}
\]

This is the formal bridge supplied by TAS_DNA.

## 6. Admission

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

Therefore operational state advances according to

\[
O_{n+1}=F(O_n,G_i),
\]

and

\[
S_{n+1}=(O_{n+1},\Gamma_{n+1}).
\]

## 7. Refusal

For refused gene \(G_i\):

\[
d_i=\mathrm{REFUSED}.
\]

Lineage still advances:

\[
\Gamma_{n+1}=\Gamma_n\Vert G_i.
\]

But the admitted projection does not:

\[
\Pi_A(\Gamma_{n+1})=\Pi_A(\Gamma_n).
\]

Therefore:

\[
O_{n+1}=O_n.
\]

Yet the irreducible full state changes:

\[
S_{n+1}=(O_n,\Gamma_n\Vert G_i)\neq(O_n,\Gamma_n)=S_n.
\]

Thus both statements are simultaneously true:

\[
\boxed{\text{refusal does not advance admitted operational state}}
\]

and

\[
\boxed{\text{refusal does advance full constitutive state}}.
\]

## 8. Admissibility

Let

\[
\operatorname{Adm}(S_n,x_i)\in\{0,1\}
\]

be the deterministic admission predicate.

A representative factorization is

\[
\operatorname{Adm}(S_n,x_i)
=
\operatorname{Auth}(x_i)
\wedge
\operatorname{Authority}(x_i)
\wedge
\operatorname{Scope}(x_i)
\wedge
\operatorname{Invariant}(S_n,x_i)
\wedge
\operatorname{Fresh}(S_n,x_i).
\]

Failure produces a refused TAS_DNA datum rather than an admitted operational transition.

## 9. Runtime fail-closed conversion

The current `CanonicalVerticalSlice` can pass verifier admission and still refuse at runtime.

\[
\operatorname{Adm}(S_n,x_i)=1
\land
\neg\operatorname{RuntimeOK}(x_i)
\Rightarrow
G_i.d=\mathrm{REFUSED}.
\]

For runtime null-collapse:

\[
\operatorname{RuntimeNullCollapse}(x_i)
\Rightarrow
G_i.d=\mathrm{REFUSED}.
\]

That gene extends \(\Gamma\), but not \(\Pi_A(\Gamma)\).

## 10. Recovery

Let

\[
\operatorname{Tip}_A(\Gamma_n)=\operatorname{Tip}(\Pi_A(\Gamma_n))
\]

be the latest admitted checkpoint.

For refusal:

\[
\operatorname{RecoveryAnchor}(G_i)=\operatorname{Tip}_A(\Gamma_n).
\]

The refused gene remains in full lineage while recovery stays anchored to authorized operational history.

## 11. Deterministic refusal receipt

Let \(p_i^-\) be the canonical refusal payload and define

\[
R_i^-=H(\operatorname{Encode}(p_i^-)).
\]

Then

\[
p_a^-=p_b^-
\Rightarrow
R_a^-=R_b^-.
\]

The resolved evaluation timestamp is part of the canonical payload.

## 12. Complete mediation

Let \(P\) be the set of consequential execution paths. TAS requires

\[
\forall e\in P,
\neg\mathbb A(e)\Rightarrow\neg\mathbb C(e).
\]

A verifier is insufficient if another path can bypass it.

## 13. Executable correspondence

Merged PR `TrueAlpha-spiral/TrueAlpha-spiral#364` directly tests that:

1. a refused TAS_DNA gene extends WakeChain evidence,
2. refusal does not advance the admission-only `state_sequence()`,
3. recovery anchors to the prior admitted checkpoint,
4. runtime null-collapse becomes a refusal,
5. repeated evaluation of the same bounded refusal payload produces the same refusal receipt ID.

Those tests validate the admitted projection. The architectural full-state relation retains that projection together with the complete authenticated lineage.
