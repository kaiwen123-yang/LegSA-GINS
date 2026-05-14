# N8C2 decision

N8C2 decision states are engineering-review states, not paper-performance
claims.

Decision priority:

1. Raw Doppler registered but absent from solver residual:
   raw_doppler_activation_missing.
2. Raw Doppler off variant does not actually toggle:
   raw_doppler_toggle_bug.
3. Raw Doppler active but dominated by receiver velocity or smoothness:
   raw_doppler_active_but_dominated.
4. Raw Doppler active and consistent with tiny on/off delta:
   raw_doppler_active_consistent_no_large_delta.
5. Smoothness dimension-normalized residual dominates:
   smoothness_process_model_needs_redesign.
6. Smoothness count dominates while normalized residual is acceptable:
   factor_activation_review_passed_with_smoothness_count_caveat.
7. Otherwise:
   factor_activation_review_passed.

Always enforced:

- no feedback;
- no output substitution;
- no trace/final_v23 solver input;
- no trace/final_v23 weight tuning;
- no paper performance claim.
