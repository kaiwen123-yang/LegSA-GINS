# N4F BY2 Filter-Core Trial Prompt Summary

Implement a diagnostic BY2 real-data trial for the current LegSA-GINS C++ filter
core. The stage converts standardized Go2 body-state gyro/accel into diagnostic
IMU increments, converts receiver-native GNSS status into trial measurements,
runs the C++ filter core, evaluates against trace as evaluation-only reference,
and writes summary/case_review artifacts.

Boundary: no raw Doppler, no Go2 priors, no source-aware weighting, no LSIM/OIM,
no FGO, no trace solver input, no output-only correction, no bad-epoch deletion,
and no numerical performance claim.

