# BY3A4C Yaw Reference Reconstruction Context

Stage: `BY3A4C_GIT_HISTORY_YAW_REFERENCE_RECONSTRUCTION_AND_VISUAL_VALIDATION`

## Decision

```text
status=BY3A4C_yaw_not_evaluable_position_only_generalization_ready
historical_BY2_yaw_fix_recovered=true
selected_reference_sign=official_ref_sign_minus
BY3_yaw_status=not_evaluable
ready_for_BY3_degradation_matrix_planning=true
ready_for_BY3_degradation_matrix_planning_scope=position_up_only
yaw_degradation_claims=false
ready_for_paper_claims=false
recommended_next_stage=BY3B_POSITION_ONLY_DEGRADATION_PLANNING_OR_HUMAN_REVIEW
```

## Recovered BY2/N4 History

- N4H2 replay had good position but old yaw around 93 deg.
- N4H2C documented the `process_data` status-yaw chain:
  `yaw_baseline=-atan2(rel_e,rel_n)`, `yaw_body=sign*yaw_baseline+offset`, `yaw_ned=90-yaw_body`.
- N4R/N4R2 candidate convention transforms were diagnostic only.
- N4R3 locked direct-identity yaw only after the correct dual_final_v23 artifact was confirmed.
- N4H2D selected `official_ref_sign_minus`, reconstructed the dual official reference from official NAV plus error_series, and invalidated the old 93 deg yaw as a stale/wrong-reference mapping.
- Fresh N4H2D replay yaw was about 1.98 deg under the reconstructed dual official reference.

## BY3 Result

Recovered and diagnostic yaw profiles were applied to existing BY3A3 outputs only. No BY3 yaw truth/reference profile was accepted. BY3 yaw is `not_evaluable`; original BY3A3/BY3A4A bad yaw metrics remain historical invalid-reference evidence.

Position/up common-overlap metrics and diagnostic figures were generated as audit evidence. They do not authorize BY3 yaw degradation or paper claims.

## Hard Rules

- Do not redo blind plus/minus 90 yaw searches as the main method.
- Do not choose yaw policy by RMSE minimization alone.
- Do not use trace, final_v23 output, LegSA output, or single-baseline output as solver input.
- Do not claim repaired BY3 yaw metrics.
- Do not claim BY3 yaw degradation readiness while `yaw_status=not_evaluable`.
- Keep `ready_for_paper_claims=false`.
