# N7B2A Metric Namespace Guard

N7B2A adds a metric namespace guard for Go2-stage reports.

Allowed namespaces:

- `parity_to_final_v23`
- `absolute_to_trace`
- `cross_source_consistency`
- `readiness_diagnostic`

N7A roll/pitch deltas such as the No-Go2 Roll/Pitch 0.043/0.031 deg values are
`parity_to_final_v23`, not absolute accuracy.

final_v23 official absolute roll/pitch around 1.0/1.5 deg can be mentioned only
as reference context in docs. It is not a proposed-method accuracy claim.

Go2 velocity comparison is `cross_source_consistency`, not truth error. Go2
velocity is not truth.

Boundary:

- `metric_namespace_missing=false` after the N7B2A guard assigns namespaces.
- `paper_performance_claim=false`
- `no_outperform_final_v23_claim=true`
- `trace_solver_input=false`
- `final_v23_output_solver_input=false`
