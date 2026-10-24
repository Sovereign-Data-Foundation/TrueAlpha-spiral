# Foundational Axioms

TrueAlphaSpiral begins from a separation that ordinary generative systems often blur:

\[
\text{Capability} \not\Rightarrow \text{Authority}.
\]

A system may be able to propose, synthesize, predict, optimize, or construct a candidate transition without thereby possessing authority to make that transition consequential.

## Axiom 1 — Capability does not imply authority

Let \(C(x)\) denote computational capability to propose action \(x\), and let \(A(x)\) denote externally grounded authority for \(x\).

TAS rejects:

\[
C(x)\Rightarrow A(x).
\]

Authority must be established independently of generative capability.

## Axiom 2 — Proof precedes consequence

Consequential mutation is admissible only after the required predicates have been recomputed and verified.

\[
\operatorname{Commit}(x)
\Rightarrow
\operatorname{Proof}(x).
\]

The verifier does not infer proof from confidence, fluency, model identity, process identity, or successful proposal generation.

## Axiom 3 — Fail closed

When admissibility cannot be established, execution does not guess.

\[
\neg\operatorname{Prove}(\operatorname{Adm}(S,x))
\Rightarrow
\neg\operatorname{Commit}(x).
\]

A failed candidate is refused, quarantined, or hard-stopped according to the applicable boundary semantics.

## Axiom 4 — TAS_DNA is the canonical minimal transition unit

The constitutional relationship is carried by one datum:

\[
G_i=(o_i,c_i,a_i,x_i,p_i,\Phi_i,d_i,r_i).
\]

The fields represent origin, context, authority, operation, parent, invariants, decision, and receipt.

Admission and refusal use the same grammar. The difference is carried by \(d_i\), not by changing the type of datum.

## Axiom 5 — Evidence and state are distinct projections

The same ordered TAS_DNA chronology supports both:

- an evidence projection retaining admissions and refusals, and
- an authorized-state projection advancing through admissions only.

For refusal:

\[
d_i=\mathrm{REFUSED}
\Rightarrow
\mathcal E_{n+1}=\mathcal E_n\Vert G_i
\land
S_{k+1}=S_k.
\]

For admission:

\[
d_i=\mathrm{ADMITTED}
\Rightarrow
\mathcal E_{n+1}=\mathcal E_n\Vert G_i
\land
S_{k+1}=F(S_k,G_i).
\]

A refusal therefore remains part of the authenticated process record without being promoted into authorized state progression.

## Axiom 6 — Complete mediation

Every consequential effect must cross the admissibility boundary.

Let \(E\) be the set of possible effect paths. TAS requires:

\[
\forall e\in E,
\neg\mathbb A(e)
\Rightarrow
\neg\mathbb C(e).
\]

The architecture fails if an alternate execution path can bypass the gate.

## Consequence

The foundational design objective is not to make a generator intrinsically authoritative. It is to make unauthorized consequence unreachable while preserving both positive and negative decisions through the same lineage-bearing TAS_DNA datum.
