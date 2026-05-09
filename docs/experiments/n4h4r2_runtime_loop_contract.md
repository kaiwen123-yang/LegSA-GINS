# N4H4R2 Runtime Loop Contract

The R2 runtime follows the KF-GINS-style loose-coupled GNSS/INS loop:

- Load config.
- Construct IMU and GNSS loaders.
- Seed the engine from config initial state.
- Add the first IMU sample.
- Add GNSS samples as high-level observations only.
- For each IMU sample, call `addImuData` and `newImuProcess`.
- Write NAV, STD, EVAL_NAV, and RUN_MANIFEST.

Update timing follows the `isToUpdate` result:

- `0`: propagation only.
- `1`: update near previous IMU epoch, then propagate.
- `2`: propagate to current epoch, then update.
- `3`: interpolate IMU to GNSS time, propagate, update, feedback, then
  propagate the residual IMU increment.

R2 does not use trace as solver input and does not use final_v23 output as
solver input.
