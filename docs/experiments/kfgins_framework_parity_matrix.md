# KF-GINS Framework Parity Matrix

N4H2C records framework parity as an audit matrix, not as an implementation
claim.

## KF-GINS Full Flow

The deep audit searches for the following KF-GINS-style runtime flow:

- input `.gnss/.imu` reader
- config reader
- `addImuData`
- `addGnssData`
- `newImuProcess`
- `isToUpdate`
- `imuInterpolate`
- `imuCompensate`
- `insPropagation`
- `F / G / Phi / Qd`
- `EKFPredict`
- `position / velocity / yaw update`
- `EKFUpdate`
- `stateFeedback`
- NAV / STD / EVAL writer

## LegSA Current Implementation

Current LegSA contains a toy/foundation filter core and writer contracts. It is
not a complete KF-GINS-style mechanization/EKF reconstruction.

## Missing Pieces

The runner writes `LEGSA_KFGINS_FRAMEWORK_PARITY_MATRIX.json` with:

- `parity_matrix`
- `missing_in_legsa`
- `implemented_as_toy_only`
- `recommended_reconstruction_items`

Current N4H2C runtime probe records these LegSA gaps relative to the requested
KF-GINS-style flow:

- missing in LegSA:
  `newImuProcess`, `isToUpdate`, `imuInterpolate`, `imuCompensate`,
  `F/G/Phi/Qd`, `EKFPredict`, `EKFUpdate`, `stateFeedback`
- implemented as toy/foundation only:
  input `.gnss/.imu` reader, `addImuData`, `addGnssData`, `insPropagation`,
  NAV/STD/EVAL writer

## Why Current LegSA Toy Filter Is Not Full Framework

The current LegSA core does not yet prove the full `newImuProcess` loop,
interpolation/compensation, continuous-time error dynamics, discrete `Phi/Qd`,
and closed KF-GINS-style feedback path. N4H2C records this as a reconstruction
gap, but it does not implement full EKF in this stage.
