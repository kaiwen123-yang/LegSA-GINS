# N9A_R2 Decision

N9A_R2 writes `N9A_R2_DECISION_REPORT.json`.

Decision rules:

- If `available_algorithm_series_count = 0`, status is
  `N9A_R2_algorithm_outputs_missing`, `ready_for_N9B = false`, and the next
  stage is `locate_or_generate_BY2_normal_algorithm_outputs`.
- If some real outputs exist but the 01-14 real-plot semantics are incomplete,
  status is `N9A_R2_real_plot_materialization_incomplete`,
  `ready_for_N9B = false`, and the next stage is
  `targeted_real_plot_completion`.
- Only if real outputs are sufficient and all semantic audits pass may status be
  `N9A_R2_BY2_normal_real_plot_materialization_complete`; even then N9B requires
  explicit user approval.

The report also preserves the R1 correction:
`N9A_R1_source_lineage_only_plot_materialization_failed`. R1 source/proxy figures
are excluded from completion and cannot justify a compare figure.
