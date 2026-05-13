# N7C5 Decision

N7C5 decision rules:

- if foot kinematic velocity is plausible, recommend
  `N7C6_foot_kinematic_velocity_factor_activation`
- if foot kinematic velocity is not ready but horizontal velocity plus
  roll/pitch are stable, proceed toward `N8A_no_feedback_FGO_foundation`
- if yaw-rate is stable, keep it as an N8A between-factor candidate
- if relative odometry increments are stable, keep them as an FGO between-factor
  candidate
- if no extra Go2 field is reliable, stop adding EKF factors and proceed toward
  N8A

Always true: no Go2 truth claim, no trace/final_v23 tuning, no formal new
activation in N7C5 except existing validated factors, no paper performance
claim.
