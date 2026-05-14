# N8F Legged Candidate Factor Activation Prompt

Goal: activate legged candidate factors inside no-feedback FGO after N8E.

Required factors:

- contact-aware weighting layer
- foot kinematic velocity factor
- Go2 yaw-rate between factor
- Go2 relative odometry between factor

Required boundaries:

- no PR #21 merge or close
- no trace/final_v23 solver input or tuning
- no FGO feedback into EKF
- no FGO output replacement of EKF NAV
- no Go2 truth claim
- no paper performance claim
- no generated figures or runtime outputs committed

Runtime role aliases:

- `N7C5_REPORT_OUTPUT_DIR`
- `N8E_REPORT_OUTPUT_DIR`
- `N8F_REPORT_OUTPUT_DIR`
- `N8F_FIGURE_OUTPUT_DIR`

