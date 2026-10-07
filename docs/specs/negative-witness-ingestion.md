# Historical Failure → Negative Witness Ingestion

**Status:** normative v1  
**Purpose:** admit prior probabilistic failures as challenge evidence without
turning an observation into self-authorizing truth.

## Trust boundary

A negative witness states only that authenticated observers documented a
specific failure pattern in a content-addressed artifact. It MUST NOT authorize
a transition, establish the falsity of a new claim, or mutate the protected
application state. A later evaluator MAY cite an active witness when its pinned
matching rule deterministically matches new evidence.

## Canonical schema and signature

The wire object MUST validate against
`schemas/negative_witness.schema.json`. `witness_id` is SHA-256 over canonical
JSON of every top-level field except `witness_id` and `attestations`. Each
attestor signs:

```text
"TAS-NEGATIVE-WITNESS-V1\0" || canonical_json(signed_payload)
```

Canonical JSON uses UTF-8, lexicographically sorted keys, no insignificant
whitespace, and unescaped Unicode. The authority snapshot is supplied by the
verifier; an artifact cannot introduce its own trusted key.

## Ingestion transition

1. **Freeze inputs.** Pin the source artifact, evidence objects, authority
   snapshot, schema version, and policy threshold by digest.
2. **Validate structure.** Require UTC timestamps, supported failure class,
   nonempty evidence and description, lowercase SHA-256 content addresses, and
   a `witness_id` recomputed from the signed payload.
3. **Verify attestations.** Resolve every `key_id` exclusively through the
   pinned authority snapshot, verify Ed25519 signatures, reject duplicate
   principals or keys, and meet the policy's distinct-principal threshold.
4. **Append atomically.** Hash an admission event containing the prior registry
   digest and `witness_id`; append it to the challenge registry. This changes
   registry state only, never application state.
5. **Emit a receipt.** Record `ADMITTED` plus both registry digests, or
   `REFUSED` plus a stable reason code. A refusal leaves the digest unchanged.

Structural, timestamp, digest, or payload defects produce `WITNESS_INVALID`.
Unknown keys, invalid signatures, repeated principals, or an unmet threshold
produce `AUTHORITY_CONTINUITY_FAILURE`.

## Snapshot and revocation semantics

Evaluation MUST name the exact challenge-registry digest it consulted. A
runtime MUST reject an implicit-`latest` or mismatched snapshot. Revocation
appends a new event and deactivates the witness; it does not delete the witness
or rewrite earlier decisions. Receipts evaluated at an older snapshot retain
their original, auditable meaning.

## Deliberate v1 exclusions

Pattern extraction and similarity are outside the admission transition. A
future policy may define deterministic matching, but a model-generated match
score cannot silently become authority. Policy evolution is a separate
transition and must cite admitted witness IDs while preserving its own approval
and rollback lineage.
