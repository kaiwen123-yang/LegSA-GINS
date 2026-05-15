# N9A_R1 BY2 Source-Aligned Normal Plot Audit Prompt

Continue on PR #49 branch `stage/N9A-BY2-full-plot-audit`. Do not merge PR #49,
do not create a tag, and do not enter N9B.

Initial N9A must be marked as scope mismatch if it only searched
`<BY2_PLOT_AUDIT_ROOT>` plus N8K-N8K6 outputs, found no
`<GNSS1_RAW>`/`<GNSS2_RAW>`/`<GNSS1_STATUS>`/`<GNSS2_STATUS>`/`<TRACE_TRUTH>` or
`<GO2_BODY_IMU_HIGHLEVEL>`, and counted 30 formal ablation variants as cases.

N9A_R1 must use runtime-only source paths passed as command-line arguments and
write tracked docs/config/scripts with aliases only:

- `<BY2_FIXPOSITION_ROOT>`
- `<GNSS1_RAW>`
- `<GNSS2_RAW>`
- `<GNSS1_STATUS>`
- `<GNSS2_STATUS>`
- `<TRACE_TRUTH>`
- `<GO2_BODY_IMU_HIGHLEVEL>`

`<TRACE_TRUTH>` is evaluation-only. `<GO2_BODY_IMU_HIGHLEVEL>` is the fused Go2
body IMU/high-level source. Fixposition receiver IMU files are diagnostic-only.

The case model is `BY2_normal_clean` plus algorithm comparison series. N8K
formal ablation variants are archive context only.

Boundaries: no algorithm change, no N9B degradation matrix, no trace/final_v23
tuning, no solver input substitution, no generated runtime artifacts committed,
and no paper performance claim.
