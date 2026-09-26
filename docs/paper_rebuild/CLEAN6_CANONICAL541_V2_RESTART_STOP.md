# P-09c restart: stopped during batch 8 archive

Terminal: `STOPPED_GATE_FAILURE`, 2026-09-11T21:16:10.201284+00:00 (2026-09-12 05:16:10.201284 Asia/Shanghai).

The `runtime_role` repair and missing-key FAIL handling were committed before continuation. The real-manifest regression passed for all 37 inputs (15 P-06 manifests plus the 22 manifests from the original stopped attempt). Those 22 original outputs were revalidated in place; none of the 33 native sequence outputs was rerun. See the [restart authorization and regression record](CLEAN6_CANONICAL541_V2_RESTART_AUTHORIZATION.md).

Archive SHA-256 reading raised `OSError: [Errno 12] Cannot allocate memory`. The sole archive without a completed receipt is `RUN_01963` (`D20_seed_06`, `A03`, `AB0111`). Its solver and v3/v2 evaluations completed. This is one archive technical failure; it does not reclassify successful solver/evaluator terminals. No retry, regeneration or post-failure cleanup was performed.

| Recorded item | Count / status |
|---|---:|
| Registered unique runs (5951 BY2 + 22 extra sequences) | 5973 |
| Attempted unique runs | 2048 |
| Native COMPLETED | 1989 |
| ALGORITHM_FAILURE_ALL_YAW_REJECTED | 59 |
| Native / evaluator technical failures | 0 / 0 |
| Archive technical failures | 1 |
| Evaluations COMPLETED / NOT_RUN_ALGORITHM_FAILURE | 3978 / 118 |
| Unexecuted unique runs | 3925 |
| Completed batches with archive and cleanup PASS | 7 |
| Batch 8 solver / evaluator records | 256 / 512, all COMPLETED |
| Batch 8 archive receipts | 255 / 256 |
| Batch 8 archive gate / cleanup | NOT_REACHED / NOT_EXECUTED |
| Batch 9 and later | NOT_EXECUTED |
| Original 33 native outputs reused / rerun | 33 / 0 |
| P-06 sequence byte gate | PASS, 105/105 |
| P-07 CAL C00 byte gate | PASS, 77/77 |

ALL_YAW_REJECTED counts: D14=34, D15=25; all other registered families have zero observed failures. Unexecuted runs are explicitly separate. Real failure records and archives were independently checked: metrics remain null, evaluators were not invoked, missing native NAV/STD/manifest/error series are marked UNAVAILABLE, and original file hashes remain in receipts and cleanup ledgers.

| Timing and retained scene | Measured value |
|---|---:|
| Restart freeze to stop, seconds | 15991.731888 |
| Original freeze to stop, seconds (includes human pause) | 22002.965357 |
| Active batch wall, seconds (scope below) | 15860.835791578997 |
| Batch 8 start to stop, seconds | 1759.469879 |
| Batch 8 owned process-tree RSS peak, bytes | 17865486336 |
| Batch 8 host used-memory peak, bytes | 18485465088 |
| Batch 8 scratch / G sampled peak growth, bytes | 30509813760 / 6246367232 |
| Batch 8 retained scratch regular files | 11403 |
| Batch 8 retained scratch logical / allocated file bytes | 30469147735 / 30492868608 |

Active batch wall adds the original attempt's 68.495169-second prefix, seven completed batch durations and batch 8 start-to-stop. It excludes restart validation and administrative gaps. Process-tree RSS sums shared resident pages per process. Filesystem growth is sampled relative to each batch's own baseline and can include concurrent activity. Exact whole-execution disk peak remains UNAVAILABLE because the early absolute baselines were not recorded; see the resource coverage note. Later observer-only samples after the execution stop are excluded from the execution resource summary.

The first-batch gate remains PASS: peak forecast 221127477999 bytes <=250000000000, duration forecast 51542.90087138401 seconds. These forecasts are not completed-full-run measurements. nproc=24; solver pool=22. Evaluator pool sizes and the measured resource reservation checks are recorded per batch in the resource CSV. The first-batch timing, RSS and output-byte measurements remain in the pilot report.

Full aggregate tables, failure-aware pairwise statistics, key-pair median/CI/win-rate results and full v1/v2 maintained/flipped comparisons are NOT_EXECUTED / UNAVAILABLE because the matrix did not finish. No partial-case statistics substitute for them. Final `c541_v2_handoff.zip` was not generated; ZIP SHA-256 is UNAVAILABLE. Protocol v2 remains the preregistered manuscript target; full numerical handoff is not delivered. The v1 main chain, A04 Outcome and decision-rule file remain unchanged.

Execution code: `737a0fb5a4a5418500824855b89b0d25af69824a`; restart contract commit: `dae932e43275ad3698f437bfdcce7959b3b5e009`; original reused-native code: `b26569185638fabdd2ad121fc25cf784d5a8fdb3`. Independent stop review verified 417 frozen source files, the contract/binary/evaluator/calibration hashes, all 256 batch-8 configs, and 29 distinct provider files (39340743 bytes). No scoped solver/evaluator/controller process remains; the additional read-only observer was stopped separately and its samples retained.

- [Batch terminals and archive/cleanup states](clean6/P09C_RESTART_STOP_BATCH008_BATCHES.csv)
- [All registered runs by dataset, family and configuration, including NOT_EXECUTED](clean6/P09C_RESTART_STOP_BATCH008_TERMINALS.csv)
- [ALL_YAW_REJECTED by family](clean6/P09C_RESTART_STOP_BATCH008_ALL_YAW_REJECTED.csv)
- [Separate archive technical failure](clean6/P09C_RESTART_STOP_BATCH008_TECHNICAL_FAILURES.csv)
- [Per-batch measured resources](clean6/P09C_RESTART_STOP_BATCH008_RESOURCES.csv)
- [Evidence hashes](clean6/P09C_RESTART_STOP_BATCH008_EVIDENCE.csv)
- [First-batch measured table](CLEAN6_CANONICAL541_V2_RESTART_PILOT.md)
- [C00 eleven-profile v3/v2 anchors](clean6/P09C_RESTART_C00_ANCHORS.csv)
- [Resource coverage and limitations](CLEAN6_CANONICAL541_V2_RESTART_RESOURCE_COVERAGE.md)

Preserved scene: `<CANONICAL541_V2_SCRATCH>/BATCH_008/`, `<CANONICAL541_V2_ROOT>/RETAINED_RUNS/`, and `<CANONICAL541_V2_ROOT>/RESTARTS/RESTART_20260912/`. Machine report: the last path's `RESTART_STOP_REPORT.json`. The original stopped-attempt records remain unchanged.
