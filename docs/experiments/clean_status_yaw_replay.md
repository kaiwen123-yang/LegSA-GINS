# Clean status-yaw replay

N4H2G exists because the historical dual_final_v23 artifact is now labeled as
likely Gaussian-yaw-noise injected evidence. That artifact remains useful as a
historical noisy/stress baseline, but it must not be called a clean nominal
baseline without the provenance caveat.

This stage reconstructs a clean process_data-compatible runtime input with:

- yaw_source_mode=status
- yaw_std_mode=fixed_1p5
- yaw_noise_std_deg=0.0
- outlier_mode=none
- outlier_ratio=0.0
- enable_outage=false
- trace_solver_input=false

The clean replay is a reconstructed clean variant, not a historical exact
dual_final_v23 artifact. Its metrics are baseline replay diagnostics only, not
proposed solver performance.

The target gates remain unchanged: horizontal <= 2.0 m, up <= 3.0 m, yaw <= 2.0
deg, and roll/pitch strict gates remain separate from relaxed reporting.
