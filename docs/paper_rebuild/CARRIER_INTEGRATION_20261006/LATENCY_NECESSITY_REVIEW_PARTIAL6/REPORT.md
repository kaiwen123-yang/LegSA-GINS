# PARTIAL6: recorded-search latency necessary condition

Read-only saved-record calculation: no AR, navigation, revalidation or reference reads. Original selected_at, N, owners, release times and retrospective outcomes remain unchanged.

**Test:** measurement_time >= original_selected_at + search.certificate.elapsed_s. Use certificate search wall-clock time, not total frontend elapsed. Assume immediate launch at original selection time, zero queue and zero other overhead. This is an optimistic necessary condition for recorded durations, not a computed real-time schedule or a new valid-measurement result.

Acquisition candidates: 16; started origins: 15; original valid outputs: 70. Necessary-condition passes: **14/70 outputs**. First-export passes among started origins: 5/15. Acquisition-export passes including suppressed candidates: 6/16.

Origins already released by ideal completion: 9. Late origins with later passing outputs: 1. Original release counts: {'RELEASED_UNRESOLVED_ACTIVE_ARC_CHANGED': 6, 'RELEASED_REJECTED_PHASE_FAULT_DIAGNOSTIC': 7, 'RELEASED_REJECTED_LENGTH': 2}.

## Original started origins

| Case | Selected_at | Search s | Ideal completion | First export | Last valid | First release | Original outputs | Passes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| partial_0110.00 | 110.998000 | 11.385654 | 122.383654 | 111.998000 | 111.998000 | 112.198000 | 1 | 0 |
| partial_0128.00 | 128.998000 | 0.446562 | 129.444562 | 129.998000 | 130.198000 | 130.398000 | 2 | 2 |
| partial_0140.00 | 140.998000 | 22.438217 | 163.436217 | 141.998000 | 142.598000 | 142.798000 | 4 | 0 |
| partial_0148.00 | 148.998000 | 0.212703 | 149.210703 | 149.998000 | 149.998000 | 150.198000 | 1 | 1 |
| partial_0168.00 | 168.998000 | 7.699470 | 176.697470 | 169.998000 | 174.598000 | 174.798000 | 24 | 0 |
| partial_0176.00 | 176.998000 | 28.498693 | 205.496693 | 177.998000 | 179.598000 | 179.798000 | 9 | 0 |
| partial_0190.00 | 190.998000 | 0.524537 | 191.522537 | 191.998000 | 191.998000 | 192.198000 | 1 | 1 |
| partial_0200.00 | 200.998000 | 0.131622 | 201.129622 | 201.998000 | 202.798000 | 202.998000 | 5 | 5 |
| partial_0216.00 | 216.998000 | 1.093624 | 218.091624 | 217.998000 | 218.798000 | 218.998000 | 5 | 4 |
| partial_0240.00 | 240.998000 | 3.787703 | 244.785702 | 241.998000 | 243.198000 | 243.398000 | 7 | 0 |
| partial_0248.00 | 248.998000 | 5.639220 | 254.637220 | 249.998000 | 250.398000 | 250.598000 | 3 | 0 |
| partial_0290.00 | 290.998000 | 7.345583 | 298.343583 | 291.998000 | 291.998000 | 292.198000 | 1 | 0 |
| partial_0298.00 | 298.998000 | 25.117220 | 324.115220 | 299.998000 | 299.998000 | 300.198000 | 1 | 0 |
| partial_0304.00 | 304.998000 | 6.118431 | 311.116431 | 305.998000 | 306.798000 | 306.998000 | 5 | 0 |
| partial_0332.00 | 332.998000 | 0.524054 | 333.522054 | 333.998000 | 333.998000 | 334.198000 | 1 | 1 |

## All recorded searches

Modes stay separate. Timeout records are included; no conditioning on certification or acceptance. Quantiles interpolate linearly at (n-1)*p; over-1/2-second counts use strict >.

| Mode | n | Certified | Min | p25 | Median | p75 | p90 | p95 | p99 | Max | >1 s | >2 s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| partial | 120 | 112 | 0.062832 | 0.705492 | 3.120553 | 7.415680 | 21.534079 | 30.000230 | 30.000627 | 30.001614 | 82/120 (68.33%) | 70/120 (58.33%) |

## Boundaries and reproduction

Passing does not newly admit a measurement. We do not reschedule owners, promote suppressed candidates, recreate missed validation, shift measurement time, or revive released origins. An origin whose ideal completion is after its original release is already expired. Even later passing outputs do not prove an implementable delayed pipeline.

Durations are one-run workstation observations, not worst-case execution times or universal lower bounds for optimized code. Queueing, preparation, screening, export and navigation add uncounted delay under the stated model. Integer truth and lifetime false-fix probability remain unavailable. Original retrospective metrics are not replaced.

Acquisition-summary SHA and every original case SHA are checked against tracking pins. Event/CSV/summary valid times and started-origin lists agree. Tables contain no raw observation payloads.

Run the standard-library-only companion script with the original saved acquisition summary and a new output directory:

    python3 scripts/paper_rebuild/carrier_phase/diagnose_solver_latency.py --acquisition-summary FRONTEND/SUMMARY.json --tracking-summary TRACKING/SUMMARY.json --output-dir NEW_OUTPUT --label LABEL
