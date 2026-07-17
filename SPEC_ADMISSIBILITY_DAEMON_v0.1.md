# SDF Admissibility Daemon

## Purpose

The daemon is a **decision boundary**: it converts one proposed transition into
one durable result. It never executes the proposed action. An executor may act
only after it receives a durable `ADMITTED` result.

The system has two input classes:

| Input | Outcome |
| --- | --- |
| Malformed transport (invalid JSON, duplicate JSON keys, or floating point values) | Dropped at ingress; no receipt and no ledger write. |
| Well-formed envelope | A durable `ADMITTED`, `REFUSED`, or `CUTOFF` result. |

## Trusted authority flow

The caller provides an envelope naming a credential, authority epoch, and
checkpoint. Those fields are **selectors**, not authority. The daemon resolves
them through an `AuthorityResolver` to an immutable `AuthoritySnapshot` and
then verifies the domain-separated `SDF-AUTH-V1` authorization message using
that snapshot's public key.

The snapshot also supplies the validity window and `scope_policy_hash`. The
scope resolver—not a caller-supplied list—decides whether the requested
operation is permitted for the candidate hash. The envelope is refused when the
snapshot is unavailable, revoked, expired, mismatched, out of scope, or has an
invalid signature.

## Result states

* `ADMITTED`: authority, signature, scope, time, parent, and state-head checks
  passed. The evidence and state histories advance.
* `REFUSED`: the well-formed request is visible as evidence, but **never**
  changes the executable state lineage.
* `CUTOFF`: the daemon could not atomically establish replay or state-lineage
  safety, or durable storage is unavailable. It is not executable and is not
  claimed as durable.

Receipts are signed over the domain-separated `SDF-RECEIPT-V1` body. The
receipt hash covers the decision and its node attestation; append metadata is a
separate durable acknowledgement.

## Two-head ledger law

Each durable result advances the evidence head. Only an admitted result advances
the state head. In the append transaction, an admitted result must present an
`expected_state_parent_hash` equal to the current state head.

\[
\text{ADMITTED} \Rightarrow E_{n+1}, S_{n+1}
\]
\[
\text{REFUSED} \Rightarrow E_{n+1}, S_n
\]

The SQLite adapter uses WAL plus `BEGIN IMMEDIATE` to atomically resolve replay
keys, detect equivocation, compare the state head, append the receipt, and
update the applicable heads.
