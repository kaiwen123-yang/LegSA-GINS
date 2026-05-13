# N8A1 FGO Yaw-Delta Policy Review

N8A1 audits the N8A no-feedback FGO output before PR #39 is merged. It checks
yaw convention, yaw wrapping, state/epoch mapping, factor policy, diagnostic
ablation proxies, and runtime-only visual sanity figures.

N8A1 does not modify EKF logic, does not feed FGO output back to EKF, and does
not replace EKF NAV with FGO output.

Required runtime role aliases:

- `N8A_REPORT_OUTPUT_DIR`
- `N8A1_REPORT_OUTPUT_DIR`
- `N8A1_FIGURE_OUTPUT_DIR`

Generated reports:

- `FGO_YAW_CONVENTION_AUDIT_REPORT.json`
- `FGO_YAW_DELTA_DIAGNOSTICS_REPORT.json`
- `FGO_STATE_EPOCH_MAPPING_AUDIT_REPORT.json`
- `FGO_FACTOR_POLICY_REVIEW_REPORT.json`
- `FGO_N8A1_ABLATION_REVIEW_REPORT.json`
- `N8A1_FGO_YAW_DELTA_POLICY_DECISION_REPORT.json`
- `N8A1_FIGURE_MANIFEST.json`
- `n8a1_fgo_yaw_delta_case_review.md`

Boundaries:

- Trace/final_v23 outputs are not FGO solver inputs.
- Diagnostic ablations are not final weight selection.
- Large FGO-vs-EKF yaw delta is diagnostic engineering evidence only.
- Runtime reports and figures are not committed.
- No paper performance claim.
