# A04 / F04 manuscript-role decision rule (pre-registered)

Status: PRE-REGISTERED. Written before any solver launch on BY2H or BY2O.
Once committed, this file may not be edited except to append the outcome section.

## Purpose

Freeze, before any result of the new sequences is seen, the rule that decides whether
the manuscript's proposed method is `A04` (`AB1011`, Source-Aware disabled) or `F04`
(`AB1111`, Source-Aware enabled). No metric, window, threshold, seed, or sequence may be
added or changed after any result of BY2H or BY2O has been seen.

## Evidence that may decide

Only the two unseen same-day, same-route BY2 sequences:

- `BY2H` — natural poor-heading-quality run, stage
  `CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE`;
- `BY2O` — natural single-antenna occlusion run, stage
  `CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE`.

`C00` and the Canonical-541 matrix are already known and are excluded from the decision.
They remain descriptive evidence in the paper.

## Preconditions (fail-closed)

1. Raw hash lock, fresh providers, BY2-frozen parameters (no per-sequence tuning), the
   frozen offline evaluator, and the same-source reference caveat apply unchanged.
2. `BY2H` must pass its own yaw physical gate: median A1 baseline length within
   `0.20..0.60 m`, no `3.5..4.5 m` regression, per-epoch out-of-band epochs labelled
   and never deleted. If the gate fails, the heading test is not executable and `A04`
   is the proposed method by default.
3. For `BY2O` the occlusion window is defined from input-side evidence only (GNSS2
   availability, satellite count, receiver status flags) and written to the stage root
   before the evaluator is run. Metrics inside the window are reported but never used
   for the decision, because the same-source reference is itself degraded there.
4. Both sequences are evaluated with the exact evaluator identity recorded in
   `CONVERSATION_HANDOFF.md`; no time-offset, sign, frame, or alignment search.

## Metrics

Wrap-safe yaw RMSE and yaw P95 over the full evaluation window; horizontal RMSE and
Up RMSE over the full window and, for `BY2O`, over the outside-occlusion window.
All values are taken from the frozen aggregate tables, never recomputed by hand.

## Tests

Heading benefit (on `BY2H`, full window):

```text
yawRMSE(F04) <= yawRMSE(A04) - 0.50 deg
OR
yawP95(F04)  <= 0.5 * yawP95(A04)
```

`0.50 deg` is one third of the frozen `1.5 deg` yaw measurement standard deviation and
about a quarter of the C00 yaw RMSE; halving of P95 is the tail-protection magnitude
already observed in the Canonical-541 matrix (`31.9 -> 15.4 deg`).

Position cost bound (on `BY2H` full window, `BY2O` full window, and `BY2O`
outside-occlusion window; every window must pass):

```text
horizontalRMSE(F04) <= 1.10 * horizontalRMSE(A04)
AND
upRMSE(F04)         <= 1.10 * upRMSE(A04)
```

## Decision

`F04` is the proposed method (Source-Aware as core) only if the heading-benefit test
passes AND the position cost bound holds on every required window. Otherwise `A04` is
the proposed method and Source-Aware is reported as a protection extension with its
full cost. Values exactly at a threshold resolve toward `A04`. If `BY2O` fails its
preconditions, the position bound is evaluated on `BY2H` only.

## Invariants regardless of outcome

- Both outcomes are reported in the manuscript.
- Source-Aware is described as always-on (clean touch rate about 84.8%), never as
  nominal-silent or fault-active.
- Position results are described as "no catastrophic regression", never as improvement.
- The Canonical-541 module conclusions are not re-interpreted by this decision.
- The strong dual-yaw configuration (`AB0000`) is presented as the unpublished backbone
  of the proposed method inside the ablation chain, not as an external baseline.

## Commitment

This file is committed and its commit hash is recorded in
`docs/paper_rebuild/CONVERSATION_HANDOFF.md` before the first solver launch on
`BY2H` or `BY2O`.

## Outcome (append only, after both sequences are sealed and evaluated)

```text
BY2H yaw gate:            <PASS|FAIL>
BY2H yawRMSE  A04 / F04:  <value> / <value>
BY2H yawP95   A04 / F04:  <value> / <value>
BY2H hRMSE    A04 / F04:  <value> / <value>
BY2H upRMSE   A04 / F04:  <value> / <value>
BY2O window (input-side): <t0>..<t1>
BY2O hRMSE  full / outside  A04 / F04: <values>
BY2O upRMSE full / outside  A04 / F04: <values>
Heading test:             <PASS|FAIL>
Position bound:           <PASS|FAIL>
Proposed method:          <A04|F04>
Evidence commit / attempt: <hash> / <attempt id>
```
