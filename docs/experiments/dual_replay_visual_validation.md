# N4H2E dual_final_v23-only Visual Validation

N4H2E generates a visual validation bundle for the fresh N4H2 replay parity result against the confirmed dual_final_v23 official reference. It is a diagnostic plotting stage only.

The bundle is intentionally dual_final_v23-only. It does not draw pure INS, single antenna, or multi-line comparison figures. The goal is to inspect whether the numerical replay parity also looks sane in trajectory, position error, attitude error, consistency, observation quality, and summary panels.

Boundary:

- solver_output_changed=false
- trace_solver_input=false
- output_only_correction=false
- bad_epoch_deletion_for_metric=false
- numerical_performance_claim=false
- manual_visual_review_required=true

Generated figures are baseline replay diagnostics, not proposed solver performance. The old stale N4H2 summary is invalidated by N4H2D and must not be reused as formal evidence.

Roll and pitch relaxed gates are not strict passes. Yaw remains a strict <=2.0 deg gate and must be reported honestly when near the boundary.

Generated figure bundles under the visual output role must not be committed.

## Startup / Initial Convergence Transient

N4H2F adds a startup transient audit for the visible opening bump observed in a few figures. A visible transient is not automatically an evidence-backed bug. It should be annotated as an initial convergence region when the first-window checks stay within gate and yaw wrap spikes are absent.

The transient audit forbids deleting or cropping the first seconds to improve metrics:

- deletion_or_crop_allowed=false
- bad_epoch_deletion_for_metric=false
- output_only_correction=false

## Yaw STD Source Distinction

N4H2F separates two different quantities:

- `input.gnss` column 15: observation yaw standard deviation from process_data input generation.
- `KF_GINS_STD.txt` yaw std: filter state covariance standard deviation.

`yaw_std=1.5` is measurement standard deviation evidence only. It must not be written as proof that 1.5 deg random yaw noise was injected into the yaw values.

The yaw gate remains `yaw_rmse_deg <= 2.0`; yaw std is not used to relax that gate.

## Process-Data Yaw-Noise Provenance

N4H2F audits process_data yaw/noise provenance separately from yaw_std. The audit distinguishes:

- no-noise status-yaw input;
- fixed yaw_std with `yaw_noise_std_deg=0`;
- Gaussian yaw-noise variants;
- legacy outlier variants;
- trace-yaw diagnostic-only variants;
- final mainline degradation/stress batch configurations.

The final mainline batch script is treated as degradation/stress evidence, not clean `nominal_none` evidence. Whether actual dual_final_v23 `input.gnss` contains yaw-noise injection must come from actual-input-to-variant matching, not from the presence of fixed yaw std.

## Merge Readiness Caveats

The visual bundle can be ready for human review while still carrying caveats:

- manual_visual_review_required=true
- roll/pitch relaxed pass is not strict pass
- yaw near boundary must be reported honestly
- if actual input matches an injected-noise variant, N4H3 must carry a provenance caveat
- generated figures and generated case-review reports must stay out of git
