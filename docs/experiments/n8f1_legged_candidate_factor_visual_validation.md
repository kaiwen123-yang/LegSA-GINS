# N8F1 Legged Candidate Factor Visual Validation

N8F1 visually validates the activated N8F legged candidate FGO factors.

Scope:

- Check N8F runtime reports and factor tables.
- Generate required visual figures for contact weighting, foot kinematic
  velocity, yaw-rate between, relative odometry between, candidate stack, solver
  effect, and summary panels.
- Review plot data coverage, factor signal, plot semantics, and visual sanity.

Boundary:

- Diagnostic engineering visual evidence only.
- No EKF modification.
- No FGO feedback into EKF.
- No FGO output substitution for EKF NAV.
- No trace/final_v23 solver input or tuning.
- No Go2 truth claim.
- No paper performance claim.

Runtime outputs are written only under `N8F1_REPORT_OUTPUT_DIR` and
`N8F1_FIGURE_OUTPUT_DIR`.

