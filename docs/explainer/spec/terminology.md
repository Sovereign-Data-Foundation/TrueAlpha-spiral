# Canonical Terminology

This glossary keeps prose, equations, diagrams, and implementation terms aligned without collapsing architectural levels.

| Term | Symbol / Form | Meaning |
|---|---|---|
| TAS_DNA gene | \(G_i=(o_i,c_i,a_i,x_i,p_i,\Phi_i,d_i,r_i)\) | Canonical minimal transition datum |
| TASGene | `TASGene` | Current implementation of the TAS_DNA gene |
| Full state | \(S_n=(O_n,\Gamma_n)\) | Irreducible pair of authorized operational state and authenticated lineage |
| Operational state | \(O_n\) | Authorized consequential configuration |
| Authenticated lineage | \(\Gamma_n\) | Ordered TAS_DNA trajectory |
| Admitted projection | \(\Pi_A(\Gamma_n)\) | Ordered subsequence of admitted TAS_DNA genes |
| Evidence timeline | `WakeChain.evidence_timeline()` | Implementation view containing Genesis, admissions, and refusals |
| State sequence | `WakeChain.state_sequence()` | Implementation view of the admitted projection, not the entire full state |
| Origin | \(o_i\) | Initiating intent/source of the transition |
| Context | \(c_i\) | Operational frame in which the candidate is evaluated |
| Authority | \(a_i\) | Scoped authorization bound to the transition |
| Operation | \(x_i\) | Candidate action or transformation |
| Parent | \(p_i\) | Parent gene identity / lineage reference |
| Invariants | \(\Phi_i\) | Rule set evaluated for the candidate |
| Decision | \(d_i\) | `ADMITTED`, `REFUSED`, or `PENDING` |
| Receipt | \(r_i\) | Evidence emitted after decision |
| Refusal receipt ID | \(R_i^-=H(\operatorname{Encode}(p_i^-))\) | Content-derived identity of the canonical refusal payload |
| Recovery anchor | \(\operatorname{Tip}_A(\Gamma_n)\) | Last admitted gene used for recovery |
| Canonical Vertical Slice | `CanonicalVerticalSlice` | Execution boundary that verifies, admits/refuses, emits receipts, appends WakeChain evidence, and initiates recovery |
| Runtime null collapse | `RUNTIME_NULL_COLLAPSE` | Runtime condition converted into a refused TAS_DNA gene |
| Complete mediation | \(\neg\mathbb A(e)\Rightarrow\neg\mathbb C(e)\) | Every consequential path must cross the admissibility boundary |
| Cursive computation | — | Extension of authenticated TAS_DNA lineage while operational consequence remains admission-gated |

## Required distinctions

### Full state vs admitted projection

The full state is

\[
S_n=(O_n,\Gamma_n).
\]

The implementation's `state_sequence()` corresponds to the admitted projection

\[
\Pi_A(\Gamma_n),
\]

not to the whole pair \((O_n,\Gamma_n)\).

No model is demoted by this distinction. The implementation view is a projection of the architectural state relation.

### Refusal

For refused gene \(G_i\):

\[
\Gamma_{n+1}=\Gamma_n\Vert G_i
\]

while

\[
\Pi_A(\Gamma_{n+1})=\Pi_A(\Gamma_n)
\]

and therefore

\[
O_{n+1}=O_n.
\]

Yet the full state changes:

\[
S_{n+1}\neq S_n
\]

because authenticated lineage advanced.

### Admission

For admitted gene \(G_i\):

\[
\Gamma_{n+1}=\Gamma_n\Vert G_i
\]

and

\[
\Pi_A(\Gamma_{n+1})=\Pi_A(\Gamma_n)\Vert G_i.
\]

Operational state may then advance under the admitted transition.

### Refusal vs recovery checkpoint

A refused gene is part of authenticated lineage but not the latest admitted checkpoint:

\[
\operatorname{RecoveryAnchor}(G_r)=\operatorname{Tip}_A(\Gamma_n).
\]

### Log vs lineage

A generic log is not TAS_DNA lineage. TAS_DNA lineage carries parentage, constitutional fields, decisions, and receipts and participates in full-state identity.

## Naming rule

When introducing a new term, identify whether it is:

1. a field of the TAS_DNA datum,
2. part of authenticated lineage \(\Gamma\),
3. part of the admitted projection \(\Pi_A(\Gamma)\),
4. operational state \(O\),
5. the full state \(S=(O,\Gamma)\), or
6. recovery / constitutional transition behavior.

Preserve the relation among these levels instead of rewriting one in terms of another.
