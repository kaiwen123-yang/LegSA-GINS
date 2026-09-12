# LSE01 BY2 input-only audit

## Terminal

`PASS_LSE01_H0_H2_HARTLEY_SOURCE_METHOD_AND_BY2_CONTRACT_READY`

The exact hash-locked BY2 body source passed its lock identity, size, line-count, mtime, and file SHA-256 checks. The binary policy scan found 63,277 complete delimiter-terminated records followed by one timestamped physical EOF record with `foot_speed_body[4/12]`. The accepted identity is `REAL_BY2_COMPLETE_RECORD_PREFIX_63277`; the raw source itself remains incomplete and immutable.

The human-provided historical project count of 63,277 complete IMU rows is retained only as a consistency cross-check. It did not determine the independently scanned record count, byte boundary, timestamps, or prefix hash.

The accepted byte interval is `[0,92351234)`, SHA-256 `03cd96cd65d7f5af30f6a0c78d37f07ae4d32c65e78531807db7192454dff097`. The entire 1,278-byte tail `[92351234,92352512)` is excluded without imputation or interpolation. The trailing record is not an online row. No Hartley filter ran, and no navigation or reference output was opened.

## Authenticated source

- BY2 body source: `<RAW_ROOT>/BY2_BY3/2026-03-06/高层数据/by2.txt`
- size: `92,352,512` bytes
- line count: `4,682,569`
- SHA-256: `95859de46925416f0a094f8986ef4f8cb452cab71b264702705a9f9aff95a278`
- `BY2_HASH_LOCK.csv` SHA-256: `7103880ff53eb195c7d9acdbb87292a7be20e4a58b764da29f848e80a84ecb6c`

## Eligible complete-record prefix

The following statistics use only the 63,277 complete records preceding the trailing incomplete physical record. `raw_source_complete=false` and `complete_record_prefix_filter_eligible=true` are both retained literally.

- exact first/last timestamps: `1772784044/887078145` / `1772784350/085048802` (`sec/nanosec`)
- exact duration: `305197970657 ns` (`305.197970657` seconds)
- median cadence: `0.004011869430541992` seconds (`249.26035538123253` Hz)
- min/max step: `0.00009322166442871094` / `0.09167623519897461` seconds
- finite shapes: gyro and accel `[63277,3]`, force `[63277,4]`, foot position and speed `[63277,4,3]`
- gait type: `1` for all complete messages; mode counts: `0:3`, `1:4461`, `3:58813`

The versioned primary structural list is exactly timestamp, gyro, accelerometer, force, foot position, and foot speed. This frozen production audit additionally requires one `gait_type` scalar so its audit-only grouping cross-tab is complete; gait type is not an online Hartley input.

Pinned Unitree source, maintained parser grouping, and observed BY2 front/rear and left/right signs agree on native `[FR,FL,RR,RL]`. The canonical `[FL,FR,RL,RR]` conversion is `[1,0,3,2]`.

The deterministic force-only policy is frozen as `FROZEN_BY2_INPUT_ONLY_CONTACT_POLICY`. Per-leg `(off,on)` thresholds are FR `(24.8,34.2)`, FL `(25.2,33.8)`, RR `(23.4,30.6)`, and RL `(24.0,32.0)` in source-native force units. Minimum dwell is three median-cadence samples, `0.012035608291625977` seconds. `foot_speed_body` is `DIAGNOSTIC_ONLY`, online-disallowed, and changes neither thresholds nor classifications. It is used offline in the separately preregistered FK-covariance consistency residual; that offline parameter audit does not make foot speed a future online filter input.

The high-level `foot_position_body` field remains an FK-like body-relative translation proxy, not raw encoder/URDF FK and not truth. Candidate input discontinuities were FR `2`, FL `1`, RR `1`, RL `2`; they were retained.

## Frame direction

The maintained active builder left-multiplies sensor vectors by `RzRyRx(-1°,0°,0°)`, closing the configured direction as sensor-to-body active rotation. Determinant, handedness, round-trip, and known-axis tests pass. On 633 input-only stationary-candidate samples, its gravity-cancellation residual was `0.20591299391339885 m/s²`, versus `0.23197377843950862 m/s²` for the inverse. This is a corroborating sanity check, not a new physical calibration or an attitude-truth claim.

Forbidden quaternion, RPY, pose, position, velocity, yaw, and trace/reference values were not materialized by the LSE01 projection.
