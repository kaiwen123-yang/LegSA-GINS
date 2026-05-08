# N4R2 yaw evaluator convention policy

N4R2 defines controlled yaw evaluator profiles so the N4R candidate can be
tested without turning it into solver tuning.

Profiles:

- `direct_identity`: `est=identity`, `ref=identity`, formal baseline.
- `official_candidate_ref_heading_to_math`: `est=identity`,
  `ref=heading_to_math_yaw`, diagnostic until dual_final_v23 parity confirms it.
- `diagnostic_ref_neg`: diagnostic grid profile only.
- `diagnostic_ref_plus90`: diagnostic grid profile only.

Policy boundary:

- solver_input_modified=false
- solver_output_changed=false
- evaluator_only=true
- trace_solver_input=false
- output_only_correction=false
- numerical_performance_claim=false

The candidate profile comes from N4R single_antenna-like official parity. It is
not a formal yaw offset, antenna installation selection, or output correction.
It remains diagnostic until dual_final_v23 artifact parity confirms the same
convention.
