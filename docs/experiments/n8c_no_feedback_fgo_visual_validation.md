# N8C No-Feedback FGO Visual Validation

N8C validates the N8B recommended `weak_yaw_smoothness_policy` through runtime-only figures and reports.

Runtime role aliases:

- N8B_REPORT_OUTPUT_DIR
- N8A2_REPORT_OUTPUT_DIR
- N8C_REPORT_OUTPUT_DIR
- N8C_FIGURE_OUTPUT_DIR

The validation checks FGO-vs-EKF trajectory, horizontal/up/yaw/roll/pitch deltas, default-vs-weak yaw behavior, factor residual proxies, factor on/off deltas, and candidate diagnostic boundaries.

Boundaries:

- FGO output remains no-feedback and does not replace EKF NAV.
- Trace/final_v23 are not solver inputs.
- Candidate factors remain diagnostic-only.
- Runtime reports and figures are not committed.
- No paper performance claim is made.
