# N8A2 FGO Yaw Convention Fix

N8A2 fixes the N8A1 yaw-wrap blocker before PR #39 is merged.

The fix is residual-level: dual-yaw, yaw smoothness, and yaw-rate diagnostic
residuals use shortest-angle wrapping. It is not output-only yaw correction.

Runtime role aliases:

- `N8A_REPORT_OUTPUT_DIR`
- `N8A2_REPORT_OUTPUT_DIR`
- `N8A2_FIGURE_OUTPUT_DIR`

Expected runtime reports:

- `FGO_YAW_RESIDUAL_CONTRACT_REPORT.json`
- `FGO_YAW_FACTOR_REGRESSION_REPORT.json`
- `N8A2_FGO_RERUN_VARIANT_SUMMARIES.json`
- `N8A2_FGO_YAW_FIX_COMPARISON_REPORT.json`
- `N8A2_FGO_YAW_CONVENTION_FIX_DECISION_REPORT.json`
- `N8A2_FIGURE_MANIFEST.json`

Boundary:

- Smoothness factor is retained.
- FGO output remains no-feedback and does not replace EKF NAV.
- Trace/final_v23 outputs are not solver inputs or weight-tuning inputs.
- No output-only correction.
- No paper performance claim.
