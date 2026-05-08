# N4H4D1 First-Epoch Diagnostics

N4H4D showed severe divergence across position, vertical, yaw, roll, and pitch, so N4H4D1 is a diagnostic-only stage.

This stage adds runtime snapshots for config/init, input streams, first updates, first propagations, and sparse state trace. These files are generated under runtime output directories only and must not be committed.

N4H4D1 does not change solver mathematics, does not tune parameters, does not delete epochs, and does not perform output-only correction. Failed parity remains failed until a later explicit fix stage proves otherwise.

Forbidden boundaries remain: `trace_solver_input=false`, `final_v23_output_substitution=false`, `output_only_correction=false`, `bad_epoch_deletion_for_metric=false`, and `numerical_performance_claim=false`.
