# Merkle Lineage Tree Rust Blueprint

## Purpose

This blueprint describes a production-grade Rust implementation for the TAS/SDF
Merkle Lineage Tree validation loop. The goal is sub-millisecond rollback from an
inadmissible candidate state to the last verified parent state while preserving a
verifiable receipt of the refusal, anomaly, or recovery event.

The design is intentionally admissibility-centric: generation may propose a
state, but the lineage loop decides whether the state can execute.

## Restored governance framework

```text
┌─────────────────────────────────────────────────────────┐
│              SOVEREIGN DIGITAL INFRASTRUCTURE           │
└────────────────────────────┬────────────────────────────┘
                             │ governed through
                             ▼
┌─────────────────────────────────────────────────────────┐
│                 CURSIVE COMPUTATION LAYER               │
│     Active state-writing with cryptographic lineage     │
└─────────────────────┬───────────────────┬───────────────┘
                      │                   │
                      ▼                   ▼
┌───────────────────────────┐   ┌───────────────────────────┐
│     PROCESS SECURITY      │   │     SYSTEM REGULATION     │
│                           │   │                           │
│ • Provenance receipts     │   │ • Pre-execution gating    │
│ • Axiom P0: equivalence   │   │ • Deterministic refusal   │
│ • Axiom P1: admissibility │   │ • Bounded resource use    │
│ • Verifiable lineage      │   │ • Recovery to valid state │
└───────────────────────────┘   └───────────────────────────┘
```

Legacy AI stacks often hide uncertainty beneath post-hoc safety filters. TAS/SDF
instead uses a path-dependent, zero-trust cryptographic constraint loop that
keeps execution subordinate to accountable authority, deterministic verification,
and receipt-bearing lineage.

## Core invariants

| Invariant | Rust enforcement surface | Failure mode |
|---|---|---|
| Origin precedes state | `OriginProof` must exist before `CandidateState` admission. | Refusal receipt: `MissingOrigin`. |
| P0 equivalence | Canonical serialization and parent hash equality checks. | Refusal receipt: `EquivalenceBreak`. |
| P1 admissibility | Constraint boundary validation before append. | Refusal receipt: `InadmissibleTransition`. |
| Rights as invariants | Protected-interest constraints cannot be downgraded to configuration flags. | Hold, stay, or refusal pending human review. |
| Bounded resource use | Validation budget and short-circuit refusal. | Refusal receipt: `BudgetExceeded`. |
| Recovery to valid state | Active pointer rolls back to last verified node. | Phoenix recovery receipt. |

## Data model

```rust
pub type Hash32 = [u8; 32];

pub struct OriginProof {
    pub subject_id: String,
    pub authority_id: String,
    pub issued_at_unix_ms: u64,
    pub signature: Vec<u8>,
}

pub struct ConstraintBoundary {
    pub policy_version: String,
    pub invariant_hash: Hash32,
    pub protected_interest: Option<String>,
    pub max_validation_ns: u64,
}

pub struct CandidateState {
    pub payload_hash: Hash32,
    pub parent_hash: Hash32,
    pub origin: OriginProof,
    pub boundary: ConstraintBoundary,
    pub paradata_hash: Hash32,
}

pub struct LineageNode {
    pub node_hash: Hash32,
    pub parent_hash: Hash32,
    pub merkle_root: Hash32,
    pub depth: u64,
    pub admitted_at_unix_ms: u64,
}

pub enum RefusalCode {
    MissingOrigin,
    EquivalenceBreak,
    InadmissibleTransition,
    BudgetExceeded,
    InvalidSignature,
    NullCollapse,
}

pub struct RefusalReceipt {
    pub candidate_hash: Hash32,
    pub parent_hash: Hash32,
    pub code: RefusalCode,
    pub verifier_id: String,
    pub observed_at_unix_ms: u64,
    pub witness_hash: Hash32,
}
```

## Validation loop

```rust
pub enum AdmissionResult {
    Admitted(LineageNode),
    Refused(RefusalReceipt),
}

pub trait ConstraintVerifier {
    fn verify_origin(&self, candidate: &CandidateState) -> bool;
    fn verify_p0_equivalence(&self, candidate: &CandidateState, parent: &LineageNode) -> bool;
    fn verify_p1_admissibility(&self, candidate: &CandidateState) -> bool;
    fn verify_budget(&self, started_ns: u128, max_ns: u64) -> bool;
}

pub fn admit_candidate<V: ConstraintVerifier>(
    verifier: &V,
    candidate: CandidateState,
    parent: &LineageNode,
    now_unix_ms: u64,
    started_ns: u128,
) -> AdmissionResult {
    if !verifier.verify_origin(&candidate) {
        return AdmissionResult::Refused(refusal(&candidate, RefusalCode::MissingOrigin, now_unix_ms));
    }

    if !verifier.verify_p0_equivalence(&candidate, parent) {
        return AdmissionResult::Refused(refusal(&candidate, RefusalCode::EquivalenceBreak, now_unix_ms));
    }

    if !verifier.verify_p1_admissibility(&candidate) {
        return AdmissionResult::Refused(refusal(&candidate, RefusalCode::InadmissibleTransition, now_unix_ms));
    }

    if !verifier.verify_budget(started_ns, candidate.boundary.max_validation_ns) {
        return AdmissionResult::Refused(refusal(&candidate, RefusalCode::BudgetExceeded, now_unix_ms));
    }

    AdmissionResult::Admitted(derive_node(candidate, parent, now_unix_ms))
}
```

## Sub-millisecond rollback strategy

Sub-millisecond rollback depends on pointer movement, not tree reconstruction:

1. Keep an atomic `active_root: AtomicHashRef` pointing to the last admitted node.
2. Validate candidates against the active root without mutating it.
3. Append admitted nodes to an immutable segment log.
4. On refusal, emit the refusal receipt and leave `active_root` unchanged.
5. On detected corruption after admission, atomically swap `active_root` back to
   the last verified ancestor and write a Phoenix recovery receipt.

This strategy makes rollback `O(1)` for the execution pointer and `O(log n)` only
for proof construction or external audit queries.

## Storage layout

```text
/lineage
  /segments
    0000000000000000.seg
    0000000000000001.seg
  /receipts
    refusals.log
    recoveries.log
  /indexes
    active_root.ptr
    node_hash_to_segment.idx
    parent_to_children.idx
```

Segments should be append-only. Indexes may be rebuilt from segments and receipts,
so they are performance aids rather than the source of truth.

## Phoenix recovery hook

```rust
pub fn phoenix_recover(
    active_root: &AtomicHashRef,
    last_verified: Hash32,
    anomaly_receipt: RefusalReceipt,
    recovery_log: &mut dyn RecoveryWriter,
) -> Result<(), RecoveryError> {
    active_root.store(last_verified);
    recovery_log.write_recovery(last_verified, anomaly_receipt)?;
    Ok(())
}
```

The anomaly remains visible in the ledger while active execution resumes from the
last verified parent hash.

## Performance targets

| Operation | Target | Technique |
|---|---:|---|
| Candidate precheck | < 100 microseconds | Canonical hash comparison and signature cache. |
| Admission append | < 500 microseconds | Preallocated segment writer and batched fsync policy. |
| Refusal receipt emit | < 500 microseconds | Append-only refusal log with compact witness hash. |
| Active-root rollback | < 50 microseconds | Atomic pointer swap. |
| Audit proof construction | O(log n) | Merkle branch lookup through segment index. |

## Boundary conditions

The implementation must fail closed when:

- origin proof is missing or invalid;
- candidate parent hash does not match the active root;
- admissibility constraints are absent, stale, or unverifiable;
- validation exceeds budget;
- all candidate paths collapse to the null operator;
- recovery cannot write a receipt; or
- the active root cannot be proven against the segment log.

## Production hardening checklist

- Use deterministic canonical serialization for every hashable structure.
- Separate admission writes from index updates so indexes cannot corrupt lineage.
- Treat refusal as a successful validation outcome, not an exception path.
- Keep recovery receipts append-only and externally auditable.
- Benchmark on realistic segment sizes and concurrent candidate loads.
- Expose read-only audit APIs for origin, authority, constraint, verification,
  refusal, receipt, and recovery proof material.
