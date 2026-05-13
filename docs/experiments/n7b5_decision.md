# N7B5 Decision

N7B5 decides whether the N7B4 frame ambiguity can be narrowed enough for N7C formal review of a horizontal Go2 velocity weak prior.

Decision rules:
- if top candidates are equivalent for horizontal velocity and horizontal-only diagnostic activation is stable, recommend `N7C_go2_horizontal_velocity_weak_prior_activation`;
- if top candidates are not equivalent but one frame remains stable, recommend `N7C_go2_best_frame_velocity_weak_prior_review`;
- if horizontal diagnostics degrade, recommend `N8A_no_feedback_FGO_foundation`;
- if no diagnostic updates occur, recommend `N7B6_activation_debug_or_N8A`.

Always false:
- paper performance claim;
- formal Go2 velocity prior in N7B5;
- formal Go2 yaw prior;
- Go2 velocity truth claim;
- trace tuning;
- final_v23 tuning;
- FGO claim.
