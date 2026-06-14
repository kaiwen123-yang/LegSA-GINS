# PAPER10X Current Context

## Stage

`PAPER10X_GIT_CONTEXT_CLEANUP_AND_COMMIT`

## Purpose

PAPER10X cleans the main repository Git context after PAPER10A/PAPER10B/PAPER10B_R1/PAPER10B_R2B/PAPER10B_R2C. It classifies dirty tracked and untracked files, keeps runtime payloads out of Git, updates safe context documents, synchronizes the project Obsidian vault, and freezes the next experiment route.

This stage is documentation and Git hygiene only. It does not run algorithms, solvers, evaluators, DA, LC, GINav, MATLAB, RTKLIB, contact-aided variants, complete FGO, random generation, degraded-input generation, or PAPER10B_R2 continuation.

## Current Fixed Facts

- `LegSA_full_EKF` is the verified main algorithm.
- `final_v23_dual_antenna_EKF` is the strong external Dual-Antenna GNSS/INS EKF baseline.
- Raw Doppler and source-aware LSIM/OIM R scaling are accepted mainline modules.
- BY2 is the main full-metric dataset.
- PAPER10B_R1 closed BY2 120 x 5 source-aware ablation.
- PAPER10B_R2B closed BY3 120 x 5 source-aware rows, but BY3 remains poor-heading stress with yaw diagnostic-only.
- PAPER10B_R2C repaired default `python3` and reinstalled conda without creating a new default env.

## Current Boundaries

- No universal source-aware superiority.
- No comprehensive outperform-final_v23 claim.
- No BY3 ordinary yaw generalization.
- No complete nine-factor FGO claim.
- No completed `LegSA_QA_Fallback_EKF` claim.
- No full contact-aided InEKF claim.
- No trace online.
- No receiver `imu-data.csv` as Go2 body IMU.
- No per-case tuning.

## Next Route

Steady submission route:

```text
PAPER10C_GO2_HIGH_LEVEL_PRIOR_EVIDENCE_FREEZE
PAPER10E_FINAL_PROPOSED_METHOD_MATRIX_AND_COMPARISON_FREEZE
PAPER10F_FIGURE_TABLE_AND_MANUSCRIPT_EXPERIMENT_SECTION
```

Stronger innovation route:

```text
PAPER10C_GO2_HIGH_LEVEL_PRIOR_EVIDENCE_FREEZE
PAPER10B2_MULTI_STATE_QUALITY_MANAGEMENT_CLOSURE
PAPER10D_SELECTED_FGO_FEEDBACK_EVIDENCE_FREEZE_optional
PAPER10E_FINAL_PROPOSED_METHOD_MATRIX_AND_COMPARISON_FREEZE
PAPER10F_FIGURE_TABLE_AND_MANUSCRIPT_EXPERIMENT_SECTION
```

PAPER10C is mandatory. PAPER10B2 is conditional on keeping multi-state quality management as a contribution. PAPER10D is optional and should not be the first priority.
