# Mechanization Foundation

N4 mechanization is a basic runnable version for the LegSA-GINS C++ filter core.
It is not a full final_v23 mechanization parity claim.

## Update Order

The simplified propagation follows the documented order:

1. velocity update
2. position update
3. attitude update

The implementation compensates the toy IMU increments using the current bias and
scale placeholders, rotates the velocity increment into navigation frame, uses a
WGS84 local-radius approximation to integrate BLH, and updates `qbn` with a
rotation-vector increment.

## Boundary

- No KF-GINS source is copied.
- No trace correction is used.
- No double-sample final_v23 mechanization equivalence is claimed.
- Real-data oracle checks are required before any numerical reproduction claim.
