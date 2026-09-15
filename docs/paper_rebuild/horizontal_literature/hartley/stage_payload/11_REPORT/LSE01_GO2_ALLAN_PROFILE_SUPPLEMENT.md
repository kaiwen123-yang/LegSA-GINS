# LSE01 Go2 Allan Profile Supplement

## Outcome

`GO2_IMU_ALLAN_90MIN_RECOVERED_V1` is registered as a recovered numerical average-axis IMU profile under the evidence label `THESIS_AND_CONTEMPORANEOUS_TERMINAL_RECORD_CROSS_CONFIRMED`. This closes the future H5 Go2 process-noise parameter provenance gate. It does not reconstruct the lost Allan dataset or fitting program, and it is not a real-data navigation result.

The prior `LSE01_H0_H2_REPORT.md` and `LSE01_H0_H2_STATUS.json` remain unchanged historical terminal artifacts. H0--H2 did not possess this recovered profile; this supplement records the later H3--H4 registration.

## Registered densities and `Qc` blocks

| Process role | Continuous density | Squared continuous PSD |
|---|---:|---:|
| Gyroscope measurement white noise | `2.865130e-04 rad/s/sqrt(Hz)` | `8.208969916900001e-8 rad^2/s` |
| Accelerometer measurement white noise | `1.285395e-03 m/s^2/sqrt(Hz)` | `1.652240306025e-6 m^2/s^3` |
| Gyroscope-bias random walk | `2.996871e-05 rad/s^2/sqrt(Hz)` | `8.981235790641001e-10 rad^2/s^3` |
| Accelerometer-bias random walk | `1.594412e-04 m/s^3/sqrt(Hz)` | `2.542149625744e-8 m^2/s^5` |

The production C++ interface distinguishes `ContinuousNoiseDensity`, whose field names carry the ASD units, `ContinuousNoisePsd`, and `DiscreteSampleStd`. The named `eq61ProcessCovariance` and `eq52ProcessCovarianceGaussLegendre64` APIs return the separately identified `Qd` quantity. Future FK and paper-regression contracts use `MeasurementStdMeters` and `PaperTable1DiscreteStd`. The four Go2 densities are squared once to construct `Qc`; they are not pre-scaled by `sqrt(dt)`. The explicitly named discrete-sample conversion is for synthetic sampling only and cannot be routed back into `Qc`.

The paper Table-1 heading is `Experiment Discrete Noise Statistics`. Its `PaperTable1DiscreteStd` type retains all six stochastic parameters. Five process-side values, including contact linear velocity `0.05 m/s`, are squared once by `eq61MappedQbarPaperTable1` and mapped through `eq61ProcessCovariancePaperTable1`; none is relabeled as a continuous ASD. The sixth value, joint-encoder noise `1 deg`, remains a measurement-side angle. `contactMeasurementCovarianceFromPaperTable1JointEncoder` converts it to radians and applies a supplied foot-position Jacobian in `m/rad` as `R = J (sigma_rad^2 I) J^T`. No degree-to-meter scalar conversion is defined or permitted.

The H5-primary mixed adapter `eq61ProcessCovarianceGo2ImuPaperContact` combines only the four recovered Go2 continuous IMU ASDs with the paper-native contact value through the Eq. 61/Qbar path. The Go2 `ContinuousNoiseDensity` contact field is exactly zero in that adapter. H5 primary does not substitute Table-1 encoder noise for the declared FK proxy: FK `sigma_fk = 0.010 m` remains a `MeasurementStdMeters` input, is converted by `isotropicMeasurementCovariance` to `R = 1.0e-4 I3 m^2`, and never enters `Qc`.

The recovered accelerometer and gyroscope bias-instability values, respectively `7.781688e-04 m/s^2` and `4.550529e-05 rad/s`, retain the role `IMU_CHARACTERIZATION_DIAGNOSTIC_ONLY`. They are neither bias random-walk densities nor initial bias standard deviations.

## Provenance limits

- The original static CSV is unavailable.
- The original fitting script is unavailable.
- Exact per-axis fitted values are unavailable.
- The exact Allan curve cannot be recomputed.
- The exact fitting implementation cannot be audited.
- The numerical arithmetic-mean three-axis profile is recovered.
- An exact sampling-rate claim is forbidden because the original timestamps are unavailable.
- Raw-artifact reproducibility is not claimed.

## Future H5 registration

The following identities are pre-registered and unexecuted:

- `H5_PRIMARY_GO2_ALLAN_RECOVERED`: Eq. 50 mean, analytical right-invariant `Phi`, Eq. 61 process covariance, four recovered Go2 continuous IMU ASDs, the paper-native contact process standard deviation `0.05 m/s` through the typed Eq. 61/Qbar adapter, and FK measurement `sigma_fk = 0.010 m` through `MeasurementStdMeters`.
- `H5_PAPER_TABLE1_PARAMETER_REGRESSION`: the same backend with all six IJRR Table-1 stochastic parameters retained in `PaperTable1DiscreteStd`; five process parameters use the typed Eq. 61/Qbar adapter, while the one-degree encoder measurement uses the supplied-Jacobian covariance mapping `R = J (sigma_rad^2 I) J^T`.
- `H5_FK_PROXY_SENSITIVITY`: `sigma_fk = 0.005, 0.010, 0.020 m`, with `0.010 m` primary.

The approximately `1e-8 I m^2` H0--H2 numerical result is registered only as `GO2_FK_PROXY_REPEATABILITY_LOWER_BOUND`, with `future_filter_primary = false`. Neither reference accuracy nor final odometry may select an H5 branch or FK covariance.

The executable dimensional artifact validates both process adapters and all-six Table-1 parameter retention; the synthetic recovery artifact exercises the encoder-Jacobian measurement covariance in a nonzero contact correction. These checks also prove that the H5-primary FK measurement standard deviation does not contaminate `Qc`. This closes parameter provenance only. H5 remains unexecuted, `ready_for_real_by2_h5 = false`, and a new human authorization is required. No real BY2 Hartley navigation, real gauge ensemble, reference access, EXT06 execution, or Canonical-541 execution occurred for this supplement.

The supplement and H3--H4 payload were published into the existing LSE01 external stage and verified byte-for-byte against the tracked payload. The historical H0--H2 report and status were not rewritten.
