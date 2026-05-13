# N7B3 Contact Model Candidates

N7B3 keeps working on Go2 contact instead of abandoning it after
`contact_v2_not_ready`. It tests multiple diagnostic-only contact models:

- `v1_original`
- `v2_force_percentile_existing`
- `v3_force_speed_joint`
- `v4_speed_dominant`
- `v5_gait_mode_windowed`
- `v6_physical_plausibility_filtered`

Threshold sources are limited to `percentile_force`, `percentile_speed`,
`mode_gait_rule`, and `window_smoothing`. Trace and final_v23 outputs are not
allowed for threshold tuning.

The comparison checks physical plausibility, all-contact avoidance,
all-uncertain avoidance, alternating ratio, walking contact pattern, and
contact-conditioned velocity consistency. These are diagnostic readiness checks
only.
