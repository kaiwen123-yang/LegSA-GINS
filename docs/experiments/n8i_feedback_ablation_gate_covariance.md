# N8I Feedback Ablation Gate/Covariance

N8I follows N8H visual validation and refines FGO feedback EKF policy.

Scope:

- build a feedback policy grid for mode, gate, covariance, and window variants;
- run real EKF replay variants when runtime inputs are provided;
- generate runtime-only reports and figures under role aliases;
- select a feedback strategy recommendation using solver-visible diagnostics.

Boundary:

- FGO feedback remains an EKF update and pseudo-measurement path;
- no output substitution or direct NAV overwrite;
- no trace/final_v23 tuning;
- no future-data feedback;
- no paper performance claim.

Runtime report role: `N8I_REPORT_OUTPUT_DIR`.

Runtime figure role: `N8I_FIGURE_OUTPUT_DIR`.
