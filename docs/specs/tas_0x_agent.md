# TAS[0X] Agent — Zero-Authority Effect Runtime

**Status:** implementation specification, v0.3  
**Package:** `tas0x`  
**Boundary:** proposal generation may be probabilistic; protected effects are deterministic and externally authorized.

## 1. Purpose

TAS[0X] is the agent composition layer for the existing TAS admissibility and SDF evidence primitives. It does **not** make a model authoritative, truthful, or self-governing. It makes one narrower promise:

> A generated proposal cannot change protected state unless independent evidence, authority scope, lineage, context, replay, invariant, and compare-and-commit checks all close.

In implementation terms, `0X` is the zero-authority effect boundary: the generator begins with **zero constitutive authority** over the protected state.

## 2. Separation of jurisdiction

```text
Generator G
   │ proposes JSON only
   ▼
Canonical seal P* ─────────────┐
   │                            │
   ├─ detached copy ─► Evidence Provider
   │                    metadata-only EvidenceBinding
   │                            │
External Evidence E ────────────┤
External Tool Binding T ────────┤ authority scope + invariant + commit primitive
External State Root S ──────────┤
External Context C ─────────────┤
External Trust Registry ────────┤
                                ▼
                         TAS[0X] / Y-Knot
                           │           │
                        admit        refuse
                           │           │
                    compare+commit   ΔS = 0
                           │           │
                           └─────┬─────┘
                                 ▼
                           terminal receipt
                                 │
                                 ▼
                           witness lineage
```

The proposal can select a registered tool **name**. It cannot select or modify the authority scope, trusted key, invariant function, state root, context, or commit implementation bound to that tool.

The evidence provider receives an `EvidenceBinding`, not the effect-bearing `ToolBinding`. `EvidenceBinding` contains only `name` and `authority_scope`; it contains no commit callback, invariant callback, protected-resource handle, or other effect capability.

Envelope-derived lineage and the caller's system invariant are separate proof obligations. TAS[0X] never folds evidence-derived facts into the `invariant_check` slot of `admit_or_refuse`.

## 3. Canonical proposal seal

After generator normalization, TAS[0X] immediately creates canonical JSON bytes for the proposal and reconstructs the runtime proposal from that sealed representation:

```text
P_generated
    ↓ normalize JSON types
P_normalized
    ↓ CanonicalJSON
bytes(P*)
```

The canonical bytes are the identity surface for the rest of the cycle. Every externally controlled pre-commit participant receives a detached copy derived from `P*`.

Therefore:

```text
EvidenceProvider(copy(P*)) cannot rewrite P*
Invariant(copy(args(P*))) cannot rewrite Commit(args(P*))
Commit(copy(args(P*))) executes only the sealed proposal
```

The exact-claim predicate compares the evidence claim against the sealed canonical bytes, not against a mutable object previously exposed to the evidence provider.

## 4. Commit predicate

For sealed proposal `P*`, evidence envelope `E`, protected state root `S_n`, context `C`, registered binding `T`, and TAS[0X] lineage coordinates `(K_n, q_n)`:

```text
Commit(P*) ⇒
    ValidEnvelopeType(E)
  ∧ CanonicalJSON(claim(E)) = CanonicalJSON(P*)
  ∧ Genesis(E) = Genesis_external
  ∧ Parent(E) = K_n
  ∧ Sequence(E) = q_n
  ∧ Authentic(E)
  ∧ LineageWellFormed(E)
  ∧ AuthorityScope(E, T)
  ∧ ContextMatch(E, C)
  ∧ NonceFresh(E)
  ∧ Invariant_T(P*, S_n) is True
  ∧ CompareAndCommit_T(P*, expected=S_n)
```

Canonical JSON comparison is type-sensitive: `true` and `1` are not the same attested claim even though Python evaluates `True == 1`.

The invariant boundary is also type-sensitive. Only the literal boolean `True` satisfies the predicate. Truthy values such as `1`, `"true"`, non-empty containers, or arbitrary objects fail closed.

No predicate compensates for another. Any failed predicate prevents the TAS[0X] transition from committing.

## 5. Terminal states

| Status | Meaning | `delta_s` claim |
|---|---|---:|
| `ADMITTED` | All proof obligations passed and the effect published a **different** protected-state root. | `1` |
| `REFUSED` | A pre-commit predicate failed. No TAS[0X] effect was attempted. | `0` |
| `CONFLICT` | The protected state no longer matched the snapshotted parent, atomic commit explicitly rejected without mutation, or a claimed success produced no state delta. | `0` for this agent transition |
| `INDETERMINATE` | Commit success or failure could not be proven. TAS[0X] records the ambiguity and hard-latches the runtime. | `null` |

`INDETERMINATE` is intentional. An ambiguous external side effect is not converted into a fictional success or a fictional refusal.

### 5.1 Indeterminate hard latch

After an `INDETERMINATE` terminal receipt:

```text
INDETERMINATE_n ⇒ Halt(TAS[0X])
Halt(TAS[0X]) ⇒ no further generator, evidence, or commit cycle
```

Terminal closure obeys a happens-before rule:

```text
Seal receipt
  → append local witness
  → advance lineage
  → establish HALT
  → invoke external witness callback
```

The halt coordinate therefore becomes authoritative before any externally controlled witness callback can re-enter the runtime. A re-entrant sink observes `RuntimeHalted` rather than starting another effect cycle on top of unresolved state.

The reference runtime has **no in-process unhalt primitive**. External reconciliation must establish the real protected-state root and then instantiate a new TAS[0X] runtime from the reconciled root plus the last terminal lineage coordinates. This prevents later actions from being layered on top of an unresolved effect.

## 6. Refusal as evidence

Every terminal path receives a domain-separated SHA-256 terminal hash and advances the TAS[0X] witness lineage. A refusal therefore changes **evidentiary history** without changing the protected application state:

```text
REFUSED ⇒ ΔS_protected = 0 ∧ ΔΓ_evidence = 1
```

The next SDF envelope must bind its `parent_hash` to the previous TAS[0X] terminal hash and its `sequence` to the next expected sequence. This makes alternate-history evidence fail closed at the agent boundary.

## 7. Witness immutability boundary

The local witness never shares mutable receipt dictionaries with callers or external sinks. TAS[0X]:

1. deep-copies a terminal body before hashing and storage;
2. stores a detached witness record;
3. establishes the indeterminate halt coordinate before external publication when applicable;
4. sends a separate detached copy to `witness_sink`;
5. returns detached copies through the public `witness` property and `TAS0XResult`.

A sink or caller may corrupt its own copy, but it cannot rewrite the local witness record corresponding to the terminal hash.

## 8. Model/provider neutrality

The core has no OpenAI, Gemini, Anthropic, local-model, or LangChain dependency. A model adapter only has to implement:

```python
def generator(request: str, snapshot: AgentSnapshot) -> Mapping[str, Any]:
    ...
```

The evidence provider is a separate callable and receives only a detached proposal, the read-only snapshot, and `EvidenceBinding` metadata. This is deliberate: the same component that invents a proposal must not be able to mint the evidence or receive the effect capability that admits it.

Malformed evidence provider output fails closed and emits a refusal receipt rather than escaping the agent loop as an uncaught exception.

## 9. Tool contract

A `ToolBinding` contains:

- `name` — the only effect selector visible to the proposal;
- `authority_scope` — externally configured accepted authority IDs;
- `invariant(arguments, snapshot)` — deterministic, envelope-independent, fail-closed check whose result must be literal `True`;
- `commit(arguments, expected_root)` — atomic compare-and-commit primitive returning `CommitResult`.

A successful commit must publish the exact `state_root_after` it returns **and that root must differ from the pre-commit root**. A failed commit must not mutate the protected state. Violating an observable no-mutation failure becomes `CONFLICT`; an unprovable mutation state becomes `INDETERMINATE`.

The effect-bearing `ToolBinding` remains inside the reference monitor. It is never supplied to the evidence provider.

## 10. Security properties exercised by tests

The reference tests prove the following executable boundaries:

1. a valid proposal commits only after all predicates pass;
2. a failed tool invariant produces refusal with no effect;
3. an unknown model-selected tool cannot self-authorize;
4. an authority ID embedded in a proposal cannot expand the external scope;
5. an alternate-history parent hash is refused independently of the system invariant slot;
6. type-confused signed claims such as JSON `true` versus `1` are refused;
7. malformed evidence provider output fails closed with a witness receipt;
8. a stale snapshot cannot commit the agent's effect;
9. a claimed successful no-op cannot produce `delta_s = 1`;
10. an ambiguous commit hard-latches the runtime before any later step;
11. refusal advances evidence lineage while protected state remains unchanged;
12. sink/result/caller mutation cannot rewrite the local witness;
13. an external witness-mirror failure cannot erase an already-terminal local receipt;
14. the evidence provider receives metadata without `commit` or `invariant` capabilities;
15. provider mutation of its detached proposal cannot alter the sealed proposal or executed arguments;
16. truthy non-boolean invariant results fail closed;
17. a re-entrant witness sink cannot start another cycle before the indeterminate latch is authoritative.

## 11. Deployment requirement: complete effect mediation

The Python object boundary withholds the registered effect callback from proposal and evidence ports. End-to-end complete effect mediation additionally requires deployment-level capability isolation:

```text
ΔS_protected ≠ 0 ⇒ mutation occurred through the registered compare-and-commit reference monitor
```

Generator, evidence, invariant, and witness adapters must not possess out-of-band credentials or direct write paths to the protected resource. If they can mutate the protected resource outside TAS[0X], no in-process verifier can truthfully guarantee complete mediation.

## 12. Non-claims

TAS[0X] does not prove that a model is conscious, truthful, benevolent, or globally correct. It does not turn signatures into truth. It does not treat possession of evidence as jurisdiction. Its proof boundary is narrower and mechanically testable: **what must be true before this agent is permitted to cause this protected effect?**