# N7B4 Contact Probability Model

N7B4 builds contact confidence features from Go2 fields only: foot force, foot speed in body frame, foot position z, mode/gait, body height, Go2 body velocity norm, yaw speed, temporal derivatives, and short-window statistics.

Important interpretation:

- `foot_speed_body` is body-frame relative speed.
- High `foot_speed_body` is not by itself a swing truth label.
- Contact probability is diagnostic and not a ground-truth contact label.

Candidate probability models:

- `force_probability`
- `speed_probability`
- `force_speed_fused_probability`
- `gait_mode_windowed_probability`
- `physical_plausibility_probability`
- `ensemble_probability`

Selection uses not-all-contact, not-all-uncertain, alternating plausibility, mode/gait consistency, and contact-conditioned velocity consistency.

Boundary: `"diagnostic_only": True`, `"paper_performance_claim": False`, `"trace_solver_input": False`, `"final_v23_output_solver_input": False`, `"fgo": False`.
