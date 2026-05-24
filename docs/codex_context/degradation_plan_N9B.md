# Degradation Plan N9B

N9B is the BY2 staged degradation route. Staged execution is complete through N9C0 global consolidated precheck, but full monolithic N9B2 was not run and is not authorized.

## Current Preparation State

- N9A normal clean completed.
- N9B0/N9B0A/N9B0A1/N9B0A2 completed.
- N9B0B/N9B0C completed.
- N9B1A/N9B1A1 completed.
- N9B1C through N9B1G2 completed.
- N9B1D through N9B1D4 completed.
- N9B1D4 is the current technical pilot source.
- N9B1E passed with C yaw caution and is the current pilot visual/go-no-go source.
- N9B2A/N9B2A1 are full-matrix preparation sources.
- N9B2B completed path lock.
- N9B2B1 completed docs/context update after path lock.
- Batch 0 normal smoke completed.
- Batch 1 deterministic completed.
- Batch 2 position noise completed.
- Batch 3 position spike completed.
- Batch 4 yaw noise completed.
- Batch 5 core module-disable completed; module-stress remains deferred.
- Batch 6 selected mixed cases completed.
- final_v23 external baseline completed and integrated.
- N9C0 global staged consolidation precheck completed.
- Current metrics source: `<N9C0_CONSOLIDATED_PRECHECK_ROOT>/matrix/N9C0_ACTIVE_FINAL_ONLY_METRICS_TABLE`.
- N9C0 active final-only metrics row count: 825.

## Current Next Stage

N9C1 consolidated figure generation may start only after human review of N9C0A.

Additional N9B2 execution must not run unless the human defines a new follow-up.

## Planned Degradation Families

- GNSS outage.
- sampling and timing degradation.
- ratio downsample `every2`, `every5`, `every10`.
- position noise.
- position spike.
- standard deviation inflation.
- receiver velocity degradation, deferred unless real receiver velocity scope is explicitly reopened.
- module-stress cases, deferred.
- Raw Doppler degradation, represented only where approved staged cases ran.
- dual yaw degradation.
- selected combined/mixed degradation.
- randomized seeds for approved seeded cases.

## Matrix Cautions

- `B_gnss_downsample_2Hz` is invalid and superseded.
- Ratio downsample cases `every2`, `every5`, and `every10` are active.
- `C_position_noise` has a yaw caution.
- `H_dual_yaw_noise` has a single-seed caveat.
- C and H require multi-seed treatment in N9B2.
- D position spike multi-seed is recommended.
- Superseded rows must never be used for active conclusions.
- `historical_nominal_none` must not be used for current claims.

## Output Boundary

N9B outputs are runtime artifacts and must not be committed by default:

- NAV / STD / EVAL_NAV.
- RUN_MANIFEST.
- feedback observation CSVs.
- FGO smoothed NAV.
- FGO factor tables.
- generated figures.
- summary/error series.

## Claim Boundary

N9B/N9C0 are for stress behavior and failure boundary audit. Claims are not allowed until N9C visual review and N9D claim-boundary review confirm source lineage, alignment, metric sanity, same-case feedback, and no substitution.
