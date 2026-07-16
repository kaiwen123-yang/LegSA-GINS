# Clean Rebuild Data Roles

## Raw Sources

| Source | Allowed role | Forbidden role |
|---|---|---|
| Fixposition raw and status | GNSS observations, quality fields, dual-receiver geometry, Raw Doppler source material | algorithm estimate, truth, direct performance metric |
| Receiver IMU | Fixposition receiver diagnostic only | propagation input or replacement for Go2 body IMU |
| Go2 body log | body IMU/state source, roll/pitch weak prior, horizontal-velocity weak prior, readiness/contact diagnostics | position, velocity, yaw, contact, or pose truth |
| Trace | Fixposition-derived same-source evaluation reference, opened offline only after all four outputs are hash-frozen | online solver input, provider/alignment/start selection, sign/offset choice, tuning, feedback, output correction, independent-ground-truth claim |
| Raw Doppler | source-backed auxiliary velocity observation after fresh provider generation | receiver-velocity alias, algorithm output, truth |

## Dataset Roles

- BY2: first clean smoke and later primary clean-rebuild experiment dataset.
- BY3: independent stress/generalization dataset only after a fresh raw-to-provider chain passes; yaw use requires its own physical-source gate.
- XB/PG: severe-GNSS boundary datasets; no frozen dual-yaw fallback or quality-aware claim is inherited from legacy work.
- All datasets remain raw inputs until their files match `RAW_FILE_HASH_LOCK.csv` and the run manifest records their source hashes.

## Dual-Antenna Geometry

- Physical antenna order: GNSS1 is robot-right and GNSS2 is robot-left under the accepted Go2 FLU installation.
- Baseline vector: `GNSS2 - GNSS1`, pointing along body `+Y_left` for the accepted installation.
- Baseline heading and body yaw are different quantities. A lateral baseline requires a `+/-90 deg` physical conversion depending on antenna order and frame convention; the accepted GNSS2-GNSS1 installation fixes body yaw to wrapped baseline heading plus 90 degrees in the locked NED convention.
- Residuals must be wrap-safe.
- Trace cannot be used to choose antenna order, sign, or the lateral 90-degree transform.
- For the clean BY2 contract, the median short-baseline length must be within `0.20..0.60 m`, and a `3.5..4.5 m` baseline regression is a hard failure. Individual epochs receive an in-band label; they are not deleted for metrics.
- The BY2 gate is not asserted as a universal antenna range for every dataset. Each later dataset requires its own source-backed geometry review; a status base vector must not be assumed to be the robot short baseline.

## Generated Data

Fresh provider files are derived artifacts. They must stay under `<CLEAN_ROOT>`, include source-role and hash lineage, and never overwrite raw files. NAV, STD, EVAL_NAV or their clean equivalents are algorithm outputs and remain untracked. They become eligible evidence only after manifest and dependency audits pass.

For CLEAN1R1C, `<BY2_GO2_BODY>/by2.txt` is the sole propagation IMU source. The fixed measurement lever arm is `[+0.03,+0.03,-0.30] m` in solver FRD for every method. It is not an evaluator point transform. The reference role is `FIXPOSITION_SAME_SOURCE_EVALUATION_REFERENCE`; `engineering_truth_alias=true` records the experiment convention, while `independent_ground_truth=false` limits the claim.

## CLEAN2 controlled-provider role

Classic-18 migrates only the mathematical perturbation policies from the legacy
specification. The active provider layer is the current source-backed
`A1_dual_diff_status_baseline_vector` from GNSS1/GNSS2 status. Across C01..C17,
GNSS position, receiver velocity, propagation IMU, Raw Doppler, and Go2 weak
priors are unchanged; only dual-yaw value, validity, standard deviation, and
case metadata may change. These rows are controlled-degradation evidence, not
clean-real evidence or 18 independent environments.
