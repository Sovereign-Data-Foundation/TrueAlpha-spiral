# Canonical Vertical Slice

`CanonicalVerticalSlice` is the concrete execution boundary where the current TrueAlphaSpiral reference implementation turns a candidate operation into a TAS_DNA gene whose decision is either admitted or refused.

This document tracks the behavior established by the implementation and refusal-path tests merged in `TrueAlpha-spiral/TrueAlpha-spiral#364`.

## One output grammar

The vertical slice does not emit one species of object for success and another for failure. Both branches are represented through the same minimal transition grammar:

\[
G_i=(o_i,c_i,a_i,x_i,p_i,\Phi_i,d_i,r_i).
\]

The branch is expressed by

\[
d_i\in\{\mathrm{ADMITTED},\mathrm{REFUSED}\}.
\]

This is TAS_DNA at the execution boundary.

## Boundary ordering

The slice receives an operation together with an authority snapshot, a context snapshot, a WakeChain, and optionally a sovereign runtime.

The current ordering is:

\[
\text{proposal}
\rightarrow
\text{verification}
\rightarrow
\text{admissibility}
\rightarrow
\text{runtime check when applicable}
\rightarrow
\text{decision}
\rightarrow
G_i
\rightarrow
\text{WakeChain evidence}.
\]

Runtime authorization is attempted only after verifier admission. A runtime anomaly can still convert the resulting gene to `REFUSED` before authorized state progression is recorded.

## Admission path

When verification succeeds and runtime does not fail closed, the slice emits an admission receipt and creates

\[
G_i.d=\mathrm{ADMITTED}.
\]

The gene is appended to evidence and becomes part of authorized state progression:

\[
\mathcal E_{n+1}=\mathcal E_n\Vert G_i,
\]

\[
S_{k+1}=F(S_k,G_i).
\]

## Refusal path

When verification fails, or when runtime produces a null-collapse/failure condition, the slice creates a refusal receipt and

\[
G_i.d=\mathrm{REFUSED}.
\]

The same gene is appended to evidence while authorized state remains unchanged:

\[
\mathcal E_{n+1}=\mathcal E_n\Vert G_i,
\]

\[
S_{k+1}=S_k.
\]

A refusal is therefore a represented TAS_DNA event without an authorized state transition.

## Two projections of the same gene chronology

The current `WakeChain` exposes two views:

1. `evidence_timeline()` — Genesis plus admissions and refusals.
2. `state_sequence()` — Genesis plus admitted links only.

PR #364 directly exercises that distinction. After one admission followed by one refusal, the evidence timeline contains three links while the admitted state sequence contains two.

These are not two competing definitions of state. They are two projections of the same lineage-bearing event stream.

## Recovery anchoring

A refused gene remains part of evidence but does not become the recovery checkpoint.

If admitted gene \(G_a\) is followed by refused gene \(G_r\), then

\[
\operatorname{RecoveryAnchor}(G_r)=G_a.
\]

At Genesis, a refusal before any admitted successor anchors recovery to `GENESIS`.

This preserves the refused datum without promoting it into authorized state.

## Runtime null collapse

PR #364 adds direct coverage for runtime null-collapse.

If verification admits the operation but the sovereign runtime returns no valid token indices, the slice assigns

```text
RUNTIME_NULL_COLLAPSE
```

and creates a refused TAS_DNA gene.

Thus:

\[
\operatorname{Verified}(x)
\land
\operatorname{RuntimeNullCollapse}(x)
\Rightarrow
G_i.d=\mathrm{REFUSED}.
\]

Evidence advances; authorized state does not.

## Deterministic refusal receipt under fixed payload

The refusal receipt is content-addressed from a canonical payload containing the bounded refusal fields, including the resolved evaluation timestamp.

Let \(p_i^-\) be that payload:

\[
R_i^-=\operatorname{SHA256}(\operatorname{CanonicalEncode}(p_i^-)).
\]

PR #364 threads the vertical slice's resolved timestamp into `RefusalArtifact`. That removes wall-clock variance from repeated evaluation of the same bounded refusal payload:

\[
p_a^-=p_b^-
\Rightarrow
R_a^-=R_b^-.
\]

The claim is intentionally bounded: attempts at different timestamps are different payloads.

## Refusal-path theorem

The implementation now directly tests:

\[
\boxed{
G_i.d=\mathrm{REFUSED}
\Rightarrow
\mathcal E_{n+1}=\mathcal E_n\Vert G_i
\land
S_{k+1}=S_k
\land
\operatorname{RecoveryAnchor}=\operatorname{LastAdmittedCheckpoint}
}
\]

and, when the bounded refusal payload is held fixed:

\[
\boxed{
p_a^-=p_b^-
\Rightarrow
R_a^-=R_b^-}
\]

These are executable invariants over the same TAS_DNA datum.

## Source milestone

This section corresponds to merged pull request `TrueAlpha-spiral/TrueAlpha-spiral#364`, **Add refusal-path coverage for CanonicalVerticalSlice and stabilize refusal receipt hashes**.
