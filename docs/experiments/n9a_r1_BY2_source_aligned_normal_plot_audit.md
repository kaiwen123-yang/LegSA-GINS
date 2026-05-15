# N9A R1 BY2 Source-Aligned Normal Plot Audit

N9A_R1 is the corrective continuation for PR #49 on branch
`stage/N9A-BY2-full-plot-audit`. It does not merge PR #49, does not create a
tag, and does not enter N9B.

The initial N9A output is marked as `N9A_initial_audit_scope_mismatch`: it only
discovered and reused the N8K-N8K6 formal ablation archive, and its 30
discovered cases are 30 formal ablation variants rather than BY2 normal
condition cases.

N9A_R1 fixes the scope by using the user-specified BY2 normal-condition source
roles:

- `<GNSS1_RAW>` and `<GNSS2_RAW>`: dual-antenna raw GNSS source audit.
- `<GNSS1_STATUS>` and `<GNSS2_STATUS>`: dual-antenna status and yaw observation audit.
- `<TRACE_TRUTH>`: truth/reference/evaluation only, never solver input.
- `<GO2_BODY_IMU_HIGHLEVEL>`: fused Go2 body IMU/high-level source.
- `<FIXPOSITION_IMU_DATA>`, `<FIXPOSITION_IMU_BIASES>`, and
  `<FIXPOSITION_IMU_TEMP>`: Fixposition receiver IMU diagnostic-only files.

The corrected case model has one main case: `BY2_normal_clean`. Algorithm names
such as `pure_INS`, `final_v23_dual_antenna_EKF`, `Raw_Doppler_EKF`,
`source_aware_EKF`, `Go2_joint_EKF`, `no_feedback_FGO`, and
`selected_feedback_EKF` are comparison series, not normal-condition cases.
N8K ablation variants are retained only as `N8K_ablation_archive`.

Runtime output roles:

- `<N9A_R1_REPORT_OUTPUT_DIR>`
- `<N9A_R1_FIGURE_OUTPUT_DIR>`
- `<N9A_R1_CASE_REVIEW_DIR>`
- `<N9A_R1_SUMMARY_DIR>`
- `<N9A_R1_INDEX_OUTPUT_DIR>`
- `<N9A_R1_PPT_OUTPUT_DIR>`

The 01-14 category schema remains the plotting contract for
`BY2_normal_clean`. Normal-condition degradation meta figures are documented
not-applicable with reason `normal_condition_no_degradation_injection`; outage
and recovery figures are documented not-applicable when no outage interval is
present.

N9A_R1 does not run a degradation matrix, does not modify algorithms, does not
tune trace/final_v23, does not use trace or final_v23 output as solver input,
does not commit runtime artifacts or generated figures, and does not make paper
performance claims.
