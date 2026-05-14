# N8E Formal Engineering Ablation With Caveats

N8E summarizes the final engineering ablation matrix after N8D FGO factor
weight policy review.

Runtime reports are generated through role aliases only:

- N5B_REPORT_OUTPUT_DIR
- N6B_REPORT_OUTPUT_DIR
- N7C6_REPORT_OUTPUT_DIR
- N8A2_REPORT_OUTPUT_DIR
- N8B_REPORT_OUTPUT_DIR
- N8C3_REPORT_OUTPUT_DIR
- N8D_REPORT_OUTPUT_DIR
- DUAL_FINAL_V23_ARTIFACT_ROOT
- N8E_REPORT_OUTPUT_DIR
- N8E_FIGURE_OUTPUT_DIR

N8E records EKF front-end module evidence and no-feedback FGO backend evidence
in one engineering matrix. It keeps the Raw Doppler FGO result as
active-but-low-marginal-value rather than treating it as a failure.

N8E is not a paper performance claim. It does not claim outperform final_v23.
FGO output is not fed back into EKF and does not replace EKF NAV. Trace and
final_v23 outputs are not solver input and are not used for weight tuning.
