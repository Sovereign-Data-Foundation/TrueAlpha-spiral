# Sovereign Data Claim: witness transition draft

Status: proposed specification from the curator's design discussion; not an implemented or sealed calculator extension. The [IOC manifest](../../IOC_CLAIM_MANIFEST.md) describes the narrower existing boundary and deferred obligations.

## Admission inputs

A claim binds canonical payload, claimant signature, nonce, parent state root, authority snapshot, and policy digest. The policy defines accepted proof formats, eligible witness roles, distinct-principal quorum, freshness, revocation, challenge standing, adjudication, and deadlines. Submitted witness evidence is separate from the requirement.

Claimant and witness signatures cover domain-separated canonical bytes. Witnesses attest the same claim, lineage, and policy bindings; multiple signatures by one principal do not supply multiple quorum votes. An environment attestation before execution is not an attestation of a future output.

Time, registry roots, revocations, and challenge status are supplied by the bound snapshot. Mere challenge filing does not invalidate a witness. An eligible unresolved challenge suspends admission only under the pinned policy; a successful post-admission challenge appends a remedial transition and preserves history.

## Commit obligation

Under one protected transaction:

1. Authenticate the receipt and its ADMIT decision.
2. Verify task, payload, policy, state, and authority bindings.
3. Require an unconsumed authorization.
4. Apply the authorized operation and derive the post-state root.
5. Sign and persist the receipt binding before/after state and witness evidence.
6. Persist lineage advancement and nonce consumption.
7. Commit all effects together.

Any failure rolls back protected state, lineage advancement, and nonce consumption. Revalidate at atomic commit or protect the bound state and authority through execution. External irreversible effects require a separately specified effect protocol; a database transaction alone cannot roll them back.

## Refusal and recovery

Refusal causes no protected payload transition and retains audit evidence. Select a deterministic primary failure code under frozen precedence, with subsidiary failures sorted by witness identifier. Missing parent, authority discontinuity, invalid witness, stale witness, and unmet quorum are distinct failures.

The discussed recovery quota is two gate submissions: original plus one authorized appeal. If the original was rejected before execution, recovery is physical execution attempt 1. An appeal carries a new authorizing receipt linked to the original refusal; it must not silently bypass the witness policy.

## Evidence required before promotion

Test invalid claimant signatures, witness substitution, duplicate principals, revoked/stale keys, parent mismatch, replay, concurrent consumption, signing/storage failure, restart, and crash recovery. Enumerate protected writers and demonstrate mediation. Freeze payload and protected-state oracle checks, receipt preimages, fixtures, configuration, and code in a release manifest.

The prior calculator archive is tracked separately in [the artifact register](artifacts.json). These requirements do not establish that archive's current interfaces or capabilities.
