# N8D Whitened Balance Policy

The balance review compares SmoothnessFactor, RawDopplerVelocityFactor,
ReceiverVelocityFactor, Go2ProprioceptiveJointFactor, and DualYawFactor through
solver-visible whitened residuals and contribution shares.

Allowed inputs are residual statistics, factor counts, finite-output checks, and
diagnostic solver summaries.

Trace/final_v23 metrics are not tuning inputs.
