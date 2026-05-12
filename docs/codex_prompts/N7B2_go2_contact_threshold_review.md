# N7B2 Go2 Contact Threshold Review Prompt

Run N7B2 as contact threshold readiness only.

Required boundaries:

- Do not merge or close PR #21.
- Do not delete remote branches.
- Do not force push.
- Do not commit raw data, by2 files, generated solver output, runtime reports,
  or generated figures.
- Do not hardcode local absolute paths in tracked docs, config, or scripts.
- Do not modify `/home/kaiwen/KF-GINS`.
- Do not use trace or final_v23 output to tune thresholds.
- Do not treat Go2 position or Go2 velocity as truth.
- Do not activate Go2 velocity prior.
- Do not activate Go2 yaw prior.
- Do not implement FGO.
- Do not make paper performance or outperform-final_v23 claims.

Runtime roots must be passed as command-line arguments and represented in
tracked documentation by role aliases only.
