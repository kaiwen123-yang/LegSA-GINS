# N6B Decision

Decision rules:
- missing trace or no R-scale change: `not_activated`,
  `N6B2_source_aware_activation_fix`;
- clean neutrality gate violation: `needs_policy_fix`,
  `N6C_source_aware_threshold_review`;
- clean neutral and improved over N6A original:
  `policy_refined_clean_neutral`;
- clean neutral with stress benefit:
  `ready_for_go2_weak_prior_or_extended_source_weighting`;
- clean neutral with weak stress evidence:
  `ready_with_weak_stress_evidence`;
- clean neutral with missing spike response:
  `ready_with_spike_response_caveat`.

Always false:
- `paper_performance_claim`;
- `proposed_factor_claim`;
- output-only correction;
- trace tuning;
- epoch deletion;
- FGO;
- Go2 prior in N6B.
