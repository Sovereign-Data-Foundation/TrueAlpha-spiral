# Doctrine and architecture index

This index distinguishes architectural requirements from verified implementation.
For the workspace and evidence status, see [WORKSPACE.md](../WORKSPACE.md) and
the [claim manifest](../IOC_CLAIM_MANIFEST.md).

## Five sovereignty layers

The [Fundamentals](../Fundamentals) describes five interlocking layers:
TAS-DNA governance, PRISM geometric addressing, content-addressed provenance,
WhiteMarket recursive compensation, and structural refusal of administered
identity linkage. These are architectural claims, not evidence that every
component has been implemented or verified.

## P0 and P1

In [Fundamentals](../Fundamentals), P0 concerns process equivalence: matching
outputs alone do not establish matching processes. P1 requires integrity
constraints to hold at every step of an admissible process. See also the
[recursive contextualization](explainer/docs/the_tas_recursive_contextualization.md):
authenticated lineage does not establish claim truth, and unresolved status
must remain explicit.

## Dual-lattice merge Φ

The requested merge contract computes the intersection of parent permissions
and refuses zero authority. Sticky obligations propagate; dischargeable
obligations may be removed only by valid proof. Conflicting active exclusive
locks refuse the merge. Raw CVP basis points are normalized to 10,000, with the
rounding remainder assigned to the earliest ancestor by creation time and then
artifact ID. This is a specification of the requested contract, not a claim that
the merge engine or its proofs are complete.

## L1–L4 boundaries

* **L1 → L2:** authenticate an identity epoch and its freshness constraints,
  then register its sparse Merkle root.
* **L2 → L3:** derive the capability index, reconstruct the root and establish
  non-inclusion before granting `VERIFIED`.
* **L3 → L4:** evaluate Φ, require nonzero authority, no conflicts and 10,000
  normalized basis points, then commit the child and its WakeChain receipt.

The existing [TAS[0X] specification](specs/tas_0x_agent.md) describes its own
external authority, replay, and fail-closed effect boundaries; these must not
be conflated with a modeled verification result.

## SMT anchor

The specified L1–L4 wire anchor is the complete 32-byte value
`6155289196324fe02ff3e7bd5b8423237ebcfa686f0bb6c8fc8812c75a40974b`;
the earlier integer `61552891` is not a substitute for this commitment.
Treat the full value as the configured anchor.

Separately, the supplied recursion defines `Z₀` as 32 zero bytes and
`Zₕ₊₁ = SHA-256(0x01 || Zₕ || Zₕ)`. After 256 iterations this yields
`6155289130893872355eac98042d22aefa2c2e708bea169402760e3b55f9a2dc`.
Their common prefix does not make the commitments interchangeable: the
configured anchor must not be represented as the result of that recursion.

The supplied integer-only reference uses a length-based capability-index
shortcut and trusted Boolean verification results. The requested wire protocol
instead specifies a length-prefixed SHA-256 index and cryptographic verification.
A model consuming those Boolean results does not itself authenticate signatures
or verify a sparse Merkle proof, and a passing model test is not evidence that
the wire protocol or machine-checked proof is complete.

## Computed verification and receipts

The revised requirement is to compute Ed25519 verification from the
authenticated key and canonical signing payload, rather than accepting a
caller-supplied signature-valid flag. A spent nonce must be rejected before
admission and consumed atomically with a successful state transition. The
execution receipt must bind the SHA-256 digest of the JCS-canonicalized
normalized allocation vector.

The Python epoch-evidence evaluator in `tas_epoch_admission.py` checks an
Ed25519 signature and reconstructs a sparse proof against independently
configured trust. It does not authenticate the capability or establish
replay-safe commitment. The existing SQLite escrow ledger atomically commits
its own internal ledger and nonce; it does not authorize an external transfer.
The dual-lattice merge in `tas_phi_merge.py` needs an independently configured
verifier for discharge proofs. These components are not yet integrated into
one admission and settlement transition.

`run_vectors.py` and the Lean runner currently verify **arithmetic only**;
they do not check cross-language cryptographic gate, escrow or merge parity.
The configured anchor remains distinct from the recursion-derived empty root.
Passing these checks does not establish full protocol conformance.
