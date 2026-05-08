# N4H4A Function Contract

The `LegSAV23Engine` function names are intentionally aligned to the KF-GINS
style transplant matrix. N4H4A only provides the framework-level call chain and
TODO numerical hooks.

## Public Runtime Surface

- `LegSAV23Engine(const GINSOptions& options)`
- `initialize()`
- `addImuData(const IMUData& imu, bool compensate=false)`
- `addGnssData(const GNSSData& gnss)`
- `newImuProcess()`
- `timestamp() const`
- `getNavState() const`
- `getFilterState() const`

## Private EKF Skeleton Hooks

- `isToUpdate(double imu_time_1, double imu_time_2, double update_time) const`
- `imuInterpolate(const IMUData& imu1, IMUData& imu2, double timestamp, IMUData& midimu)`
- `imuCompensate(IMUData& imu)`
- `insPropagation(const IMUData& imupre, const IMUData& imucur)`
- `buildFGPhiQd(const IMUData& imucur)`
- `EKFPredict()`
- `gnssUpdate(const GNSSData& gnss)`
- `gnssPositionUpdate(const GNSSData& gnss)`
- `gnssVelocityUpdate(const GNSSData& gnss)`
- `gnssYawUpdate(const GNSSData& gnss)`
- `EKFUpdate()`
- `stateFeedback()`
- `checkCov() const`

All critical C++ functions carry Chinese comments that state purpose, coordinate
or unit expectations, N4H4A skeleton status, and the N4H4B/C follow-up boundary.
