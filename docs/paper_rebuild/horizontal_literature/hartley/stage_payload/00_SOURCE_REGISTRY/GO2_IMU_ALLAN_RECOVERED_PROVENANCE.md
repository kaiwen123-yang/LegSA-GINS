# Go2 IMU Allan Profile Recovered Provenance

## Registered identity

- Profile: `GO2_IMU_ALLAN_90MIN_RECOVERED_V1`
- Evidence label: `THESIS_AND_CONTEMPORANEOUS_TERMINAL_RECORD_CROSS_CONFIRMED`
- Platform: Unitree Go2 body IMU
- Condition: stationary
- Reported duration: 90 minutes / 5400 seconds
- Reported sample count: about 2.4 million
- Axis policy: arithmetic mean of the x, y, and z fitted values

This is a recovered numerical average-axis profile, not a raw-artifact reproduction. The two independent surviving records are the user's thesis, printed pages 41--43, and a contemporaneous terminal record from the original fitting run. Both record the same four principal values. The terminal record names the lost CSV by basename as `go2_imu_extracted.csv`; its former local absolute path is intentionally not registered in tracked clean-rebuild material.

## Recovered continuous noise densities

| Role | Symbol | Density | Continuous PSD used in `Qc` |
|---|---|---:|---:|
| Gyroscope measurement white noise | `sigma_g` | `2.865130e-04 rad/s/sqrt(Hz)` | `8.208969916900001e-8 rad^2/s` |
| Accelerometer measurement white noise | `sigma_a` | `1.285395e-03 m/s^2/sqrt(Hz)` | `1.652240306025e-6 m^2/s^3` |
| Gyroscope-bias random-walk drive | `sigma_bg` | `2.996871e-05 rad/s^2/sqrt(Hz)` | `8.981235790641001e-10 rad^2/s^3` |
| Accelerometer-bias random-walk drive | `sigma_ba` | `1.594412e-04 m/s^3/sqrt(Hz)` | `2.542149625744e-8 m^2/s^5` |

The model roles are

`omega_m = omega + b_g + n_g`,

`a_m = a + b_a + n_a`,

`dot(b_g) = w_bg`, and

`dot(b_a) = w_ba`.

Each continuous amplitude spectral density is squared exactly once to form its continuous PSD block. No multiplication or division by `sqrt(dt)` occurs before `Qc` construction. A discrete sample standard deviation is a separately named sampler-interface quantity and must never be fed back into `Qc`.

## Diagnostic values that are not process densities

- Accelerometer bias instability: `7.781688e-04 m/s^2`
- Gyroscope bias instability: `4.550529e-05 rad/s`
- Semantic role: `IMU_CHARACTERIZATION_DIAGNOSTIC_ONLY`

These two bias-instability values do not replace `sigma_bg` or `sigma_ba` and are not initial-bias standard deviations. They may only support a separately declared future initial-bias-covariance sensitivity.

## Evidence limitations

The following boundaries are frozen literally:

- `original_static_csv_available = false`
- `original_fitting_script_available = false`
- `exact_per_axis_values_available = false`
- `exact_Allan_curve_recomputable = false`
- `exact_fitting_implementation_auditable = false`
- `numeric_average_axis_profile_recovered = true`

The original timestamps are unavailable, so an exact sampling-rate claim is forbidden. Raw-artifact reproducibility and exact Allan-curve recomputation are not claimed. These limitations do not invalidate the cross-confirmed numerical average-axis profile or its scoped dimensional and covariance-mapping regression role.

## H3--H5 boundary

H3--H4 may use this profile only for unit, interface, and numerical process-covariance regression. It is pre-registered for the future `H5_PRIMARY_GO2_ALLAN_RECOVERED` run, but no real BY2 Hartley navigation, reference access, parameter selection, or performance claim occurs in this phase.
