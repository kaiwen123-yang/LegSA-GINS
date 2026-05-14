# N8C3 Raw Doppler FGO factor fix

N8C3 fixes RawDopplerVelocityFactor activation in the no-feedback FGO solver
residual vector.

Runtime role aliases:

- N8C2_REPORT_OUTPUT_DIR
- N8C_REPORT_OUTPUT_DIR
- N8B_REPORT_OUTPUT_DIR
- N8A2_REPORT_OUTPUT_DIR
- N5B_REPORT_OUTPUT_DIR
- N8C3_REPORT_OUTPUT_DIR
- N8C3_FIGURE_OUTPUT_DIR

Required evidence:

- Raw Doppler source rows are found.
- Aligned Raw Doppler factor rows are created for FGO epochs.
- Raw Doppler residual rows are appended to the solver residual vector.
- Raw Doppler Jacobian rows are nonzero and touch velocity state blocks.
- raw_doppler_off removes factor rows and residual dimensions.

This is an activation fix only.  It does not feed FGO output back to EKF and
does not replace EKF NAV.
