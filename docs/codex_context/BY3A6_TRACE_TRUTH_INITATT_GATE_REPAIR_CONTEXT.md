# BY3A6 Trace Truth Initatt Gate Repair Context

Stage: `BY3A6_LONG_TRACE_TRUTH_INITATT_YAW_GATE_FORENSIC_AND_SAFE_REPAIR`

Purpose: audit BY3 yaw failure from trace truth through evaluator parsing/base_time, A1 dual-diff yaw input, initatt selection, yaw-update gate behavior, normal NAV output, and final metrics. This stage was normal-only and safety-gated.

Current status: superseded by BY3A7 for BY3 yaw readiness. BY3A6 remains the accepted trace/evaluator/base_time/initatt forensic reference, but BY3A7 repaired the later IMU yaw propagation failure.

Runtime aliases:

- Stage root: `<BY3A6_STAGE_ROOT>`
- Normal runtime root: `<BY3_FULL_MATRIX_ROOT>/BY3A6_TRACE_TRUTH_INITATT_GATE_FORENSIC`
- Prior A1 yaw input source: `<BY3A5B_STAGE_ROOT>`
- BY3 receiver trace source: `<BY3_RECEIVER_ROOT>`

Final decision:

```text
status=BY3A6_position_up_ready_yaw_issue_remaining
trace_truth_lock=BY3A6_trace_truth_locked_parser_safe
evaluator_parser_basetime=BY3A6_evaluator_parser_basetime_valid
a1_input=BY3A6_a1_dual_diff_input_valid_with_caution
initatt=BY3A6_initatt_bug_confirmed
yaw_gate=BY3A6_yaw_gate_logs_missing_but_proxy_suspicious
root_cause=BY3A6_root_cause_repairable_config_and_solver_rerun
repair=BY3A6_repair_ready
normal_rerun=BY3A6_normal_rerun_completed
post_repair=BY3A6_yaw_still_failed_update_gate_issue
ready_for_BY3_degradation_matrix_planning=false
ready_for_BY3_degradation_matrix_planning_scope=none_pending_human_review
ready_for_paper_claims=false
recommended_next_stage=human_review_yaw_issue_or_position_only_BY3B
```

Locked findings:

- The BY3 trace file is the evaluation truth reference. Trace remains evaluation-only and must never be solver input, initatt input, or tuning input.
- The evaluator uses raw numeric `lat`, `lon`, `height`, `yaw`, `pitch`, and `roll` for the current trace. `processed_lat` and `processed_lon` are unsafe for blind evaluation because they are string-like and longitude/latitude-like in the opposite fields.
- Base-time alignment is valid for the current BY3 normal chain; the first trace-relative time and first A1 dual-diff GNSS time differ by milliseconds.
- BY3A5B A1_dual_diff remains the mainline dual-yaw input with caution. Source/schema/starttime coverage are valid, but A1-vs-trace heading quality and yaw-gate behavior are not solved.
- Stage1 and `LegSA_full_EKF` previously used stale first-row A1 yaw near the start of the file instead of the first usable A1 yaw near solver starttime. This was repaired by selecting the first dual GNSS/A1 yaw row at or after the requested starttime.
- The repair did not use trace, final_v23 output, single output, LegSA output, or RMSE minimization.
- The BY3 normal-only rerun completed after initatt repair. No BY3 degradation, artificial degradation, parameter retuning, output substitution, or paper-claim work was performed.
- Post-repair yaw still fails: LegSA_full_EKF yaw RMSE is about 102.64 deg, single is about 103.49 deg, and final_v23 is about 102.57 deg. Position/up sanity remains acceptable, but yaw likely needs a separate yaw-gate/A1-dynamics review.

Hard boundary after BY3A6:

- Do not claim repaired BY3 yaw.
- Do not claim BY3 yaw degradation readiness or paper readiness.
- Do not dismiss trace, A1_dual_diff, or evaluator policy without a later evidence-backed stage.
- Do not run BY3 degradation matrix before explicit human approval.
