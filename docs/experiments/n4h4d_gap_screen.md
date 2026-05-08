# N4H4D Gap Screen

The N4H4D gap screen classifies parity failures without tuning or hiding the
gap. It is a diagnostic router for the next stage, not a metric repair layer.

Gap categories:

- `input_config`: missing clean input, start/end mismatch, missing initialization
  fields, antlever mismatch, or provenance mismatch.
- `runtime`: update counts too low, yaw/velocity updates absent, feedback not
  applied, or yaw scheme_C rejecting too many updates.
- `output_evaluation`: missing EVAL_NAV, reference reconstruction failure, time
  mismatch, or yaw wrap convention mismatch.
- `mechanization_update`: position, vertical, yaw, roll, or pitch divergence
  after running the closed-loop filter.

Recommended next stages include input/config repair, time alignment repair,
update trigger repair, state feedback sign audit, yaw convention audit,
mechanization debug, evaluator repair, or visual validation if parity passes.

The gap screen never deletes epochs, never rewrites solver output, and never
uses trace as solver input.
