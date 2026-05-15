# N9A R1 Decision

N9A_R1 decision reports are generated at runtime as
`N9A_R1_DECISION_REPORT.json` under `<N9A_R1_REPORT_OUTPUT_DIR>`.

The initial N9A status is expected to be:

- `initial_n9a_status = N9A_initial_audit_scope_mismatch`
- `initial_n9a_ready_for_N9B = false`

N9A_R1 may report `ready_for_N9B = true` only if all of the following are true:

- raw/status GNSS inputs exist and pass row/time audit;
- trace exists and is recorded as evaluation-only;
- `by2.txt` is recorded as fused Go2 body IMU/high-level input;
- receiver IMU files are recorded as diagnostic-only;
- `BY2_normal_clean` is the only normal-condition case;
- ablation variants are not counted as normal cases;
- 01-14 category coverage is complete or documented not-applicable;
- no algorithm change, no degradation matrix run, no path leak, and no paper
  performance claim.

If any condition fails, the next stage is
`targeted_source_lineage_or_plot_fix`, not N9B.
