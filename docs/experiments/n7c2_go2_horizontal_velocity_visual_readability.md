# N7C2 Go2 Horizontal Velocity Visual Readability

N7C2 is a readability audit for the N7C/N7C1 Go2 horizontal velocity weak-prior figures.

It explains why plots with multiple legend entries may visually show only one or two curves. The audit uses source time series, not pixel OCR. Highly overlapped curves are allowed when the controlled weak prior has a tiny visible effect on the clean run.

Runtime inputs are referenced only by role alias:

- `N7C_RUNTIME_REPORT_ROOT`
- `N7C1_RUNTIME_REPORT_ROOT`

Mandatory readability figures:

- `clean_horizontal_error_no_go2_vs_go2_alpha_style.png`
- `clean_horizontal_delta_go2_minus_no_go2_zoom.png`
- `clean_yaw_error_no_go2_vs_go2_alpha_style.png`
- `clean_yaw_delta_go2_minus_no_go2_zoom.png`
- `go2_horizontal_velocity_vs_receiver_split_components.png`
- `go2_horizontal_velocity_vs_raw_doppler_split_components.png`
- `go2_prior_std_policy_annotated.png`
- `vertical_disabled_annotated.png`
- `update_residual_zoom.png`
- `n7c2_visual_overlap_summary.png`

Boundary:

- No solver math change.
- No prior std change.
- No tuning, epoch deletion, or output-only correction.
- No paper performance claim.
- No outperform-final_v23 claim.
