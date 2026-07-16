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

## v0.2 hardening rules

The daemon distinguishes **transport ingress** from **constitutional decisions**.
Malformed or non-canonical JSON (including duplicate keys or floating-point
numbers) is rejected before receipt construction and is neither signed nor
recorded. A well-formed transition that fails an invariant receives a canonical
refusal receipt.

Authorization is time-bounded: `origin.issued_at`, the evaluation time, and
`authority.valid_until` must be RFC 3339 timestamps with timezones and satisfy
`issued_at <= current_time < valid_until` after UTC normalization. The requested
actions must be permitted by both `authority_scope` and the immutable
`scope_policy` supplied by the authority snapshot.

Each ledger implementation must consume a replay key atomically. Its key binds
credential identity, authority epoch, authority checkpoint hash, and origin
nonce. An identical authorization retry is idempotent; a different
authorization using the same replay key produces a `CUTOFF`. Parent receipts
must be canonical-hash verified before an admissible child can be appended.
Production integrations must additionally inject a trusted gatekeeper-signature
verifier; a receipt-carried key is never a trust root. A refusal can be recorded without a parent because it does not
advance the state lineage.

## v0.3 authenticated authority and two-head ledger

A transition cannot supply its own authority. The daemon resolves an immutable
`AuthoritySnapshot` from `(credential_id, authority_epoch,
authority_checkpoint_hash)`, verifies a domain-separated authorization message
with the snapshot key, and resolves operation permission through the snapshot's
`scope_policy_hash`. The envelope's authority fields are evidence references,
not an authorization source.

The ledger maintains independent histories. Every durable decision advances the
evidence head. Only an `ADMITTED` decision advances the state head, and its
expected parent must compare equal to the current state head within the same
transaction. A `REFUSED` decision is evidentiary only and can never be used as
a state parent. A production adapter uses SQLite WAL and `BEGIN IMMEDIATE` to
make replay-key uniqueness, head comparison, receipt insertion, and head
updates one transaction.
