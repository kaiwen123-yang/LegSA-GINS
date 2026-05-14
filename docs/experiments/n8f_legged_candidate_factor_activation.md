# N8F Legged Candidate Factor Activation

N8F formally activates the N7C5/N8E legged candidate factors inside the
no-feedback FGO chain.

Activated components:

- `ContactAwareWeightingLayer`: R-scale layer only, no direct state residual.
- `FootKinematicVelocityFactor`: horizontal velocity residual on `vN/vE`.
- `YawRateBetweenFactor`: wrapped yaw between residual on `yaw_k/yaw_{k+1}`.
- `RelativeOdometryBetweenFactor`: horizontal position-increment between
  residual on `p_k/p_{k+1}`.

Boundary:

- No FGO feedback into EKF in N8F.
- No FGO output substitution for EKF NAV.
- No trace or final_v23 solver input.
- No trace or final_v23 weight tuning.
- No Go2 contact, velocity, yaw, or position truth claim.
- No paper performance claim.

Runtime outputs are written only under `N8F_REPORT_OUTPUT_DIR` and
`N8F_FIGURE_OUTPUT_DIR`.

