# TAS calculus reference project

Status: curator-supplied source packaged for checking; **Lake build not executed in this session**.

This directory is an independent Lake project inside the TAS_DNA repository. It contains the supplied operational semantics with newest-first lineage, full refusal proposal fields, the explicit StateMachine wrapper, and trace laws. Source comments have minor typographic normalization; definitions and proof bodies are unchanged.

## Pinned releases

- Lean: leanprover/lean4:v4.16.0.
- Mathlib: v4.16.0. Its release lean-toolchain was inspected and specifies the same Lean version.
- Lake's release PackageConfig supports the supplied version and keywords fields.

These checks establish release configuration compatibility, not successful elaboration of this file.

## Check the development

With Git and an elan-managed Lean installation available, run from this directory:

```sh
lake update
lake exe cache get
lake build TASCalculus
lake env lean AxiomAudit.lean
```

Stop if any command fails. Cache retrieval is an optimization, not proof verification. Preserve the actual command output and exit status; do not assume the build succeeds.

Review the axiom report for unexpected declarations, especially sorryAx. A successful build can still contain admitted proofs in general; the report and source review must accompany the machine-check claim. This supplied source contains no explicit sorry placeholders or added axiom declarations.

The successful first resolution generates lake-manifest.json. Commit that exact generated lockfile to record resolved Mathlib and transitive dependency revisions; no lockfile has been fabricated here. A tag pin alone is weaker than recorded immutable dependency commits.

## Evidence and scope

Record the source commit, Lean version, generated dependency manifest, build and axiom-audit results, and artifact digests before upgrading status to machine-checked or sealed.

The preservation theorem establishes operational decoding consistency and gate-generated well-formedness for finite traces relative to abstract G and ω. It does not itself establish concrete signature verification, external authority, durable storage, complete runtime mediation, or the geodesic theorem.

The separately reported sovereign_calc archive has not been recovered by packaging this Lean project. See the [collection curation contract](../../docs/curation/README.md) for provenance and claim boundaries.
