# N8D FGO Factor Weight Policy Review Prompt

N8D starts after N8C3 Raw Doppler FGO solver activation is fixed.

Review no-feedback FGO factor weight policy for SmoothnessFactor,
RawDopplerVelocityFactor, ReceiverVelocityFactor, Go2ProprioceptiveJointFactor,
and DualYawFactor.

Use solver-visible diagnostics only for policy selection. Trace/final_v23 are
not weight-tuning inputs.

Run real no-feedback solver ablations, generate runtime-only reports and
figures, keep candidate factors diagnostic-only, do not delete smoothness as a
final shortcut, do not feed FGO output back into EKF, do not replace EKF NAV, and
make no paper performance claim.
