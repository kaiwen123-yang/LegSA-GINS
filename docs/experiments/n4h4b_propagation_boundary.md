# N4H4B Propagation Boundary

N4H4B is limited to INS mechanization and EKF prediction.

It keeps these fields false in `RUN_MANIFEST.json`:

- `measurement_update_implemented`
- `state_feedback_implemented`
- `trace_solver_input`
- `raw_doppler`
- `go2_prior`
- `lsim_oim`
- `fgo`
- `fgo_feedback`
- `output_only_correction`
- `bad_epoch_deletion_for_metric`
- `numerical_performance_claim`
- `final_v23_output_substitution`

GNSS update functions, `EKFUpdate`, and `stateFeedback` remain N4H4C TODOs.
The propagation toy dry-run is a build/runtime smoke test only.

Chinese comments are required around the key Earth, Rotation, mechanization,
matrix-builder, predictor, and engine functions. The comments must preserve the
NED/BLH/body/ECEF unit and frame boundaries and must not describe N4H4B as
complete EKF parity.
