# Frame Conventions

## Go2 Body / IMU Frame

Go2 body / IMU frame is FLU.

- X forward;
- Y left;
- Z up.

Go2 body/IMU frame is FLU: X forward, Y left, Z up.

## final_v23-style IMU Assumption

final_v23-style IMU stream is treated as FRD-compatible unless explicitly declared otherwise.

## Navigation Frames

GNSS/INS modules must explicitly distinguish:

- NED;
- ENU;
- ECEF;
- BLH;

NED, ENU, ECEF, BLH must be explicitly declared.

## System Frames

System frames must be explicit:

- body;
- odom;
- map.

body, odom, map, navigation must not be mixed.

## Quaternion / Attitude Conventions

The project must explicitly document:

- qbn;
- qeb;
- yaw_math;
- yaw_heading.

## Go2 sportmodestate Rule

- imu_state belongs to body / IMU.
- position and velocity belong to leg odom / odom.
- foot_position_body and foot_speed_body are body-relative.

## Move Command Rule

- Move(vx, vy, vyaw) is body-frame velocity.
- MoveToPos(x, y, yaw) is odom-frame target.

## Hard Rules

- Do not mix Go2 body, odom, map, navigation, ENU, NED, ECEF, and BLH.
- Do not apply a second FLU-to-FRD transform.
- Any Go2 data must pass through a frame-safe adapter before entering estimator, factors, or smoother.
