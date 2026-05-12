# N7A Go2 body-state weak prior prompt

Implement N7A after N6B source-aware policy refinement.

Scope:
- parse Go2 `/sportmodestate` / `by2.txt` body-state fields;
- verify quaternion/rpy, frame, and time contracts;
- build runtime-only `GO2_ATTITUDE_WEAK_PRIORS.csv`;
- activate only `go2_attitude_roll_pitch` roll/pitch weak prior in EKF;
- connect the Go2 source to source-aware R scaling;
- run baseline/raw/source-aware/Go2 diagnostic ablations.

Boundaries:
- Go2 body-state is not truth.
- Go2 position and velocity priors are disabled by default in N7A.
- Go2 yaw prior is disabled in N7A.
- No trace/final_v23 output is used for Go2 prior construction.
- No paper performance claim.
- No outperform final_v23 claim.
- No FGO.
- Do not merge PR #21.
- Do not tag N7A.
