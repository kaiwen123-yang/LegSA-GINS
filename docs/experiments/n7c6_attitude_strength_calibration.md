# N7C6 Attitude Strength Calibration

N7C6 scans Go2 roll/pitch observation strength:

- `rollpitch_only_5deg`
- `rollpitch_only_3deg`
- `rollpitch_only_1p6deg`
- `rollpitch_only_1deg`
- `joint_rp0p75_hv1p0_diagnostic`

Go2 roll/pitch are treated as proprioceptive observations, not truth. The scan
uses solver-visible runtime residual/NIS diagnostics and clean/stress comparison
only after the candidate policies are defined. It does not use trace or
final_v23 output to tune std.
