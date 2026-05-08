# N4H4D2 Mechanization Sanity

N4H4D2 separates immediate mechanization faults from long free-INS drift.

The process_data-compatible IMU has already been converted from Go2 FLU to FRD
upstream, so LegSA-v23-core must not apply a second FLU-to-FRD transform. The
sanity report checks early dtheta/dvel magnitudes, dvel/dt, short-window height
and attitude jumps, and covariance health.

Long propagation-only drift is diagnostic context, not by itself proof of a
mechanization bug.

