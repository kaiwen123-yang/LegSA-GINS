# BY3A4A Lateral Dual-Antenna Yaw Repair Context

BY3A4A_LATERAL_DUAL_ANTENNA_YAW_REPAIR_SEED_EXPLANATION_AND_CONTEXT_MEMORY_LOCK is a BY3 normal-evaluation repair and memory-lock stage after BY3A3.

## Decision

```text
status=BY3A4A_yaw_policy_inconclusive
lateral_dual_antenna_geometry_locked=true
by2_lateral_yaw_policy_recovered=partial
original_BY3A3_yaw_metrics_preserved=true
repaired_yaw_metrics_accepted=false
common_overlap_metrics_ready=true
seed0_9_explanation_created=true
ready_for_BY3_degradation_matrix_planning=false
ready_for_paper_claims=false
recommended_next_stage=manual_review_dual_antenna_yaw_policy
```

## Locked Yaw Rule

- Dual antennas are mounted laterally, perpendicular to the robot forward/head direction.
- Antenna-baseline heading is not robot body heading.
- Body heading requires a plus/minus 90 degree correction from antenna-baseline heading, depending on antenna order and coordinate/frame convention.
- The plus/minus 90 degree choice must not be selected by yaw RMSE minimization alone.
- Yaw references must unwrap before interpolation and wrap only after differencing.
- BY2 accepted yaw policy evidence must be used as reference, but BY3A4A recovered it only as partial for formal offset selection.

## What BY3A4A Did

- Audited BY2 lateral yaw evidence from tracked docs/source.
- Tested current BY3A3, BY2-recovered lateral, lateral plus/minus 90, and baseline-reversal yaw policies using existing BY3A3 solver outputs only.
- Preserved original BY3A3 yaw metrics as historical caution evidence.
- Recomputed strict common-overlap metrics from existing BY3A3 official evaluation error series.
- Regenerated diagnostic figures from real BY3A3 outputs and common-overlap data; these do not supersede BY3A3 yaw figures.
- Generated `seed0-9随机种子说明.md` and `seed0-9随机种子说明.json` under `<BY2_DEGRADATION_TEXT_SUMMARY_ROOT>/00_INDEX`.
- Updated Obsidian BY3/BY2 memory notes.

## Safety Boundary

- No BY3 degradation matrix was run.
- No solver was rerun.
- No parameter retuning was performed.
- Trace remained evaluation-only and was not solver input.
- final_v23, single-baseline, and LegSA outputs were not used as solver inputs.
- No paper claims, final_v23 outperformance claims, or BY3 generalization-success claims are authorized.

## Current Blocker

No physically meaningful and BY2-backed yaw policy passed sanity across `LegSA_full_EKF`, `single_antenna_gnss1_status_KF_GINS`, and `final_v23_dual_antenna_EKF`. BY3 degradation planning remains blocked until manual review resolves the BY3 dual-antenna yaw truth/reference policy.
