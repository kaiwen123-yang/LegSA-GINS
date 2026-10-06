# V2: recorded-search latency necessary condition

Read-only saved-record calculation: no AR, navigation, revalidation or reference reads. Original selected_at, N, owners, release times and retrospective outcomes remain unchanged.

**Test:** measurement_time >= original_selected_at + search.certificate.elapsed_s. Use certificate search wall-clock time, not total frontend elapsed. Assume immediate launch at original selection time, zero queue and zero other overhead. This is an optimistic necessary condition for recorded durations, not a computed real-time schedule or a new valid-measurement result.

Acquisition candidates: 6; started origins: 6; original valid outputs: 24. Necessary-condition passes: **7/24 outputs**. First-export passes among started origins: 5/6. Acquisition-export passes including suppressed candidates: 5/6.

Origins already released by ideal completion: 1. Late origins with later passing outputs: 0. Original release counts: {'RELEASED_REJECTED_PHASE_FAULT_DIAGNOSTIC': 4, 'RELEASED_UNRESOLVED_ACTIVE_ARC_CHANGED': 2}.

## Original started origins

| Case | Selected_at | Search s | Ideal completion | First export | Last valid | First release | Original outputs | Passes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| partial_0148.00 | 148.998000 | 0.210019 | 149.208019 | 149.998000 | 149.998000 | 150.198000 | 1 | 1 |
| partial_0154.00 | 154.998000 | 0.253254 | 155.251254 | 155.998000 | 156.398000 | 156.598000 | 3 | 3 |
| partial_0156.00 | 156.998000 | 0.376333 | 157.374333 | 157.998000 | 157.998000 | 158.198000 | 1 | 1 |
| partial_0168.00 | 168.998000 | 7.458144 | 176.456144 | 169.998000 | 173.198000 | 173.398000 | 17 | 0 |
| partial_0332.00 | 332.998000 | 0.522327 | 333.520327 | 333.998000 | 333.998000 | 334.198000 | 1 | 1 |
| partial_0334.00 | 334.998000 | 0.542648 | 335.540648 | 335.998000 | 335.998000 | 336.198000 | 1 | 1 |

## All recorded searches

Modes stay separate. Timeout records are included; no conditioning on certification or acceptance. Quantiles interpolate linearly at (n-1)*p; over-1/2-second counts use strict >.

| Mode | n | Certified | Min | p25 | Median | p75 | p90 | p95 | p99 | Max | >1 s | >2 s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| full | 120 | 120 | 0.015099 | 0.065793 | 0.116204 | 2.081642 | 4.447313 | 6.850215 | 12.015389 | 15.726660 | 32/120 (26.67%) | 30/120 (25.00%) |
| partial | 120 | 115 | 0.045372 | 0.386997 | 1.843951 | 5.831080 | 17.313774 | 27.308172 | 30.000269 | 30.002018 | 69/120 (57.50%) | 58/120 (48.33%) |

## Boundaries and reproduction

Passing does not newly admit a measurement. We do not reschedule owners, promote suppressed candidates, recreate missed validation, shift measurement time, or revive released origins. An origin whose ideal completion is after its original release is already expired. Even later passing outputs do not prove an implementable delayed pipeline.

Durations are one-run workstation observations, not worst-case execution times or universal lower bounds for optimized code. Queueing, preparation, screening, export and navigation add uncounted delay under the stated model. Integer truth and lifetime false-fix probability remain unavailable. Original retrospective metrics are not replaced.

Acquisition-summary SHA and every original case SHA are checked against tracking pins. Event/CSV/summary valid times and started-origin lists agree. Tables contain no raw observation payloads.

Run the standard-library-only companion script with the original saved acquisition summary and a new output directory:

    python3 scripts/paper_rebuild/carrier_phase/diagnose_solver_latency.py --acquisition-summary FRONTEND/SUMMARY.json --tracking-summary TRACKING/SUMMARY.json --output-dir NEW_OUTPUT --label LABEL
