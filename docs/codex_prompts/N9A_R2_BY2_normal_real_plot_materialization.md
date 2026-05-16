# Codex Prompt: N9A_R2 BY2 Normal Real Plot Materialization

Continue PR #49 on `stage/N9A-BY2-full-plot-audit`. Do not merge the PR, create
tags, enter N9B, run the degradation matrix, or change algorithms.

First discover real BY2 normal algorithm outputs. Do not draw compare,
position-error, trajectory, consistency, feedback, FGO, or legged-factor figures
unless the required runtime artifacts exist. Source GNSS/status, trace, Go2
high-level data, and receiver IMU diagnostics have restricted source/audit
roles and must not be used as algorithm estimates.

Required reports:

- `N9A_R2_ALGORITHM_OUTPUT_DISCOVERY_REPORT.json`
- `N9A_R2_DECISION_REPORT.json`
- semantic audits for source-proxy exclusion, real trajectory, real position
  error, metric bars, velocity source distinction, compare requirements,
  consistency STD requirements, false-complete prevention, no algorithm change,
  no degradation matrix run, and no performance claim.

If real algorithm outputs are missing, mark the stage failed for materialization:
`ready_for_N9B = false`.
