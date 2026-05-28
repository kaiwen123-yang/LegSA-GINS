# BY3A0 to BY3E Generalization Report

BY3A0_TO_BY3E_GENERALIZATION_AND_BY2_DEGRADATION_REPORT_REORG completed the context lock, BY3 source inventory, BY3 kick-event alignment, BY3 candidate input generation, BY2 text-summary generation, and BY2 degradation figure archive reorganization.

BY3 normal solver and evaluator execution remain blocked by input/provider handoff gates. No BY3 degradation matrix, representative validation, paper claim, or final_v23/LegSA parameter retuning was run.

## Runtime Roots

- BY3 stage root: `<BY3_STAGE_ROOT>`
- BY3 full-matrix placeholder root: `<BY3_FULL_MATRIX_ROOT>`
- BY3 receiver source: `<BY3_RECEIVER_ROOT>`
- BY3 Go2 body/high-level source: `<BY3_GO2_BODY_SOURCE>`
- BY2 degradation evidence archive: `<BY2_DEGRADATION_ARCHIVE_ROOT>`
- Obsidian BY3 notes: `<OBSIDIAN_BY3_GENERALIZATION_ROOT>`

## Decisions

```text
status=BY3_solver_or_evaluator_blocked
by3a0_context_lock=complete
by3a_inventory=complete_read_only_inventory
by3b_alignment=BY3B_alignment_passed_no_trace_tuning
by3c_input_generation=partial_candidate_inputs_with_provider_blockers
by3d_solver_execution=not_run_blocked_by_gate
by3e_official_evaluation=not_run_no_successful_solver_outputs
by2t_text_summaries=complete_from_active_final_only_metrics
by2f_archive=complete_copy_only_manifested
ready_for_BY3_degradation_matrix_planning=false
ready_for_paper_claims=false
recommended_next_stage=repair_BY3_solver_or_evaluator
```

## Scope Notes

BY3A inventory and body IMU audit are source-role reports only. BY3B alignment uses the BY2 event-normalized kick policy as a fixed policy reference and does not tune against trace. Trace remains evaluation-only after alignment. BY3 receiver IMU remains diagnostic only. `by3.txt` remains Go2 body/high-level source data, not truth.

BY3C generated candidate Go2 IMU and GNSS-status inputs, but BY3A1 later found strict BY2 parity mismatches in delimiter/header, IMU column count, single-baseline schema, and original time-normalization policy. BY3D and BY3E did not run. No solver/evaluator output, BY3 normal metrics, BY3 degradation/full matrix, random generation, degraded-input generation, final_v23 modification, algorithm math change, feedback-policy change, or paper claim was produced.

BY2T generated per-family text summaries from the active final-only BY2 metrics table while excluding superseded rows, `historical_nominal_none`, and `B_gnss_downsample_2Hz`. BY2F copied existing BY2 figures into `<BY2_DEGRADATION_ARCHIVE_ROOT>` with manifests and hash-based deduplication where feasible; original BY2 runtime and figure evidence was not moved or deleted.
