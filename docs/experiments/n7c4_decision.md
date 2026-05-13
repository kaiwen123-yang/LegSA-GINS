# N7C4 Decision

N7C4 selects a recommended default policy using clean neutrality, stress
diagnostics, and residual/NIS-proxy overconfidence checks.

Decision rules:

- `fixed_1p0` clean neutral and not overconfident: `stronger_policy_ready`
- `fixed_1p5` clean neutral while `fixed_1p0` overconfident: `moderate_policy_ready`
- only `fixed_2p0` stable: `weak_policy_required`
- recalibrated adaptive improves stress without clean degradation:
  `adaptive_policy_ready`
- all stronger variants degrade: `keep_fixed_2p0_and_proceed_N8A`

Always true:

- paper performance claim is false
- Go2 velocity is not truth
- no outperform claim
- no FGO
- vertical/yaw/position Go2 priors remain disabled
