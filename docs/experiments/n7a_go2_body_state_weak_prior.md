# N7A Go2 body-state weak prior

N7A adds the first Go2 body-state weak prior on top of the source-backed port-core and N6B source-aware policy layer.

Go2 body-state is not truth. The `/sportmodestate` / `by2.txt` fields are robot internal odometry and IMU/high-level state. N7A activates only a conservative roll/pitch weak prior by default. Go2 position and velocity priors are disabled by default in N7A. Go2 yaw prior is disabled in N7A.

The active source is `go2_attitude_roll_pitch`. It uses Go2 roll/pitch from the internally consistent rpy/quaternion stream, builds `GO2_ATTITUDE_WEAK_PRIORS.csv` as runtime-only input, and applies the weak prior through the C++ EKFUpdate path. It does not do output-only correction.

No trace/final_v23 output is used for Go2 prior construction. No paper performance claim. No outperform final_v23 claim. No FGO claim in N7A.
