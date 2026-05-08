# final_v23 Input Source Chain

Stage N4H1 audits the final_v23 input source chain before starting full KF-GINS-style EKF reconstruction.

## Layer 1: Runtime Actual Input

final_v23 reads a 15-column `.gnss` file through `gnsspath`.

The runtime columns are:

- `time`
- `lat`
- `lon`
- `height`
- `std_n`
- `std_e`
- `std_d`
- `vn`
- `ve`
- `vd`
- `std_vn`
- `std_ve`
- `std_vd`
- `yaw`
- `yaw_std`

At runtime, `gnssdata.blh`, standard deviations, velocity, and yaw are loaded from this `.gnss` layer. This is not a raw GNSS observation stream.

## Layer 2: Upstream Generation Fields

The audited upstream field map is:

- position from `gnss1-status` `pos_lat`, `pos_lon`, and `pos_height`;
- position standard deviation from `pos_acc_h` and `pos_acc_v`;
- velocity from `gnss1-raw` `UBX-NAV-PVT` fields `vn`, `ve`, `vd`, and `sAcc`;
- yaw from `gnss1-status` plus `gnss2-status` A1 dual-difference rel_pos fields;
- trace evaluation-only for alignment checks and evaluation, not as the main final_v23 positioning observation input.

## Boundary

This audit is diagnostic only. It does not implement proposed solver logic, raw Doppler, Go2 priors, source-aware weighting, LSIM/OIM, FGO, or full EKF.

final_v23 input audit must not be described as proposed solver implementation or numerical performance evidence.
