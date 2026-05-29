# BY3B Degradation Plan

BY3B is a planning/precheck package for future BY3 degradation execution. It is not an execution stage.

Primary metric scope:

- horizontal RMSE / P95 / max
- north/east/up RMSE
- up RMSE / P95 / max
- recovery time and position consistency if available

Diagnostic-only yaw scope:

- yaw RMSE / P95 / max
- yaw gate counts
- yaw observation quality and A1 quality notes
- final_v23 versus LegSA yaw trend

Planned families:

- `A_outage`: 3s, 5s, 10s, 20s
- `B_downsample`: every2, every5, every10; `B_gnss_downsample_2Hz` remains invalid
- `C_position_noise`: mild, medium, strong with seeds 0..9
- `D_position_spike`: mild, medium, strong with seeds 0..9
- `E_position_std_inflation`: x2, x5, x10
- `M_position_up_mixed`: five selected position/up mixed cases
- `H_dual_yaw_noise`: diagnostic only with seeds 0..9 if human-approved
- `E_yaw_std_inflation`: diagnostic only if human-approved
- optional mixed yaw diagnostic only after separate review

Future batch plan:

- Batch 0: normal parity recheck with BY3A7/BY3A8 accepted sources
- Batch 1: deterministic A/B/E_position_std
- Batch 2: C_position_noise seeds 0..9
- Batch 3: D_position_spike seeds 0..9
- Batch 4: diagnostic H_dual_yaw_noise only if approved
- Batch 5: diagnostic E_yaw_std only if approved
- Batch 6: selected mixed position/up cases
- Batch 7: optional mixed yaw diagnostic after review

Execution gate:

`BY3C_POSITION_UP_DEGRADATION_EXECUTION_BATCH0_AND_BATCH1` may start only after human review. BY3B itself did not generate random arrays, degraded inputs, solver outputs, evaluator outputs, figures, or paper claims.
