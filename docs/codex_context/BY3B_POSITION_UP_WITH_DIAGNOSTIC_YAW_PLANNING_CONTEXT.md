# BY3B Position Up With Diagnostic Yaw Planning Context

Stage: `BY3B_POSITION_UP_WITH_DIAGNOSTIC_YAW_PLANNING`

Purpose: import the BY3A8 decision, lock accepted BY3 sources, and plan BY3 degradation execution as position/up primary with yaw retained only as diagnostic engineering evidence.

Runtime aliases:

- Stage root: `<BY3B_STAGE_ROOT>`
- Future execution root: `<BY3_FULL_MATRIX_ROOT>/BY3B_POSITION_UP_DEGRADATION_MATRIX`
- Accepted prior root: `<BY3A8_STAGE_ROOT>`
- Accepted IMU source: `<BY3A7_STAGE_ROOT>/repaired_input_or_config/BY3_GO2_PROCESS_DATA_STATIC_BIAS_REPAIRED.imu`
- Accepted dual-yaw source: `<BY3A7_STAGE_ROOT>/repaired_input_or_config/BY3_DUAL_A1_DIFF_15COL_REPAIRED.gnss`

Final decision:

```text
status=BY3B_position_up_diagnostic_yaw_plan_complete
ready_for_BY3C_position_up_degradation_execution=true
human_final_decision_required_before_execution=true
yaw_claim_scope=diagnostic_only
ready_for_paper_claims=false
recommended_next_stage=BY3C_POSITION_UP_DEGRADATION_EXECUTION_BATCH0_TO_BATCH3_LONG_PIPELINE
```

Supersession note: BY3C later executed the approved Batch0-Batch3 position/up subset. BY3B remains planning/precheck evidence only and still does not itself contain degraded inputs, random arrays, solver outputs, evaluator outputs, figures, degradation outputs, or paper claims.

Planning scope:

- Position/up-primary units: `75`
- Diagnostic-yaw units: `43`
- Total case-seed units: `118`
- Planned future solver rows: `311`
- Future command templates: dry-run only with `execute_now=false`

Locked boundaries:

- BY3A7 repaired IMU is the accepted future BY3 IMU input.
- A1_dual_diff short-baseline yaw remains the accepted dual-yaw input with BY3A8 diagnostic caveats.
- HDT and GNSS status long-baseline `rel_pos_n/e/d` remain forbidden as mainline yaw sources.
- Future LegSA degraded cases must generate same-case feedback from each degraded case's stage1 official EVAL_NAV state/estimate columns only.
- BY2 feedback, BY3 normal feedback reuse, trace/error feedback, final_v23 output solver input, single output solver input, and trace solver input remain forbidden.
- BY3B did not generate degraded inputs, random arrays, solvers, evaluators, figures, degradation outputs, or paper claims.
