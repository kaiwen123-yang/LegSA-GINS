# N7C6 Decision

Decision rules:

- Gross clean degradation gives `joint_factor_not_ready`.
- Roll/pitch overconfidence gives `horizontal_factor_only_recommended`.
- Neutral `joint_rp1p6_hv1p0` with acceptable NIS gives
  `go2_proprioceptive_joint_factor_ready`.
- Neutral `joint_rp1deg_hv1p0` with acceptable NIS gives
  `stronger_go2_proprioceptive_joint_factor_ready`.
- No benefit over horizontal-only gives `horizontal_factor_sufficient`.

Always true:

- Go2 body-state is not truth.
- Go2 position/yaw/vertical velocity priors remain disabled.
- No trace/final_v23 tuning.
- No FGO.
- No paper performance claim.
- No outperform final_v23 claim.
