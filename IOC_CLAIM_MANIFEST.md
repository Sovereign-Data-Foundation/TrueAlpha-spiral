# August 21 IOC Claim Manifest

**Baseline:** commit `015d8d9d438fa95e270082f40de7f62d82b28a8d`  
**Scope:** the Python SDF evidence-verification and TAS admission path added by
PR #49.  
**Status vocabulary:** **PROVED** means supported by a machine-checkable proof;
**TESTED** means observed only within the named test scope; **DESIGNED** means
specified but not demonstrated.  A hash is evidence only when an evaluator can
recompute it from the identified inputs.

This manifest is deliberately narrower than an authorization, certification,
compliance determination, or claim that every protected-state mutation crosses
this boundary. It records what the current repository demonstrates and the
obligations that remain open.

## IOC safety claim

The target whole-system property is:

```text
for every transition t:
    mutates_protected_state(t)
    => crosses_commit_boundary(t) and admission_verdict(t) == 1

admission_verdict(t) == 0 => protected_state_after == protected_state_before
```

At this baseline that property is **DESIGNED, NOT PROVED**. The repository tests
one admission function, but does not inventory all mutation paths or prove that
they are mediated by it.

## Claims and recomputable evidence

| ID | Status | Narrow release claim | Evidence and independent check |
|---|---|---|---|
| IOC-01 | **TESTED** | An envelope signature is checked against externally supplied authority/credential trust maps at `admit_or_refuse`; an embedded key must match the resolved trusted key. | `sdf_evidence_envelope.py::_check_authentic`; trust-boundary tests in `tests/test_sdf_evidence_envelope.py`. Run `python -m pytest tests/test_sdf_evidence_envelope.py`. |
| IOC-02 | **TESTED** | A credential entry binds its reference to an expected authority identifier and public key. | `sdf_evidence_envelope.py::_check_authentic`; credential/authority mismatch tests in `tests/test_sdf_evidence_envelope.py`. Run the test command above. |
| IOC-03 | **TESTED** | The consequential boundary compares the signed claim with the normalized proposal passed to the transition callback. | `tas_admissibility.py::admit_or_refuse`; claim/proposal binding tests in `tests/test_sdf_evidence_envelope.py`. |
| IOC-04 | **TESTED** | Proposal normalization accepts only JSON values and rejects non-finite floats. | `tas_admissibility.py::_json_value`; JSON-model tests in `tests/test_sdf_evidence_envelope.py`. |
| IOC-05 | **TESTED** | Predicate and receipt identifiers are deterministic domain-separated SHA-256 hashes for identical inputs. | `sdf_evidence_envelope.py::_domain_hash` and receipt tests in `tests/test_sdf_evidence_envelope.py`. These hashes are not signatures, MACs, or proof of a signer. |
| IOC-06 | **TESTED** | Refusal returned by `admit_or_refuse` reports `delta_s == 0`, preserves the supplied state-root value, and does not invoke the transition callback in the tested refusal paths. | Refusal-path tests in `tests/test_sdf_evidence_envelope.py`. This is local boundary behavior, not a complete-mediation proof. |
| IOC-07 | **TESTED** | Lineage fields and the envelope canonical hash are checked for syntactic and internal consistency. | `sdf_evidence_envelope.py::_check_lineage`; lineage tests in `tests/test_sdf_evidence_envelope.py`. This claim is intentionally named **lineage-field consistency**, not authenticated ancestry. |
| IOC-08 | **TESTED** | A process-local mutable set detects a nonce already present during verification and records a nonce after a successful callback. | Replay tests in `tests/test_sdf_evidence_envelope.py`. This is best-effort replay detection only; it is not atomic or durable consumption. |

## Explicitly deferred obligations (release blockers for the stronger claim)

The following statements **must not** be inferred from the claims above:

1. **Authenticated ancestry.** Introduce an external lineage resolver, require
   the resolved parent artifact to hash to `parent_hash`, require sequence
   continuity, walk to a trusted genesis, and enforce a bounded traversal with
   cycle detection. Until then, `lineage_intact` is only a legacy field name.
2. **Atomic durable nonce consumption.** Replace `Set[str]` with a transactional
   nonce store exposing an atomic consume-if-absent operation. Commit consumption
   before calling the effect function, and add concurrent-worker, restart, and
   crash-injection tests.
3. **Complete effect mediation.** Enumerate every protected-state writer and
   demonstrate that no writer can bypass the commit boundary. Direct mutation,
   recovery, administrative, migration, and callback paths are in scope.
4. **Transition-output validation.** Reject a transition result unless it is the
   required 64-character lowercase hexadecimal state root; define failure and
   recovery behavior after nonce commitment.
5. **Authenticated receipts.** Bind the binary/canonical receipt to an external
   signer or MAC key and verify that authentication at the gateway. Existing
   receipt hashes provide deterministic integrity identifiers, not
   non-repudiation, sealing, immutability, or signer authentication.
6. **Crash-consistent evidence advancement.** Atomically record refusal/admission
   evidence and the relevant state commitment, then prove recovery behavior with
   fault injection.
7. **Independent release assurance.** Produce authenticated build provenance and
   an independent clean-room reproducibility result. Neither is claimed by this
   manifest.
8. **Agency authorization and compliance.** Architecture artifacts may support an
   accountable authority's review, but this repository does not issue an ATO or
   establish compliance by itself.

## Exit criteria for the stronger IOC statement

The stronger claim may move from **DESIGNED** only when one frozen release
provides all of the following recomputable artifacts:

- a protected-state writer inventory and negative bypass tests;
- authenticated ancestry fixtures, including missing-parent, fork, cycle,
  sequence-gap, untrusted-genesis, and depth-limit failures;
- a durable nonce-store transaction log plus concurrency and crash-recovery
  results showing commitment before effect;
- validated before/after state roots and authenticated receipts binding proposal,
  evidence, nonce commitment, verdict, and resulting state;
- a formal model/model-check result for the commit ordering and recovery states;
- authenticated build provenance and an independent reproducibility report; and
- an evidence index mapping every release claim to immutable artifact digests.

The acceptance demonstration must include both observations:

```text
refused:   verdict == 0, protected state unchanged, refusal evidence advanced
admitted:  verdict == 1, protected state changed, authenticated cause/effect receipt
```

Until those exit criteria are met, the defensible statement is:

> PR #49 strengthens local admissibility authentication and deterministic
> evidence hashing. It does not yet establish authenticated ancestry, atomic
> durable replay exclusion, authenticated receipts, or whole-system complete
> effect mediation.
