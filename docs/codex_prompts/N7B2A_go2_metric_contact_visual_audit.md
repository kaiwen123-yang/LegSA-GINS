# N7B2A Go2 Metric Contact Visual Audit Prompt

Run N7B2A as an additional review commit on the existing N7B2 PR branch.

Required boundaries:

- Do not merge PR #36.
- Do not create an N7B2 or N7B2A tag.
- Do not create a new PR.
- Do not merge or close PR #21.
- Do not delete remote branches.
- Do not force push.
- Do not commit raw data, by2 files, runtime reports, solver outputs, or
  generated figures.
- Do not hardcode local absolute paths in tracked docs, config, or scripts.
- Do not modify the external KF-GINS working tree.
- Do not use trace or final_v23 output to tune contact thresholds.
- Do not treat Go2 position or Go2 velocity as truth.
- Do not activate Go2 velocity prior.
- Do not activate Go2 yaw prior.
- Do not implement FGO.
- Do not make paper performance or outperform-final_v23 claims.

Runtime roots must be passed as command-line arguments and described in tracked
documentation by role aliases only.
