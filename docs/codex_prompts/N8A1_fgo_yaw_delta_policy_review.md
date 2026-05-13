# N8A1 FGO Yaw-Delta Policy Review Prompt

Goal: audit N8A FGO yaw delta before merging PR #39.

Do not merge PR #39, do not create an N8A/N8A1 tag, do not create a new PR, and
do not enter N8B.

Hard boundaries:

- Do not modify EKF logic.
- Do not feed FGO output back to EKF.
- Do not replace EKF NAV with FGO output.
- Do not use trace/final_v23 output as FGO solver input.
- Do not use trace/final_v23 output to tune FGO weights.
- Do not commit runtime reports, figures, raw data, `by2.txt`, `FGO_SMOOTHED_NAV.csv`, or `FGO_FACTOR_TABLE.csv`.
- Do not make paper performance or outperform-final_v23 claims.

Runtime role aliases:

- `N8A_REPORT_OUTPUT_DIR`
- `N8A1_REPORT_OUTPUT_DIR`
- `N8A1_FIGURE_OUTPUT_DIR`

Expected tracked additions are the N8A1 audit modules, runner, audit scripts,
docs, and tests only.
