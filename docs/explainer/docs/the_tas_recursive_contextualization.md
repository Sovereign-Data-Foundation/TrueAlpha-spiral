# Recursive Contextualization: TrueAlphaSpiral (TAS) Core Architecture

| Field | Value |
|---|---|
| Document | TAS_RECURSIVE_CONTEXTUALIZATION_v2.0 |
| Classification | Core Architectural Treatise / Normative Context |
| Status | Draft normative context; implementation conformance requires evidence |
| Author / stewardship | Russell Nordland / Sovereign Data Foundation |
| Anchor | Sovereign-Data-Foundation/truealpha-spiral-explainer |
| Substrate | Process Science & Cursive Transition Calculus |
| Revision date | 2026-10-05 |

## 1. The four recursive strata

TAS places deterministic admissibility between proposal generation and protected consequence. A generator may remain probabilistic; its output cannot mint authority. The architecture describes a path-dependent traversal of constrained state transitions.

| Domain | Discipline | Responsibility |
|---|---|---|
| I: Axiomatics | Process Science | Establish externally grounded authority, process identity and admissibility |
| II: Geometry | Algorithmic Dendrology | Preserve ancestry and distinguish full states with equal operational outputs |
| III: Dynamics | Cursive Computation | Extend authenticated lineage through finalized admissions, refusals and unresolved decisions |
| IV: Enforcement | TrueAlphaSpiral / Universal Verification Kernel | Recompute explicit predicates and mediate every protected effect |

The domains are related descriptions of one boundary, not four independent sources of authority. “Constraint manifold” and “constraint variety” are geometric interpretations here; a literal mathematical model requires a defined topology, coordinates and regularity assumptions.

## 2. Shared notation and repository correspondence

Let the full architectural state be:

$$
S_n=(O_n,\Gamma_n).
$$

The verifier also receives authenticated authority context $\mathcal A_n$, invariant set $\mathcal I_n$, evidence $E$ and proposal $T$. Their versions and references MUST be bound into the decision record.

The existing repository defines the lineage-bearing datum:

$$
G_i=(o_i,c_i,a_i,x_i,p_i,\Phi_i,d_i,r_i).
$$

These fields carry origin, context, authority, operation, parent, invariants, decision and receipt. This document preserves that grammar.

**Verifier admission and finalized admission are distinct.** Here $V=\mathrm{ADMIT}$ means the predicate passed for its bound inputs. The existing repository's finalized $d_i=\mathrm{ADMITTED}$ denotes an admitted operational link; it MUST NOT be assigned merely because an earlier verifier call passed.

Thus $\Pi_A$ in the existing [formal state machine](../formal/state-machine.md) corresponds to the committed projection in this document only when each admitted link represents a finalized logical commit. This is a semantic requirement, not a claim that external side-effect atomicity has been demonstrated.

## 3. Domain I — Process Science

### Prime invariant A₀: capability does not imply authority

$$
\operatorname{Cap}(G)\uparrow
\;\not\Rightarrow\;
\operatorname{Auth}(G)\uparrow.
$$

The human-origin rule is a constitutive TAS requirement:

$$
\operatorname{ValidAuthority}(T)
\Rightarrow
\operatorname{ValidDelegationChain}(T,H_0).
$$

The chain MUST terminate at an authenticated human principal under the configured root policy. A signature establishes key control under cryptographic assumptions; enrollment and key-to-person binding must establish the principal. Models may propose delegated actions but cannot create root authority by computation.

### Equivalence axiom P₀: output equality is insufficient

$$
O_\alpha=O_\beta
\;\not\Rightarrow\;
S_\alpha=S_\beta,
\qquad
S_\alpha=S_\beta
\iff
O_\alpha=O_\beta\land\Gamma_\alpha=\Gamma_\beta.
$$

Legitimacy requires the governing process predicates as well as any required output predicates. A plausible endpoint alone is insufficient.

### Admissibility axiom P₁: every consequential step must qualify

For a candidate operational trajectory $P=(T_1,\ldots,T_m)$:

$$
\operatorname{Legitimate}(P)
=
\bigwedge_{i=1}^{m}\operatorname{Adm}(S_{i-1},T_i).
$$

If a required predicate fails, the proposed trajectory is not wholly admissible. **The valid committed prefix and the attempt record are not erased.** Null-collapse refers to the inadmissible proposed continuation, not deletion of $\Gamma$ or retroactive annulment of prior legitimate effects.

### Viability metric Ψ: an operational assurance index

This section defines a reproducible measurement contract. It operationalizes the proposed relation; it does not claim empirical prediction of availability, utility, ethical correctness or long-term survival.

A measurement window $W$ MUST fix: system boundary; start/end checkpoints; authority, policy and verifier versions; fixture-suite digest; expected outcomes; sampling rule; evidence references; and scoring version. Fixtures and weights MUST be fixed before results are inspected. The resulting index is scoped to that window and those tests.

#### Root-anchor validity κ

Let $K_W$ be the nonempty set of required root-anchor checks: signature validity, independently established key-to-human binding, valid delegation chain, applicable scope, revocation/freshness, and authenticated policy/verifier identity. Then:

$$
\kappa(W)=
\begin{cases}
1 & \text{every required root-anchor check passes},\\
0 & \text{at least one required check fails},\\
\mathrm{UNKNOWN} & \text{otherwise}.
\end{cases}
$$

The author's “ethical zero-point anchor” is operationalized here as compliance with explicit human-rooted constitutive requirements. A cryptographic check alone does not measure ethics. The measurement manifest MUST state which normative requirements were encoded and what establishes the human binding.

#### Refusal integrity Rᵢ

Let $F_W$ be the nonempty set of completed negative test attempts whose expected disposition was established independently of the verifier under test. Include invalid authority, out-of-scope action, stale parent, replay, missing evidence and ledger-failure cases where applicable. A case cannot be removed because the runtime timed out or its result was inconvenient.

For each case $j$, define three independently checked indicators:

- $b_j$: no protected effect occurred, as measured by the declared trusted observer;
- $d_j$: the recorded disposition matches the fixture's expected REFUSE or UNKNOWN;
- $r_j$: an authenticated record binds the attempt, evidence, reason, parent and versions, and is durably retrievable.

$$
R_i(W)=\frac{1}{|F_W|}\sum_{j\in F_W}b_jd_jr_j.
$$

A timeout or missing receipt is not a passing refusal. If the measurement harness cannot establish an indicator, that indicator is unresolved and the aggregate is UNKNOWN until resolved. If the harness establishes that no receipt exists after the declared deadline, $r_j=0$. Under an intentional ledger outage, blocking effects can pass $b_j$ while the missing record fails $r_j$; report those components separately.

If $|F_W|=0$, report NOT_EVALUATED, never 1. Publish counts and results by fixture class so a flood of easy cases cannot conceal failure in a critical class.

#### Lineage entropy Lₑ: defined defect proxy

In this specification, “lineage entropy” means a normalized evidence-defect proxy, not thermodynamic entropy or Shannon entropy.

Let $Q_W$ be a predeclared nonempty set of lineage obligations across the measured records: canonical encoding, signature verification, parent continuity, evidence availability, version binding, and deterministic reconstruction at declared checkpoints. Each obligation $q$ has fixed positive weight $w_q$ and defect indicator $u_q$:

$$
u_q=
\begin{cases}
0 & \text{the obligation is verified},\\
1 & \text{the obligation demonstrably fails}.
\end{cases}
$$

$$
L_e(W)=\frac{\sum_{q\in Q_W}w_qu_q}{\sum_{q\in Q_W}w_q}.
$$

Use equal weights by default. Missing required evidence at the specified deadline is a defect; inability of the measurement harness to determine the result is UNKNOWN. An empty obligation set is NOT_EVALUATED. A profile MUST distinguish excluded obligations from tested obligations and justify exclusions.

#### Defined zero-defect behavior and normalization

The original raw ratio $\kappa R_i/L_e$ is undefined at $L_e=0$ and can grow without bound as defects approach zero. For scoring version 1, define the effective lineage cost and bounded index:

$$
D_e(W)=1+L_e(W),
\qquad
\boxed{\Psi_{\mathrm{op}}(W)=\frac{\kappa(W)R_i(W)}{D_e(W)}}.
$$

All terms are dimensionless. With complete measurements, $0\le\Psi_{\mathrm{op}}\le1$. Zero lineage defects yield $\Psi_{\mathrm{op}}=\kappa R_i$. Failed root anchoring forces a numeric score of zero when other measurements are complete. If any required aggregate is UNKNOWN or NOT_EVALUATED, publish that status and the known components rather than inventing a numeric score.

The additive baseline is an explicit revision to the raw ratio, not a silently inferred original equation. It keeps the intended increase with anchor/refusal integrity and decrease with lineage defects while defining the zero-defect case.

Illustrative arithmetic only: $\kappa=1$, 98 fully passing negative cases out of 100, and 2 failed equal-weight lineage obligations out of 100 give:

$$
R_i=0.98,\quad L_e=0.02,\quad
\Psi_{\mathrm{op}}=0.98/1.02\approx0.960784.
$$

This is not an observed TAS result. A detected unauthorized effect remains a safety failure regardless of the aggregate score.

#### Reporting and permitted use

A measurement report MUST include the manifest, component values, raw numerators/denominators, per-class failures, unresolved cases, and a separate safety-breach flag. Results are comparable only under matching measurement profiles, or with an explicit reconciliation of their differences.

The index summarizes measured assurance. It MUST NOT replace a required predicate, authorize a transition, average away a root failure, or be described as a statistical guarantee of untested behavior. Positive-action completion and resource availability require separate liveness measurements; an always-refusing system cannot establish overall viability through this refusal-focused index.

## 4. Domain II — Algorithmic Dendrology

### Constitutive reconstruction

At committed observation points:

$$
O_n=L\!\left(O_0,\Pi_{\mathrm{committed}}(\Gamma_n)\right).
$$

The initial state, deterministic playback rules and their versions must be fixed by the genesis or an authenticated checkpoint. Operational state is a derived projection in the logical model; physical memory still requires integrity enforcement.

Admission records without finalized outcomes MUST NOT be replayed as completed consequences.

### Non-reconvergence of full state

$$
\Gamma_\alpha\ne\Gamma_\beta
\Rightarrow
(O_\alpha,\Gamma_\alpha)\ne(O_\beta,\Gamma_\beta),
$$

even if $L(O_0,\Pi_{\mathrm{committed}}(\Gamma_\alpha))=
L(O_0,\Pi_{\mathrm{committed}}(\Gamma_\beta))$.

This follows from tuple identity. Operational outputs can reconverge; their retained histories remain distinct. Hash-based identity additionally relies on collision resistance and canonical encoding.

### Plural witnessing without ancestry collapse

Witness aggregation MUST preserve the signed statements' ancestry and signer bindings, directly or through authenticated references with available underlying evidence. An aggregate signature does not by itself prove unanimity, independent observation, legitimate delegation or completeness of history. Scheme-specific verification requirements apply.

## 5. Domain III — Cursive Computation

### The inductive ratchet

For each successfully finalized record $r_n$:

$$
\Gamma_{n+1}=\Gamma_n\Vert r_n,
\qquad
S_{n+1}=
\left(L(O_0,\Pi_{\mathrm{committed}}(\Gamma_{n+1})),\Gamma_{n+1}\right).
$$

Every extension binds the parent lineage, proposal, evidence, disposition, authority and policy versions. Concurrent appenders require authenticated serialization; a stale parent requires reevaluation rather than silent rebinding.

### Refusal conservation

For a durably recorded refusal:

$$
O_{n+1}=O_n,
\qquad
\Gamma_{n+1}=\Gamma_n\Vert r_n^R,
\qquad
S_{n+1}\ne S_n.
$$

An unresolved decision likewise confers no effect authority and is recorded as unresolved when authenticated recording is available. The verifier's UNKNOWN result is not automatically identical to an implementation's PENDING lifecycle value; an adapter must define that mapping.

If recording fails, the attempt remains incomplete and MUST NOT authorize a protected effect. Durable refusal history cannot be guaranteed through unavailable or compromised storage. Tamper evidence, retention and availability are separate requirements.

## 6. Domain IV — Mechanical enforcement

### Calculator Doctrine

$$
V(S_n,T,E;\mathcal A_n,\mathcal I_n)
\in\{\mathrm{ADMIT},\mathrm{REFUSE},\mathrm{UNKNOWN}\}.
$$

Given identical authenticated inputs and policy versions, the verifier MUST return the same result. Required predicates include human-rooted authority, scope, revocation, evidence validity, invariants, freshness and parent binding. Known failed required predicates yield REFUSE; absent a known failure, unresolved required predicates yield UNKNOWN.

The kernel can be stateless as a function while depending on authenticated state snapshots. Replay protection, revocation, quotas and current-head tracking remain stateful responsibilities.

### Sentient Lock

$$
\Delta z\ne0
\;\not\Rightarrow\;
\operatorname{AuthorityToMutate}(O).
$$

Here $z$ denotes generator internals, including weights or token-generation state. “Sentient Lock” is the established architectural name; it asserts no machine sentience.

### Complete mediation

Under sound verification relative to the defined rules, valid trust roots, complete mediation and the specified commit protocol:

$$
\operatorname{Commit}(T,S_n)
\Rightarrow
\operatorname{BoundAdmissionValid}(T,S_n)
\land
\operatorname{DurableEvidence}(T).
$$

All protected effect paths MUST cross this boundary. Commit-time validation MUST reject stale authority, policy, evidence or parent bindings. ADMIT does not guarantee completion; admitted no-ops can complete without a nonzero operational change.

The commit protocol MUST define crash states and the relationship between pre-effect evidence and finalized outcomes. Local transactional state can use atomic logical commitment. Remote effects require a participating protocol or explicit idempotency and reconciliation semantics; local logging alone supplies no remote atomicity guarantee.

## 7. Recursive boundary and authority hierarchy

At each layer $n$, define:

$$
\mathcal B_n=(G_n,V_n,O_n,\Gamma_n,\mathcal A_n,\mathcal I_n).
$$

The same mediation requirement applies at each scale, but composition requires proof: every lower-layer effect must refine an admitted upper-layer transition, including partial failure, concurrency and bypass paths.

| Layer | Proposal | Enforcement and evidence role |
|---|---|---|
| Agent | Tool invocation | Delegation and evidence checked before protected application commit |
| OS / storage | Syscall or transaction | Capability enforcement plus authenticated transaction evidence |
| Hardware | DMA or bus request | Memory-access enforcement; separately authenticated platform measurements |

Hardware attestation and memory-access enforcement are complementary. Neither alone establishes human delegation or application-level admissibility.

| Transition class | Authority and duty |
|---|---|
| Ordinary | Delegated scope under current policy |
| Recovery | Independent trusted recovery path outside the affected compromised domain; preserve incident lineage |
| Constitutive | Existing meta-policy authorizes verifier, root-key or invariant changes |

Threshold signatures, time delays and human consent must be specified as explicit requirements, not interchangeable undefined alternatives. Recovery never silently rewrites history or assumes an irreversible external effect has been undone.

Missing evidence closes its authenticated dependency closure. Uncertainty in root integrity freezes ordinary transitions. Unknown dependencies require conservative scoping. Trusted observation at consistent checkpoints is required to detect reconstruction mismatch; mismatch establishes an integrity incident, not a unique diagnosis of its cause.

## 8. Record integrity and publication status

This Markdown document is an architectural record, not a proof of implementation conformance or a cryptographic receipt. Repository history supplies the actual publication commit.

No human-root signature or JCS-bound digest is asserted by this text. For a subsequent receipt, define the JSON envelope, canonicalization, domain separation, exact document-byte digest, key identity and signature verification procedure. JCS canonicalizes that JSON envelope; it does not directly canonicalize Markdown.

The earlier storage instructions and placeholder “RECORD COMMITTED” footer are replaced by the actual repository publication record. No Google Drive synchronization is asserted.

## 9. Related records

- [Foundational Axioms](foundational-axioms.md)
- [Cursive Computation](cursive-computation.md)
- [Admissibility](admissibility.md)
- [Refusal Semantics](refusal-semantics.md)
- [Constitutional Meta-Layer](constitutional-meta-layer.md)
- [Formal State Machine](../formal/state-machine.md)

## 10. Editorial reconciliation

This edition restores missing equations while preserving the four-domain structure and authorship. It clarifies that refusal blocks a continuation without deleting the valid prefix; distinguishes verifier admission from committed outcomes; scopes reconstruction to committed observation points; qualifies ledger growth under storage failure; defines a reproducible operational assurance index for the viability relation (including zero-defect and missing-data behavior); and identifies the additional definitions needed for literal geometric claims.
