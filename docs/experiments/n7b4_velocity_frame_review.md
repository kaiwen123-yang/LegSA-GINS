# N7B4 Velocity Frame Review

N7B4 scores Go2 velocity frame hypotheses with two diagnostic evidence groups.

Internal evidence:

- derivative of Go2 position versus transformed Go2 velocity;
- short-window velocity integration versus Go2 position delta;
- yaw/yaw-speed consistency;
- heading alignment as a weak diagnostic only.

External cross-source evidence:

- transformed Go2 velocity versus receiver-native velocity;
- transformed Go2 velocity versus raw Doppler velocity.

These are consistency scores, not truth errors. The output frame status can be `resolved_for_diagnostic`, `ambiguous_but_testable`, or `unresolved`.

Boundary: `"diagnostic_only": True`, `"paper_performance_claim": False`, `"trace_solver_input": False`, `"final_v23_output_solver_input": False`, `"fgo": False`.
