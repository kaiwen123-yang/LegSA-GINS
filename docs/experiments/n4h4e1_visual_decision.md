# N4H4E1 Visual Decision

N4H4E1 reports one of these visual candidate statuses:

- `passed_after_std_unit_fix`: STD units are consistent, corrected figures are
  generated, and manual review is still required.
- `passed_with_remaining_caveat`: visual semantics are fixed but unit evidence
  still needs recovery.
- `failed_std_unit_issue`: STD unit consistency is not established.
- `failed_visual_anomaly`: plot semantics or corrected figures remain
  incomplete.

N5 raw Doppler factor foundation can start only after the corrected N4H4E1
figures pass manual visual review.

N4H4E1 keeps `paper_performance_claim=false`,
`proposed_factor_claim=false`, `trace_solver_input=false`, and
`final_v23_output_solver_input=false`.
