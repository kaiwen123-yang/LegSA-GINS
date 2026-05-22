# Degradation Plan N9B

N9B is the full BY2 degradation matrix route. N9B2 full execution is not authorized by N9B2B1.

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
- N9B2B1 is docs/context update after path lock.

## Entry Conditions For Execution

N9B2 execution may start only after:

- N9B2B1 human review completes.
- N9B2C batch0 smoke plan and optional execution precheck is approved.
- N9B2D batch0 normal parity smoke is reviewed.
- N9B2E batch1 deterministic execution is explicitly approved by the human.
- staged batch reviews support proceeding.

## Planned Degradation Families

- GNSS outage.
- sampling and timing degradation.
- ratio downsample `every2`, `every5`, `every10`.
- position noise.
- position spike.
- standard deviation inflation.
- receiver velocity degradation, only if real receiver velocity exists.
- Raw Doppler degradation.
- dual yaw degradation.
- Go2 attitude degradation.
- Go2 velocity degradation.
- contact degradation.
- foot kinematic degradation.
- yaw-rate and relative-odometry degradation.
- combined degradation.
- randomized seeds.

## Matrix Cautions

- `B_gnss_downsample_2Hz` is invalid and superseded.
- Ratio downsample cases `every2`, `every5`, and `every10` are active.
- `C_position_noise` has a yaw caution.
- `H_dual_yaw_noise` has a single-seed caveat.
- C and H require multi-seed treatment in N9B2.
- D position spike multi-seed is recommended.
- Superseded rows must never be used for active conclusions.

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

N9B is for stress behavior and failure boundary audit. Claims are not allowed until N9C/N9D review confirms source lineage, alignment, metric sanity, same-case feedback, and no substitution.
