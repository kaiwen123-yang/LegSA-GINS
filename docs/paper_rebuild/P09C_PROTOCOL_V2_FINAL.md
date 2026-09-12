# P-09c protocol v2 final numerical handoff

24 batches complete; native terminals `{'COMPLETED': 5869, 'ALGORITHM_FAILURE_ALL_YAW_REJECTED': 104}`; evaluator terminals `{'COMPLETED': 11738, 'NOT_RUN_ALGORITHM_FAILURE': 208}`; archive pending `0`. Sequence/C00 gate `PASS`, matched files `{'P07_C00': 77, 'P06_CAL': 105}`, combined `182/182`. All eleven CAL C00 configurations are retained in both evaluator versions. Original native reuse is 33, reruns 0.

Scientific commit: `737a0fb5a4a5418500824855b89b0d25af69824a`. Archive I/O commit: `ea478eea88aaf9739823dfc152fa108dd17f8d0c`. v3 is primary and v2 parallel. Delta is candidate minus reference; negative is better. The table copies frozen median intervals and finite/failure-aware denominators; displayed values use seven significant digits.

| Evaluator | Pair | Metric | Median delta | Median 95% CI | Finite win rate | N | Failure-aware win rate | Denominator |
|---|---|---|---:|---|---:|---:|---:|---:|
| v3 | full_vs_strong | horizontal_rmse_m | -0.001096684 | [-0.0011076, -0.00109324] | 0.8795411 | 523 | 0.8632163 | 541 |
| v3 | full_vs_strong | yaw_rmse_deg | -0.04717315 | [-0.04722884, -0.04717307] | 0.9732314 | 523 | 0.9537893 | 541 |
| v3 | full_vs_strong | yaw_p95_absolute_deg | -0.1395244 | [-0.1395251, -0.1395244] | 0.9789675 | 523 | 0.9593346 | 541 |
| v3 | full_vs_no_SA | horizontal_rmse_m | 0.0004458726 | [0.0004369789, 0.000452448] | 0.2428843 | 527 | 0.2421442 | 541 |
| v3 | full_vs_no_SA | yaw_rmse_deg | -0.01364626 | [-0.01364982, -0.01364626] | 0.8842505 | 527 | 0.8669131 | 541 |
| v3 | full_vs_no_SA | yaw_p95_absolute_deg | -0.005056774 | [-0.005056852, -0.005056774] | 0.7855787 | 527 | 0.7707948 | 541 |
| v3 | A04_vs_F03 | horizontal_rmse_m | -0.001545688 | [-0.001547641, -0.001545688] | 0.8954373 | 526 | 0.8853974 | 541 |
| v3 | A04_vs_F03 | yaw_rmse_deg | -0.03352681 | [-0.03353205, -0.03352681] | 0.9467681 | 526 | 0.935305 | 541 |
| v3 | A04_vs_F03 | yaw_p95_absolute_deg | -0.1344676 | [-0.1344676, -0.1344666] | 0.9790875 | 526 | 0.9667283 | 541 |
| v2 | full_vs_strong | horizontal_rmse_m | 0.003866627 | [0.003789383, 0.003884519] | 0.1988528 | 523 | 0.2051756 | 541 |
| v2 | full_vs_strong | yaw_rmse_deg | -0.04717315 | [-0.04722884, -0.04717307] | 0.9732314 | 523 | 0.9537893 | 541 |
| v2 | full_vs_strong | yaw_p95_absolute_deg | -0.1395244 | [-0.1395251, -0.1395244] | 0.9789675 | 523 | 0.9593346 | 541 |
| v2 | full_vs_no_SA | horizontal_rmse_m | -0.0005324295 | [-0.0005332246, -0.0005324295] | 0.829222 | 527 | 0.8133087 | 541 |
| v2 | full_vs_no_SA | yaw_rmse_deg | -0.01364626 | [-0.01364982, -0.01364626] | 0.8842505 | 527 | 0.8669131 | 541 |
| v2 | full_vs_no_SA | yaw_p95_absolute_deg | -0.005056774 | [-0.005056852, -0.005056774] | 0.7855787 | 527 | 0.7707948 | 541 |
| v2 | A04_vs_F03 | horizontal_rmse_m | 0.004400434 | [0.004340106, 0.004412608] | 0.1768061 | 526 | 0.1866913 | 541 |
| v2 | A04_vs_F03 | yaw_rmse_deg | -0.03352681 | [-0.03353205, -0.03352681] | 0.9467681 | 526 | 0.935305 | 541 |
| v2 | A04_vs_F03 | yaw_p95_absolute_deg | -0.1344676 | [-0.1344676, -0.1344666] | 0.9790875 | 526 | 0.9667283 | 541 |

V1/v2 frozen classification counts over both versions and all five metrics: `{'INCOMPLETE': 140, 'MAINTAINED': 8, 'FLIPPED': 2}`. Classifications are copied unchanged, including INCOMPLETE.

- [KEY_PAIRS](clean6/P09C_PROTOCOL_V2_FINAL_KEY_PAIRS.csv)
- [V1_V2_COMPARISONS](clean6/P09C_PROTOCOL_V2_FINAL_V1_V2_COMPARISONS.csv)
- [TERMINALS](clean6/P09C_PROTOCOL_V2_FINAL_TERMINALS.csv)
- [ALL_YAW_REJECTED](clean6/P09C_PROTOCOL_V2_FINAL_ALL_YAW_REJECTED.csv)
- [C00_ANCHORS](clean6/P09C_PROTOCOL_V2_FINAL_C00_ANCHORS.csv)
- [TIMING](clean6/P09C_PROTOCOL_V2_FINAL_TIMING.csv)
- [BOOKKEEPING_NOTES](clean6/P09C_PROTOCOL_V2_FINAL_BOOKKEEPING_NOTES.csv)
- [EVIDENCE](clean6/P09C_PROTOCOL_V2_FINAL_EVIDENCE.csv)

First-batch measurements copied from the existing pilot report:

| Item | Measured value |
|---|---:|
| nproc / solver pool | 24 / 22 |
| Available memory at batch start, bytes | 23816892416 |
| Evaluator pool sizes | [22] |
| Solver process-tree peak RSS, bytes | 5180096512 |
| Per-run recorded solver_seconds mean / min / max | 8.053166 / 6.429979 / 14.245862 |
| Per-run recorded runtime_seconds mean / min / max | 21.551352 / 7.918636 / 49.826044 |
| Solver output bytes mean / min / max | 73177315.964844 / 70151129 / 101459526 |
| Sealed solver+evaluation source bytes mean / min / max | 121484318.699219 / 117606082 / 165570887 |
| Retained bytes mean / min / max | 13149055.781250 / 12777985 / 17407736 |
| Retained allocated bytes mean / min / max | 22436864 / 21757952 / 26476544 |
| v3 evaluator seconds mean / min / max | 4.970566 / 3.896335 / 6.404246 |
| v2 evaluator seconds mean / min / max | 5.443883 / 3.811822 / 6.998400 |
| v3 RSS bytes mean / min / max | 251334736.000000 / 247914496.000000 / 305799168.000000 |
| v2 RSS bytes mean / min / max | 251454144.000000 / 247386112.000000 / 305602560.000000 |
| Restart batch wall seconds | 2079.1257006410005 |
| Prior attempt active prefix seconds | 68.495169 |
| Combined batch active seconds | 2147.6208696410004 |
| Restart freeze through pilot-report wall seconds | 2117.5306038856506 |
| CPU utilization fraction | 0.11849640346090072 |
| Owned process-tree RSS peak, bytes | 6288302080 |
| Scratch / G sampled peak growth since restart batch, bytes | 28446859264 / 6332088320 |
| Original retained scratch allocated bytes at restart | 2685743104 |
| Full execution time extrapolation, seconds | 51542.90087138401 |
| Full peak extrapolation, bytes | 221127477999 |
| solver_seconds mean / min / max (existing measured records; N=256) | 8.053166 / 6.429979 / 14.24586 |
| runtime_seconds mean / min / max (existing measured records; N=256) | 21.55135 / 7.918636 / 49.82604 |
| solver_output_bytes mean / min / max (existing measured records; N=256) | 7.317732e+07 / 7.015113e+07 / 1.014595e+08 |
| source_bytes mean / min / max (existing measured records; N=256) | 1.214843e+08 / 1.176061e+08 / 1.655709e+08 |
| retained_bytes mean / min / max (existing measured records; N=256) | 1.314906e+07 / 1.277798e+07 / 1.740774e+07 |
| retained_allocated_bytes mean / min / max (existing measured records; N=256) | 2.243686e+07 / 2.175795e+07 / 2.647654e+07 |

| Timing / occupancy item | Recorded value |
|---|---|
| total_wall_time_seconds | 56954.40605348201 |
| total_wall_time_scope | prior active prefix (including original batch8) plus selected final batch/recovery walls plus omitted batches>=9 closed RESOURCE_SAMPLES elapsed fragments; fragment final tails unavailable, so this is accounted active duration with explicit sampled parts; human pauses, administrative gaps, aggregate and pack excluded |
| total_wall_time_measurement_status | INCLUDES_SAMPLED_ELAPSED_FRAGMENTS_FINAL_TAIL_UNAVAILABLE |
| prior_active_seconds | 15860.835791578997 |
| current_archive_recovery_and_batches9_24_seconds | 41093.57026190301 |
| selected_batch_and_recovery_final_wall_seconds | 39416.81485901501 |
| omitted_closed_fragment_sampled_elapsed_seconds | 1676.755402888004 |
| recovered_batch_measurements | Structured measurements: see linked TIMING.csv |
| successful_archive_component_timings | Structured measurements: see linked TIMING.csv |
| original_start_to_execution_complete_seconds | 92609.910298 |
| original_start_to_execution_complete_scope | elapsed wall time including human pauses and administrative gaps |
| whole_execution_peak_status | UNAVAILABLE_EARLY_ABSOLUTE_BASELINES_NOT_STORED |
| remaining_batches_max_scratch_peak_growth_bytes | 34147487744 |
| remaining_batches_max_g_peak_growth_bytes | 7067140096 |
| disk_growth_scope | per-batch sampled filesystem changes; recovered batch absolute samples rebased to its original baseline where available; concurrent activity included; not a retroactive whole-execution peak |
| scientific_code_commit | 737a0fb5a4a5418500824855b89b0d25af69824a |
| io_fix_code_commit | ea478eea88aaf9739823dfc152fa108dd17f8d0c |
| continuation_resource_sample_count | 13849 |
| continuation_scratch_peak_growth_bytes | 3865583616 |
| continuation_g_peak_growth_bytes | 103455916032 |
| continuation_simultaneous_combined_peak_growth_bytes | 101214117888 |
| continuation_combined_occupancy_estimate_bytes | 178005286912 |
| continuation_combined_occupancy_scope | fixed measured task allocation baseline plus simultaneous sampled net filesystem growth; estimate, not exact isolated-task or whole-execution peak |
| continuation_disk_measurement_scope | batch8 I/O recovery and batches9-24 resource samples versus the current continuation baseline; filesystem-wide changes may include concurrent activity; no retrospective early samples |
| aggregate_wall_seconds | 414.81821122099063 |

Active wall and elapsed wall scopes remain those recorded in AGGREGATION_INVOCATION. Aggregate duration is separate. Whole-execution absolute peak remains UNAVAILABLE where early baselines were not stored; later baselines are not retrospective peaks.

ZIP validation: `PASS_COPIED_FROM_COMPLETED_VALIDATION`; ZIP SHA-256: `30e6e263922ed317db0bc6e1cabe4b38d576bd0ec501e1f8f7b45fffa94beefb`. The hash is copied from the completed validation file when available.

RUN_01963 historical gap: `sealed post-hoc after archival interruption; content verified against scratch (size+sha256)`. `historical_full_file_seal_available=false`; both v3 and v2 are covered. The original missing historical seal and STOP records remain preserved.

Bookkeeping notes: 441 unique entries after deduplication of BATCH_LEDGER.jsonl notes and BATCH_LEDGER.notes. The linked notes CSV retains source locations, repeated-entry counts and complete alias-converted note content.

Final scratch release supplement: 198 derived preparation files (66,327,303 bytes) from batch 14 attempt01 were omitted by the original cleanup plan. All five affected runs have verified attempt02 archive receipts. The exact supplemental plan and per-file INTENT/DELETED ledger passed; remaining scratch file count is 0. Original batch timing and cleanup ledgers are unchanged; this final bookkeeping release is recorded separately.
