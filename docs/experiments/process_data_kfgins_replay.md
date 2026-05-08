# N4H2 process_data-compatible KF-GINS replay

N4H2 verifies that the N4H1P2 process_data-compatible BY2 `.gnss` and `.imu`
runtime inputs can be consumed by the external KF-GINS executable, then parses
and evaluates the produced baseline outputs.

This is baseline replay evidence only. It is not a proposed solver result and
does not authorize a formal performance claim.

## Scope

- Generate process_data-compatible `.gnss` / `.imu` inputs from BY2 upstream
  receiver and Go2 body-state fields.
- Run the external KF-GINS binary against those generated inputs.
- Parse `KF_GINS_Navresult.nav`, `KF_GINS_STD.txt`, and
  `KF_GINS_IMU_ERR.txt`.
- Evaluate parsed NAV against trace reference in evaluation-only mode.
- Keep real generated inputs and replay outputs out of Git.

## Real Run Summary

Local artifact root:

outside the Git worktree, under a local N4H2 artifact directory.

Input generation:

| Field | Value |
|---|---:|
| `.gnss` rows | 303 |
| `.imu` rows | 63277 |
| `coverage_status` | passed |
| `output_to_status_ratio` | 1.0 |
| PVT velocity rows | 1510 |
| status yaw rows | 302 |
| `trace_solver_input` | false |
| `output_only_correction` | false |

External KF-GINS replay:

| Field | Value |
|---|---:|
| return code | 0 |
| replay status | executed_no_oracle_claim |
| `KF_GINS_Navresult.nav` rows | 56642 |
| `KF_GINS_STD.txt` rows | 56642 |
| `KF_GINS_IMU_ERR.txt` rows | 56642 |
| replay start / end | 66 s / 340 s |

Evaluation-only trace alignment:

| Metric | Value |
|---|---:|
| estimated rows | 56642 |
| trace rows | 6040 |
| aligned rows | 56566 |
| horizontal RMSE m | 0.3479654209159466 |
| horizontal P95 m | 0.5609978710111065 |
| horizontal max m | 0.8659480298641918 |
| up RMSE m | 0.7940101228929531 |
| roll RMSE deg | 1.0674301793679788 |
| pitch RMSE deg | 1.6712386339103198 |
| yaw RMSE deg | 93.55731196644105 |
| yaw P95 deg | 147.05664026037135 |

The position replay is parseable and aligned. The yaw metric is diagnostic only
and remains a blocker for any final_v23 parity or proposed-method performance
wording.

## Boundary

- `trace_solver_input=false`.
- `trace_used_for_tuning=false`.
- `output_only_correction=false`.
- `bad_epoch_deletion_for_metric=false`.
- `formal_performance_claim_allowed=false`.
- generated `.gnss` / `.imu` files are runtime input reconstruction artifacts,
  not proposed algorithm output.
- external KF-GINS is used as a baseline executable; the LegSA-GINS proposed
  solver does not read final_v23/KF-GINS outputs.

## Generated Artifacts

The real-data artifacts are intentionally kept outside the Git worktree:

- `inputs/BY2_PROCESS_DATA_COMPAT.gnss`
- `inputs/BY2_PROCESS_DATA_COMPAT.imu`
- `inputs/PROCESS_DATA_COMPAT_REPORT.json`
- `replay/kfgins_output/KF_GINS_Navresult.nav`
- `replay/kfgins_output/KF_GINS_STD.txt`
- `replay/kfgins_output/KF_GINS_IMU_ERR.txt`
- `replay/standardized/FINAL_V23_EVAL_NAV.csv`
- `replay/evaluation/FINAL_V23_TRACE_EVAL_SUMMARY.json`
- `replay/N4H2_REPLAY_REPORT.json`

## Verdict

N4H2 replay execution, output parsing, and evaluation-only reporting are
complete. The supported claim is:

`process_data-compatible runtime inputs can drive an external KF-GINS baseline
replay and produce parseable NAV/STD/IMU_ERR outputs on BY2.`

The unsupported claims remain:

- final_v23 parity achieved;
- proposed LegSA-GINS performance;
- yaw-chain closure;
- raw Doppler / Go2 prior / source-aware weighting / LSIM / OIM / FGO support.
