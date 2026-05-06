# Frame Conventions

## Go2 Body / IMU Frame

Go2 body / IMU frame is FLU:

- X forward;
- Y left;
- Z up.

## Navigation Frames

GNSS/INS modules must explicitly distinguish:

- NED;
- ENU;
- ECEF;
- BLH;
- body;
- odom;
- map.

## Quaternion / Attitude Conventions

The project must explicitly document:

- qbn;
- qeb;
- yaw_math;
- yaw_heading.

## Hard Rules

- Do not mix Go2 body, odom, map, navigation, ENU, NED, ECEF, and BLH.
- Do not apply a second FLU-to-FRD transform.
- Any Go2 data must pass through a frame-safe adapter before entering estimator, factors, or smoother.
