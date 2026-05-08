# N4R3 dual artifact intake decision

N4R3 handles manual intake of the suspected dual_final_v23 artifact group using
the role alias `DUAL_FINAL_V23_ARTIFACT_ROOT`.

The intake decision requires:

- required files are present outside the repository;
- summary metrics satisfy the dual confirmation window;
- single_antenna-like metrics are rejected;
- no artifact files are committed.

The expected dual envelope is approximately horizontal 0.353 m, up 0.818 m,
yaw 1.814 deg, roll 1.025 deg, and pitch 1.524 deg. A group with horizontal
around 38.947 m or yaw around 41.375 deg is single_antenna-like and must not be
confirmed as dual_final_v23.

Yaw evaluator formalization remains blocked until the official parity lock
confirms a profile. The diagnostic replay value around 2.06058 deg is
near-gate evidence only, not a yaw pass.

Boundary:

- trace_solver_input=false
- output_only_correction=false
- numerical_performance_claim=false
- solver_output_changed=false
