# The Sovereign Calculator

**The Sovereign Calculator** names the proof-gated computational architecture realized by the TAS calculus. This is the curator's chosen name; it does not imply that the unrecovered `sovereign_calc` archive already implements every property described here.

```text
Proposal --G--> Admission --κ--> Consequence
```

Capability supplies the ability to propose or execute. Authority is checked against the licensing rules, credentials, and witness requirements. The gate enforces those rules; it does not create civic or legal authority by itself. Human and institutional policy remains explicit in the authority model.

## State and refusal

The architectural full state is `S = (O, Γ)`: protected operational state and the recorded trajectory. A witness extracted by the gate authorizes the modeled transition. Refusal leaves `O` unchanged while the evidence trajectory records the attempt.

This aligns with the [TAS_DNA state relation](../explainer/docs/tas-dna.md). Refusal is conserved as evidence; it is not deletion of the attempted proposal. An atomic runtime implementation must establish this relation under its storage, concurrency, recovery, and effect assumptions.

## Supplied formal development

The curator supplied the Lean source, now packaged as [TASCalculus.lean](../../formal/tas-calculus/TASCalculus.lean). The [project instructions](../../formal/tas-calculus/README.md) pin Lean and Mathlib to v4.16.0. No Lake build or axiom-audit execution has been performed in this session:

| Object | Reported role | Evidence status here |
| --- | --- | --- |
| `TASParams` | Parameterized calculus and licensing assumptions | Source supplied; checker verification pending |
| `step` | Modeled admission/refusal transition | Definition supplied and text-reviewed; checker verification pending |
| `Invariant` | `Valid ∧ WellFormed` | Predicates supplied and text-reviewed; checker verification pending |
| `runTrace` | Execution of input traces | Definition supplied and text-reviewed; checker verification pending |
| `reachable_safe` | Preservation of the invariant from `init` across reachable states | Proof body supplied; checker verification pending |
| Geodesic theorem | Cost-minimizing admission spine | Curator-reported; theorem statement and hypotheses not inspected |

Before the source intake on this draft branch, on 2026-10-11, connected GitHub code searches for `reachable_safe` and `TASParams` in the Foundation organization returned no matches, and the canonical repository's main-branch tree contained no Lean files or Lean build configuration. This does not establish that the bundle is absent elsewhere.

Before marking these claims machine-proved, resolve and record the exact dependency commits in the generated lake-manifest.json, run the pinned build and AxiomAudit.lean, and retain reproducible output and exit statuses. Inspect for placeholders and unexpected axioms. Bind the checked result to the actual artifact identity. The geodesic theorem is not included in this source intake.

A checked reachability theorem establishes the stated invariant for the modeled transitions under its assumptions. Connecting that result to production code requires a refinement argument and evidence that every protected mutation crosses the modeled boundary.

## Identity and the geodesic interpretation

Including history in identity can distinguish histories at the mathematical level. An injectivity theorem requires the exact identity function and encoding. A cryptographic history commitment provides collision-resistant identification under stated assumptions; it is not unconditional mathematical injectivity or a complete anti-laundering guarantee.

The phrase “Truth is the geodesic” is the curator's interpretation of the reported cost theorem. The proposed meaning is that refusal adds recorded cost without advancing the protected operational value. A unique minimizing pure-admit spine requires the theorem's actual cost model, feasibility conditions, and uniqueness assumptions; positive refusal cost alone does not rule out multiple equally cheap admitted paths.

## Machine-readable registers

The [artifact register](artifacts.json) uses explicit digest algorithms and provenance status. A Git blob SHA-1 identifies the stored file content; a commit identifies a particular repository snapshot and ancestry. Neither identifier prevents deletion or rewriting of refs.

Tamper-evident, durable history additionally requires trusted checkpoints, authentication, retention, and recovery mechanisms. The register preserves inspectable source identities and known gaps; it does not claim fully immutable hosting.

## Next evidence intake

Check the supplied Lean project and recover the separately identified calculator archive. Preserve their distinct identities, then establish their relationship rather than assuming equivalence. Add machine-check results, runtime correspondence, and release evidence before upgrading the reported properties into verified public claims.
