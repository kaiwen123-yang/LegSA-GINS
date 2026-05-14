# N8C2 FGO factor activation review

N8C2 reviews whether active/default FGO factors have direct residual evidence,
proxy residual evidence, true toggle behavior, and bounded contribution
classification.

Runtime role aliases:

- N8C_REPORT_OUTPUT_DIR
- N8B_REPORT_OUTPUT_DIR
- N8A2_REPORT_OUTPUT_DIR
- N5B_REPORT_OUTPUT_DIR
- N7C6_REPORT_OUTPUT_DIR
- N7C5_REPORT_OUTPUT_DIR
- N8C2_REPORT_OUTPUT_DIR
- N8C2_FIGURE_OUTPUT_DIR

Required reports:

- FGO_FACTOR_ACTIVATION_AUDIT_REPORT.json
- FGO_RESIDUAL_WHITENING_REVIEW_REPORT.json
- FGO_RAW_DOPPLER_FACTOR_ACTIVATION_REVIEW.json
- FGO_FACTOR_TOGGLE_INTEGRITY_REPORT.json
- N8C2_FGO_FACTOR_ACTIVATION_DECISION_REPORT.json

Boundaries:

- No FGO feedback to EKF.
- No FGO output substitution for EKF NAV.
- No trace/final_v23 solver input or weight tuning.
- Candidate factors remain diagnostic unless a later stage formally promotes
  them.
- No paper performance claim.
