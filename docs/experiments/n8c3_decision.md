# N8C3 decision

Decision priority:

1. Missing Raw Doppler source: `raw_doppler_source_missing`.
2. No aligned factors: `raw_doppler_alignment_blocker`.
3. Not in solver residual vector: `raw_doppler_solver_injection_failed`.
4. raw_doppler_off does not change residual dimension:
   `raw_doppler_toggle_failed`.
5. Active but tiny on/off delta: `raw_doppler_active_consistent_or_dominated`.
6. Active and stable weight sensitivity:
   `raw_doppler_fgo_factor_activation_fixed`.
7. Active but degraded weight sensitivity:
   `raw_doppler_active_weight_policy_needs_review`.

Always enforced:

- no feedback;
- no output substitution;
- no trace/final_v23 solver input;
- no trace/final_v23 weight tuning;
- no paper performance claim.
