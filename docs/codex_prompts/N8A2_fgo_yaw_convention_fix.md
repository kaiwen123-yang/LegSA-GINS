# N8A2 FGO Yaw Convention Fix Prompt

Fix the PR #39 yaw convention blocker without merging PR #39, creating tags, or
opening a new PR.

Do not enter N8B. Do not delete smoothness to pass metrics. Do not use
trace/final_v23 outputs as solver inputs or weight-tuning inputs. Do not feed
FGO output back into EKF, substitute EKF NAV, or apply output-only yaw
correction.

Runtime paths must be passed only as command arguments through role aliases:

- `N8A_REPORT_OUTPUT_DIR`
- `N8A2_REPORT_OUTPUT_DIR`
- `N8A2_FIGURE_OUTPUT_DIR`

Tracked docs/config/scripts must not contain local absolute runtime paths.
