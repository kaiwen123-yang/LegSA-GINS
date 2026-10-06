# Selected-class search optimization

This is an implementation/performance change to the existing exact objective,
not a changed observation model, acceptance threshold or integer-fix claim.

## Implementation

- The original full integer vector remains in the search. For a proper subset
  class key, condition on each selected coordinate at the initial best seed's
  value plus/minus one. Two LAMBDA integer seeds for all other coordinates are
  lifted back to the original vector and evaluated using the unchanged full
  residual plus exact per-epoch length constraints. These candidates supply
  feasible upper bounds only; conditional ILS is not a partial-search certificate.
- Cache the relaxed baseline covariance, gain and marginal maximum eigenvalues
  by suffix depth. Each node still computes its own conditional center and uses
  the unchanged maximum of marginal sphere lower bounds. Correlated epoch
  marginals are never summed into an invalid lower bound.
- Optional conditional-seed failures fall back to the original exact search.
  Seed generation consumes the same wall-time budget. Timeout and node-limit
  exits remain uncertified and cannot produce an admitted candidate.
- No full-to-partial certificate reuse, covariance adjustment, future-guided
  subset choice or changed integer dimension was introduced.

## Verification

59 relevant unit/oracle tests passed in Ubuntu 22.04 WSL, including independent
dense GLS and raw-residual exhaustive two-class checks, nontrivial unimodular
coordinates, original versus cached node bounds, conditional-seed failure and
timeout behavior, and the partial frontend contracts. The old fixed 3D mock
explicitly declines optional 2D conditional seeds so its original poor-seed
full-search test remains intact.

## Bounded real-model regression

Three previously prepared selection windows were reused: 180, 182 and 192 s.
Each received exactly one new CILS call with a 30 s / 100,000 node budget.
Each also used 16 internal conditional ILS seed calls, with zero seed failures.
The exact subset and full-label vector were checked against the old pilot.
Only the five selection epochs entered the solver. No future admission, native
navigation, evaluator or reference payload was run/read.

| Start (s) | Old solver time (s) | New time (s) | Old certificate | New certificate | Best full cost | New second full cost |
|---:|---:|---:|---|---|---:|---:|
| 180 | 18.092 | 11.953 | global | global | 392.440804712 | 2337.614354962 |
| 182 | 30.000 | 10.146 | timeout | global | 497.545059165 | 3939.856999915 |
| 192 | 30.000 | 2.668 | timeout | global | 504.015512591 | 3191.143499124 |

All three best full integer vectors and full costs equal the old candidates.
At 180 s the certified second vector and cost also match exactly. At 182 and
192 s the old second candidates were uncertified high-cost upper bounds
(approximately 2.76 and 2.68 million); the new results certify the actual second
selected classes. This is not evidence of improved position/heading accuracy.

These are development-window timings on the same WSL environment, not a
controlled hardware benchmark or a held-out scientific comparison. Per-window
runtime still reaches approximately 12 s; this implementation is not yet a
real-time 5 Hz AR frontend. Seed quality and avoiding repeated depth algebra
improved these three cases, but search remains data dependent.

## Records

The old FRONTEND pilot is untouched. New scratch records are in
<CARRIER_INTEGRATION_SCRATCH>/SEARCH_OPTIMIZATION_V1: INPUTS.json, CALLS.jsonl,
three full result JSON files, SUMMARY.json and COMPARISON.csv. The input record
pins the actual edited solver bytes used for this run; root owns the subsequent
Git commit. The reusable regression driver is the sibling
search_optimization_regression_v1.py. No scientific call was retried.

Executed solver SHA256: `5f9c231ccdcabb0998bf435c02a923634ea1af2c7d19356c1df30fa7842a36b0`.
