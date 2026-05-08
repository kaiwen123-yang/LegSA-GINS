# N4H4D Parity Decision

N4H4D uses engineering baseline parity gates, not paper performance claims.

Project gates:

- `horizontal_rmse_m <= 2.0`
- `up_rmse_m <= 3.0`
- `yaw_rmse_deg <= 2.0`
- strict roll: `roll_rmse_deg <= 1.0`
- strict pitch: `pitch_rmse_deg <= 1.0`
- relaxed roll/pitch: `<= 1.6`

Engineering parity candidate requires horizontal/up/yaw gates, relaxed
roll/pitch gates, and closeness to the external clean replay baseline:

- horizontal delta <= 0.5 m;
- up delta <= 0.8 m;
- yaw delta <= 0.5 deg.

Near-gate status is only allowed for position/up passing, yaw in `(2.0, 2.2]`,
and relaxed roll/pitch passing. It is not a pass. Yaw greater than 2 deg is
never reported as a strict pass, and relaxed roll/pitch is never reported as
strict roll/pitch pass.
