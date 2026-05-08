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

