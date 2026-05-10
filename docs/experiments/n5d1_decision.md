# N5D1 Decision

N5D1 decides whether visual validation evidence has been repaired enough to
restore the N5D conclusion.

Decision rules:

- If mandatory clean ablation figures remain empty, status is
  `visual_validation_not_ready` and the next stage is
  `N5D2_clean_ablation_timeseries_recovery`.
- If clean figures are repaired but spike evidence is missing, status is
  `visual_validation_partial_spike_evidence_missing` and the next stage is
  `N5D2_raw_doppler_spike_trace_recovery`.
- If clean figures are repaired, mandatory coverage passes, spike audit is
  complete, and no source/time blocker is found, status is
  `visual_validation_repaired_ready`.
- If spike evidence indicates a policy issue, status is
  `visual_repaired_but_spike_policy_needed`.

Always false in N5D1:

- `paper_performance_claim`
- `proposed_factor_claim`
- `trace_solver_input`
- `final_v23_output_solver_input`
- `output_only_correction`
- `bad_epoch_deletion_for_metric`

N5D1 does not implement LSIM/OIM, Go2 prior, source-aware weighting, or FGO.
