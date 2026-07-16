# CLEAN2 BY2 ablation and Classic-18 protocol

## Identity and namespaces

- Stage: `CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18`
- Dataset: `BY2`
- Clean protocol: `CLEAN_REAL_DATA_FINAL_V23`
- Canonical method count: 4
- Clean factorial count: 16
- Classic case count: 18
- Unique formal process count: 110
- Clean namespace: `BY2_REAL_CLEAN_MODULE_ABLATION`
- Controlled namespace: `BY2_CONTROLLED_DUAL_YAW_DEGRADATION`

C00 is `data_mode=real_by2_raw`, `synthetic_data_used=false`, and
`semisynthetic_data_used=false`. C01..C17 are
`data_mode=real_base_controlled_degradation`, `synthetic_data_used=false`, and
`semisynthetic_data_used=true`. Controlled rows never enter the C00 clean table.

## Fixed method and feature identity

`configs/paper_rebuild/methods.yaml` remains the only canonical method catalog.
The factorial backbone is strong/clean final_v23. Factorial strings are read
left to right as `RD,SA,RP,HV`; they are ablation configurations, not new paper
methods. AB0000 aliases canonical strong and AB1111 aliases canonical full
LegSA.

The unique effective-process key is:

```text
(case_id, structural_method, feature_RD, feature_SA, feature_RP, feature_HV)
```

Canonical aliases do not create another process. The fixed count is
`2 + 16 + 17*4 + 6*4 = 110`.

## Current-provider mapping

The legacy `classic_18cases.yaml` supplies mathematical policy only. Its legacy
providers, full backend, solvers, and performance evidence remain denied. The
active layer is `A1_dual_diff_status_baseline_vector` from GNSS1/GNSS2 status.
The extended GNSS schema is the frozen 15 final_v23 columns followed by
`position_valid`, `velocity_valid`, and `yaw_valid`.

Across all cases, columns 1..13 and validity columns 16..17 remain token-identical
to C00. Outage/downsample changes only column 18. Value perturbations may change
column 14. C10/C14 may change only column 15. IMU, Raw Doppler, Go2 roll/pitch,
and Go2 horizontal-velocity providers remain content-identical to C00.

## Deterministic policy details

- RNG: `numpy.random.Generator(PCG64(seed))`.
- Fractional spike cardinality: `floor(fraction*N + 0.5)` over the currently
  valid yaw epochs, with no replacement; selected indices are sorted before
  application and ledger output.
- C01 starts at valid-yaw index `N//2` and withholds `[time,time+10s)` by setting
  only `yaw_valid=false`.
- Downsample retains the first valid yaw epoch, then retains an epoch only when
  its timestamp minus the last retained timestamp meets the frozen minimum.
- Vector-noise draws are made in row order as east, north, up. Spike selection
  is drawn before direction or sign values.
- Mixed noise, baseline-spike, and yaw-spike sub-operations each restart an
  independent `PCG64(seed)` and execute in that order.
- Perturbed vectors are renormalized to exactly 0.350 m whenever the case policy
  requires nominal-length preservation.

## Frozen descriptive formulas

For response `y` and effect coding `x in {-1,+1}`:

```text
coefficient_i = (1/16) sum(x_i*y)
main_effect_i = 2*coefficient_i
coefficient_ij = (1/16) sum(x_i*x_j*y)
interaction_effect_ij = 2*coefficient_ij
```

Both coefficient and doubled effect are recorded. No p-value, significance, or
universal causal claim is permitted. Final error means the last matched
evaluator epoch's signed component error and corresponding absolute/magnitude
summary; unmatched tail epochs are never silently substituted or deleted.

## Trace, retry, and invalidation gates

Provider generation and solving accept no trace path. Structural health checks
are limited to exit status, files, rows/times, finite values, counters, and file
read ledgers. A technical retry is allowed once only for crash, transient I/O,
resource exhaustion, or lost PTY; every attempt is recorded. Metrics never
trigger retries.

All 110 output bundles must be terminal and hash sealed before offline trace
evaluation starts. Any code, tracked config, executable, or provider change
invalidates the formal set and requires restart from C00.

## Claim boundary

Classic-18 is a controlled dual-yaw degradation pilot on a real BY2 base. It is
not 18 real scenarios, severe-GNSS real-world generalization, independent truth,
or universal robustness evidence. CLEAN2 does not establish universal
superiority.
