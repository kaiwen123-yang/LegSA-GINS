# N7C1 Decision

N7C1 maps visual validation evidence to a bounded next-stage recommendation.

Decision states:

- `visual_validation_failed_empty_figures`
- `visual_validation_failed_vertical_boundary`
- `visual_validation_failed_clean_degradation`
- `visual_validation_failed_stress_instability`
- `visual_validation_passed_with_weak_stress_evidence`
- `visual_validation_passed`

Passing N7C1 does not implement N8A. It only says that N7C figures and plotted-data coverage are sufficient to support the already bounded N7C engineering conclusion.

Always false:

- `paper_performance_claim`
- `go2_velocity_truth_claim`
- `trace_solver_input`
- `final_v23_output_solver_input`
- `output_only_correction`
- `fgo`

Always disabled:

- Go2 vertical velocity prior
- Go2 position prior
- Go2 yaw prior
