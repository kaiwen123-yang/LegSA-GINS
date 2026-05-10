# N5B Raw Doppler Factor Activation Trial

N5B runs two diagnostic replays when a valid Doppler velocity factor file exists:

- baseline source-backed port replay with `enable_raw_doppler=false`;
- raw Doppler enabled replay with `enable_raw_doppler=true` and `raw_doppler_factor_path` pointing to the runtime factor CSV.

The raw Doppler update is an auxiliary velocity factor in the EKF. It does not replace the baseline receiver-native GNSS velocity factor and does not consume RTKLIB position solutions.

The trial reports `raw_doppler_solver_enabled`, `raw_doppler_update_count`, `raw_doppler_reject_count`, factor epoch counts, factor source, and diagnostic delta. The delta is not a paper performance claim.
