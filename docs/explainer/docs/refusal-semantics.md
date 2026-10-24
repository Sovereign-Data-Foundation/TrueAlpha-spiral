# Refusal Semantics

A refusal is a TAS_DNA gene whose decision is `REFUSED`.

Admission and refusal use the same canonical transition grammar:

\[
G_i=(o_i,c_i,a_i,x_i,p_i,\Phi_i,d_i,r_i).
\]

For refusal:

\[
d_i=\mathrm{REFUSED}.
\]

## Refusal at both levels

Let the authenticated lineage be

\[
\Gamma_n=(G_1,\ldots,G_n)
\]

and let

\[
\Pi_A(\Gamma_n)
\]

be its admitted projection.

A refused gene extends full lineage:

\[
\Gamma_{n+1}=\Gamma_n\Vert G_i,
\]

but leaves the admitted projection unchanged:

\[
\Pi_A(\Gamma_{n+1})=\Pi_A(\Gamma_n).
\]

Therefore authorized operational state is preserved:

\[
O_{n+1}=O_n.
\]

At the same time, for the irreducible full state

\[
S_n=(O_n,\Gamma_n),
\]

we have

\[
S_{n+1}=(O_n,\Gamma_n\Vert G_i)\neq S_n.
\]

So refusal preserves operational state while advancing constitutive state.

## Evidence timeline vs state sequence

The reference implementation exposes this distinction through two WakeChain views:

- `evidence_timeline()` contains Genesis, admissions, and refusals,
- `state_sequence()` contains Genesis and admissions only.

After one admission followed by one refusal:

```text
evidence timeline: Genesis -> Admission -> Refusal
state sequence:    Genesis -> Admission
```

The admission-only `state_sequence()` is the implementation projection \(\Pi_A(\Gamma)\). It does not replace the full state \(S=(O,\Gamma)\).

## Refusal-path invariant

For refused gene \(G_i\):

\[
\boxed{
G_i.d=\mathrm{REFUSED}
\Rightarrow
\Gamma_{n+1}=\Gamma_n\Vert G_i
\land
\Pi_A(\Gamma_{n+1})=\Pi_A(\Gamma_n)
\land
O_{n+1}=O_n
\land
S_{n+1}\neq S_n
}
\]

## Recovery anchor

A refused gene remains in authenticated lineage but does not become an authorized recovery checkpoint.

Let

\[
\operatorname{Tip}_A(\Gamma_n)=\operatorname{Tip}(\Pi_A(\Gamma_n)).
\]

Then

\[
\operatorname{RecoveryAnchor}(G_i)=\operatorname{Tip}_A(\Gamma_n).
\]

At Genesis, recovery anchors to `GENESIS` until an admitted successor exists.

## Runtime null collapse

If verifier admission is followed by runtime null-collapse, the vertical slice records

```text
RUNTIME_NULL_COLLAPSE
```

and emits a refused TAS_DNA gene:

\[
\operatorname{Verified}(x)
\land
\operatorname{RuntimeNullCollapse}(x)
\Rightarrow
G_i.d=\mathrm{REFUSED}.
\]

The refusal extends \(\Gamma\) but not \(\Pi_A(\Gamma)\).

## Deterministic refusal identity

Let \(p_i^-\) be the canonical refusal payload and

\[
R_i^-=H(\operatorname{Encode}(p_i^-)).
\]

Then

\[
p_a^-=p_b^-
\Rightarrow
R_a^-=R_b^-.
\]

Merged PR `TrueAlpha-spiral/TrueAlpha-spiral#364` passes the resolved evaluation timestamp into the refusal artifact so repeated evaluation of the same bounded refusal payload yields the same receipt identity instead of drifting with wall-clock time.

## Refusal is non-compensatory

A refusal is not equivalent to committing a mutation and later undoing it.

TAS prefers

\[
\text{verify}\rightarrow\text{admit}\rightarrow\text{commit}
\]

over

\[
\text{commit}\rightarrow\text{detect}\rightarrow\text{compensate}.
\]

The refused TAS_DNA gene proves that the candidate reached the boundary without becoming an admitted operational transition.
