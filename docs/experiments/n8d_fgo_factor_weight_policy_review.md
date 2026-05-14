# N8D FGO Factor Weight Policy Review

N8D follows the N8C3 Raw Doppler FGO solver-factor activation fix.

Runtime role aliases:

- N8C3_REPORT_OUTPUT_DIR
- N8C2_REPORT_OUTPUT_DIR
- N8C_REPORT_OUTPUT_DIR
- N8B_REPORT_OUTPUT_DIR
- N8A2_REPORT_OUTPUT_DIR
- N5B_REPORT_OUTPUT_DIR
- N7C6_REPORT_OUTPUT_DIR
- N8D_REPORT_OUTPUT_DIR
- N8D_FIGURE_OUTPUT_DIR

N8D reviews no-feedback FGO factor weights using solver-visible diagnostics:
whitened residuals, dimension-normalized residuals, factor counts, NIS proxy,
finite-output checks, and factor toggle integrity.

Trace/final_v23 are evaluation-only and are not used for weight tuning.

FGO output is not fed back into EKF and does not replace EKF NAV.

No paper performance claim is made.
