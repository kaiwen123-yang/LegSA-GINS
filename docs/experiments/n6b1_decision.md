# N6B1 Decision Rules

N6B1 maps visual evidence to bounded engineering decisions:

- empty mandatory figures -> `visual_validation_failed_empty_figures`;
- source stuck at cap -> `visual_validation_failed_weight_policy`;
- clean gross degradation -> `visual_validation_failed_clean_degradation`;
- missing spike visibility with otherwise OK evidence ->
  `visual_validation_passed_with_spike_response_caveat`;
- all checks passing -> `visual_validation_passed`.

The recommended next stage may continue review of the already-open N7A PR, but
N6B1 itself does not create N7B, merge PR #32, tag N6B1, add Go2 priors, or add
FGO.

All N6B1 decisions keep:

- `paper_performance_claim=false`;
- `no_outperform_final_v23_claim=true`;
- `final_v23_output_solver_input=false`;
- `trace_solver_input=false`;
- `output_only_correction=false`;
- `bad_epoch_deletion_for_metric=false`.
