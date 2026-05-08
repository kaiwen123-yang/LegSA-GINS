# process_data Deep Audit

N4H2C audits the two-layer process_data chain:

1. runtime input: the actual final_v23 `input.gnss` consumed by KF-GINS;
2. upstream generation: `process_data.py` and run/config scripts that created
   the runtime input.

## Runtime Input vs Upstream Generation

The runtime file is the controlling evidence. The upstream generation code is
used only to explain why the runtime columns have their observed values.

The 15-column runtime `.gnss` contract is:

`time lat lon height std_n std_e std_d vn ve vd std_vn std_ve std_vd yaw yaw_std`

## Status Yaw and Trace Yaw Modes

N4H2C searches for:

- status yaw / `A1_dual_diff`
- trace yaw mode
- `yaw_source_mode`
- `yaw_std_mode`
- `status_yaw_std_mode`
- fixed `1.5` degree yaw standard deviation mode
- dynamic or suspicious-only modes

Trace yaw is diagnostic-only and must not become solver input.

## Yaw Parameters

N4H2C records evidence for:

- `YAW_SIGN`
- `YAW_INSTALL_OFFSET_DEG`
- automatic install-offset application flags
- outage and outlier switches
- yaw noise injection parameters
- IMU install roll/pitch/yaw parameters
- IMU/GNSS time offset
- antenna lever arm
- `initatt`
- `imunoise`

## Nominal Defaults Observed

Nominal replay should not default-enable trace yaw, outage, outlier, or yaw
noise injection. When runtime evidence is missing, the report must say
`evidence_missing` instead of guessing.

Current N4H2C runtime probe found process_data keyword evidence for:

- `yaw_source_mode`
- `yaw_std_mode`
- `YAW_SIGN`
- `YAW_INSTALL_OFFSET_DEG`
- status yaw and trace yaw modes
- fixed yaw standard deviation mode
- outage / outlier / yaw-noise parameters
- IMU install and config parameters

The actual final_v23 case-root artifact itself was not visible in the current
WSL runtime probe, so actual `input.gnss` still has `evidence_missing`.

## Uncertainty

N4H2C does not tune yaw offsets to trace and does not formally select an offset
without physical antenna-order or actual-input evidence.
