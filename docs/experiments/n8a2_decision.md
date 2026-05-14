# N8A2 Decision

Decision priority:

- `yaw_wrap_fix_failed` if yaw residual wrap tests fail.
- `yaw_delta_still_large_factor_policy_review_needed` if the default fixed
  variant still has wrapped yaw delta RMSE above 10 deg.
- `yaw_convention_fixed_foundation_ready` if wrapped yaw delta improves
  significantly and no gross degradation is introduced.
- `yaw_wrap_fixed_smoothness_policy_caveat` if yaw wrap is fixed but smoothness
  still requires policy review.

If no-smoothness is much better, N8A2 records
`secondary_recommendation=N8B_smoothness_weight_review`; it does not delete
smoothness as the final fix.

Always: no feedback, no output substitution, no output-only yaw correction, no
trace/final_v23 solver input, and no paper performance claim.
