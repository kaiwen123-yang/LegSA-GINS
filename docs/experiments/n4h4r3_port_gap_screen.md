# N4H4R3 Gap Screen

The gap screen classifies failures without changing the solver output. It checks
input/config evidence, runtime update counts, output/evaluation availability,
and filter-level divergence categories.

The screen can recommend config/input repair, runtime-loop/update-count repair,
yaw convention review, writer/evaluator repair, or filter math gap work. These
recommendations are diagnostic next-stage labels, not performance claims.

No local trace is allowed as solver input, no final_v23 output is substituted
into the proposed solver path, no epoch is deleted for metrics, and no
output-only correction is applied.
