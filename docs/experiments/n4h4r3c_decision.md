# N4H4R3C Decision

Decision rules:

- If `corrected_parity_status=backbone_parity_passed`, the next stage is
  `N4H4E_visual_validation_for_source_backed_port`.
- If `corrected_parity_status=parity_to_finalv23_passed_absolute_missing`, the
  next stage is `N4H4R3D_absolute_trace_evaluation_recovery`.
- If `corrected_parity_status=evaluator_or_reference_mismatch`, the next stage
  is `N4H4R3D_reference_evaluator_fix`.
- If `corrected_parity_status=port_parity_failed`, the next stage is
  `N4H4R3D_port_parity_gap_fix`.

The decision is an engineering backbone decision only. It is not a proposed
factor result, not an outperform final_v23 claim, and not a paper performance
claim.

Always false:

- proposed factor claim;
- output-only correction;
- tuning;
- epoch deletion;
- trace solver input;
- final_v23 output solver input.
