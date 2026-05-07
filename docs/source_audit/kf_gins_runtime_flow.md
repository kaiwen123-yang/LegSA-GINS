# KF-GINS / final_v23 Runtime Flow

## Scope

This document summarizes the KF-GINS/final_v23-style runtime flow for LegSA-GINS reproduction planning.
It is not proposed algorithm implementation.
It is not numerical performance evidence.

## Main Program Structure

The main program in `/home/kaiwen/KF-GINS/src/kf_gins.cpp` expects one YAML config path. It loads the YAML, converts configuration into `GINSOptions`, reads input/output paths, creates `GnssFileLoader` and `ImuFileLoader`, constructs `GIEngine`, constructs three `FileSaver` outputs, aligns the first IMU and GNSS epochs, then loops over IMU samples.

Within the loop it refreshes GNSS data when needed, adds each IMU sample to the engine, calls `newImuProcess`, reads `timestamp`, `getNavState`, and `getCovariance`, then writes NAV and STD rows.

## Config Loading

Observed configuration keys:

- `imupath`
- `gnsspath`
- `outputpath`
- `imudatalen`
- `imudatarate`
- `starttime`
- `endtime`
- `initpos`
- `initvel`
- `initatt`
- `initgyrbias`
- `initaccbias`
- `initgyrscale`
- `initaccscale`
- `initposstd`
- `initvelstd`
- `initattstd`
- `initbgstd`
- `initbastd`
- `initsgstd`
- `initsastd`
- `imunoise`
- `antlever`

The default sample config is `/home/kaiwen/KF-GINS/dataset/kf-gins.yaml`.

## IMU / GNSS File Loading

`ImuFileLoader` reads time, incremental angle, incremental velocity, and optionally odometer velocity. `GnssFileLoader` reads receiver-native position and standard deviation fields, with optional velocity and yaw fields when the row has enough columns.

The generic base utilities are `FileLoader` and `FileSaver`.

## GIEngine Construction

`GIEngine` is constructed from `GINSOptions`. The constructor and initialization path set up initial state, covariance, process noise, and IMU error model state. N3B only records this as a source map; it does not port the implementation.

## Processing Loop

Observed loop structure:

- read GNSS when GNSS time is older than the current IMU time;
- read the next IMU sample;
- call `addImuData`;
- call `addGnssData` when a new GNSS row is loaded;
- call `newImuProcess`;
- read `timestamp`;
- read `getNavState`;
- read `getCovariance`;
- write NAV and STD outputs.

## newImuProcess Time Alignment Logic

`newImuProcess` calls `isToUpdate(imupre.time, imucur.time, gnss.time)` when GNSS is valid.

The observed return values are:

- `0`: only propagation.
- `1`: GNSS is near the previous IMU epoch.
- `2`: GNSS is near the current IMU epoch.
- `3`: GNSS is between two IMU epochs, interpolation required.

## GNSS Update Logic

The GNSS update path applies antenna lever-arm compensation, forms a GNSS position innovation, builds the position measurement matrix, builds measurement covariance from GNSS standard deviations, calls EKF update paths, and invalidates or consumes GNSS after update. The audited source also contains yaw, velocity, zero-velocity, and yaw-rate style updates from later local branches; N3B does not adopt those proposed factors.

## EKF Predict / Update / Feedback

`EKFPredict` propagates covariance and error state. `EKFUpdate` computes a Kalman gain and applies the Joseph-form covariance update. `stateFeedback` feeds position, velocity, attitude, bias, and scale corrections into the navigation state, then resets the error state and checks covariance.

This is source-audit information only. LegSA-GINS N3B does not implement EKF logic.

## INS Mechanization Order

velocity update -> position update -> attitude update

This order comes from KF-GINS source parsing and source audit. It does not mean LegSA-GINS has implemented complete mechanization.

## NAV / STD Output Structure

Observed output structure:

- NAV output: `KF_GINS_Navresult.nav`, 11 columns: week, time, latitude, longitude, height, north velocity, east velocity, down velocity, roll, pitch, yaw.
- STD output: `KF_GINS_STD.txt`, 22 columns: time, PVA standard deviations, gyro-bias standard deviations, accelerometer-bias standard deviations, gyro-scale standard deviations, accelerometer-scale standard deviations.
- IMU_ERR output: `KF_GINS_IMU_ERR.txt`, 13 columns: time, gyro bias, accelerometer bias, gyro scale, accelerometer scale.

N3C needs to bridge these outputs to `LegSA_NAV.nav`, `LegSA_STD.csv`, and `EVAL_NAV.csv` without letting the proposed solver read final_v23 output.
