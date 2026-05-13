# N7C2 Decision

N7C2 emits `N7C2_JACOBIAN_VISUAL_DECISION_REPORT.json`.

Decision statuses:

- `visual_readability_not_ready`
- `jacobian_contract_not_ready`
- `go2_horizontal_jacobian_boundary_failed`
- `ready_to_merge_N7C_and_start_N8A`

The ready status only means no N7C2 visual-readability or Jacobian-contract blocker was found. It is a recommendation to merge PR #38 and tag N7C in a later controlled step.

N7C2 itself does not merge PR #38, create a tag, create a new PR, or start N8A.

Always false:

- `paper_performance_claim`
- `go2_velocity_truth_claim`
- `fgo`
- `output_only_correction`
- `trace_solver_input`
- `final_v23_output_solver_input`
