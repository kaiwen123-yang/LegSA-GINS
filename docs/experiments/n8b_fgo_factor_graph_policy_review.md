# N8B FGO Factor Graph Policy Review

N8B reviews the no-feedback FGO factor graph policy after N8A2 fixed yaw residual wrapping.

Runtime role aliases:

- N8A2_REPORT_OUTPUT_DIR
- N8A_REPORT_OUTPUT_DIR
- N7C6_REPORT_OUTPUT_DIR
- N7C5_REPORT_OUTPUT_DIR
- N8B_REPORT_OUTPUT_DIR
- N8B_FIGURE_OUTPUT_DIR

Required outputs include the policy grid, smoothness review, factor-weight review, diagnostic candidate review, real policy ablation summaries, comparison report, decision report, figure manifest, and case review.

Boundaries:

- Real solver reruns are required for N8B ablations; proxy-only evidence is not enough.
- FGO output remains no-feedback and does not replace EKF NAV.
- Trace/final_v23 outputs are not solver inputs and are not used for weight tuning.
- Smoothness is not deleted as a final shortcut.
- Candidate factors remain diagnostic unless a later stage promotes them.
- No paper performance claim is made.
