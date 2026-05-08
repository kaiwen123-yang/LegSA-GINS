# process_data Runtime Parameter Audit

N4H2C-2 audits process_data defaults and invocation evidence before any full EKF
work.

## Default Parameters

The audit extracts:

- `BASE_TIME`
- `USE_STATUS_YAW`
- `YAW_SIGN`
- `YAW_INSTALL_OFFSET_DEG`
- `AUTO_APPLY_BEST_INSTALL`
- `YAW_SOURCE_MODE`
- yaw noise / outage / outlier defaults
- yaw standard-deviation defaults
- IMU install and IMU/GNSS time-offset defaults

## Nominal Safety

Nominal replay must use explicit safe flags or equivalent evidence:

- trace yaw disabled as solver input
- outage disabled
- outlier mode none
- yaw noise zero

If defaults include disturbance/noise/outage behavior, N4H2C reports that as
diagnostic risk rather than silently treating it as nominal.

## Runtime Snapshot

Read-only extraction from the external `process_data.py` role found:

- `BASE_TIME`: 1772784000.0
- `YAW_SOURCE_MODE`: `status`
- `USE_STATUS_YAW`: true
- `YAW_SIGN`: 1.0
- `YAW_INSTALL_OFFSET_DEG`: 0.0
- `AUTO_APPLY_BEST_INSTALL`: false
- `STATUS_YAW_STD_MODE_DEFAULT`: `fixed_1p5`
- `OUTLIER_MODE_DEFAULT`: `legacy15`
- `YAW_NOISE_STD_DEG`: 1.5

The runtime report classified:

- likely_yaw_source_mode: `status`
- likely_yaw_std_mode: `fixed_1p5`
- nominal_defaults_are_noisy_or_degraded: true
- explicit_nominal_safe_flags_found: false

This means nominal-safe replay still needs invocation evidence, not just default
inspection. The audit does not modify external source and does not copy source
into this repository.

## Boundary

`trace_yaw` remains diagnostic-only and cannot become formal solver input.
