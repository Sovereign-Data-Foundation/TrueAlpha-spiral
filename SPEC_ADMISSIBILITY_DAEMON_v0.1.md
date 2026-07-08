# SDF Admissibility Daemon v0.1

**Milestone:** Public Proof Surface v0.1

Core rule:

> SDF witnesses the proof surface. The sovereign retains the substance.

The admissibility daemon is a deterministic runtime gate. It accepts or refuses
proposed state transitions before execution and emits a canonical forensic
receipt for either outcome.

## Required invariants

1. `origin_integrity` — the transition has an origin identifier, type,
   authority source, timestamp, and replay-resistant nonce.
2. `authority_match` — requested actions are inside the actor's authority scope
   and outside denied capabilities.
3. `lineage_continuity` — the proposed parent hash matches the expected parent
   hash.
4. `consent_validity` — consent is present when the authority requires consent.
5. `substance_privacy` — private payloads are neither stored nor revealed on the
   public proof surface.
6. `receipt_generation` — every accepted or refused transition produces a
   canonical hashable receipt.
7. `refusal_legibility` — refusals identify the failed invariants.

## Governing maxim

> No admissibility daemon receipt → no execution.

## Privacy boundary

The daemon records public proof metadata and hashes. It does not require model
weights, user secrets, private payload content, or internal business logic.
