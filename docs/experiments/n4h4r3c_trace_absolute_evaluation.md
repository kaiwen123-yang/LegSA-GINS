# N4H4R3C Trace Absolute Evaluation

Trace/reference trajectories are evaluation-only. They must not enter the
solver, config, update model, measurement model, or writer path.

N4H4R3C may use a runtime-only trace path when existing manifests cannot
recover the reference. That path must not be written to tracked docs or config
files.

The absolute evaluator preserves the confirmed dual_final_v23 evaluator profile
for yaw and reports evidence_missing if the trace/reference cannot be recovered.
It does not fabricate absolute metrics.

Boundary flags required in reports:

- `trace_solver_input=false`
- `final_v23_output_solver_input=false`
- `paper_performance_claim=false`
- `proposed_factor_claim=false`
- `output_only_correction=false`
- `bad_epoch_deletion_for_metric=false`
- `no_outperform_final_v23_claim=true`
