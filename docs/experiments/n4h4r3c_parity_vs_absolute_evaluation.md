# N4H4R3C Parity Vs Absolute Evaluation

N4H4R3C uses three separate metric groups.

A. `port_vs_final_v23_nav_parity`

This compares the source-backed port NAV/EVAL_NAV output with the
dual_final_v23 NAV output. A small A means the port is close to the baseline
output stream. A is not absolute performance.

B. `port_vs_trace_absolute`

This compares the source-backed port NAV/EVAL_NAV output with the
evaluation-only trace/reference trajectory. B is an absolute metric, but it is
not a paper performance claim.

C. `final_v23_vs_trace_absolute`

This compares dual_final_v23 NAV with the same evaluation-only trace/reference
trajectory. C is the reproduced baseline absolute metric. The R3C gate is: A is
small and B is close to C.

R3B-style external closeness checks are invalid when they compare A directly
against external absolute metrics. The corrected comparison must compare
absolute metrics with absolute metrics.
