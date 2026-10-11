# Gating energy evaluation: protocol draft

Status: proposed protocol, no measured energy result supplied by this curation change.

The hypothesis is whether gating avoids specified execution costs at equivalent legitimate completion. This evaluation makes no claim about replacing centralized computation.

## Primary measurement

Use end-to-end paired energy differences, baseline minus TAS. Component accounting is diagnostic and must not double-count initial gate, appeal gate, persistence, cleanup, or payload costs. Legitimate payload residuals normalize over the evaluation population; admitted-invalid residuals compare TAS execution/remediation against baseline execution/remediation. Never infer component energy from batch resolution alone.

Evaluate both required output and protected terminal state against a frozen oracle for every legitimate exposure. Incomplete or non-equivalent completion withholds savings claims.

## Frozen controls

- Policy development: exact stratified 70/30 split, separated from measurement calibration.
- Batch calibration: disjoint representative fixtures; start at 1,000 requests and double until BOTH modes satisfy E_batch >= 100q and T_batch >= max(10 seconds, 100τ), at the same batch size.
- q is the counter quantum; τ is the configured sampling interval.
- Evaluation: 30 paired batches initially, rotating mode order and seeded interleaving.
- Identical submitted bytes and authority-event sequences within a pair.
- Preserve replay, stale, and revoked prerequisites; restore identical initial state between batches and preserve state within each batch.
- Diagnostic fixture blocks are separate and excluded from the primary aggregate.
- Hold payload budgets and legitimate utility constant; report false refusals and recovery.
- If counters are inaccessible, report timing and energy as unmeasured.

## Population and repetitions

The discussed corpus has 100,000 tasks: 85,000 legitimate and 15,000 invalid. Invalid cost tiers contain 10,500 cheap, 3,750 expensive, and 750 catastrophic items. The held-out population contains 30,000 tasks, including 25,500 legitimate tasks.

Calibrated K determines exposure count. Report distinct tasks separately from exposures. Balance cluster repetitions deterministically; repeated clusters within a batch need isolated instance state. Freeze category counts, scheduling, PRNG stream consumption, authority events, and actual generator code before execution.

The proposed generator uses RFC 8439 ChaCha20 with a 32-bit counter and 96-bit nonce. Any displayed derived key must be recomputed from the seed, not accepted as an assertion.

## Statistical result

For each pair p, ΔE_p = E_baseline,p - E_TAS,p. Report the mean and paired 95% interval. With 30 suitably independent pair differences, the proposed Student t interval is mean ± 2.04523 * s / sqrt(30); assess dependence and assumptions before using it.

Report instrumentation uncertainty separately. An expanded conservative decision interval does not automatically have calibrated joint 95% coverage. A resolved interval wholly above zero supports savings, wholly below zero supports increased energy, and containing zero is inconclusive at this resolution. Failed calibration also prevents a resolved verdict.

All illustrative telemetry remains mock data. Freeze the protocol, code, configuration, fixtures, expected results, and environment evidence under recorded digests before claiming a sealed evaluation.
