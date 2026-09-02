# TAS[0X] Agent — Zero-Authority Effect Runtime

**Status:** implementation specification, v0.1  
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
Proposal P ───────────────┐
                         │
External Evidence E ─────┤
External Tool Binding T ─┤ authority scope + invariant + commit primitive
External State Root S ───┤
External Context C ──────┤
External Trust Registry ─┤
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

## 3. Commit predicate

For proposal `P`, evidence envelope `E`, protected state root `S_n`, context `C`, registered binding `T`, and TAS[0X] lineage coordinates `(K_n, q_n)`:

```text
Commit(P) ⇒
    Authentic(E)
  ∧ LineageWellFormed(E)
  ∧ AuthorityScope(E, T)
  ∧ ContextMatch(E, C)
  ∧ NonceFresh(E)
  ∧ Claim(E) = P
  ∧ Genesis(E) = Genesis_external
  ∧ Parent(E) = K_n
  ∧ Sequence(E) = q_n
  ∧ Invariant_T(P, S_n)
  ∧ CompareAndCommit_T(P, expected=S_n)
```

No predicate compensates for another. Any failed predicate prevents the TAS[0X] transition from committing.

## 4. Terminal states

| Status | Meaning | `delta_s` claim |
|---|---|---:|
| `ADMITTED` | All proof obligations passed and the effect published a new protected-state root. | `1` |
| `REFUSED` | A pre-commit predicate failed. No TAS[0X] effect was attempted. | `0` |
| `CONFLICT` | The protected state no longer matched the snapshotted parent, or atomic commit explicitly rejected without mutation. | `0` for this agent transition |
| `INDETERMINATE` | Commit success or failure could not be proven. TAS[0X] halts and does not claim success or failure. | `null` |

`INDETERMINATE` is intentional. An ambiguous external side effect is not converted into a fictional success or a fictional refusal.

## 5. Refusal as evidence

Every terminal path receives a domain-separated SHA-256 terminal hash and advances the TAS[0X] witness lineage. A refusal therefore changes **evidentiary history** without changing the protected application state:

```text
REFUSED ⇒ ΔS_protected = 0 ∧ ΔΓ_evidence = 1
```

The next SDF envelope must bind its `parent_hash` to the previous TAS[0X] terminal hash and its `sequence` to the next expected sequence. This makes alternate-history evidence fail closed at the agent boundary.

## 6. Model/provider neutrality

The core has no OpenAI, Gemini, Anthropic, local-model, or LangChain dependency. A model adapter only has to implement:

```python
def generator(request: str, snapshot: AgentSnapshot) -> Mapping[str, Any]:
    ...
```

The evidence provider is a separate callable. This is deliberate: the same component that invents a proposal must not be able to mint the evidence or authority that admits it.

## 7. Tool contract

A `ToolBinding` contains:

- `name` — the only effect selector visible to the proposal;
- `authority_scope` — externally configured accepted authority IDs;
- `invariant(arguments, snapshot)` — deterministic, fail-closed check;
- `commit(arguments, expected_root)` — atomic compare-and-commit primitive returning `CommitResult`.

A successful commit must publish the exact `state_root_after` it returns. A failed commit must not mutate the protected state. Violating either rule becomes `INDETERMINATE` rather than an admission.

## 8. Security properties exercised by tests

The reference tests prove the following executable boundaries:

1. a valid proposal commits only after all predicates pass;
2. a failed tool invariant produces refusal with no effect;
3. an unknown model-selected tool cannot self-authorize;
4. an authority ID embedded in a proposal cannot expand the external scope;
5. an alternate-history parent hash is refused;
6. a stale snapshot cannot commit the agent's effect;
7. an ambiguous commit cannot be mislabeled as success;
8. refusal advances evidence lineage while protected state remains unchanged;
9. an external witness-mirror failure cannot erase an already-terminal local receipt.

## 9. Non-claims

TAS[0X] does not prove that a model is conscious, truthful, benevolent, or globally correct. It does not turn signatures into truth. It does not treat possession of evidence as jurisdiction. Its proof boundary is narrower and mechanically testable: **what must be true before this agent is permitted to cause this protected effect?**
