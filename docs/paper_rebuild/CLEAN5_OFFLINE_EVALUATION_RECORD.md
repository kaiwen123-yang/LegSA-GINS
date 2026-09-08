# CLEAN5 C-05 offline evaluation and decision-input record

Feature/code-freeze commit: `64a25e667c10ba30499108edaa8f559a5bef8b64`. Record commit: this commit. Validation: 432 passed. A2 is PASS; BY2H and BY2O each completed five formal offline evaluations with sequence gate PASS. Decision-input extraction completed after both sequence gates. No solver rerun, provider generation, configuration tuning, plotting or manuscript-role selection is recorded.

## C-05 A2 evaluator identity record (2026-09-08)

A2 completed with `status=PASS` and `full_identity_gate=PASS` before BY2H/BY2O formal evaluation. This section records only the authorized known-C00 reproduction, synthetic column-selection tests and three header-only reads. It contains no new-sequence performance results, manuscript-role decision or metric interpretation.

| Identity | Value |
| --- | --- |
| implementation/code freeze | `64a25e667c10ba30499108edaa8f559a5bef8b64` |
| tests | 432 passed |
| A2 created_at (UTC) | 2026-09-08T12:22:16.711310+00:00 |
| archived evaluator SHA-256 | `aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da` |
| A2 evidence root | `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY` |
| A2-1 | `PASS_KNOWN_C00_TWELVE_METRIC_REPRODUCTION` |
| A2-2 | `PASS_SYNTHETIC_COLUMN_SELECTION_AND_HOOK_PARITY` |
| A2-3 | PASS; identical 80-byte headers, selected columns plain |
| BY2H/BY2O evaluator execution count during A2 | 0 |
| parent raw-reference content opens | 0 |

The archived script remains byte-identical. Observation captures selected columns and hashes the evaluator's already-open reference handle before pandas parsing, then rewinds that handle. It does not replace evaluator functions, arrays, statistics or input columns. A2 uses two known C00 evaluator executions, four synthetic evaluator executions and one separate header syscall-audit session.

### A2-1: twelve-field known-C00 reproduction

Sources are the frozen Canonical unique terminal/evaluation registries, not the manuscript rounded anchors. The frozen registry resolves A04 to `<CANONICAL541_ATTEMPT>/10_INTERNAL_ABLATION_RUNS/RUN_00006`, physical CSV row 7, and F04 to `<CANONICAL541_ATTEMPT>/08_FULL_ALGORITHM_RUNS/RUN_00004`, physical CSV row 5. A04 is in `10_INTERNAL_ABLATION_RUNS`; it is not read from an assumed `08_FULL_ALGORITHM_RUNS` location. `<CANONICAL541_ATTEMPT>` denotes `<CLEAN_ROOT>/stages/CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX/.attempt_20260808T200855P0800`. Physical row numbers are 1-based including the header. Selected NAV, STD and native-manifest inputs match six frozen OUTPUT_HASH_MANIFEST entries; other Canonical payloads were not opened by this proof. Every field below passes relative difference <=1e-10; a zero frozen reference requires exact zero.

| Field | A04 frozen token | A04 fresh | A04 relative difference | F04 frozen token | F04 fresh | F04 relative difference | gates |
| --- | --- | --- | --- | --- | --- | --- | --- |
| horizontal_rmse_m | 0.35238638733674005 | 0.35238638733674005 | 0.0 | 0.3548025409632719 | 0.354802540963272 | 3.1291292943138295e-16 | PASS / PASS |
| horizontal_p95_m | 0.5609714085594036 | 0.5609714085594036 | 0.0 | 0.56696110163272 | 0.56696110163272 | 0.0 | PASS / PASS |
| horizontal_max_m | 0.852705970599069 | 0.852705970599069 | 0.0 | 0.8724294262918791 | 0.8724294262918791 | 0.0 | PASS / PASS |
| position_3d_rmse_m | 0.8903584609765574 | 0.8903584609765574 | 0.0 | 0.9263782283427902 | 0.9263782283427902 | 0.0 | PASS / PASS |
| up_rmse_m | 0.8176564211527388 | 0.8176564211527388 | 0.0 | 0.855740485704359 | 0.855740485704359 | 0.0 | PASS / PASS |
| up_p95_absolute_m | 1.5621602804240131 | 1.5621602804240131 | 0.0 | 1.66507248064606 | 1.66507248064606 | 0.0 | PASS / PASS |
| up_max_absolute_m | 2.423406633206426 | 2.423406633206426 | 0.0 | 2.678948040249439 | 2.678948040249439 | 0.0 | PASS / PASS |
| yaw_rmse_deg | 1.9340756561653565 | 1.9340756561653565 | 0.0 | 1.9549590248265367 | 1.9549590248265367 | 0.0 | PASS / PASS |
| yaw_p95_absolute_deg | 3.5190897118359357 | 3.5190897118359357 | 0.0 | 3.489695180632398 | 3.489695180632398 | 0.0 | PASS / PASS |
| yaw_max_absolute_deg | 9.285013805238409 | 9.285013805238407 | 1.9131439938172925e-16 | 9.15938836723842 | 9.15938836723842 | 0.0 | PASS / PASS |
| position_3d_p95_m | 1.6040762897388117 | 1.6040762897388117 | 0.0 | 1.7084924311510445 | 1.7084924311510445 | 0.0 | PASS / PASS |
| position_3d_max_m | 2.4888093822110378 | 2.4888093822110378 | 0.0 | 2.721181392791411 | 2.721181392791411 | 0.0 | PASS / PASS |

| Method | run_id | exit | runtime_seconds | yaw RMSE rounded 6 / required | trace/raw opens | total opens | writes / raw writes / outside writes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A04 | RUN_00006 | 0 | 4.6942904429997725 | 1.934076 / 1.934076 | 1 / 1 | 841 | 3 / 0 / 0 |
| F04 | RUN_00004 | 0 | 4.839294282999617 | 1.954959 / 1.954959 | 1 / 1 | 841 | 3 / 0 / 0 |

Each C00 child opens the locked BY2 reference exactly once, read-only, with capture PID equal to the strace reference-open PID; bag/fpl opens are 0. The parent reference-open count is 0. BY2 reference SHA-256 is `ee3ee42dea3ada196dfdbcc78fd07524f91b4ce4fb94d9d6482a3e7d4b34aa4c`. These two runs are identity-reproduction evidence only.

### A2-2: frozen source selection and synthetic response

Archived source: `<CLEAN_ROOT>/16_FINAL_V23_ARCHIVE_RECOVERY/ARCHIVE_45953164c53e/selected/MAIN/KF-GINS/bin/evaluate_nav_trace_kfgins_v2.py`, 18195 bytes; `load_trace` lines 140–172, function-source SHA-256 `487853df5279e8675902954a15e06a9a985924cf39cca9c6e4cff02ce6a6f224`. Its search iterates ordered candidate names and then source-header order, using a case-insensitive exact-or-substring match. The observed header places plain fields before processed fields; it does not establish a universal preference for exact names regardless of column order.

| Field | assignment line | variable | ordered candidates | selected synthetic/actual header column |
| --- | --- | --- | --- | --- |
| time | 148 | time_col | aligned_time, time, stamp, timestamp | time |
| lat | 149 | lat_col | lat, latitude, pos_lat | lat |
| lon | 150 | lon_col | lon, longitude, pos_lon | lon |
| height | 151 | alt_col | height, alt, altitude, pos_height | height |
| roll | 152 | roll_col | roll | roll |
| pitch | 153 | pitch_col | pitch | pitch |
| yaw | 154 | yaw_col | yaw | yaw |

The unselected synthetic fields are `processed_lat`, `processed_lon` and `processed_height`. Time is `time-base_time` unless the selected field name contains `aligned_time`. Yaw uses reference unwrapping, `wrap360(90-yaw_enu)` and a wrap-safe residual. No time-offset/sign/frame/column search or evaluator modification occurred.

Synthetic identity fixture: data_mode=`synthetic_evaluator_identity_only`, synthetic_data_used=true, semisynthetic_data_used=false, eligible_for_real_result_tables=false. It has 11 rows, base_time=1000.0, window=[10.0, 20.0], ECEF straight-motion velocity [2.0, -1.0, 0.5] m/s and yaw rate 2.0 deg/s. All three processed geodetic fields differ from their plain counterparts; the frozen ECEF offset vector is [267.2612419124244, 534.5224838248488, 801.7837257372732] m, target 1000.0 m, with recorded norm range [999.9999999989483, 1000.0000000009395] m.

| Synthetic field | plain | plain/processed swapped | plain yaw +90 deg |
| --- | --- | --- | --- |
| horizontal_rmse_m | 0.0 | 683.7530949797472 | 0.0 |
| horizontal_p95_m | 0.0 | 683.7530949810518 | 0.0 |
| horizontal_max_m | 0.0 | 683.7530949811714 | 0.0 |
| position_3d_rmse_m | 0.0 | 999.999999999763 | 0.0 |
| position_3d_p95_m | 0.0 | 1000.0000000008151 | 0.0 |
| position_3d_max_m | 0.0 | 1000.0000000011886 | 0.0 |
| up_rmse_m | 0.0 | 729.7134404032468 | 0.0 |
| up_p95_absolute_m | 0.0 | 729.7134404039953 | 0.0 |
| up_max_absolute_m | 0.0 | 729.7134404041248 | 0.0 |
| yaw_rmse_deg | 0.0 | 0.0 | 90.0 |
| yaw_p95_absolute_deg | 0.0 | 0.0 | 90.0 |
| yaw_max_absolute_deg | 0.0 | 0.0 | 90.0 |

| Registered synthetic check | Result |
| --- | --- |
| plain_nav_matches_plain_columns | PASS |
| swapped_plain_columns_have_1000m_error | PASS |
| yaw_column_plus_90_changes_yaw_error_by_90 | PASS |
| baseline_yaw_matches | PASS |

Registered tolerances: matching position maximum <=0.001 m; swapped-coordinate 3D target 1000 m with absolute tolerance 0.01 m; yaw shift 90 deg with tolerance 1e-10 deg. The 1000 m target is 3D/ECEF displacement, not horizontal displacement. These values test field identity and are excluded from real-data result tables.

| Observed versus plain output | Byte-identical | uninstrumented SHA-256 | instrumented SHA-256 |
| --- | --- | --- | --- |
| summary.json | True | `bc95197ccb4bf359624f50a30c38a879665a7c27b26ce07998ffacf4f8afde8f` | `bc95197ccb4bf359624f50a30c38a879665a7c27b26ce07998ffacf4f8afde8f` |
| error_series.csv | True | `b9ccfa0dee7919ff8e73c7a3951b007af7f678db272711a49c085b5384f8699b` | `b9ccfa0dee7919ff8e73c7a3951b007af7f678db272711a49c085b5384f8699b` |

| Synthetic execution | variant | instrumented | exit | runtime_seconds | reference opens | raw-root opens | write/outside/raw-write counts |
| --- | --- | --- | --- | --- | --- | --- | --- |
| plain_uninst | plain | False | 0 | 1.2253739119987586 | 1 | 0 | 2 / 0 / 0 |
| plain_inst | plain | True | 0 | 1.1802589990002161 | 1 | 0 | 3 / 0 / 0 |
| swap_inst | swap | True | 0 | 1.1488400449998153 | 1 | 0 | 3 / 0 / 0 |
| yaw90_inst | yaw90 | True | 0 | 1.1962563449997106 | 1 | 0 | 3 / 0 / 0 |

All four synthetic runs have bag/fpl opens 0. Synthetic references reside under the A2 synthetic-input directory rather than RAW_ROOT; raw-root open count 0 does not mean the synthetic reference was not read. The uninstrumented baseline has no capture; each instrumented run records one reference hash on the existing evaluator handle.

### A2-3: actual header-only equivalence

The three actual reference files were opened in the dedicated header child using one-byte `os.read` calls until the first LF. The syscall audit verifies that the returned bytes equal exactly one header line and includes no data-line byte. Each source header is exactly:

```csv
time,lat,lon,height,processed_lat,processed_lon,processed_height,yaw,pitch,roll
```

| Dataset | read role | bytes | data-line bytes | PID | header SHA-256 |
| --- | --- | --- | --- | --- | --- |
| BY2 | header_only_read | 80 | 0 | 24013 | `ac1eb992a3eb705e1313eec12e91c83268eb2e9f9d0b4e5eb1ffb629dc69107d` |
| BY2H | header_only_read | 80 | 0 | 24013 | `ac1eb992a3eb705e1313eec12e91c83268eb2e9f9d0b4e5eb1ffb629dc69107d` |
| BY2O | header_only_read | 80 | 0 | 24013 | `ac1eb992a3eb705e1313eec12e91c83268eb2e9f9d0b4e5eb1ffb629dc69107d` |

Header bytes and column lists are identical; every row resolves to plain `time,lat,lon,height,yaw,pitch,roll` under the unchanged source rule. Header audit: trace opens=3, bag opens=0, fpl opens=0, data-line bytes=0, writes=1, raw writes=0, outside-output writes=0. Equivalence basis: `identical headers plus C00 reproduction`. This explicitly authorized header read is separate from full-reference evaluation and from integrity-hash checkpoints.

### A2 artifact references

The table below identifies small A2 metadata/logs by a read-only SHA-256 calculation. The archived-source, frozen-input, synthetic-input, error-series and strace hashes in the subsequent tables are copied from the frozen identity metadata; their payloads were not reread while preparing this section. Paths are portable aliases.

| Small metadata/log path | SHA-256 | bytes |
| --- | --- | --- |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/EVALUATOR_IDENTITY_GATE.json` | `8cf25e267d215104ae425cd45179b8cb8a9319d37960f9a2d5df63624e06ecf9` | 313772 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/A2_1_C00_REPRODUCTION_GATE.json` | `712d6fa60f47c421786e9c4daf475b42c388d92fadc72aaad885c6cf22686b4f` | 37929 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/A2_2_SYNTHETIC_GATE.json` | `646303789e01122054e73e7dc6325e329be0c96e9f23a384e5a8fa18dbcb9ae1` | 43906 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/HEADER_ONLY/HEADER_GATE.json` | `8002e07a18036945aac48682dccdb4dbd58fb7294dbad482103680aab94c9c95` | 5050 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/HEADER_ONLY/HEADER_ONLY_READS.json` | `a9e570e7d77861a2bf0d87a2a8d85421eb9c94bdb8175c1bbd55e92a0660b442` | 3332 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/HEADER_ONLY/stdout.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/HEADER_ONLY/stderr.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/C00_A04/CAPTURE_CONFIG.json` | `a92bd441f923f9fb360da175b503a95e0afd0d2314a48e41513f9a988d1c678c` | 703 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/C00_A04/EVALUATOR_CAPTURE.json` | `31ffacf53b74c1040944b1a0053a671d7c8b6a5217cc6291a6d51232b794e56e` | 1482 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/C00_A04/EVALUATOR_STRACE_AUDIT.json` | `4a9622edcac814883ce29c148d3f62ebed154c84e672c64a674207b9e556a019` | 4787 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/C00_A04/summary.json` | `88af374700a82931f3acf3ff58a2f662f3dd796d9f65d92cd468d298638fd102` | 1509 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/C00_A04/evaluator_stdout.log` | `645402029e2936833db984afa30427c728510f855660f1dbac886fa3b3b965d7` | 2965 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/C00_A04/evaluator_stderr.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/C00_F04/CAPTURE_CONFIG.json` | `358f4e23b9de4680a718a4e6ee2c5ef06b0870efd276a5d6704b95cb7565d4ce` | 703 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/C00_F04/EVALUATOR_CAPTURE.json` | `3d8af556766a1ba9820ebba3276a8f5c8f538deef316f268e8813edca52a4ae8` | 1482 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/C00_F04/EVALUATOR_STRACE_AUDIT.json` | `ccdb3791018ed7897acacbad93c0fd692eca541d45981424447c0f2cdd57e0bf` | 4780 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/C00_F04/summary.json` | `53ac6cb775f48f89c21bded32f83e7dc68a291a1a551c6ce33c91e6488cacf78` | 1514 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/C00_F04/evaluator_stdout.log` | `8a53b6f8392bf0b8d87f9cd5a7736f94889d71b0ac8f16d957580c069d39bef1` | 2965 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/C00_F04/evaluator_stderr.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/plain_uninst/CAPTURE_CONFIG.json` | `acdc35ae3d9bc83602a6cbe3aa55cd0a01f1f6d7dbdb377e7f2b718aeacc48b5` | 672 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/plain_uninst/EVALUATOR_STRACE_AUDIT.json` | `40db77523d4b2b0a8da48631f4ffb482564cb55b6e143d7d75ac99ccce022367` | 3905 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/plain_uninst/summary.json` | `bc95197ccb4bf359624f50a30c38a879665a7c27b26ce07998ffacf4f8afde8f` | 1082 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/plain_uninst/evaluator_stdout.log` | `ca17ff819143948c28754573b6edb18768b8fddc6705b8937a323de15827d169` | 2842 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/plain_uninst/evaluator_stderr.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/plain_inst/CAPTURE_CONFIG.json` | `74672f7a3c869b858982668114469e5dac5fa7b5d858396cb957c874b3a531ba` | 670 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/plain_inst/EVALUATOR_CAPTURE.json` | `8cc9e64f55e26a469b59c700da68e4af8bce495f0736483a5b9ef753efab6f23` | 1417 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/plain_inst/EVALUATOR_STRACE_AUDIT.json` | `a4683ad30491826884839a7009e5ed80d2dd5c12ef0312e748f7da413b6d91c1` | 4595 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/plain_inst/summary.json` | `bc95197ccb4bf359624f50a30c38a879665a7c27b26ce07998ffacf4f8afde8f` | 1082 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/plain_inst/evaluator_stdout.log` | `51f8e96036bbe8d918ba71d117b990d5ff14a3ce9ec9df45aca4c72b5c25f449` | 2981 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/plain_inst/evaluator_stderr.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/swap_inst/CAPTURE_CONFIG.json` | `595ee237ebb7c4a8b3bcf59316bb5eeef646b4b3821c12a07b0e9f04a0193e73` | 668 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/swap_inst/EVALUATOR_CAPTURE.json` | `099ce3da15c295a3745e24cbade1dbbe0b629fa916d501c9259f3d8519fd2358` | 1448 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/swap_inst/EVALUATOR_STRACE_AUDIT.json` | `614672b7968d259fe16885c02e3ec399feb7bbe90c747d3340a0fc2ad66bb930` | 4582 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/swap_inst/summary.json` | `c91762923f7cebc1c85567478a213a632100092be469ec6b3e699f568b357b46` | 1222 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/swap_inst/evaluator_stdout.log` | `fcf1ee5ac7df24da1458a428704844263f897e0eec61fadd741537c6e7c5cbdc` | 2973 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/swap_inst/evaluator_stderr.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/yaw90_inst/CAPTURE_CONFIG.json` | `4a5a53ac9e90c8f039681fdc479c8ed015a2f4317b7928d819e581d5431104f6` | 670 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/yaw90_inst/EVALUATOR_CAPTURE.json` | `034a1ddfc6be23f9886b3f498c2e0baa888349b7b07f1bfd60256b3792702285` | 1417 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/yaw90_inst/EVALUATOR_STRACE_AUDIT.json` | `825e8850cb08c5cc55ceb84ce43296b7d7f418572545f6160f25dd5801bb977e` | 4595 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/yaw90_inst/summary.json` | `bc1c399cfae420c1eb52c343411a3e4071570d722264d8009e9610661c30fcd0` | 1086 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/yaw90_inst/evaluator_stdout.log` | `d7e78fed7b8b94d104ebb463761f6fc6c06a92e0fe8d006caebc63f522ca1c07` | 2977 |
| `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/yaw90_inst/evaluator_stderr.log` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 |

| Recorded source/output reference | Path | recorded SHA-256 | bytes |
| --- | --- | --- | --- |
| archived evaluator | `<CLEAN_ROOT>/16_FINAL_V23_ARCHIVE_RECOVERY/ARCHIVE_45953164c53e/selected/MAIN/KF-GINS/bin/evaluate_nav_trace_kfgins_v2.py` | `aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da` | 18195 |
| frozen unique_terminal_registry | `<CLEAN_ROOT>/stages/CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX/.attempt_20260808T200855P0800/11_OUTPUT_SEAL/UNIQUE_RUN_TERMINAL_REGISTRY.csv` | `114b44ca662ff480978321a3cf3e24930313cd377e50aa4df3317a88682ef927` | 9762804 |
| frozen unique_evaluation_results | `<CLEAN_ROOT>/stages/CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX/.attempt_20260808T200855P0800/12_OFFLINE_EVALUATION/UNIQUE_EVALUATION_RESULTS.csv` | `d9e236f677fee85858224a09f1f6bb763193980d0190787fdf7100463d494c4f` | 49631414 |
| Canonical output_hash_manifest | `<CLEAN_ROOT>/stages/CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX/.attempt_20260808T200855P0800/11_OUTPUT_SEAL/OUTPUT_HASH_MANIFEST.csv` | `98d5588d7a068c56a95059a01b8957ffd66b7fddc36ea295643e03d5aeb2492b` | 41716892 |
| Canonical output_seal_journal | `<CLEAN_ROOT>/stages/CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX/.attempt_20260808T200855P0800/11_OUTPUT_SEAL/OUTPUT_SEAL_JOURNAL.json` | `0a6c8ac34bb01e58d1a3663a9c400dcaf827ae9b79f487a313a2b970103a1602` | 958 |
| C00 A04 KF_GINS_Navresult.nav; seal CSV row 106 | `<CLEAN_ROOT>/stages/CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX/.attempt_20260808T200855P0800/10_INTERNAL_ABLATION_RUNS/RUN_00006/KF_GINS_Navresult.nav` | `3463c03dbdebe3d21e7e7e8fb50e20a8c9e7eeb5b68a5f4f1c335ca024a33923` | 10025634 |
| C00 A04 KF_GINS_STD.txt; seal CSV row 107 | `<CLEAN_ROOT>/stages/CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX/.attempt_20260808T200855P0800/10_INTERNAL_ABLATION_RUNS/RUN_00006/KF_GINS_STD.txt` | `849a6ed7641a2443a8495480e3429d9669a705b0a5c8277486ec2fc3188097f3` | 19994626 |
| C00 A04 RUN_MANIFEST.json; seal CSV row 114 | `<CLEAN_ROOT>/stages/CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX/.attempt_20260808T200855P0800/10_INTERNAL_ABLATION_RUNS/RUN_00006/RUN_MANIFEST.json` | `b5534845478dc4f34e3c397f716768ab1d1b289866f20172e32043169cce3dd4` | 21460 |
| C00 F04 KF_GINS_Navresult.nav; seal CSV row 66 | `<CLEAN_ROOT>/stages/CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX/.attempt_20260808T200855P0800/08_FULL_ALGORITHM_RUNS/RUN_00004/KF_GINS_Navresult.nav` | `0b9249b36dd450e272125272ef4fec9a0e9490de6408b4bea386fcfea4ba4b37` | 10025634 |
| C00 F04 KF_GINS_STD.txt; seal CSV row 67 | `<CLEAN_ROOT>/stages/CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX/.attempt_20260808T200855P0800/08_FULL_ALGORITHM_RUNS/RUN_00004/KF_GINS_STD.txt` | `aa74014d4eb763eb0dcf214bd0c6864601a963c0142737b1a095786379347c62` | 19994626 |
| C00 F04 RUN_MANIFEST.json; seal CSV row 74 | `<CLEAN_ROOT>/stages/CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX/.attempt_20260808T200855P0800/08_FULL_ALGORITHM_RUNS/RUN_00004/RUN_MANIFEST.json` | `7f85232b61170c21a0cb2bcbada250ba9d5abad4f7125309506a6da7807c6e32` | 21895 |
| synthetic plain reference | `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SYNTHETIC_INPUTS/synthetic_reference_plain.csv` | `1d535e92c807902c2aa8a4de10be20a2fde4392fa2d9aa3cbb402f475d045792` | 1456 |
| synthetic swap reference | `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SYNTHETIC_INPUTS/synthetic_reference_swap.csv` | `523be5613dc688215247e7dc9c2c0da37f64f3ed2b5e4f85bf1a64398a88d4d8` | 1456 |
| synthetic yaw90 reference | `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SYNTHETIC_INPUTS/synthetic_reference_yaw90.csv` | `a7c649ca1fc0f5dbe0e427307891850e9e1030d313204bcde82955d9ef81eed6` | 1467 |
| synthetic nav | `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SYNTHETIC_INPUTS/SYNTHETIC_NAV.nav` | `f864657fbef596218b04a24f0985fad7abaff9aff18d9e8b6ba83fff81a60809` | 806 |
| synthetic std | `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SYNTHETIC_INPUTS/SYNTHETIC_STD.txt` | `82f2fb311ae34b819884c84bb40e72813782f5d19dee12a2a344f9648b88718e` | 231 |
| A04 error series | `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/C00_A04/error_series.csv` | `abcfd663063ef915049726e7b99bc2089f95e445e2d09f646d82214885d84bcf` | 13062349 |
| F04 error series | `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/C00_F04/error_series.csv` | `105620d7c0d0d15b8ba17abfb554b4957ebdf85cb869d95e5bbab66236bd3fcd` | 13065154 |
| plain_uninst error series | `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/plain_uninst/error_series.csv` | `b9ccfa0dee7919ff8e73c7a3951b007af7f678db272711a49c085b5384f8699b` | 889 |
| plain_inst error series | `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/plain_inst/error_series.csv` | `b9ccfa0dee7919ff8e73c7a3951b007af7f678db272711a49c085b5384f8699b` | 889 |
| swap_inst error series | `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/swap_inst/error_series.csv` | `e7f39199fad195ac3ef5ed13c97da6a0c9d818ba463d0161f46030487dfadc51` | 1695 |
| yaw90_inst error series | `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/yaw90_inst/error_series.csv` | `a9a2a816e1e5532b4854a8062426d20369dfd58cf7d273e1eefeb8d3677c61ca` | 900 |

| Session | Strace path | metadata-recorded SHA-256 |
| --- | --- | --- |
| A04 | `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/C00_A04/EVALUATOR_OPENAT.strace` | `710538c29162862b1c9bfdb4bee5c5b7388259c678ba0d18367a19d519687a53` |
| F04 | `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/C00_F04/EVALUATOR_OPENAT.strace` | `821743f805eb73eb1082ddac36a99b80549a163302c3a1a00e08b8dca75aeac5` |
| plain_uninst | `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/plain_uninst/EVALUATOR_OPENAT.strace` | `3b63e4249a6eb0f175a5e3d8b15b2ecca3748cbc5f5b1f216b9f700f8740e3ea` |
| plain_inst | `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/plain_inst/EVALUATOR_OPENAT.strace` | `422e126c993f0fa75823f9b4259fbde3e9bc4e67243ff298f988edd2fa275e6c` |
| swap_inst | `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/swap_inst/EVALUATOR_OPENAT.strace` | `83b29f269eb8f4c73d7cb8bb713bd7303d75a995c6d3265cf0ec8755327191bb` |
| yaw90_inst | `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/SCRATCH/yaw90_inst/EVALUATOR_OPENAT.strace` | `b2eb06da2ce97b14cfd43446df0b99d031a1674f14e274f48ff5a2f2e6e21a30` |
| header-only | `<CLEAN_ROOT>/stages/CLEAN5_DECISION/00_EVALUATOR_IDENTITY/HEADER_ONLY/HEADER_ONLY.strace` | `e154c523ecbccc94ca5a64bc31daccaa40f3745c6290d7af5bdd45fcac25b137` |

Frozen BY2 raw hash lock: `<CLEAN_ROOT>/01_RAW_HASH_LOCK/RAW_FILE_HASH_LOCK.csv`, SHA-256 `f6e5d7965d17857e5b4a846501883f4675f2331a1164fab3de9e5ba9470f1ad7`; reference SHA-256 `ee3ee42dea3ada196dfdbcc78fd07524f91b4ce4fb94d9d6482a3e7d4b34aa4c` (verified inside each C00 evaluator child). The decision-rule file remains unchanged at SHA-256 `4699d35abbfd8a56f282323b082aa5e29658e62a9575f3812836a6095f8fecce`.

A2 completion is limited to evaluator identity and read-scope admission. This section does not report BY2H/BY2O evaluation completion and does not append the frozen rule's decision section.

## C-05 formal BY2H/BY2O evaluations

The following values are transcribed from frozen `08_AGGREGATE` tables and `07_OFFLINE_EVALUATION` metadata. No NAV, STD, reference-trace or error-series payload was read to prepare this record. Sources use the sequence stages below; CSV row references are physical 1-based rows including the header. Numeric tokens are copied as stored; blank non-applicable segment signed means are displayed as NA.

| Dataset | stage root | window | data_mode |
| --- | --- | --- | --- |
| BY2H | `<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE` | [413.0, 683.0] | real_by2h_raw |
| BY2O | `<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE` | [3186.0, 3563.0] | real_by2o_raw |

The evaluator reads the reference only in each archived-evaluator child. The selected fields are `time,lat,lon,height,yaw,pitch,roll`, matching A2 header evidence. Reference identity remains Fixposition-derived same-source evaluation reference, not independent ground truth. `synthetic_data_used=false`, `semisynthetic_data_used=false` and `trace_used_online=false` apply to the formal result rows.

### Ten full-window metric rows

Source: each stage's `08_AGGREGATE/UNIQUE_EVALUATION_RESULTS.csv`. H/3D/Up/yaw RMSE and yaw P95/max correspond exactly to columns `horizontal_rmse_m`, `position_3d_rmse_m`, `up_rmse_m`, `yaw_rmse_deg`, `yaw_p95_absolute_deg`, `yaw_max_absolute_deg`.

| Dataset | method | CSV row | H RMSE m | 3D RMSE m | Up RMSE m | yaw RMSE deg | yaw P95 deg | yaw max deg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BY2H | F01 | 2 | 0.350287318034121 | 0.9382312930697655 | 0.8703888522492844 | 3.901903684236999 | 7.587503061763519 | 15.608760155983362 |
| BY2H | F02 | 3 | 0.3533047246267501 | 0.94093394829563 | 0.8720851257828101 | 2.122373174596984 | 4.49810212166371 | 9.660404227614208 |
| BY2H | F03 | 4 | 0.3493989341446908 | 0.9378185121275451 | 0.8703010665899913 | 2.007378775222027 | 3.9689476459262805 | 9.183711050614193 |
| BY2H | A04 | 5 | 0.34935966382182015 | 0.9376283343409457 | 0.8701119000756633 | 2.059813237028886 | 4.106967381555717 | 9.228891656614223 |
| BY2H | F04 | 6 | 0.3519394504567077 | 0.9820147384460368 | 0.9167832730462901 | 2.068136355189828 | 4.117244083402463 | 9.182745849614207 |
| BY2O | F01 | 2 | 0.34885606913950923 | 1.226955126402717 | 1.1763155721278356 | 6.904338520339069 | 11.147492790748924 | 19.77780176530177 |
| BY2O | F02 | 3 | 0.35126814394043093 | 1.2301223765060691 | 1.1789027747162122 | 2.799343199123982 | 4.331735138305672 | 14.178272026725551 |
| BY2O | F03 | 4 | 0.34829103801970734 | 1.2267485149897945 | 1.1762675171341004 | 3.3117800038172738 | 5.416606535325678 | 15.842345957301774 |
| BY2O | A04 | 5 | 0.3480453400303894 | 1.2265283026818157 | 1.1761105894271449 | 3.31421398690487 | 5.474313206398441 | 15.838141305301775 |
| BY2O | F04 | 6 | 0.3509123233117259 | 1.6027327531292752 | 1.5638455228382735 | 3.4041823976228605 | 5.6101672674416 | 16.022958167301795 |

### BY2O A04/F04 complete window-segment rows

Source: `08_AGGREGATE/WINDOW_SEGMENT_SUMMARY.csv`, columns `segment_id,metric_name,unit,rmse,p95_abs,max_abs,count,signed_mean,time_start,time_end,secondary_run_epoch_count`. The main input-side occlusion interval is [3369.943066596985,3411.951585292816]; the pre-registered secondary interval is [3495.939144849777,3508.9415624141693]. Pre is before the main start, during includes both main endpoints, post is after the main end, outside is pre union post, and full is the complete evaluation window. The secondary interval is retained in post/outside/full; its row counts are copied below. During-window values are reported and do not enter decision inputs.

BY2O A04:

| segment | metric | unit | rmse | p95_abs | max_abs | count | signed_mean | time_start | time_end | secondary epochs | CSV row |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pre | horizontal | m | 0.3681680550722095 | 0.6429532590245733 | 1.374752529492454 | 38538 | NA | 3186.005234 | 3369.941063 | 0 | 62 |
| pre | position_3d | m | 1.388612144746291 | 3.6034417224322053 | 6.388056961010628 | 38538 | NA | 3186.005234 | 3369.941063 | 0 | 63 |
| pre | up | m | 1.3389159688947025 | 3.593659178430634 | 6.387054071838184 | 38538 | -0.5768680517853815 | 3186.005234 | 3369.941063 | 0 | 64 |
| pre | yaw | deg | 4.2516643999771215 | 9.049299871852261 | 15.838141305301775 | 38538 | 2.953596882887731 | 3186.005234 | 3369.941063 | 0 | 65 |
| during | horizontal | m | 0.17865574827394134 | 0.23242023186522234 | 0.2626967566210383 | 7611 | NA | 3369.947066 | 3411.947048 | 0 | 66 |
| during | position_3d | m | 0.7621102789644417 | 1.5350860637224466 | 3.3708606903328016 | 7611 | NA | 3369.947066 | 3411.947048 | 0 | 67 |
| during | up | m | 0.7408739440093283 | 1.5215059854743664 | 3.3643397360874943 | 7611 | -0.05878070683212565 | 3369.947066 | 3411.947048 | 0 | 68 |
| during | yaw | deg | 2.5240078398789034 | 3.062457536952678 | 3.217824663995998 | 7611 | 2.503602374307646 | 3369.947066 | 3411.947048 | 0 | 69 |
| post | horizontal | m | 0.35383914556902646 | 0.5906399511717733 | 1.098427683309089 | 30399 | NA | 3411.953049 | 3562.997055 | 2754 | 70 |
| post | position_3d | m | 1.0946434382137264 | 2.250347001627515 | 4.283447667517263 | 30399 | NA | 3411.953049 | 3562.997055 | 2754 | 71 |
| post | up | m | 1.0358774618106863 | 2.236859664658832 | 4.276479408756195 | 30399 | -0.5209698973199307 | 3411.953049 | 3562.997055 | 2754 | 72 |
| post | yaw | deg | 1.7741081766246816 | 3.266344850241748 | 7.704653816291284 | 30399 | 1.0286798287410082 | 3411.953049 | 3562.997055 | 2754 | 73 |
| outside | horizontal | m | 0.3619193978532313 | 0.6195797912836656 | 1.374752529492454 | 68937 | NA | 3186.005234 | 3562.997055 | 2754 | 74 |
| outside | position_3d | m | 1.2674136719264117 | 2.9278707573868563 | 6.388056961010628 | 68937 | NA | 3186.005234 | 3562.997055 | 2754 | 75 |
| outside | up | m | 1.2146405909747724 | 2.917141958709933 | 6.387054071838184 | 68937 | -0.5522187633394782 | 3186.005234 | 3562.997055 | 2754 | 76 |
| outside | yaw | deg | 3.3901854442580306 | 5.889042182168772 | 15.838141305301775 | 68937 | 2.1047703669528013 | 3186.005234 | 3562.997055 | 2754 | 77 |
| full | horizontal | m | 0.3480453400303894 | 0.6058982344781588 | 1.374752529492454 | 76548 | NA | 3186.005234 | 3562.997055 | 2754 | 78 |
| full | position_3d | m | 1.2265283026818157 | 2.7307777533824935 | 6.388056961010628 | 76548 | NA | 3186.005234 | 3562.997055 | 2754 | 79 |
| full | up | m | 1.1761105894271449 | 2.7171203201150256 | 6.387054071838184 | 76548 | -0.5031572980095224 | 3186.005234 | 3562.997055 | 2754 | 80 |
| full | yaw | deg | 3.31421398690487 | 5.474313206398441 | 15.838141305301775 | 76548 | 2.1444253600026224 | 3186.005234 | 3562.997055 | 2754 | 81 |

BY2O F04:

| segment | metric | unit | rmse | p95_abs | max_abs | count | signed_mean | time_start | time_end | secondary epochs | CSV row |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pre | horizontal | m | 0.37193590552059136 | 0.6516936131328457 | 1.4114785351496055 | 38538 | NA | 3186.005234 | 3369.941063 | 0 | 82 |
| pre | position_3d | m | 1.931637705340531 | 5.5139535202200465 | 9.271763438861 | 38538 | NA | 3186.005234 | 3369.941063 | 0 | 83 |
| pre | up | m | 1.8954914684265425 | 5.503532906295311 | 9.271036343904598 | 38538 | -0.757569184446082 | 3186.005234 | 3369.941063 | 0 | 84 |
| pre | yaw | deg | 4.361471110289078 | 9.151234223646235 | 16.022958167301795 | 38538 | 3.0908160646216554 | 3186.005234 | 3369.941063 | 0 | 85 |
| during | horizontal | m | 0.17860735329525412 | 0.2324022308561413 | 0.2629177933806397 | 7611 | NA | 3369.947066 | 3411.947048 | 0 | 86 |
| during | position_3d | m | 1.034241621447962 | 2.3737713560368707 | 5.345909999905947 | 7611 | NA | 3369.947066 | 3411.947048 | 0 | 87 |
| during | up | m | 1.0187026773716528 | 2.364834433458867 | 5.341815457349682 | 7611 | -0.1371215482618855 | 3369.947066 | 3411.947048 | 0 | 88 |
| during | yaw | deg | 2.7165434651348273 | 3.160064832028894 | 3.283477519996012 | 7611 | 2.7012407603115873 | 3369.947066 | 3411.947048 | 0 | 89 |
| post | horizontal | m | 0.3559737209962452 | 0.5958986248777477 | 1.111275894210808 | 30399 | NA | 3411.953049 | 3562.997055 | 2754 | 90 |
| post | position_3d | m | 1.2125881790904094 | 2.572652999066845 | 5.028879573749396 | 30399 | NA | 3411.953049 | 3562.997055 | 2754 | 91 |
| post | up | m | 1.15916038667213 | 2.5605843711536833 | 5.024360951574931 | 30399 | -0.559207356757161 | 3411.953049 | 3562.997055 | 2754 | 92 |
| post | yaw | deg | 1.793847938345788 | 3.318243257623362 | 7.738833785291263 | 30399 | 1.0445201992690518 | 3411.953049 | 3562.997055 | 2754 | 93 |
| outside | horizontal | m | 0.3649831506138463 | 0.6256140652312668 | 1.4114785351496055 | 68937 | NA | 3186.005234 | 3562.997055 | 2754 | 94 |
| outside | position_3d | m | 1.6535598751840472 | 3.7841139328149356 | 9.271763438861 | 68937 | NA | 3186.005234 | 3562.997055 | 2754 | 95 |
| outside | up | m | 1.6127763516950118 | 3.770463889834574 | 9.271036343904598 | 68937 | -0.6700979977115924 | 3186.005234 | 3562.997055 | 2754 | 96 |
| outside | yaw | deg | 3.4717627303842202 | 6.073023980369241 | 16.022958167301795 | 68937 | 2.188465396462991 | 3186.005234 | 3562.997055 | 2754 | 97 |
| full | horizontal | m | 0.3509123233117259 | 0.6114753018762525 | 1.4114785351496055 | 76548 | NA | 3186.005234 | 3562.997055 | 2754 | 98 |
| full | position_3d | m | 1.6027327531292752 | 3.6656100175707533 | 9.271763438861 | 76548 | NA | 3186.005234 | 3562.997055 | 2754 | 99 |
| full | up | m | 1.5638455228382735 | 3.6562485583767708 | 9.271036343904598 | 76548 | -0.6171053165603969 | 3186.005234 | 3562.997055 | 2754 | 100 |
| full | yaw | deg | 3.4041823976228605 | 5.6101672674416 | 16.022958167301795 | 76548 | 2.239449527913215 | 3186.005234 | 3562.997055 | 2754 | 101 |

### Six frozen pairwise comparisons per sequence

Source: `08_AGGREGATE/PAIRWISE_CASE_LEVEL.csv`; every value below is the stored `delta_candidate_minus_reference` token, joined by `comparison,metric_name,case_id`. No delta is recomputed here. Column labels retain the frozen comparison names; candidate/reference identities are:

| comparison | candidate | reference |
| --- | --- | --- |
| full_vs_no_SA | F04 | A04 |
| full_vs_strong | F04 | F03 |
| strong_vs_basic | F03 | F02 |
| basic_vs_single | F02 | F01 |
| no_SA_vs_strong | A04 | F03 |
| no_SA_vs_basic | A04 | F02 |

BY2H deltas:

| metric_name | full_vs_no_SA | full_vs_strong | strong_vs_basic | basic_vs_single | no_SA_vs_strong | no_SA_vs_basic |
| --- | --- | --- | --- | --- | --- | --- |
| horizontal_rmse_m | 0.0025797866348875598 | 0.002540516312016905 | -0.0039057904820593015 | 0.0030174065926291127 | -3.9270322870654795e-05 | -0.003945060804929956 |
| position_3d_rmse_m | 0.04438640410509109 | 0.04419622631849174 | -0.003115436168084962 | 0.0027026552258645475 | -0.0001901777865993548 | -0.0033056139546843166 |
| east_rmse_m | 0.0013370151542725917 | 0.0011666931347852905 | -0.000820523456682487 | 0.0001407331391558575 | -0.0001703220194873012 | -0.0009908454761697882 |
| north_rmse_m | 0.0024594277814489196 | 0.0026103506739311166 | -0.00521367207994175 | 0.004641198152646825 | 0.00015092289248219704 | -0.005062749187459553 |
| up_rmse_m | 0.046671372970626845 | 0.04648220645629886 | -0.0017840591928187655 | 0.0016962735335256385 | -0.00018916651432798748 | -0.001973225707146753 |
| yaw_rmse_deg | 0.008323118160942222 | 0.06075757996780107 | -0.11499439937495692 | -1.779530509640015 | 0.052434461806858845 | -0.06255993756809808 |
| roll_rmse_deg | 0.003595425898625715 | 0.0001415709412413424 | -0.0006543368180444986 | -0.006178751445307107 | -0.0034538549573843724 | -0.004108191775428871 |
| pitch_rmse_deg | 0.0008902619238901899 | -0.0012697471150500128 | -0.004117607835125936 | 0.012098948148870692 | -0.0021600090389402027 | -0.006277616874066139 |
| horizontal_p95_m | 0.007055189355439806 | 0.006002170519851413 | -0.007650115868154561 | 0.004662482099975329 | -0.001053018835588393 | -0.008703134703742954 |
| position_3d_p95_m | 0.11570968016737493 | 0.11516494811133571 | -0.004338496741366882 | 0.0026356226706312214 | -0.000544732056039221 | -0.004883228797406103 |
| yaw_p95_absolute_deg | 0.010276701846746228 | 0.1482964374761826 | -0.5291544757374291 | -3.089400940099809 | 0.13801973562943637 | -0.39113474010799276 |

| comparison | source CSV rows |
| --- | --- |
| full_vs_no_SA | 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12 |
| full_vs_strong | 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23 |
| strong_vs_basic | 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34 |
| basic_vs_single | 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45 |
| no_SA_vs_strong | 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56 |
| no_SA_vs_basic | 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67 |

BY2O deltas:

| metric_name | full_vs_no_SA | full_vs_strong | strong_vs_basic | basic_vs_single | no_SA_vs_strong | no_SA_vs_basic |
| --- | --- | --- | --- | --- | --- | --- |
| horizontal_rmse_m | 0.0028669832813364993 | 0.002621285292018549 | -0.0029771059207235884 | 0.002412074800921704 | -0.00024569798931795006 | -0.0032228039100415384 |
| position_3d_rmse_m | 0.37620445044745954 | 0.3759842381394807 | -0.003373861516274612 | 0.0031672501033521705 | -0.00022021230797886204 | -0.003594073824253474 |
| east_rmse_m | 0.001969081878704537 | 0.0017109202411655922 | -0.002404461680195147 | 0.0019458865685725857 | -0.00025816163753894505 | -0.002662623317734092 |
| north_rmse_m | 0.0021055000195821516 | 0.002028320005534434 | -0.0017709300685046503 | 0.0014373775768025399 | -7.718001404771746e-05 | -0.0018481100825523677 |
| up_rmse_m | 0.38773493341112863 | 0.3875780057041731 | -0.002635257582111805 | 0.002587202588376636 | -0.00015692770695552305 | -0.002792185289067328 |
| yaw_rmse_deg | 0.08996841071799055 | 0.09240239380558668 | 0.5124368046932917 | -4.104995321215087 | 0.0024339830875961255 | 0.5148707877808878 |
| roll_rmse_deg | 0.005943193672327984 | -0.015041651829366898 | -0.020946392481891563 | 0.015510623808330903 | -0.020984845501694882 | -0.041931237983586445 |
| pitch_rmse_deg | 0.0014781656655962205 | -0.0010932782738251046 | -0.0015936419069833008 | 0.0035288203627812376 | -0.002571443939421325 | -0.004165085846404626 |
| horizontal_p95_m | 0.005577067398093716 | 0.0047641283720202265 | -0.005433099998441104 | 0.0030661018196395107 | -0.0008129390260734892 | -0.006246039024514594 |
| position_3d_p95_m | 0.9348322641882598 | 0.9347037817390933 | -0.006299285484941741 | 0.0059511896510668905 | -0.00012848244916652263 | -0.006427767934108264 |
| yaw_p95_absolute_deg | 0.1358540610431591 | 0.19356073211592228 | 1.084871397020006 | -6.815757652443252 | 0.05770667107276317 | 1.142578068092769 |
| fault_window_horizontal_rmse_m | -4.839497868722176e-05 | 0.00010578843943825911 | -1.733122048153124e-05 | 0.0007682955474526687 | 0.00015418341812548086 | 0.00013685219764394962 |
| post_window_horizontal_rmse_m | 0.0021345754272187323 | 0.0019483621363330927 | -0.0023257778341383983 | 0.0022848875578627137 | -0.00018621329088563954 | -0.002511991125024038 |

| comparison | source CSV rows |
| --- | --- |
| full_vs_no_SA | 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14 |
| full_vs_strong | 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27 |
| strong_vs_basic | 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40 |
| basic_vs_single | 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53 |
| no_SA_vs_strong | 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66 |
| no_SA_vs_basic | 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79 |

BY2H contains the 11 metric rows present in its frozen pairwise table; BY2O contains those rows plus `fault_window_horizontal_rmse_m` and `post_window_horizontal_rmse_m`. No unavailable BY2H fault-window row is filled with a zero.

### Evaluation gates, coverage and read audits

Source: `UNIQUE_EVALUATION_RESULTS.csv` for counts/timing, and the frozen `EVALUATION_SEQUENCE_GATE.json` run_gates for parity, consistency and strace. All ten per-run gates are PASS. The frozen summary-parity gate checks all 13 required RMSE/P95 fields against maintained Canonical statistics at relative tolerance 1e-10. The separate consistency thresholds are 0.01 m horizontal/Up and 0.01 deg yaw; the independent reference is the unchanged evaluator's `load_trace` return.

| Dataset | method | output epochs | reference epochs | matched | unmatched | coverage ratio | finite epochs | finite ratio | time_start | time_end |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BY2H | F01 | 58580 | 5400 | 58580 | 0 | 1.0 | 58580 | 1.0 | 413.047045 | 682.99505 |
| BY2H | F02 | 58580 | 5400 | 58580 | 0 | 1.0 | 58580 | 1.0 | 413.047045 | 682.99505 |
| BY2H | F03 | 58580 | 5400 | 58580 | 0 | 1.0 | 58580 | 1.0 | 413.047045 | 682.99505 |
| BY2H | A04 | 58580 | 5400 | 58580 | 0 | 1.0 | 58580 | 1.0 | 413.047045 | 682.99505 |
| BY2H | F04 | 58580 | 5400 | 58580 | 0 | 1.0 | 58580 | 1.0 | 413.047045 | 682.99505 |
| BY2O | F01 | 76548 | 7540 | 76548 | 0 | 1.0 | 76548 | 1.0 | 3186.005234 | 3562.997055 |
| BY2O | F02 | 76548 | 7540 | 76548 | 0 | 1.0 | 76548 | 1.0 | 3186.005234 | 3562.997055 |
| BY2O | F03 | 76548 | 7540 | 76548 | 0 | 1.0 | 76548 | 1.0 | 3186.005234 | 3562.997055 |
| BY2O | A04 | 76548 | 7540 | 76548 | 0 | 1.0 | 76548 | 1.0 | 3186.005234 | 3562.997055 |
| BY2O | F04 | 76548 | 7540 | 76548 | 0 | 1.0 | 76548 | 1.0 | 3186.005234 | 3562.997055 |

| Dataset | method | summary fields | max relative difference | consistency H max m | consistency Up max m | consistency yaw max deg | gate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BY2H | F01 | 13 | 2.0250614568741407e-16 | 0.0018797224534221866 | 1.1021734934502092e-05 | 3.126388037344441e-13 | PASS |
| BY2H | F02 | 13 | 1.246201491230394e-16 | 0.0033641034903218775 | 1.0635046162832396e-05 | 2.2737367544323206e-13 | PASS |
| BY2H | F03 | 13 | 2.0300958774928788e-16 | 0.0018479842666473897 | 1.0718738007398088e-05 | 2.2737367544323206e-13 | PASS |
| BY2H | A04 | 13 | 1.2751881876314066e-16 | 0.001837658096343004 | 1.0577086628771326e-05 | 1.7053025658242404e-13 | PASS |
| BY2H | F04 | 13 | 2.1572158504776828e-16 | 0.0018447839628249203 | 1.0726191060683732e-05 | 1.9895196601282805e-13 | PASS |
| BY2O | F01 | 13 | 1.2159938535175096e-16 | 0.00253529308506138 | 1.990621192771158e-05 | 5.115907697472721e-13 | PASS |
| BY2O | F02 | 13 | 1.2083843364767561e-16 | 0.002594705857014541 | 2.00113609725161e-05 | 5.115907697472721e-13 | PASS |
| BY2O | F03 | 13 | 2.1078001427417585e-16 | 0.002572706851015196 | 1.990663791406888e-05 | 5.684341886080801e-13 | PASS |
| BY2O | A04 | 13 | 2.1098683604969422e-16 | 0.0025684501761866286 | 1.9888971241499576e-05 | 3.979039320256561e-13 | PASS |
| BY2O | F04 | 13 | 1.207031749796817e-16 | 0.002598142463120723 | 2.0398522323272772e-05 | 5.115907697472721e-13 | PASS |

| Dataset | method | evaluator exit | evaluation runtime s | trace opens | raw opens | bag opens | fpl opens | writes | raw writes | outside-output writes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BY2H | F01 | 0 | 4.931583704999866 | 1 | 1 | 0 | 0 | 3 | 0 | 0 |
| BY2H | F02 | 0 | 4.800740209999276 | 1 | 1 | 0 | 0 | 3 | 0 | 0 |
| BY2H | F03 | 0 | 4.543324598998879 | 1 | 1 | 0 | 0 | 3 | 0 | 0 |
| BY2H | A04 | 0 | 4.935713677999956 | 1 | 1 | 0 | 0 | 3 | 0 | 0 |
| BY2H | F04 | 0 | 4.877702843999941 | 1 | 1 | 0 | 0 | 3 | 0 | 0 |
| BY2O | F01 | 0 | 5.933673714998804 | 1 | 1 | 0 | 0 | 3 | 0 | 0 |
| BY2O | F02 | 0 | 6.253665473001092 | 1 | 1 | 0 | 0 | 3 | 0 | 0 |
| BY2O | F03 | 0 | 5.975666751999597 | 1 | 1 | 0 | 0 | 3 | 0 | 0 |
| BY2O | A04 | 0 | 5.950327945000026 | 1 | 1 | 0 | 0 | 3 | 0 | 0 |
| BY2O | F04 | 0 | 5.9757453270012775 | 1 | 1 | 0 | 0 | 3 | 0 | 0 |

| Dataset | sequence gate | completed | logical rows | wall seconds | CPU seconds | formal trace/raw opens | formal bag/fpl opens | formal raw/outside writes | retry count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BY2H | PASS | 5 | 7 | 41.52901240999927 | 15.016048 | 5 / 5 | 0 / 0 | 0 / 0 | 0 |
| BY2O | PASS | 5 | 7 | 52.27150536299996 | 18.897275999999998 | 5 / 5 | 0 / 0 | 0 / 0 | 0 |

Each formal reference open is successful and read-only, its PID matches the capture PID, and its complete SHA-256 is verified through the same handle before parsing. The parent performs metadata/stat checks rather than reference content parsing. Selected columns, capture flags, read-only scope and reference identity remain recorded per run. The H/O trace hashes are:

| Dataset | reference SHA-256 | A2 identity-gate SHA-256 |
| --- | --- | --- |
| BY2H | `8d11fe360753bfcdbc54f7bf793fcb25850c0997b7aaad4ec1c9f10859c0f84f` | `8cf25e267d215104ae425cd45179b8cb8a9319d37960f9a2d5df63624e06ecf9` |
| BY2O | `4f7b3007c6a0b43ce1b0fb4908f23c042891154b4adbc7af4c3d8a47ca363cd9` | `8cf25e267d215104ae425cd45179b8cb8a9319d37960f9a2d5df63624e06ecf9` |

### Pre/post frozen-output checks and preservation

`PRE_EVALUATION.json` and `POST_EVALUATION.json` record V2 seal validation, contract identity and the full seal-directory hash mapping. These are sealed-output checks; they are not described as new 22-file raw checkpoints. The pre/post mappings are equal for both sequences.

| Dataset | phase | sealed files validated | gate | OUTPUT_SEAL SHA-256 | contract SHA-256 |
| --- | --- | --- | --- | --- | --- |
| BY2H | PRE | 86 | PASS | `e34f283f753a2e564379bcace85e383d407e8b84b9309f9163f8de4a818374f5` | `64bf78d5d4241294922fbc6c18eaeb8ad4c2e40663ba8e5306ab67e1d07d4e19` |
| BY2H | POST | 86 | PASS | `e34f283f753a2e564379bcace85e383d407e8b84b9309f9163f8de4a818374f5` | `64bf78d5d4241294922fbc6c18eaeb8ad4c2e40663ba8e5306ab67e1d07d4e19` |
| BY2O | PRE | 86 | PASS | `ab037dadf7725bb47022ee0a86d9c0ee8f8b45a87acc152270bebc23c5d95285` | `bf42b2bee9ed96bd81d479bbb8b5533c58c6fce2ddbb5d9eabdeaf60cfd1144d` |
| BY2O | POST | 86 | PASS | `ab037dadf7725bb47022ee0a86d9c0ee8f8b45a87acc152270bebc23c5d95285` | `bf42b2bee9ed96bd81d479bbb8b5533c58c6fce2ddbb5d9eabdeaf60cfd1144d` |

Root preservation checks retain the original protected-file hashes, keep contracts unchanged from `06ad53e`, and retain the C-04 detached snapshot `clean5-run-7a5b48f0920f` with empty status including untracked files. No trace-driven sign, frame, offset or parameter change, epoch deletion, direct NAV overwrite, retry or plot was performed. The decision rule remains byte-identical; this record does not append a manuscript-role selection.

### Formal metadata and aggregate SHA-256 index

All rows below name only frozen JSON/CSV metadata and aggregate tables. Aggregate hashes are verified against `aggregate_files` in the sequence gate. Error-series and reference/NAV/STD payloads are not reopened for this index. Paths in this table are relative to the dataset stage.

| Dataset | metadata/aggregate path | SHA-256 | bytes |
| --- | --- | --- | --- |
| BY2H | `07_OFFLINE_EVALUATION/PRE_EVALUATION.json` | `e00b04df7b7ea4478943ccaa98773ba08137813cd5a3d21ffedb32cf92b4b505` | 97624 |
| BY2H | `07_OFFLINE_EVALUATION/POST_EVALUATION.json` | `e00b04df7b7ea4478943ccaa98773ba08137813cd5a3d21ffedb32cf92b4b505` | 97624 |
| BY2H | `07_OFFLINE_EVALUATION/EVALUATION_SEQUENCE_GATE.json` | `5edc28e2ef642671b7ff2c3d0c222a70aae79237063469e492fe8237c641f032` | 100851 |
| BY2H | `08_AGGREGATE/UNIQUE_EVALUATION_RESULTS.csv` | `98734e2c580c9aef1afffaa3c24b12d14c1b5d9f86cb56bca991cea2e6f1dab3` | 53870 |
| BY2H | `08_AGGREGATE/LOGICAL_EVALUATION_RESULTS.csv` | `0894271fe9858d5a1e168bc6d3870ccbab10372d93a42c26bbf5a173639838d7` | 70648 |
| BY2H | `08_AGGREGATE/UNIQUE_METHOD_SUMMARY.csv` | `eedf1c9a821e1284014bf461d3e8eaf139bb6ebdf4eec0e455db4d80b239c650` | 461192 |
| BY2H | `08_AGGREGATE/LOGICAL_METHOD_SUMMARY.csv` | `eabd9aa49cbef67916fe2f42a9dc9d5af43a9fc6b9acf191b52ba92b6c528f81` | 640640 |
| BY2H | `08_AGGREGATE/PAIRWISE_CASE_LEVEL.csv` | `b1c8193b1588a88de30bbaa7b76a8ce036522b0a436b949e61f39b0051d66453` | 11385 |
| BY2H | `08_AGGREGATE/PAIRWISE_SUMMARY.csv` | `c1761e6125ebd2ea8e7505fb8bdaee0719d0f2c61609c097fdbf4282e8e7fa30` | 49938 |
| BY2H | `08_AGGREGATE/MODULE_ACTION_SUMMARY.csv` | `794456302bf474c216a754d45818fbe896eda80626a82b920c050867d6b8f278` | 31484 |
| BY2H | `08_AGGREGATE/WINDOW_SEGMENT_SUMMARY.csv` | `5cea7fcd9982c63bce9c151ed90d88b3a54b572a5e52c5e57929c480ee23c2c6` | 4014 |
| BY2H | `08_AGGREGATE/RUNTIME_SUMMARY.csv` | `67d2caa904ee2d460ae283e255afe41fd73b2d7fa0cf8f0be3a15f4ff374e5c4` | 6839 |
| BY2H | `08_AGGREGATE/METRIC_COVERAGE_REPORT.csv` | `8b3bc490a6e25451d061d398c35d6f95f461a15b50242fd94382ae27e88648ef` | 53105 |
| BY2H | `08_AGGREGATE/FINAL_EVALUATION_SUMMARY.json` | `eaa16b3a7d133ee55ef9a7e055cc20586a6c97383949ac758d9dea674729a56e` | 53707 |
| BY2H | `08_AGGREGATE/FIELD_DEFINITIONS.json` | `859cd9a2b1eaefb42e2540d59b6be272c04dba9a058d200a11702aac57a4d09a` | 2517 |
| BY2H | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_F01_single_antenna_EKF/CAPTURE_CONFIG.json` | `6c012aeb1e4543674d6d3f7c3e1632e904d74960fa36a527e079937d67cc7878` | 748 |
| BY2H | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_F01_single_antenna_EKF/EVALUATOR_CAPTURE.json` | `88340877373d11a49989351c47d1a22fdad7d0680d53b0e6a80bb14174be02b5` | 1482 |
| BY2H | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_F01_single_antenna_EKF/EVALUATOR_STRACE_AUDIT.json` | `aaafb5e173fea2b15dde2d3ecf95c536dab45cab6370b6709b55c8f7170465ef` | 5184 |
| BY2H | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_F01_single_antenna_EKF/EVALUATION_GATE.json` | `8e66a1ccb06ad12d7aace455654d6bc62a57992b5aeec969a021c36ec52c0a9b` | 9618 |
| BY2H | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_F01_single_antenna_EKF/summary.json` | `a3944cf6f0d46c0a724383af6fb278835cb7b48252deb1c297d7f7d3446b54ec` | 1508 |
| BY2H | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_F02_basic_dual_yaw_EKF/CAPTURE_CONFIG.json` | `6efb132f0993d69c79f374693ab4f38049a28a85d6ffb557ffc5baed4b5a9c23` | 748 |
| BY2H | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_F02_basic_dual_yaw_EKF/EVALUATOR_CAPTURE.json` | `d91a65fe6462b454ac5cac9183be943efdc4a522e930450e177556a869897d72` | 1483 |
| BY2H | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_F02_basic_dual_yaw_EKF/EVALUATOR_STRACE_AUDIT.json` | `07db335e6704bea2a17eb2a8d3dae9b0b49461d461c9748d3bdd9c6ca9b4dff2` | 5184 |
| BY2H | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_F02_basic_dual_yaw_EKF/EVALUATION_GATE.json` | `c711e7a01ca6eb89abab57c720e418633fdd3b47df56b3709b8dc63b3304af8f` | 9557 |
| BY2H | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_F02_basic_dual_yaw_EKF/summary.json` | `5d636465c09e4efa1ff8216e938e858576019047e1250c3bc5050530f281a4a3` | 1502 |
| BY2H | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_F03_AB0000/CAPTURE_CONFIG.json` | `618cc772a4dcb1f379f172663f56398858d116015ab0f379a3135dc0c8cb74f5` | 736 |
| BY2H | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_F03_AB0000/EVALUATOR_CAPTURE.json` | `de70ae985dd3c6cd0b914ef753864f10a3f65e7eb5be31d13420f6b033fa89d0` | 1483 |
| BY2H | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_F03_AB0000/EVALUATOR_STRACE_AUDIT.json` | `2255ef9cab6e25238548caf676274f0d3e76553ca41ad809f9fad42cdea9294a` | 5040 |
| BY2H | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_F03_AB0000/EVALUATION_GATE.json` | `3a776184fac0d96b5cb4aaba9f6b4af1a8a4024360f1bd4b37f65cfe9d04cf56` | 9428 |
| BY2H | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_F03_AB0000/summary.json` | `fdf131cc5c07371d5ec05433ddd7582d33fa71cb7c77293f6883f3abce4b6812` | 1508 |
| BY2H | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_A04_AB1011/CAPTURE_CONFIG.json` | `6f1e8b2ca05af315105bb17ee720ef3b959db0e5e54fcd45aec33fcd759306a5` | 736 |
| BY2H | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_A04_AB1011/EVALUATOR_CAPTURE.json` | `194464882845c92ea6385c52162231a8a8df4daf76b1caa36205dea703d1e1ae` | 1482 |
| BY2H | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_A04_AB1011/EVALUATOR_STRACE_AUDIT.json` | `d4e526cd62a4770cbedc82b2367c2581c9c1348ef6d1efef96e3886c39b319c1` | 5040 |
| BY2H | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_A04_AB1011/EVALUATION_GATE.json` | `8483228aa29059cdbe4c344561d1084b98b63bdf3960a9d5ed7d410f8ada4900` | 9404 |
| BY2H | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_A04_AB1011/summary.json` | `ff1cb75a4e571ee0fd7845266784f5551a074dc00111ff6fd3fcc8d9c40f6b88` | 1505 |
| BY2H | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_F04_AB1111/CAPTURE_CONFIG.json` | `5ce7d247d346e71403703ea1cf5ca14ae90eb6f5d7a4535f7bd73e560e0388d4` | 736 |
| BY2H | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_F04_AB1111/EVALUATOR_CAPTURE.json` | `ac9799599bf3e264e1f04576cad367922015ed5e61ea9882c480e7585adc5f12` | 1483 |
| BY2H | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_F04_AB1111/EVALUATOR_STRACE_AUDIT.json` | `13aed11569b695183db5ce5242dce1213c718fab40af98872b830a28af1deb83` | 5040 |
| BY2H | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_F04_AB1111/EVALUATION_GATE.json` | `7347189a9fdda9dd0911f6bb5d89d84a748b157f79c33a0d5e4ef8d7e7624031` | 9448 |
| BY2H | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_F04_AB1111/summary.json` | `4a2a32d19f4d79776d914862ba8a7f27504075aa877da640b935c996e295e077` | 1523 |
| BY2O | `07_OFFLINE_EVALUATION/PRE_EVALUATION.json` | `7d4e7cdd3fcd850f3dafcecebb742da8b90508a82e27683c99c01f184edfbcd0` | 105200 |
| BY2O | `07_OFFLINE_EVALUATION/POST_EVALUATION.json` | `7d4e7cdd3fcd850f3dafcecebb742da8b90508a82e27683c99c01f184edfbcd0` | 105200 |
| BY2O | `07_OFFLINE_EVALUATION/EVALUATION_SEQUENCE_GATE.json` | `25297e960f1efdcbcffc22141a57ee8d448ef2dfa18ca1bb63c69b1045bb1501` | 101844 |
| BY2O | `08_AGGREGATE/UNIQUE_EVALUATION_RESULTS.csv` | `aa68bc4ba865842eb37358b9c4ccea3e230233e8602ec1610b390f8ffc2c4ced` | 60579 |
| BY2O | `08_AGGREGATE/LOGICAL_EVALUATION_RESULTS.csv` | `b2c295d5826e12a31e70c3c3c2be40afab93cf6874a158b63d0a44f8538d1897` | 80004 |
| BY2O | `08_AGGREGATE/UNIQUE_METHOD_SUMMARY.csv` | `2a814c9a6a27245faea1368f5addc6c3c39a218dc5215325ec226a9bde9167ce` | 574713 |
| BY2O | `08_AGGREGATE/LOGICAL_METHOD_SUMMARY.csv` | `6131676a47ce019e70602df315c9ea49f33bcbf4fcdb68cef48073955ee26199` | 797911 |
| BY2O | `08_AGGREGATE/PAIRWISE_CASE_LEVEL.csv` | `3601c4bb6c72a280869d4ea02ccc7f002760858d27eda80bd242aa9fa9281a7d` | 13617 |
| BY2O | `08_AGGREGATE/PAIRWISE_SUMMARY.csv` | `d06444d2c0dbc2b64e81f9b87031710c67709c61a2a47f760ad172773d5c03b3` | 59274 |
| BY2O | `08_AGGREGATE/MODULE_ACTION_SUMMARY.csv` | `50b4fa980f5c617e00043a2e650c91ea3df48a2f0783153a427d44f684c96c9f` | 31464 |
| BY2O | `08_AGGREGATE/WINDOW_SEGMENT_SUMMARY.csv` | `c254497a9e402dba46329375cbbe65cf48b65af10b2a4df350a289823e28a322` | 23055 |
| BY2O | `08_AGGREGATE/RUNTIME_SUMMARY.csv` | `3287674bf1c38c4ba8aedd6cce41122d38d50593bc61785f7dae59c4dbea8ed0` | 6941 |
| BY2O | `08_AGGREGATE/METRIC_COVERAGE_REPORT.csv` | `4703227a4a85a01144d8d0e8f1d32502206f6db80ac43b91446a8887cdab7b17` | 50647 |
| BY2O | `08_AGGREGATE/FINAL_EVALUATION_SUMMARY.json` | `d7df2bc17b884b3536dbba25c9593874c7b1886d7a1da54de57fe6b9d9282fd4` | 54462 |
| BY2O | `08_AGGREGATE/FIELD_DEFINITIONS.json` | `859cd9a2b1eaefb42e2540d59b6be272c04dba9a058d200a11702aac57a4d09a` | 2517 |
| BY2O | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_F01_single_antenna_EKF/CAPTURE_CONFIG.json` | `546c1754780a108f35b6d119ac6669b501b4f187cda1af4289f30478af156f36` | 762 |
| BY2O | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_F01_single_antenna_EKF/EVALUATOR_CAPTURE.json` | `1b11349e62b25db220fbd6d9bbd1bd617b341fa14f18f92dd5fd91d98ddb87a7` | 1481 |
| BY2O | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_F01_single_antenna_EKF/EVALUATOR_STRACE_AUDIT.json` | `4c3e77c5731286a59a69efdbafa920244d55a925a6a175155d6e8d3de9b2ed05` | 5328 |
| BY2O | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_F01_single_antenna_EKF/EVALUATION_GATE.json` | `960c9838a1e7541f028f15695fca9f29b8084091f20c5c0a5bb805f243647e7b` | 9706 |
| BY2O | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_F01_single_antenna_EKF/summary.json` | `36c27001d5f1da6b584f81b67e1037402dc968a75c5c3fd6ea458edecc4152e4` | 1538 |
| BY2O | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_F02_basic_dual_yaw_EKF/CAPTURE_CONFIG.json` | `a94dc02af835b07dc3e902dd2124cee9e9838df600c95fba800e0cab6f77985a` | 762 |
| BY2O | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_F02_basic_dual_yaw_EKF/EVALUATOR_CAPTURE.json` | `4e67018929410455f7076dff401a739a991e834c7f15f434462e09adf9b8ffbf` | 1481 |
| BY2O | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_F02_basic_dual_yaw_EKF/EVALUATOR_STRACE_AUDIT.json` | `db58a223cbad43c074bfa840dad834b209c6ed1852716497279ca178b3d3a7e5` | 5328 |
| BY2O | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_F02_basic_dual_yaw_EKF/EVALUATION_GATE.json` | `36d72a041e16821fc17947051e02a58170546cbaf946d74bb9e83ab1165a55f1` | 9722 |
| BY2O | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_F02_basic_dual_yaw_EKF/summary.json` | `c7f96773009ed090ba3cab75105c37769ff4a0dd399f752d930267c49beb3796` | 1539 |
| BY2O | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_F03_AB0000/CAPTURE_CONFIG.json` | `0c161b3a0673331003a02f959fc0acbdfe44d005ea6a7562102414562216f016` | 750 |
| BY2O | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_F03_AB0000/EVALUATOR_CAPTURE.json` | `4dbb091a6ca8428c4fabff2e1ab3df06cd23e16b75102e4e0aae4c5b68ef8d54` | 1482 |
| BY2O | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_F03_AB0000/EVALUATOR_STRACE_AUDIT.json` | `32260eab08450b344986642ba5c8275801910a0760216acd12f3d89f1496cefd` | 5184 |
| BY2O | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_F03_AB0000/EVALUATION_GATE.json` | `e0206c1f4e42c975a84dc83f6eb19ddb077d1b1e5c534bd11b7dc8c33ac32016` | 9612 |
| BY2O | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_F03_AB0000/summary.json` | `d34556b584f4376ee3760530f7848a83802d06ca8a6fd58403c8f9d5ad865117` | 1543 |
| BY2O | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_A04_AB1011/CAPTURE_CONFIG.json` | `7913a43e73986eb00c8828ead2541e050e9d50f661a18e67fddfad07eef47864` | 750 |
| BY2O | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_A04_AB1011/EVALUATOR_CAPTURE.json` | `18871e897736eb056b2ac86523a5e9371ebc2cd7fd5d4ef5cf557417168af3f9` | 1484 |
| BY2O | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_A04_AB1011/EVALUATOR_STRACE_AUDIT.json` | `6342e392aae2d62928030a7143b3bf6381021209abd4d0d01da810636142b6b6` | 5184 |
| BY2O | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_A04_AB1011/EVALUATION_GATE.json` | `22df6404e554c4c117635103fcbe32d45ad85add4be06e094368444a75922167` | 9590 |
| BY2O | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_A04_AB1011/summary.json` | `74693b71622f0d4acc92cadc6f5b31bd0d0ee7ae0362f9ed2965de34bf4bd55c` | 1534 |
| BY2O | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_F04_AB1111/CAPTURE_CONFIG.json` | `63dbc8cc41a7887141be7fb067f839a6369ee49c151f85353987878b72ff2260` | 750 |
| BY2O | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_F04_AB1111/EVALUATOR_CAPTURE.json` | `301b6e73da77b4acd46c8c898620fd9a0b79c83b59bab52768c6674813d32db1` | 1483 |
| BY2O | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_F04_AB1111/EVALUATOR_STRACE_AUDIT.json` | `01e1adba2fa885ec3e9c3484522a1abc484c31c2ca61fa25d01e0574922e989d` | 5185 |
| BY2O | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_F04_AB1111/EVALUATION_GATE.json` | `e0dfa895021ab33b45ce55c2700853778fce488fda3a08ea36acb6eccb1f66de` | 9569 |
| BY2O | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_F04_AB1111/summary.json` | `c44fb21767bc599e2873fa3aa955b12fa022ab08b4f926cec4691f984cc94902` | 1540 |

Formal strace hashes are copied from the frozen audit metadata without parsing the log again:

| Dataset | run_id | relative strace path | recorded SHA-256 |
| --- | --- | --- | --- |
| BY2H | BY2H_F01_single_antenna_EKF | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_F01_single_antenna_EKF/EVALUATOR_OPENAT.strace` | `d9043bc359bfb15d86e8528445de745c2cd8ffb23b6ac491620924d1a31b0e81` |
| BY2H | BY2H_F02_basic_dual_yaw_EKF | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_F02_basic_dual_yaw_EKF/EVALUATOR_OPENAT.strace` | `b21e3dd69d1ebdaf53a69fd03846f5ec8bc5e92585ad1904231e55ad04516eef` |
| BY2H | BY2H_F03_AB0000 | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_F03_AB0000/EVALUATOR_OPENAT.strace` | `de83a3ac97dd2f2b225f5a820aa59136eecf93b95f2fb56f61c56053d1a4eb23` |
| BY2H | BY2H_A04_AB1011 | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_A04_AB1011/EVALUATOR_OPENAT.strace` | `41114200b111ecace4f7898b772a9f37aef1f305e6e481b469013cb7be3d0f1e` |
| BY2H | BY2H_F04_AB1111 | `07_OFFLINE_EVALUATION/PER_RUN/BY2H_F04_AB1111/EVALUATOR_OPENAT.strace` | `66072d57d1f2461bd747ee1beb14edb50577629a7170f0ee32cc25a855b8ddef` |
| BY2O | BY2O_F01_single_antenna_EKF | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_F01_single_antenna_EKF/EVALUATOR_OPENAT.strace` | `5c0e5874857a51ce12456a54cb2b503282c71fb7690d56e042cb833d288afea8` |
| BY2O | BY2O_F02_basic_dual_yaw_EKF | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_F02_basic_dual_yaw_EKF/EVALUATOR_OPENAT.strace` | `4dbf60b2f0c8d31c5b05c31e58115ce06ee59fc51432a9410ec34a40be80e98b` |
| BY2O | BY2O_F03_AB0000 | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_F03_AB0000/EVALUATOR_OPENAT.strace` | `e64ff70bbc7b8d8b49ada0eb666eadf48f3bc6c7db02e4e871cde9b4978c8e7d` |
| BY2O | BY2O_A04_AB1011 | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_A04_AB1011/EVALUATOR_OPENAT.strace` | `23b5bce386df0483f9b9a2c08040c4d0aea4d338db70b4ede028575d43886e98` |
| BY2O | BY2O_F04_AB1111 | `07_OFFLINE_EVALUATION/PER_RUN/BY2O_F04_AB1111/EVALUATOR_OPENAT.strace` | `c00eaef875175ad3e139f3bc4ffa08bb0f711e23df19a5852394a0ac4775cf2c` |

## Frozen decision-input JSON, literal copy

Source: `<CLEAN_ROOT>/stages/CLEAN5_DECISION/A04_F04_DECISION_INPUTS.json`; SHA-256 `d9867e64d9e57caea19cfd83b7c7dfba5e9fc95e789859fefbc1820b8230ef1e`; 26545 bytes. The following block is the original UTF-8 JSON text, without value, path, whitespace or key changes. It records inputs and comparison gates only.

```json
{
  "schema_version": "clean5.c05.decision_inputs.v1",
  "extraction_status": "PASS",
  "data_mode": "real_clean5_frozen_evaluation",
  "synthetic_data_used": false,
  "semisynthetic_data_used": false,
  "sources": {
    "by2h_table": {
      "file": "<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/08_AGGREGATE/WINDOW_SEGMENT_SUMMARY.csv",
      "sha256": "5cea7fcd9982c63bce9c151ed90d88b3a54b572a5e52c5e57929c480ee23c2c6",
      "size_bytes": 4014
    },
    "by2o_table": {
      "file": "<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/08_AGGREGATE/WINDOW_SEGMENT_SUMMARY.csv",
      "sha256": "c254497a9e402dba46329375cbbe65cf48b65af10b2a4df350a289823e28a322",
      "size_bytes": 23055
    },
    "yaw_gate": {
      "file": "<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/02_PROVIDER_FREEZE/YAW_PHYSICAL_GATE.json",
      "sha256": "24888cab1cac488737ed1677c38904a14974f7a586a348a6fc90f51370116fc3",
      "size_bytes": 37446
    },
    "occlusion_window": {
      "file": "<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/01_SEQUENCE_CONTRACT/OCCLUSION_WINDOW.json",
      "sha256": "4ffabd12c71ef08ec3bb43bb5969fe97883b657c6d68aec2fc827f1fb56e349f",
      "size_bytes": 2743950
    },
    "rule": {
      "file": "<CODE_ROOT>/docs/paper_rebuild/A04_F04_ROLE_DECISION_RULE.md",
      "sha256": "4699d35abbfd8a56f282323b082aa5e29658e62a9575f3812836a6095f8fecce",
      "size_bytes": 4578
    }
  },
  "inputs": {
    "BY2H": {
      "yaw_physical_gate": {
        "status": "PASS",
        "value": true,
        "source": {
          "file": "<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/02_PROVIDER_FREEZE/YAW_PHYSICAL_GATE.json",
          "sha256": "24888cab1cac488737ed1677c38904a14974f7a586a348a6fc90f51370116fc3",
          "size_bytes": 37446,
          "json_pointer": "/physical_pass",
          "line": 1502,
          "column": "physical_pass",
          "raw_token": "true"
        }
      },
      "full": {
        "A04": {
          "horizontal_rmse_m": {
            "value": 0.34935966382182015,
            "unit": "m",
            "source": {
              "file": "<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/08_AGGREGATE/WINDOW_SEGMENT_SUMMARY.csv",
              "sha256": "5cea7fcd9982c63bce9c151ed90d88b3a54b572a5e52c5e57929c480ee23c2c6",
              "size_bytes": 4014,
              "row": 14,
              "row_end": 14,
              "row_number_convention": "physical line, 1-based including header",
              "column": "rmse",
              "raw_token": "0.34935966382182015",
              "identity": {
                "dataset_id": "BY2H",
                "method_id": "A04",
                "effective_configuration_id": "AB1011",
                "segment_id": "full",
                "metric_name": "horizontal",
                "run_id": "BY2H_A04_AB1011",
                "case_id": "CLEAN5_BY2H_NATURAL"
              }
            }
          },
          "up_rmse_m": {
            "value": 0.8701119000756633,
            "unit": "m",
            "source": {
              "file": "<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/08_AGGREGATE/WINDOW_SEGMENT_SUMMARY.csv",
              "sha256": "5cea7fcd9982c63bce9c151ed90d88b3a54b572a5e52c5e57929c480ee23c2c6",
              "size_bytes": 4014,
              "row": 16,
              "row_end": 16,
              "row_number_convention": "physical line, 1-based including header",
              "column": "rmse",
              "raw_token": "0.8701119000756633",
              "identity": {
                "dataset_id": "BY2H",
                "method_id": "A04",
                "effective_configuration_id": "AB1011",
                "segment_id": "full",
                "metric_name": "up",
                "run_id": "BY2H_A04_AB1011",
                "case_id": "CLEAN5_BY2H_NATURAL"
              }
            }
          },
          "yaw_rmse_deg": {
            "value": 2.059813237028886,
            "unit": "deg",
            "source": {
              "file": "<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/08_AGGREGATE/WINDOW_SEGMENT_SUMMARY.csv",
              "sha256": "5cea7fcd9982c63bce9c151ed90d88b3a54b572a5e52c5e57929c480ee23c2c6",
              "size_bytes": 4014,
              "row": 17,
              "row_end": 17,
              "row_number_convention": "physical line, 1-based including header",
              "column": "rmse",
              "raw_token": "2.059813237028886",
              "identity": {
                "dataset_id": "BY2H",
                "method_id": "A04",
                "effective_configuration_id": "AB1011",
                "segment_id": "full",
                "metric_name": "yaw",
                "run_id": "BY2H_A04_AB1011",
                "case_id": "CLEAN5_BY2H_NATURAL"
              }
            }
          },
          "yaw_p95_deg": {
            "value": 4.106967381555717,
            "unit": "deg",
            "source": {
              "file": "<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/08_AGGREGATE/WINDOW_SEGMENT_SUMMARY.csv",
              "sha256": "5cea7fcd9982c63bce9c151ed90d88b3a54b572a5e52c5e57929c480ee23c2c6",
              "size_bytes": 4014,
              "row": 17,
              "row_end": 17,
              "row_number_convention": "physical line, 1-based including header",
              "column": "p95_abs",
              "raw_token": "4.106967381555717",
              "identity": {
                "dataset_id": "BY2H",
                "method_id": "A04",
                "effective_configuration_id": "AB1011",
                "segment_id": "full",
                "metric_name": "yaw",
                "run_id": "BY2H_A04_AB1011",
                "case_id": "CLEAN5_BY2H_NATURAL"
              }
            }
          }
        },
        "F04": {
          "horizontal_rmse_m": {
            "value": 0.3519394504567077,
            "unit": "m",
            "source": {
              "file": "<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/08_AGGREGATE/WINDOW_SEGMENT_SUMMARY.csv",
              "sha256": "5cea7fcd9982c63bce9c151ed90d88b3a54b572a5e52c5e57929c480ee23c2c6",
              "size_bytes": 4014,
              "row": 18,
              "row_end": 18,
              "row_number_convention": "physical line, 1-based including header",
              "column": "rmse",
              "raw_token": "0.3519394504567077",
              "identity": {
                "dataset_id": "BY2H",
                "method_id": "F04",
                "effective_configuration_id": "AB1111",
                "segment_id": "full",
                "metric_name": "horizontal",
                "run_id": "BY2H_F04_AB1111",
                "case_id": "CLEAN5_BY2H_NATURAL"
              }
            }
          },
          "up_rmse_m": {
            "value": 0.9167832730462901,
            "unit": "m",
            "source": {
              "file": "<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/08_AGGREGATE/WINDOW_SEGMENT_SUMMARY.csv",
              "sha256": "5cea7fcd9982c63bce9c151ed90d88b3a54b572a5e52c5e57929c480ee23c2c6",
              "size_bytes": 4014,
              "row": 20,
              "row_end": 20,
              "row_number_convention": "physical line, 1-based including header",
              "column": "rmse",
              "raw_token": "0.9167832730462901",
              "identity": {
                "dataset_id": "BY2H",
                "method_id": "F04",
                "effective_configuration_id": "AB1111",
                "segment_id": "full",
                "metric_name": "up",
                "run_id": "BY2H_F04_AB1111",
                "case_id": "CLEAN5_BY2H_NATURAL"
              }
            }
          },
          "yaw_rmse_deg": {
            "value": 2.068136355189828,
            "unit": "deg",
            "source": {
              "file": "<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/08_AGGREGATE/WINDOW_SEGMENT_SUMMARY.csv",
              "sha256": "5cea7fcd9982c63bce9c151ed90d88b3a54b572a5e52c5e57929c480ee23c2c6",
              "size_bytes": 4014,
              "row": 21,
              "row_end": 21,
              "row_number_convention": "physical line, 1-based including header",
              "column": "rmse",
              "raw_token": "2.068136355189828",
              "identity": {
                "dataset_id": "BY2H",
                "method_id": "F04",
                "effective_configuration_id": "AB1111",
                "segment_id": "full",
                "metric_name": "yaw",
                "run_id": "BY2H_F04_AB1111",
                "case_id": "CLEAN5_BY2H_NATURAL"
              }
            }
          },
          "yaw_p95_deg": {
            "value": 4.117244083402463,
            "unit": "deg",
            "source": {
              "file": "<CLEAN_ROOT>/stages/CLEAN5_BY2H_NATURAL_POOR_HEADING_SEQUENCE/08_AGGREGATE/WINDOW_SEGMENT_SUMMARY.csv",
              "sha256": "5cea7fcd9982c63bce9c151ed90d88b3a54b572a5e52c5e57929c480ee23c2c6",
              "size_bytes": 4014,
              "row": 21,
              "row_end": 21,
              "row_number_convention": "physical line, 1-based including header",
              "column": "p95_abs",
              "raw_token": "4.117244083402463",
              "identity": {
                "dataset_id": "BY2H",
                "method_id": "F04",
                "effective_configuration_id": "AB1111",
                "segment_id": "full",
                "metric_name": "yaw",
                "run_id": "BY2H_F04_AB1111",
                "case_id": "CLEAN5_BY2H_NATURAL"
              }
            }
          }
        }
      }
    },
    "BY2O": {
      "occlusion_window": {
        "t0": {
          "value": 3369.943066596985,
          "source": {
            "file": "<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/01_SEQUENCE_CONTRACT/OCCLUSION_WINDOW.json",
            "sha256": "4ffabd12c71ef08ec3bb43bb5969fe97883b657c6d68aec2fc827f1fb56e349f",
            "size_bytes": 2743950,
            "json_pointer": "/main_window/t0",
            "line": 79569,
            "column": "t0",
            "raw_token": "3369.943066596985"
          }
        },
        "t1": {
          "value": 3411.951585292816,
          "source": {
            "file": "<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/01_SEQUENCE_CONTRACT/OCCLUSION_WINDOW.json",
            "sha256": "4ffabd12c71ef08ec3bb43bb5969fe97883b657c6d68aec2fc827f1fb56e349f",
            "size_bytes": 2743950,
            "json_pointer": "/main_window/t1",
            "line": 79570,
            "column": "t1",
            "raw_token": "3411.951585292816"
          }
        }
      },
      "full": {
        "A04": {
          "horizontal_rmse_m": {
            "value": 0.3480453400303894,
            "unit": "m",
            "source": {
              "file": "<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/08_AGGREGATE/WINDOW_SEGMENT_SUMMARY.csv",
              "sha256": "c254497a9e402dba46329375cbbe65cf48b65af10b2a4df350a289823e28a322",
              "size_bytes": 23055,
              "row": 78,
              "row_end": 78,
              "row_number_convention": "physical line, 1-based including header",
              "column": "rmse",
              "raw_token": "0.3480453400303894",
              "identity": {
                "dataset_id": "BY2O",
                "method_id": "A04",
                "effective_configuration_id": "AB1011",
                "segment_id": "full",
                "metric_name": "horizontal",
                "run_id": "BY2O_A04_AB1011",
                "case_id": "CLEAN5_BY2O_NATURAL"
              }
            }
          },
          "up_rmse_m": {
            "value": 1.1761105894271449,
            "unit": "m",
            "source": {
              "file": "<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/08_AGGREGATE/WINDOW_SEGMENT_SUMMARY.csv",
              "sha256": "c254497a9e402dba46329375cbbe65cf48b65af10b2a4df350a289823e28a322",
              "size_bytes": 23055,
              "row": 80,
              "row_end": 80,
              "row_number_convention": "physical line, 1-based including header",
              "column": "rmse",
              "raw_token": "1.1761105894271449",
              "identity": {
                "dataset_id": "BY2O",
                "method_id": "A04",
                "effective_configuration_id": "AB1011",
                "segment_id": "full",
                "metric_name": "up",
                "run_id": "BY2O_A04_AB1011",
                "case_id": "CLEAN5_BY2O_NATURAL"
              }
            }
          }
        },
        "F04": {
          "horizontal_rmse_m": {
            "value": 0.3509123233117259,
            "unit": "m",
            "source": {
              "file": "<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/08_AGGREGATE/WINDOW_SEGMENT_SUMMARY.csv",
              "sha256": "c254497a9e402dba46329375cbbe65cf48b65af10b2a4df350a289823e28a322",
              "size_bytes": 23055,
              "row": 98,
              "row_end": 98,
              "row_number_convention": "physical line, 1-based including header",
              "column": "rmse",
              "raw_token": "0.3509123233117259",
              "identity": {
                "dataset_id": "BY2O",
                "method_id": "F04",
                "effective_configuration_id": "AB1111",
                "segment_id": "full",
                "metric_name": "horizontal",
                "run_id": "BY2O_F04_AB1111",
                "case_id": "CLEAN5_BY2O_NATURAL"
              }
            }
          },
          "up_rmse_m": {
            "value": 1.5638455228382735,
            "unit": "m",
            "source": {
              "file": "<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/08_AGGREGATE/WINDOW_SEGMENT_SUMMARY.csv",
              "sha256": "c254497a9e402dba46329375cbbe65cf48b65af10b2a4df350a289823e28a322",
              "size_bytes": 23055,
              "row": 100,
              "row_end": 100,
              "row_number_convention": "physical line, 1-based including header",
              "column": "rmse",
              "raw_token": "1.5638455228382735",
              "identity": {
                "dataset_id": "BY2O",
                "method_id": "F04",
                "effective_configuration_id": "AB1111",
                "segment_id": "full",
                "metric_name": "up",
                "run_id": "BY2O_F04_AB1111",
                "case_id": "CLEAN5_BY2O_NATURAL"
              }
            }
          }
        }
      },
      "outside": {
        "A04": {
          "horizontal_rmse_m": {
            "value": 0.3619193978532313,
            "unit": "m",
            "source": {
              "file": "<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/08_AGGREGATE/WINDOW_SEGMENT_SUMMARY.csv",
              "sha256": "c254497a9e402dba46329375cbbe65cf48b65af10b2a4df350a289823e28a322",
              "size_bytes": 23055,
              "row": 74,
              "row_end": 74,
              "row_number_convention": "physical line, 1-based including header",
              "column": "rmse",
              "raw_token": "0.3619193978532313",
              "identity": {
                "dataset_id": "BY2O",
                "method_id": "A04",
                "effective_configuration_id": "AB1011",
                "segment_id": "outside",
                "metric_name": "horizontal",
                "run_id": "BY2O_A04_AB1011",
                "case_id": "CLEAN5_BY2O_NATURAL"
              }
            }
          },
          "up_rmse_m": {
            "value": 1.2146405909747724,
            "unit": "m",
            "source": {
              "file": "<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/08_AGGREGATE/WINDOW_SEGMENT_SUMMARY.csv",
              "sha256": "c254497a9e402dba46329375cbbe65cf48b65af10b2a4df350a289823e28a322",
              "size_bytes": 23055,
              "row": 76,
              "row_end": 76,
              "row_number_convention": "physical line, 1-based including header",
              "column": "rmse",
              "raw_token": "1.2146405909747724",
              "identity": {
                "dataset_id": "BY2O",
                "method_id": "A04",
                "effective_configuration_id": "AB1011",
                "segment_id": "outside",
                "metric_name": "up",
                "run_id": "BY2O_A04_AB1011",
                "case_id": "CLEAN5_BY2O_NATURAL"
              }
            }
          }
        },
        "F04": {
          "horizontal_rmse_m": {
            "value": 0.3649831506138463,
            "unit": "m",
            "source": {
              "file": "<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/08_AGGREGATE/WINDOW_SEGMENT_SUMMARY.csv",
              "sha256": "c254497a9e402dba46329375cbbe65cf48b65af10b2a4df350a289823e28a322",
              "size_bytes": 23055,
              "row": 94,
              "row_end": 94,
              "row_number_convention": "physical line, 1-based including header",
              "column": "rmse",
              "raw_token": "0.3649831506138463",
              "identity": {
                "dataset_id": "BY2O",
                "method_id": "F04",
                "effective_configuration_id": "AB1111",
                "segment_id": "outside",
                "metric_name": "horizontal",
                "run_id": "BY2O_F04_AB1111",
                "case_id": "CLEAN5_BY2O_NATURAL"
              }
            }
          },
          "up_rmse_m": {
            "value": 1.6127763516950118,
            "unit": "m",
            "source": {
              "file": "<CLEAN_ROOT>/stages/CLEAN5_BY2O_NATURAL_SINGLE_ANTENNA_OCCLUSION_SEQUENCE/08_AGGREGATE/WINDOW_SEGMENT_SUMMARY.csv",
              "sha256": "c254497a9e402dba46329375cbbe65cf48b65af10b2a4df350a289823e28a322",
              "size_bytes": 23055,
              "row": 96,
              "row_end": 96,
              "row_number_convention": "physical line, 1-based including header",
              "column": "rmse",
              "raw_token": "1.6127763516950118",
              "identity": {
                "dataset_id": "BY2O",
                "method_id": "F04",
                "effective_configuration_id": "AB1111",
                "segment_id": "outside",
                "metric_name": "up",
                "run_id": "BY2O_F04_AB1111",
                "case_id": "CLEAN5_BY2O_NATURAL"
              }
            }
          }
        }
      }
    }
  },
  "comparison_policy": {
    "arithmetic": "exact decimal CSV tokens",
    "equality": "inclusive formula recorded; strict_pass excludes exact threshold equality",
    "heading": "OR of strictly passing branches, subject to BY2H physical gate",
    "position": "AND of all six strictly passing comparisons",
    "tolerance_or_rounding_applied": false
  },
  "tests": {
    "heading": {
      "status": "FAIL",
      "executable": true,
      "branches": {
        "yaw_rmse_deg": {
          "formula": "yawRMSE(F04) <= yawRMSE(A04) - 0.50 deg",
          "input_paths": [
            "/inputs/BY2H/full/A04/yaw_rmse_deg",
            "/inputs/BY2H/full/F04/yaw_rmse_deg"
          ],
          "rule_source": {
            "file": "<CODE_ROOT>/docs/paper_rebuild/A04_F04_ROLE_DECISION_RULE.md",
            "sha256": "4699d35abbfd8a56f282323b082aa5e29658e62a9575f3812836a6095f8fecce",
            "size_bytes": 4578,
            "line": 51,
            "column": "pre_registered_formula",
            "raw_token": "yawRMSE(F04) <= yawRMSE(A04) - 0.50 deg"
          },
          "left_decimal": "2.068136355189828",
          "right_decimal": "1.559813237028886",
          "inclusive_comparison": false,
          "threshold_equal": false,
          "strict_pass": false
        },
        "yaw_p95_deg": {
          "formula": "yawP95(F04)  <= 0.5 * yawP95(A04)",
          "input_paths": [
            "/inputs/BY2H/full/A04/yaw_p95_deg",
            "/inputs/BY2H/full/F04/yaw_p95_deg"
          ],
          "rule_source": {
            "file": "<CODE_ROOT>/docs/paper_rebuild/A04_F04_ROLE_DECISION_RULE.md",
            "sha256": "4699d35abbfd8a56f282323b082aa5e29658e62a9575f3812836a6095f8fecce",
            "size_bytes": 4578,
            "line": 53,
            "column": "pre_registered_formula",
            "raw_token": "yawP95(F04)  <= 0.5 * yawP95(A04)"
          },
          "left_decimal": "4.117244083402463",
          "right_decimal": "2.0534836907778585",
          "inclusive_comparison": false,
          "threshold_equal": false,
          "strict_pass": false
        }
      }
    },
    "position": {
      "status": "FAIL",
      "windows": {
        "BY2H_full": {
          "horizontal_rmse_m": {
            "formula": "horizontalRMSE(F04) <= 1.10 * horizontalRMSE(A04)",
            "input_paths": [
              "/inputs/BY2H/full/A04/horizontal_rmse_m",
              "/inputs/BY2H/full/F04/horizontal_rmse_m"
            ],
            "rule_source": {
              "file": "<CODE_ROOT>/docs/paper_rebuild/A04_F04_ROLE_DECISION_RULE.md",
              "sha256": "4699d35abbfd8a56f282323b082aa5e29658e62a9575f3812836a6095f8fecce",
              "size_bytes": 4578,
              "line": 64,
              "column": "pre_registered_formula",
              "raw_token": "horizontalRMSE(F04) <= 1.10 * horizontalRMSE(A04)"
            },
            "left_decimal": "0.3519394504567077",
            "right_decimal": "0.3842956302040021650",
            "inclusive_comparison": true,
            "threshold_equal": false,
            "strict_pass": true
          },
          "up_rmse_m": {
            "formula": "upRMSE(F04)         <= 1.10 * upRMSE(A04)",
            "input_paths": [
              "/inputs/BY2H/full/A04/up_rmse_m",
              "/inputs/BY2H/full/F04/up_rmse_m"
            ],
            "rule_source": {
              "file": "<CODE_ROOT>/docs/paper_rebuild/A04_F04_ROLE_DECISION_RULE.md",
              "sha256": "4699d35abbfd8a56f282323b082aa5e29658e62a9575f3812836a6095f8fecce",
              "size_bytes": 4578,
              "line": 66,
              "column": "pre_registered_formula",
              "raw_token": "upRMSE(F04)         <= 1.10 * upRMSE(A04)"
            },
            "left_decimal": "0.9167832730462901",
            "right_decimal": "0.957123090083229630",
            "inclusive_comparison": true,
            "threshold_equal": false,
            "strict_pass": true
          }
        },
        "BY2O_full": {
          "horizontal_rmse_m": {
            "formula": "horizontalRMSE(F04) <= 1.10 * horizontalRMSE(A04)",
            "input_paths": [
              "/inputs/BY2O/full/A04/horizontal_rmse_m",
              "/inputs/BY2O/full/F04/horizontal_rmse_m"
            ],
            "rule_source": {
              "file": "<CODE_ROOT>/docs/paper_rebuild/A04_F04_ROLE_DECISION_RULE.md",
              "sha256": "4699d35abbfd8a56f282323b082aa5e29658e62a9575f3812836a6095f8fecce",
              "size_bytes": 4578,
              "line": 64,
              "column": "pre_registered_formula",
              "raw_token": "horizontalRMSE(F04) <= 1.10 * horizontalRMSE(A04)"
            },
            "left_decimal": "0.3509123233117259",
            "right_decimal": "0.382849874033428340",
            "inclusive_comparison": true,
            "threshold_equal": false,
            "strict_pass": true
          },
          "up_rmse_m": {
            "formula": "upRMSE(F04)         <= 1.10 * upRMSE(A04)",
            "input_paths": [
              "/inputs/BY2O/full/A04/up_rmse_m",
              "/inputs/BY2O/full/F04/up_rmse_m"
            ],
            "rule_source": {
              "file": "<CODE_ROOT>/docs/paper_rebuild/A04_F04_ROLE_DECISION_RULE.md",
              "sha256": "4699d35abbfd8a56f282323b082aa5e29658e62a9575f3812836a6095f8fecce",
              "size_bytes": 4578,
              "line": 66,
              "column": "pre_registered_formula",
              "raw_token": "upRMSE(F04)         <= 1.10 * upRMSE(A04)"
            },
            "left_decimal": "1.5638455228382735",
            "right_decimal": "1.293721648369859390",
            "inclusive_comparison": false,
            "threshold_equal": false,
            "strict_pass": false
          }
        },
        "BY2O_outside": {
          "horizontal_rmse_m": {
            "formula": "horizontalRMSE(F04) <= 1.10 * horizontalRMSE(A04)",
            "input_paths": [
              "/inputs/BY2O/outside/A04/horizontal_rmse_m",
              "/inputs/BY2O/outside/F04/horizontal_rmse_m"
            ],
            "rule_source": {
              "file": "<CODE_ROOT>/docs/paper_rebuild/A04_F04_ROLE_DECISION_RULE.md",
              "sha256": "4699d35abbfd8a56f282323b082aa5e29658e62a9575f3812836a6095f8fecce",
              "size_bytes": 4578,
              "line": 64,
              "column": "pre_registered_formula",
              "raw_token": "horizontalRMSE(F04) <= 1.10 * horizontalRMSE(A04)"
            },
            "left_decimal": "0.3649831506138463",
            "right_decimal": "0.398111337638554430",
            "inclusive_comparison": true,
            "threshold_equal": false,
            "strict_pass": true
          },
          "up_rmse_m": {
            "formula": "upRMSE(F04)         <= 1.10 * upRMSE(A04)",
            "input_paths": [
              "/inputs/BY2O/outside/A04/up_rmse_m",
              "/inputs/BY2O/outside/F04/up_rmse_m"
            ],
            "rule_source": {
              "file": "<CODE_ROOT>/docs/paper_rebuild/A04_F04_ROLE_DECISION_RULE.md",
              "sha256": "4699d35abbfd8a56f282323b082aa5e29658e62a9575f3812836a6095f8fecce",
              "size_bytes": 4578,
              "line": 66,
              "column": "pre_registered_formula",
              "raw_token": "upRMSE(F04)         <= 1.10 * upRMSE(A04)"
            },
            "left_decimal": "1.6127763516950118",
            "right_decimal": "1.336104650072249640",
            "inclusive_comparison": false,
            "threshold_equal": false,
            "strict_pass": false
          }
        }
      }
    }
  },
  "metric_recomputation_count": 0,
  "reference_payload_read_count": 0
}
```
