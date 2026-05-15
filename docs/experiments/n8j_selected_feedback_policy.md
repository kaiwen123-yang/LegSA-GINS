# N8J Selected Feedback Policy

N8J locks the selected N8I policy:

- policy name: `n8i_selected_conservative_feedback`;
- feedback mode: `horizontal_velocity_attitude_feedback`;
- gate policy: `combined_conservative_gate`;
- covariance policy: `inflation_auto_from_residual_proxy`;
- window policy: `window_5s_stride_1s`;
- primary position feedback: disabled;
- horizontal velocity feedback: enabled;
- attitude feedback: enabled.

The selected policy report is `N8J_SELECTED_FEEDBACK_POLICY_REPORT.json`.

The audit requires the selected policy to match N8I and records
`hidden_policy_change=false`.
