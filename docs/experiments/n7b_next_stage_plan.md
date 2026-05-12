# N7B Next-Stage Plan

N7B closes only the readiness question. It does not activate new Go2 priors.

Possible next stages:

- `N7B2_contact_threshold_review` if contact labels are invalid or too
  uncertain.
- `N7B2_velocity_frame_or_quality_review` if Go2 velocity is cross-source
  inconsistent.
- `N7C_go2_velocity_contact_weak_prior_activation` if contact and velocity
  readiness passes.
- `N7C_go2_yaw_rate_weak_prior_review` if yaw-speed is the stronger future
  signal.
- `N8A_no_feedback_FGO_foundation` if extended Go2 priors are skipped.

All future activation work must preserve:

- Go2 position is not truth.
- Go2 velocity is not truth.
- Cross-source velocity comparison is not truth error.
- Trace remains evaluation-only and is not solver input.
- final_v23 output is not solver input.
- No output-only correction.
- No epoch deletion.
- No paper performance claim.
- No outperform final_v23 claim.
