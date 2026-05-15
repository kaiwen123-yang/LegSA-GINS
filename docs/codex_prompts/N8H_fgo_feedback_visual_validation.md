# N8H FGO Feedback Visual Validation Prompt

Use this prompt only on the N8G branch for PR #45 follow-up validation.

Hard boundaries:

- do not merge PR #45;
- do not create N8G/N8H tags;
- do not create a new PR;
- do not modify `/home/kaiwen/KF-GINS`;
- do not use trace/final_v23 outputs as solver input or tuning evidence;
- do not replace EKF NAV with FGO output;
- do not perform output-only correction;
- do not make paper performance or outperform-final_v23 claims.

Runtime role aliases:

- `N8G_REPORT_OUTPUT_DIR`
- `N8G_FIGURE_OUTPUT_DIR`
- `N8H_REPORT_OUTPUT_DIR`
- `N8H_FIGURE_OUTPUT_DIR`
- `N8F_REPORT_OUTPUT_DIR`
- `N8F1_REPORT_OUTPUT_DIR`
- `N8E_REPORT_OUTPUT_DIR`

Tracked docs, configs, and scripts must use role aliases, not local absolute
paths.
