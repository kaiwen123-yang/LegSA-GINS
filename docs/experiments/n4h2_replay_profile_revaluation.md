# N4R2 N4H2 replay profile re-evaluation

N4R2 re-evaluates the N4H2 replay NAV under controlled yaw evaluator profiles:

- `direct_identity`
- `official_candidate_ref_heading_to_math`
- `confirmed_dual_profile`, only if dual_final_v23 parity confirms one

This is evaluator-only. It does not rewrite replay NAV, change solver output,
delete epochs, or relax gates.

Required report fields:

- direct_yaw_rmse_deg
- official_candidate_yaw_rmse_deg
- confirmed_profile_yaw_rmse_deg when available
- horizontal_rmse_m
- up_rmse_m
- yaw_gate_pass_for_each_profile
- solver_output_changed=false
- evaluator_only=true
- trace_solver_input=false

If the official candidate gives yaw around 2.06 deg, the report must mark the
strict yaw gate as false because the project gate is yaw_rmse_deg <= 2.0. Such a
result is near-boundary diagnostic evidence only, not a pass and not proposed
solver performance.

N4R3 adds `confirmed_dual_profile` when the official parity lock confirms one.
Formal yaw pass is false unless that confirmed profile also gives
yaw_rmse_deg <= 2.0. If the confirmed profile fails the replay yaw gate, the
diagnostic candidate remains informative but not formal.
