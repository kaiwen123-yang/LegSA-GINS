# Degradation Plan N9B

N9B is not started. Do not run N9B during N9A_R0 or N9A_R3.

## Entry Conditions

N9B may start only after:

- N9A_R3 gate is complete.
- N9A_R4 draws only allowed normal-condition figures.
- N9A final review passes.
- User explicitly approves N9B.

## Planned Degradation Families

- GNSS outage.
- sampling and timing degradation.
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

N9B is for stress behavior and failure boundary audit. Claims are not allowed until N9C/N9D review confirms source lineage, alignment, metric sanity, and no substitution.
