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

## Fresh base-provider reproducibility gate

Raw Doppler is regenerated from hash-locked source; no prior provider or RINEX
is a runtime input. The only permitted post-`convbin` normalization is the
unique 80-byte `PGM / RUN BY / DATE` line. The resulting observation/navigation
RINEX hashes must be
`570726bf49855905a4ee230cc977910f6f22ed4f6ad480d7aa486833b8ba62dd` and
`5fa101567fcb1a044fd5f63850b5744ef20af568de48ac5f2ca7766978bf9ffa`,
respectively, and all non-target bytes must be unchanged. The legacy CSV value
`73ad4264ae4c4e54be835aea17420575d736ddf38bdfa8908e4fd6e0d33b1d4a` is
retained solely as `frozen_current_clean_anchor_compatibility_identity`, never
as the actual conversion-contract hash. Canonical alias identity and actual
attempt-path execution each have independent contracts and hashes; actual paths
must remain beneath the fresh provider root.

The active time-rebased Raw Doppler CSV must hash to
`a40b9933295f6c2c989884d67cc674313f2fe03113c8acdf1d02ddf28734d722`.
Failure of
any normalized-RINEX, identity-role, path-confinement, or active-provider lock
stops at `BLOCKED_CLEAN2_BASE_PROVIDER_PARITY_FAILED` before C00. The anchor
metadata provenance is CLEAN1 code freeze
`5c807633f699238aa2244a0496881dff71550273` and report commit
`a3909830288b29a8576626408c0eea700abea5ef`; this provenance is not permission
to read their old payloads.

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

## Terminal execution record

The protocol was executed at code freeze
`8b592681de3aef97e33e86e1092664950d8db114`. The fresh chain passed all
fail-closed gates:

- raw integrity `22/22` at pre-provider, post-provider, and post-run;
- exact five-provider content-hash parity;
- 18 deterministic current-provider cases;
- 110 unique formal configurations with 110 first-attempt terminal passes and
  zero metric-driven reruns;
- C00 single/basic/strong/full byte-identical structural parity;
- 1,143 artifacts hash sealed before any trace read;
- 110 exact offline evaluations, each with 56,642 matched epochs, zero
  unmatched epochs, finite output, and coverage 1.0;
- single, position/velocity, basic fixed-std, strong/full identity, module
  counter, aggregate, and figure-render invariants;
- final independent read-only review and the terminal evidence gate.

The terminal machine decision is
`PASS_CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18_FRESH_EVIDENCE_READY_FOR_HUMAN_REVIEW`.
This closes only the authorized BY2 clean factorial and controlled Classic-18
pilot. It does not authorize CLEAN2 PR merge, a CLEAN2 tag, final paper figures,
BY3/XB, or the 60x9 matrix.
