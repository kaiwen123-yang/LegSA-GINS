# N4H4C GNSS Updates, EKFUpdate, and StateFeedback

N4H4C implements the LegSA-owned loose-coupled GNSS measurement update path in
`legsa_v23_core`. It adds position, velocity, and yaw measurement blocks,
Joseph-form `EKFUpdate`, and KF-GINS-style error-state feedback after the
N4H4B mechanization and prediction path.

This stage is not a final_v23 numerical parity claim. The toy update run only
checks that the update branch, covariance update, feedback, writers, manifest,
audits, and tests execute inside the LegSA-owned framework.

Implemented scope:

- GNSS position update from 15-column `.gnss` BLH/std input.
- GNSS velocity update from 15-column `.gnss` vn/ve/vd input.
- GNSS yaw update from status-yaw with scheme_C gate.
- `EKFUpdate` using Joseph form.
- `stateFeedback` with position/velocity negative feedback, attitude left
  multiplication, bias/scale additive feedback, and dx reset.
- `newImuProcess` update branches for before, at, and inside IMU intervals.
- `--dry-run-update-toy` and manifest flags for the update foundation.

Forbidden scope remains disabled:

- no raw Doppler;
- no raw pseudorange;
- no Go2 prior;
- no LSIM/OIM;
- no FGO or FGO feedback;
- no Neural Gate;
- no final_v23 output substitution;
- no trace solver input;
- no clean replay parity claim;
- no paper performance claim.

The read-only formula audit searches `reference/final_v23_repo` and
`/home/kaiwen/KF-GINS` for short evidence snippets. It preserves
`evidence_missing` where formula details are not directly confirmed. In this
stage, velocity lever-arm correction is intentionally disabled when evidence is
missing, and the yaw residual defaults to obs-minus-pred with conservative
PHI-z mapping recorded in `RUN_MANIFEST.json`.

N4H4D is the next clean replay parity stage. It may use clean process-data
compatible runtime input for baseline parity testing, but final_v23 outputs must
remain outside proposed solver input.
