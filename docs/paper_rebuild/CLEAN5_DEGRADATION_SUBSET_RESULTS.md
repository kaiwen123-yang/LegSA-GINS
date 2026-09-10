# CLEAN5 修正链退化子集结果

决定：**`HUMAN_DECISION_REQUIRED`**。机械选择 **61** 个 case、排除 **480** 个；两链求解共 **1332 完成、10 失败**，子集 v2/v3 评估记录共 **2664 完成、20 缺失**。60 个主指标配对/版本项为 **23 维持、13 翻转、24 不完整**。

GINav 横向评估为 `UNAVAILABLE_EVALUATION_FAILED`，正式指标不可用。子集 2664 个 COMPLETED 中有 **295 个 capture.consistency=false**，按既有封装规则保留原终态和指标，作为诊断单独登记。最终封存验证状态见末节。

V6：`PASS_BY_HUMAN_AMENDMENT`。原始预注册提交 `b73fbaae7f8ef9da444c4320e1cd6d1a43df64f2`；检查点口径补充及执行合约提交 `3326a9cbd50d80156fe46309cd1ee5336b5a3c3b`；执行代码 `24cc761e4085561888a9d8546df8b89300d340fe`。主链锚点、A04/F04 Outcome、冻结可执行文件和评估器不变。失败 run 未重试，case、指标和四列表未事后调整；全量矩阵未自动重跑。陀螺 z 轴标度输入侧检查保留为后续项，本任务未执行。

## 来源别名与展示约定

所有本机绝对路径只在未跟踪产物中保存。报告使用以下别名；表内数值展示为 9 位有效数字，原始 CSV/JSON 的数值 token 不改写。决定 JSON 原文、完整哈希和引文不作数值格式化。H/3D/Up 及体坐标偏差单位 m；yaw RMSE/P95 单位 deg；时刻/时段单位 s；加速度 m/s²；航向速率 deg/s；胜率和 Pearson r 无量纲。

| 别名 | 路径 |
|---|---|
| S | `<CLEAN_ROOT>/stages/CLEAN5_DEGSUBSET_BY2` |
| K | `<CLEAN_ROOT>/stages/CLEAN5_CALIBRATED_SENSOR_MODEL` |
| V | `K/09_YAW_CHANGE_CHECK` |
| P | `<CLEAN_ROOT>/stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF` |
| C | `<CLEAN_ROOT>/stages/CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX/.attempt_20260808T200855P0800` |
| H | `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON` |
| 合约 | `<CODE_ROOT>/configs/paper_rebuild/clean5/CLEAN5_DEGRADATION_SUBSET_CONTRACT.yaml` |

## V-CHK 来源及人类修订的 V5/V6

V1–V4 原始统计未改写。完整表及定义为 `docs/paper_rebuild/CLEAN5_YAW_CHANGE_CHECK.md` 和以下封存输出；V-CHK 自身 solver/evaluator/provider 生成均 0，raw trace/.bag/.fpl 打开均 0。

| 检查 | 完整数据来源 |
|---|---|
| V1 | `V/V1_COUNTS.csv`；`V/V1_COUNTS_WITH_DELTAS.csv` |
| V2 | `V/V2_A04_10S_BINS.csv`；`V/V2_A04_TOP5.csv`；`V/V2_P05_N02_MINUS_N00_BINS.csv`；`V/V2_P05_N02_MINUS_N00_TOP5.csv` |
| V3 | `V/V3_FIRST30_1S_BINS.csv`；`V/V3_FULL_WINDOW_1S_BINS.csv`；`V/V3_FIRST_ENTRY.csv` |
| V4 | `V/V4_F01_10S_BINS.csv` |
| 定义/配对/来源 | `V/ANALYSIS_DEFINITIONS.json`；`V/STATISTICS.json`；`V/INPUT_CATALOG.json`；`V/INPUT_HASH_LEDGER.csv` |
| 旧总门 | `V/YAW_CHANGE_CHECK_DECISION.json`：保留旧 `UNDETERMINED` / STOP 历史记录 |
| 当前 V5/V6 | `docs/paper_rebuild/CLEAN5_YAW_CHANGE_CHECK.md` 的“修订与放行”节，提交 `967d6b396b95ef7ec416b187813e0872a1c7fd1b` |

2026-09-10 人类将 V5 改为逐序列登记，不再要求三序列同一总标签；当前 V6=`PASS_BY_HUMAN_AMENDMENT`。旧 STOP 保留为历史来源，当前 P-07 依据人类修订执行。

| 序列 | 人类登记标签 | 登记依据（展示值） |
|---|---|---|
| BY2 | `INITIAL_TRANSIENT + TURN_SEGMENT_TRACKING` | 前 30 s 净差贡献 56.4541337%；236–266 s 三箱；总 MAE 差 +0.123967050 deg ≤ 0.25 deg |
| BY2H | `INITIAL_TRANSIENT` | 首次 1 s 箱均值进入 ±2 deg：冻结相对起点 26 s，CAL 1 s |
| BY2O | `POST_GATING_RECOVERY` | 3316–3366 s 段；CAL−冻结分箱差与水平加速度 r=+0.808440234 |

人类修订说明原文：“三序列降权/拒绝均减少、接受数不变、首次进入时刻相同、F02 与 A04 在 CAL 下的转弯暂态一致（非门控）”。同时保留已登记的精确边界：A04 downweight+reject 为 45→28、46→24、61→42；accepted 为 268→269、265→264、365→365，“接受数不变”仅对 BY2O 严格成立；BY2H reject 为 5→5。BY2/BY2H 的 A04/F02 原始样本首次进入时刻相同；BY2O A04 为 3193.38706→3193.86306 s，F02 为 3186.20706→3192.00305 s。上述标签依人类决定登记，不据此调参；1 s 箱首次进入不表示持续保持。

## 子集与运行终态

Canonical 541；机械选择 61；排除 480（非选定 seed）；NOT_TRANSFERABLE：[]；seed 回退：[]。
每个 degradation_type_id 的注册表只有一个严重度参数等级。C00 + D01_seed_00 至 D60_seed_00。

| 链 | 终态 | 次数 |
|---|---|---|
| CAL | COMPLETED | 669 |
| CAL | FAILED_TECHNICAL | 2 |
| V2S | COMPLETED | 663 |
| V2S | FAILED_TECHNICAL | 8 |

| 评估版本 | 链 | 终态 | 次数 |
|---|---|---|---|
| v3 | CAL | COMPLETED | 669 |
| v3 | CAL | UNAVAILABLE_FAILED_SOLVER | 2 |
| v3 | V2S | COMPLETED | 663 |
| v3 | V2S | UNAVAILABLE_FAILED_SOLVER | 8 |
| v2 | CAL | COMPLETED | 669 |
| v2 | CAL | UNAVAILABLE_FAILED_SOLVER | 2 |
| v2 | V2S | COMPLETED | 663 |
| v2 | V2S | UNAVAILABLE_FAILED_SOLVER | 8 |

选定 case 清单：

```text
C00_clean_normal
D01_seed_00
D02_seed_00
D03_seed_00
D04_seed_00
D05_seed_00
D06_seed_00
D07_seed_00
D08_seed_00
D09_seed_00
D10_seed_00
D11_seed_00
D12_seed_00
D13_seed_00
D14_seed_00
D15_seed_00
D16_seed_00
D17_seed_00
D18_seed_00
D19_seed_00
D20_seed_00
D21_seed_00
D22_seed_00
D23_seed_00
D24_seed_00
D25_seed_00
D26_seed_00
D27_seed_00
D28_seed_00
D29_seed_00
D30_seed_00
D31_seed_00
D32_seed_00
D33_seed_00
D34_seed_00
D35_seed_00
D36_seed_00
D37_seed_00
D38_seed_00
D39_seed_00
D40_seed_00
D41_seed_00
D42_seed_00
D43_seed_00
D44_seed_00
D45_seed_00
D46_seed_00
D47_seed_00
D48_seed_00
D49_seed_00
D50_seed_00
D51_seed_00
D52_seed_00
D53_seed_00
D54_seed_00
D55_seed_00
D56_seed_00
D57_seed_00
D58_seed_00
D59_seed_00
D60_seed_00
```

## 失败 run 与评估不可用记录

| 链 | run_id | case_id | method | 原生 exit | 终态 | 失败类型 | retry |
|---|---|---|---|---|---|---|---|
| CAL | RUN_01400 | D15_seed_00 | F03 | 1 | FAILED_TECHNICAL | FAILED_NATIVE_SOLVER | 0 |
| CAL | RUN_05756 | D59_seed_00 | F03 | 1 | FAILED_TECHNICAL | FAILED_NATIVE_SOLVER | 0 |
| V2S | RUN_01301 | D14_seed_00 | F03 | 1 | FAILED_TECHNICAL | FAILED_NATIVE_SOLVER | 0 |
| V2S | RUN_01304 | D14_seed_00 | A04 | 1 | FAILED_TECHNICAL | FAILED_NATIVE_SOLVER | 0 |
| V2S | RUN_01403 | D15_seed_00 | A04 | 1 | FAILED_TECHNICAL | FAILED_NATIVE_SOLVER | 0 |
| V2S | RUN_02592 | D27_seed_00 | A05 | 1 | FAILED_TECHNICAL | FAILED_NATIVE_SOLVER | 0 |
| V2S | RUN_02594 | D27_seed_00 | A07 | 1 | FAILED_TECHNICAL | FAILED_NATIVE_SOLVER | 0 |
| V2S | RUN_02596 | D27_seed_00 | A09 | 1 | FAILED_TECHNICAL | FAILED_NATIVE_SOLVER | 0 |
| V2S | RUN_05759 | D59_seed_00 | A04 | 1 | FAILED_TECHNICAL | FAILED_NATIVE_SOLVER | 0 |
| V2S | RUN_05763 | D59_seed_00 | A08 | 1 | FAILED_TECHNICAL | FAILED_NATIVE_SOLVER | 0 |

每行来源：`S/03_RUNS/CLEAN5_DEGSUBSET_<chain>/<run_id>/P07_RUN_TERMINAL.json`；总记录 `S/03_RUNS/RUN_RECORDS.json`。全部失败 run 的两个版本评估目录均仅含结果 JSON，未调用评估器。

10 个失败 run 的原生报错均为 `FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH: actual formal module activation counters mismatch`。其 `PORT_GNSS_UPDATE_TRACE.csv` 均记录 position/RV 各 1369 次，yaw attempt=273、normal=0、downweight=0、reject=273、accepted=0（67–339 s），原生 `yaw_active>0` 计数条件未满足；没有 NAV/STD 或原生 RUN_MANIFEST。拒绝的进一步原因没有由现有记录证明。

子集评估记录 2684；实际子集评估器调用 2664，另有 20 个 `UNAVAILABLE_FAILED_SOLVER` 记录。横向后处理另调用 4 次，合计 2668 次评估器进程；横向没有新求解。

## 注入映射与语义等价证据

P/RV 名义 5 Hz；每次测量 std 不变，污染机会约为冻结输入的 5 倍，实际计数见下表。A1 仅有效行；RD/RP/HV 保留源频率。缺失正式实现为有效位 0；冻结库本来使用有效位，删行对照不适用。D57 保留独立时延/抖动后的不规则时间并集。
C00 的数据模式为 real_clean；D01–D60 为 real_base_controlled_degradation。冻结 schema 的 synthetic/semisynthetic 均为 false，另以 controlled_degradation_applied 明示受控注入。

| case | 迁移规则 | 冻结参数 | 语义门 |
|---|---|---|---|
| C00_clean_normal | CLEAN_REFERENCE_BYTE_IDENTITY | {"operation": "none"} | PASS_SEMANTIC_EQUIVALENCE |
| D01_seed_00 | FROZEN_TIME_WINDOWS_UNCHANGED | {"duration_s": 3, "operation": "outage", "sources": ["gnss_position"]} | PASS_SEMANTIC_EQUIVALENCE |
| D02_seed_00 | FROZEN_TIME_WINDOWS_UNCHANGED | {"duration_s": 5, "operation": "outage", "sources": ["gnss_position"]} | PASS_SEMANTIC_EQUIVALENCE |
| D03_seed_00 | FROZEN_TIME_WINDOWS_UNCHANGED | {"duration_s": 10, "operation": "outage", "sources": ["gnss_position"]} | PASS_SEMANTIC_EQUIVALENCE |
| D04_seed_00 | FROZEN_TIME_WINDOWS_UNCHANGED | {"duration_s": 20, "operation": "outage", "sources": ["gnss_position"]} | PASS_SEMANTIC_EQUIVALENCE |
| D05_seed_00 | FROZEN_TIME_WINDOWS_UNCHANGED | {"duration_s": 10, "operation": "outage", "sources": ["gnss_position", "receiver_velocity"]} | PASS_SEMANTIC_EQUIVALENCE |
| D06_seed_00 | FROZEN_TIME_WINDOWS_UNCHANGED | {"duration_s": 20, "operation": "outage", "sources": ["gnss_position", "receiver_velocity", "dual_yaw"]} | PASS_SEMANTIC_EQUIVALENCE |
| D07_seed_00 | FROZEN_TIME_WINDOWS_UNCHANGED | {"duration_each_s": 3.0, "interval_centers_relative_to_anchor_s": [-6.0, 0.0, 6.0], "interval_count": 3, "operation": "repeated_outage", "seed_controls": "interval_start_times", "sources": ["gnss_position"]} | PASS_SEMANTIC_EQUIVALENCE |
| D08_seed_00 | FROZEN_TARGET_RATE_PHASE_ON_NOMINAL_5HZ_INPUT | {"operation": "downsample", "seed_controls": "phase", "sources": ["gnss_position", "receiver_velocity", "dual_yaw"], "target_rate_hz": 5} | PASS_SEMANTIC_EQUIVALENCE |
| D09_seed_00 | FROZEN_TARGET_RATE_PHASE_ON_NOMINAL_5HZ_INPUT | {"operation": "downsample", "seed_controls": "phase", "sources": ["gnss_position", "receiver_velocity", "dual_yaw"], "target_rate_hz": 2} | PASS_SEMANTIC_EQUIVALENCE |
| D10_seed_00 | FROZEN_TARGET_RATE_PHASE_ON_NOMINAL_5HZ_INPUT | {"operation": "downsample", "seed_controls": "phase", "sources": ["gnss_position", "receiver_velocity", "dual_yaw"], "target_rate_hz": 1} | PASS_SEMANTIC_EQUIVALENCE |
| D11_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"dropout_ratio": 0.3, "operation": "random_dropout", "seed_controls": "dropout_pattern", "sources": ["gnss_position", "receiver_velocity", "dual_yaw"]} | PASS_SEMANTIC_EQUIVALENCE |
| D12_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"dropout_ratio": 0.6, "operation": "random_dropout", "seed_controls": "dropout_pattern", "sources": ["gnss_position", "receiver_velocity", "dual_yaw"]} | PASS_SEMANTIC_EQUIVALENCE |
| D13_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"h_sigma_m": 0.5, "operation": "gaussian_position_noise", "v_sigma_m": 1.0} | PASS_SEMANTIC_EQUIVALENCE |
| D14_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"h_sigma_m": 1.5, "operation": "gaussian_position_noise", "v_sigma_m": 2.5} | PASS_SEMANTIC_EQUIVALENCE |
| D15_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"h_sigma_m": 3.0, "operation": "gaussian_position_noise", "v_sigma_m": 5.0} | PASS_SEMANTIC_EQUIVALENCE |
| D16_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"horizontal_bias_m": 1.5, "operation": "static_position_bias", "seed_controls": "horizontal_direction_and_vertical_sign", "vertical_bias_m": 0.5} | PASS_SEMANTIC_EQUIVALENCE |
| D17_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"horizontal_bias_m": 3.0, "operation": "static_position_bias", "seed_controls": "horizontal_direction_and_vertical_sign", "vertical_bias_m": 1.0} | PASS_SEMANTIC_EQUIVALENCE |
| D18_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"horizontal_end_m": 3.0, "horizontal_start_m": 0.0, "operation": "slow_drift_bias", "vertical_end_m": 1.0, "vertical_start_m": 0.0} | PASS_SEMANTIC_EQUIVALENCE |
| D19_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"angular_time_denominator_s": 30.0, "horizontal_amplitude_m": 2.0, "operation": "sinusoidal_multipath", "period_s": 188.49555921538757, "phase_rule": "2*pi*U(component_substream)", "seed_controls": "phase", "vertical_amplitude_m": 0.5} | PASS_SEMANTIC_EQUIVALENCE |
| D20_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"horizontal_m": 2.0, "operation": "position_spike", "probability": 0.02, "vertical_m": 1.0} | PASS_SEMANTIC_EQUIVALENCE |
| D21_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"horizontal_m": 4.0, "operation": "position_spike", "probability": 0.05, "vertical_m": 2.0} | PASS_SEMANTIC_EQUIVALENCE |
| D22_seed_00 | FROZEN_EPOCH_COUNT_TO_EQUAL_DURATION_SECONDS | {"burst_length_epochs_max": 5, "burst_length_epochs_min": 3, "horizontal_m": 8.0, "operation": "position_burst_spike", "vertical_m": 4.0} | PASS_SEMANTIC_EQUIVALENCE |
| D23_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"factor": 1.5, "operation": "std_inflation", "source": "gnss_position_std"} | PASS_SEMANTIC_EQUIVALENCE |
| D24_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"factor": 2.5, "operation": "std_inflation", "source": "gnss_position_std"} | PASS_SEMANTIC_EQUIVALENCE |
| D25_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"factor": 4.0, "operation": "std_inflation", "source": "gnss_position_std"} | PASS_SEMANTIC_EQUIVALENCE |
| D26_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"factor": 0.25, "operation": "std_deflation", "source": "gnss_position_std"} | PASS_SEMANTIC_EQUIVALENCE |
| D27_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"h_sigma_m": 3.0, "operation": "bad_position_optimistic_std", "std_factor": 0.25, "v_sigma_m": 5.0} | PASS_SEMANTIC_EQUIVALENCE |
| D28_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"operation": "good_position_pessimistic_std", "std_factor": 4.0, "value_change": "unchanged"} | PASS_SEMANTIC_EQUIVALENCE |
| D29_seed_00 | AUDIT_METADATA_NO_ACTIVE_SOLVER_PATH | {"operation": "status_quality_downgrade_only", "value_change": "unchanged"} | PASS_SEMANTIC_EQUIVALENCE |
| D30_seed_00 | FROZEN_TIME_WINDOWS_UNCHANGED | {"duration_s": 5, "operation": "outage", "sources": ["dual_yaw"]} | PASS_SEMANTIC_EQUIVALENCE |
| D31_seed_00 | FROZEN_TIME_WINDOWS_UNCHANGED | {"duration_s": 20, "operation": "outage", "sources": ["dual_yaw"]} | PASS_SEMANTIC_EQUIVALENCE |
| D32_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"operation": "dual_yaw_gaussian_noise", "sigma_deg": 1.0, "yaw_wrap": "required"} | PASS_SEMANTIC_EQUIVALENCE |
| D33_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"operation": "dual_yaw_gaussian_noise", "sigma_deg": 5.0, "yaw_wrap": "required"} | PASS_SEMANTIC_EQUIVALENCE |
| D34_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"operation": "dual_yaw_spike", "probability": 0.05, "signed_spike_magnitude_deg": 10.0, "yaw_wrap": "required"} | PASS_SEMANTIC_EQUIVALENCE |
| D35_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"operation": "dual_yaw_spike", "probability": 0.1, "signed_spike_magnitude_deg": 10.0, "yaw_wrap": "required"} | PASS_SEMANTIC_EQUIVALENCE |
| D36_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"factor": 1.5, "operation": "yaw_std_inflation"} | PASS_SEMANTIC_EQUIVALENCE |
| D37_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"factor": 3.0, "operation": "yaw_std_inflation"} | PASS_SEMANTIC_EQUIVALENCE |
| D38_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"operation": "bad_yaw_optimistic_std", "optional_spike_component": true, "yaw_noise_sigma_deg": 10.0, "yaw_std_factor": 0.25, "yaw_wrap": "required"} | PASS_SEMANTIC_EQUIVALENCE |
| D39_seed_00 | FROZEN_EPOCH_COUNT_TO_EQUAL_DURATION_SECONDS | {"burst_count": 3, "burst_length_valid_epochs_max": 4, "burst_length_valid_epochs_min": 2, "fields": ["rel_valid", "quality"], "operation": "baseline_quality_dropout", "seed_controls": "unavailable_bursts"} | PASS_SEMANTIC_EQUIVALENCE |
| D40_seed_00 | AUDIT_METADATA_NO_ACTIVE_SOLVER_PATH | {"baseline_length_additive_jitter_sigma_m": 0.03, "baseline_length_jitter_m": "seeded_small_jitter", "baseline_length_solver_visible": false, "minimum_baseline_length_m": 0.01, "operation": "baseline_length_jitter_relacc", "preserve_baseline_direction": true, "rel_acc_factor": 2.0, "rel_acc_field_available": false, "rel_acc_inflation": true, "rel_acc_no_active_path": true, "solver_runtime_input_expected_invariant": true, "unit_aliasing_forbidden": true} | PASS_SEMANTIC_EQUIVALENCE |
| D41_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"h_sigma_m": 3.0, "operation": "gnss1_gnss2_asymmetric_noise", "seed_controls": "antenna_selection", "v_sigma_m": 2.0} | PASS_SEMANTIC_EQUIVALENCE |
| D42_seed_00 | FROZEN_TIME_WINDOWS_UNCHANGED | {"duration_s": 20, "operation": "outage", "sources": ["receiver_velocity"]} | PASS_SEMANTIC_EQUIVALENCE |
| D43_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"operation": "receiver_velocity_noise", "sigma_mps": 0.5} | PASS_SEMANTIC_EQUIVALENCE |
| D44_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"magnitude_mps": 2.0, "operation": "receiver_velocity_spike", "probability": 0.02} | PASS_SEMANTIC_EQUIVALENCE |
| D45_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"operation": "receiver_velocity_noise_optimistic_std", "sigma_mps": 0.5, "std_factor": 0.25} | PASS_SEMANTIC_EQUIVALENCE |
| D46_seed_00 | FROZEN_TIME_WINDOWS_UNCHANGED | {"duration_s": 20, "operation": "outage", "sources": ["raw_doppler_velocity"]} | PASS_SEMANTIC_EQUIVALENCE |
| D47_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"operation": "raw_doppler_velocity_noise", "sigma_mps": 0.5} | PASS_SEMANTIC_EQUIVALENCE |
| D48_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"magnitude_mps": 1.5, "operation": "raw_doppler_velocity_spike", "probability": 0.02} | PASS_SEMANTIC_EQUIVALENCE |
| D49_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"anomaly": "noise_or_spike_seeded", "gaussian_sigma_mps": 0.5, "operation": "raw_doppler_anomaly_optimistic_std", "optimistic_or_floor_std_policy": true, "spike_component": false, "std_factor": 0.25, "std_floor_component": false} | PASS_SEMANTIC_EQUIVALENCE |
| D50_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"conflict_magnitude_mps": 1.0, "operation": "raw_receiver_velocity_conflict", "raw_doppler_horizontal_offset_mps": 1.0, "receiver_velocity_unchanged": true} | PASS_SEMANTIC_EQUIVALENCE |
| D51_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"dropout_ratio": 0.5, "operation": "go2_roll_pitch_dropout_noise", "remaining_noise_sigma_deg": 3.0} | PASS_SEMANTIC_EQUIVALENCE |
| D52_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"bias_deg": 2.0, "operation": "go2_roll_pitch_bias", "seed_controls": "roll_pitch_direction"} | PASS_SEMANTIC_EQUIVALENCE |
| D53_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"operation": "go2_horizontal_velocity_noise", "sigma_mps": 1.0} | PASS_SEMANTIC_EQUIVALENCE |
| D54_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"dropout_ratio": 0.5, "operation": "go2_horizontal_velocity_scale_or_dropout", "scale": 1.5, "seed_group_controls": "scale_vs_dropout", "seed_groups": {"seed_00_to_seed_03": {"dropout_ratio": 0.0, "scale": 1.5}, "seed_04_to_seed_07": {"dropout_ratio": 0.5, "scale": 1.0}, "seed_08": {"dropout_ratio": 0.5, "scale": 1.5}}} | PASS_SEMANTIC_EQUIVALENCE |
| D55_seed_00 | AUDIT_METADATA_NO_ACTIVE_SOLVER_PATH | {"operation": "go2_contact_motion_metadata_uncertain", "pattern": "missing_or_uncertain_seeded", "selection_ratio": 0.35, "uncertainty_pattern": "contact_uncertain_and_mode_gait_unknown"} | PASS_SEMANTIC_EQUIVALENCE |
| D56_seed_00 | AUDIT_METADATA_NO_ACTIVE_SOLVER_PATH | {"even_pattern": "high_force_high_speed", "odd_pattern": "low_force_low_speed", "operation": "go2_foot_speed_contact_conflict", "pattern": "foot_force_and_foot_speed_conflict_seeded", "seed_08_pattern": "alternating", "selection_ratio": 0.3} | PASS_SEMANTIC_EQUIVALENCE |
| D57_seed_00 | INDEPENDENT_SOURCE_LATENCY_JITTER_STABLE_UNION | {"components": ["latency_shift", "timestamp_jitter"], "jitter_max_range_s": [0.02, 0.05], "jitter_range_ms": [20, 50], "latency_range_s": [0.1, 0.3], "operation": "multi_source_latency_jitter", "per_source_independent_substreams": true, "stable_sort": true} | PASS_SEMANTIC_EQUIVALENCE |
| D58_seed_00 | FROZEN_TIME_WINDOWS_UNCHANGED | {"components": ["position_outage_10s", "dual_yaw_spike", "clean_recovery_interval"], "degradation_duration_s": 10.0, "operation": "mixed_components", "recovery_duration_s": 20.0, "recovery_interval": "required", "yaw_spike_magnitude_deg": 10.0, "yaw_spike_probability": 0.1} | PASS_SEMANTIC_EQUIVALENCE |
| D59_seed_00 | FROZEN_PER_MEASUREMENT_LAW_AMPLITUDE_AND_SUBSTREAMS | {"components": ["bad_position", "good_yaw", "raw_receiver_velocity_conflict"], "conflict_magnitude_mps": 1.0, "operation": "mixed_components"} | PASS_SEMANTIC_EQUIVALENCE |
| D60_seed_00 | FROZEN_TIME_WINDOWS_UNCHANGED | {"components": ["bad_position_optimistic_std", "bad_yaw_optimistic_std", "bad_velocity_optimistic_std", "clean_recovery_interval"], "degradation_duration_s": 20.0, "operation": "mixed_components", "recovery_duration_s": 20.0, "recovery_interval": "required"} | PASS_SEMANTIC_EQUIVALENCE |

逐源注入前后 affected rows、实际时段、字段幅值、std/状态/时间变化与冻结同 case 摘要：

| case | 源 | 冻结影响行数 | 冻结时段 | 冻结字段幅值 | 新链影响行数 | 新链时段 | 新链字段幅值 |
|---|---|---|---|---|---|---|---|
| C00_clean_normal | gnss_position | 0 | [UNAVAILABLE,UNAVAILABLE] | {"changed_fields":{},"delta":{}} | 0 | [UNAVAILABLE,UNAVAILABLE] | {"changed_fields":{},"delta":{}} |
| C00_clean_normal | receiver_velocity | 0 | [UNAVAILABLE,UNAVAILABLE] | {"changed_fields":{},"delta":{}} | 0 | [UNAVAILABLE,UNAVAILABLE] | {"changed_fields":{},"delta":{}} |
| C00_clean_normal | dual_yaw | 0 | [UNAVAILABLE,UNAVAILABLE] | {"changed_fields":{},"delta":{}} | 0 | [UNAVAILABLE,UNAVAILABLE] | {"changed_fields":{},"delta":{}} |
| C00_clean_normal | raw_doppler | 0 | [UNAVAILABLE,UNAVAILABLE] | {"changed_fields":{},"delta":{}} | 0 | [UNAVAILABLE,UNAVAILABLE] | {"changed_fields":{},"delta":{}} |
| C00_clean_normal | go2_rp | 0 | [UNAVAILABLE,UNAVAILABLE] | {"changed_fields":{},"delta":{}} | 0 | [UNAVAILABLE,UNAVAILABLE] | {"changed_fields":{},"delta":{}} |
| C00_clean_normal | go2_hv | 0 | [UNAVAILABLE,UNAVAILABLE] | {"changed_fields":{},"delta":{}} | 0 | [UNAVAILABLE,UNAVAILABLE] | {"changed_fields":{},"delta":{}} |
| C00_clean_normal | source_quality_metadata | 0 | [UNAVAILABLE,UNAVAILABLE] | {"changed_fields":{},"delta":{}} | 0 | [UNAVAILABLE,UNAVAILABLE] | {"changed_fields":{},"delta":{}} |
| D01_seed_00 | gnss_position | 3 | [205.204989,207.206256] | {"changed_fields":{"status":3,"valid":3},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} | 15 | [204.8,207.6] | {"changed_fields":{"status":15,"valid":15},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} |
| D02_seed_00 | gnss_position | 5 | [204.20564,208.204936] | {"changed_fields":{"status":5,"valid":5},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} | 25 | [203.8,208.6] | {"changed_fields":{"status":25,"valid":25},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} |
| D03_seed_00 | gnss_position | 10 | [201.211278,210.205992] | {"changed_fields":{"status":10,"valid":10},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} | 50 | [201.2,211] | {"changed_fields":{"status":50,"valid":50},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} |
| D04_seed_00 | gnss_position | 20 | [196.210194,215.205113] | {"changed_fields":{"status":20,"valid":20},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} | 100 | [196.2,216] | {"changed_fields":{"status":100,"valid":100},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} |
| D05_seed_00 | gnss_position | 10 | [201.211278,210.205992] | {"changed_fields":{"status":10,"valid":10},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} | 50 | [201.2,211] | {"changed_fields":{"status":50,"valid":50},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} |
| D05_seed_00 | receiver_velocity | 10 | [201.211278,210.205992] | {"changed_fields":{"status":10,"valid":10},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"velocity_delta_norm_mps":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} | 50 | [201.2,211] | {"changed_fields":{"status":50,"valid":50},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"velocity_delta_norm_mps":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} |
| D06_seed_00 | gnss_position | 20 | [196.210194,215.205113] | {"changed_fields":{"status":20,"valid":20},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} | 100 | [196.2,216] | {"changed_fields":{"status":100,"valid":100},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} |
| D06_seed_00 | receiver_velocity | 20 | [196.210194,215.205113] | {"changed_fields":{"status":20,"valid":20},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"velocity_delta_norm_mps":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} | 100 | [196.2,216] | {"changed_fields":{"status":100,"valid":100},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"velocity_delta_norm_mps":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} |
| D06_seed_00 | dual_yaw | 20 | [196.210194,215.205113] | {"changed_fields":{"source_status":20,"valid":20},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0}}} | 20 | [197,216] | {"changed_fields":{"source_status":20,"valid":20},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0}}} |
| D07_seed_00 | gnss_position | 9 | [199.203046,213.205368] | {"changed_fields":{"status":9,"valid":9},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} | 45 | [198.8,213.6] | {"changed_fields":{"status":45,"valid":45},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} |
| D09_seed_00 | gnss_position | 0 | [UNAVAILABLE,UNAVAILABLE] | {"changed_fields":{},"delta":{}} | 906 | [56,357.6] | {"changed_fields":{"status":906,"valid":906},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} |
| D09_seed_00 | receiver_velocity | 0 | [UNAVAILABLE,UNAVAILABLE] | {"changed_fields":{},"delta":{}} | 906 | [56,357.6] | {"changed_fields":{"status":906,"valid":906},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"velocity_delta_norm_mps":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} |
| D10_seed_00 | gnss_position | 0 | [UNAVAILABLE,UNAVAILABLE] | {"changed_fields":{},"delta":{}} | 1207 | [56,357.6] | {"changed_fields":{"status":1207,"valid":1207},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} |
| D10_seed_00 | receiver_velocity | 0 | [UNAVAILABLE,UNAVAILABLE] | {"changed_fields":{},"delta":{}} | 1207 | [56,357.6] | {"changed_fields":{"status":1207,"valid":1207},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"velocity_delta_norm_mps":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} |
| D11_seed_00 | gnss_position | 91 | [55.206795,357.201323] | {"changed_fields":{"status":91,"valid":91},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} | 453 | [55.8,357.4] | {"changed_fields":{"status":453,"valid":453},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} |
| D11_seed_00 | receiver_velocity | 91 | [56.215729,355.203544] | {"changed_fields":{"status":91,"valid":91},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"velocity_delta_norm_mps":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} | 453 | [56.4000001,357] | {"changed_fields":{"status":453,"valid":453},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"velocity_delta_norm_mps":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} |
| D11_seed_00 | dual_yaw | 91 | [55.206795,350.203794] | {"changed_fields":{"source_status":91,"valid":91},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0}}} | 90 | [56,354] | {"changed_fields":{"source_status":90,"valid":90},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0}}} |
| D12_seed_00 | gnss_position | 182 | [55.206795,356.210457] | {"changed_fields":{"status":182,"valid":182},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} | 906 | [55.8,357.6] | {"changed_fields":{"status":906,"valid":906},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} |
| D12_seed_00 | receiver_velocity | 182 | [55.206795,357.201323] | {"changed_fields":{"status":182,"valid":182},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"velocity_delta_norm_mps":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} | 906 | [56.2,357.6] | {"changed_fields":{"status":906,"valid":906},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"velocity_delta_norm_mps":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} |
| D12_seed_00 | dual_yaw | 182 | [55.206795,357.201323] | {"changed_fields":{"source_status":182,"valid":182},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0}}} | 181 | [56,352] | {"changed_fields":{"source_status":181,"valid":181},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0}}} |
| D13_seed_00 | gnss_position | 303 | [55.206795,357.201323] | {"changed_fields":{"height_m":303,"lat_deg":303,"lon_deg":303},"delta":{"height_m":{"min":-2.961736000000002,"max":2.7299740000000057,"mean":-0.06035341584158368,"population_std":1.0241848369598243},"lat_deg":{"min":-1.0048200003609509e-05,"max":1.2764399997422515e-05,"mean":6.354211221468936e-07,"population_std":4.213199303576134e-06},"lon_deg":{"min":-1.6594399994573905e-05,"max":1.8091699999445154e-05,"mean":2.138801981814005e-07,"population_std":5.915796901909063e-06},"position_delta_n_m":{"min":-1.115702580716477,"max":1.4172961726415683,"mean":0.07055403615343922,"population_std":0.4678128722295392},"position_delta_e_m":{"min":-1.4173845650038643,"max":1.5452719018161865,"mean":0.018268285430019193,"population_std":0.5052889152320408},"position_delta_u_m":{"min":-2.9617361933697524,"max":2.729973964744744,"mean":-0.06035345347967123,"population_std":1.0241848400092475},"position_delta_h_m":{"min":0.025668712295505533,"max":1.7933021654332535,"mean":0.6134204967543738,"population_std":0.3212361556732591},"position_delta_3d_m":{"min":0.1620746333514382,"max":3.3519826509933965,"mean":1.117297096346389,"population_std":0.5326553274846085}}} | 1510 | [55.8,357.6] | {"changed_fields":{"height_m":1510,"lat_deg":1510,"lon_deg":1510},"delta":{"height_m":{"min":-3.8580346210000016,"max":3.580095550000003,"mean":0.017582495029139125,"population_std":0.9929516123325091},"lat_deg":{"min":-1.952504700142299e-05,"max":1.5717304002293986e-05,"mean":1.241436675077871e-07,"population_std":4.50804416082223e-06},"lon_deg":{"min":-2.0745264990296164e-05,"max":1.7965538006592396e-05,"mean":8.670705706803323e-08,"population_std":5.757838267717921e-06},"position_delta_n_m":{"min":-2.167965344256336,"max":1.74517154196938,"mean":0.013784320376700798,"population_std":0.5005509898692847},"position_delta_e_m":{"min":-1.7719282763642716,"max":1.5345016948923473,"mean":0.007405946571161704,"population_std":0.49179725837249444},"position_delta_u_m":{"min":-3.858034684056511,"max":3.580095507276535,"mean":0.017582456380464878,"population_std":0.9929516121269243},"position_delta_h_m":{"min":0.00805360161694024,"max":2.2156646092362204,"mean":0.623600107388154,"population_std":0.3221546187782631},"position_delta_3d_m":{"min":0.033647323192209526,"max":3.9603080193152005,"mean":1.0901536859082726,"population_std":0.5389690902390611}}} |
| D14_seed_00 | gnss_position | 303 | [55.206795,357.201323] | {"changed_fields":{"height_m":303,"lat_deg":303,"lon_deg":303},"delta":{"height_m":{"min":-7.404339999999998,"max":6.8249350000000035,"mean":-0.15088336633663355,"population_std":2.560462089158946},"lat_deg":{"min":-3.0144500001938468e-05,"max":3.829329999405218e-05,"mean":1.9062613860666202e-06,"population_std":1.2639594354223133e-05},"lon_deg":{"min":-4.97832999997172e-05,"max":5.427509999833546e-05,"mean":6.416379540923546e-07,"population_std":1.77473906911461e-05},"position_delta_n_m":{"min":-3.3470965436301015,"max":4.251899977957174,"mean":0.211661964451594,"population_std":1.4034382237489733},"position_delta_e_m":{"min":-4.252161206657245,"max":4.635812146378748,"mean":0.054804607831250164,"population_std":1.5158666111368004},"position_delta_u_m":{"min":-7.404341736688307,"max":6.824934700539468,"mean":-0.15088370466987489,"population_std":2.560462117289314},"position_delta_h_m":{"min":0.07699907977460413,"max":5.379913013996644,"mean":1.8402609475562253,"population_std":0.9637086737046375},"position_delta_3d_m":{"min":0.4770775858907052,"max":8.774930305884837,"mean":3.0148415147972125,"population_std":1.3434126506542645}}} | 1510 | [55.8,357.6] | {"changed_fields":{"height_m":1510,"lat_deg":1510,"lon_deg":1510},"delta":{"height_m":{"min":-9.645085621,"max":8.950238550000002,"mean":0.04395648641986766,"population_std":2.482379031448848},"lat_deg":{"min":-5.8575246995928865e-05,"max":4.7152004000849956e-05,"mean":3.7243340260967204e-07,"population_std":1.3524133815227252e-05},"lon_deg":{"min":-6.223586500198053e-05,"max":5.389663800769995e-05,"mean":2.601220236106924e-07,"population_std":1.727351786955124e-05},"position_delta_n_m":{"min":-6.503909627905607,"max":5.23552326457349,"mean":0.04135333744076115,"population_std":1.501653131654245},"position_delta_e_m":{"min":-5.315793525799706,"max":4.603506483173128,"mean":0.022217907654954783,"population_std":1.4753920291936462},"position_delta_u_m":{"min":-9.645086185561569,"max":8.950238161260627,"mean":0.043956138607911546,"population_std":2.482379029405274},"position_delta_h_m":{"min":0.024158008580986698,"max":6.647005294423021,"mean":1.8708004420337603,"population_std":0.9664642816159769},"position_delta_3d_m":{"min":0.09627775221131865,"max":10.011204092296834,"mean":2.9526541978234113,"population_std":1.3711011915177447}}} |
| D15_seed_00 | gnss_position | 303 | [55.206795,357.201323] | {"changed_fields":{"height_m":303,"lat_deg":303,"lon_deg":303},"delta":{"height_m":{"min":-14.808676000000002,"max":13.649871000000005,"mean":-0.3017661221122109,"population_std":5.120924108533565},"lat_deg":{"min":-6.028909999855614e-05,"max":7.658659999520978e-05,"mean":3.8125191418930177e-06,"population_std":2.5279191712415646e-05},"lon_deg":{"min":-9.956670000121903e-05,"max":0.00010855019999667093,"mean":1.2832722775223817e-06,"population_std":3.549478724034095e-05},"position_delta_n_m":{"min":-6.694203891054993,"max":8.503801135322817,"mean":0.423323745561575,"population_std":2.8068767836041055},"position_delta_e_m":{"min":-8.504327914935493,"max":9.271612537010407,"mean":0.10960883373621255,"population_std":3.0317332940159223},"position_delta_u_m":{"min":-14.808682945685954,"max":13.649869808760393,"mean":-0.30176747582631014,"population_std":5.120924221222505},"position_delta_h_m":{"min":0.153988298105034,"max":10.759832146787321,"mean":3.6805222078067144,"population_std":1.9274172906278615},"position_delta_3d_m":{"min":0.954155478506953,"max":17.54985299368945,"mean":6.029683225175052,"population_std":2.686825232013078}}} | 1510 | [55.8,357.6] | {"changed_fields":{"height_m":1510,"lat_deg":1510,"lon_deg":1510},"delta":{"height_m":{"min":-19.290170620999998,"max":17.900478550000003,"mean":0.08791365794304644,"population_std":4.964758063824832},"lat_deg":{"min":-0.00011715044699656119,"max":9.430410400312894e-05,"mean":7.448638662028379e-07,"population_std":2.7048266414867983e-05},"lon_deg":{"min":-0.00012447166498930073,"max":0.00010779323800136353,"mean":5.202446728848499e-07,"population_std":3.454703386978738e-05},"position_delta_n_m":{"min":-13.007820153550387,"max":10.471051860347785,"mean":0.08270668229494947,"population_std":3.0033061739325584},"position_delta_e_m":{"min":-10.631589944910854,"max":9.207007634017486,"mean":0.04443585374199328,"population_std":2.950783877141311},"position_delta_u_m":{"min":-19.290172880222936,"max":17.90047698936098,"mean":0.08791226674337246,"population_std":4.964758055639466},"position_delta_h_m":{"min":0.048313636705799766,"max":13.294010308296153,"mean":3.7416008135077004,"population_std":1.93292828545993},"position_delta_3d_m":{"min":0.19255481632992208,"max":20.02240502868436,"mean":5.905308309757771,"population_std":2.7422022698479593}}} |
| D16_seed_00 | gnss_position | 303 | [55.206795,357.201323] | {"changed_fields":{"height_m":303,"lat_deg":303,"lon_deg":303},"delta":{"height_m":{"min":0.5,"max":0.5,"mean":0.5,"population_std":0.0},"lat_deg":{"min":1.1887699997714662e-05,"max":1.188770000482009e-05,"mean":1.1887699999825186e-05,"population_std":3.2468231341780448e-15},"lon_deg":{"min":-8.342400008132245e-06,"max":-8.34239999392139e-06,"mean":-8.342399999877754e-06,"population_std":7.011900832321765e-15},"position_delta_n_m":{"min":1.31995161905341,"max":1.319951801891554,"mean":1.3199517104414547,"population_std":5.087060722122788e-08},"position_delta_e_m":{"min":-0.7125569063730821,"max":-0.7125509013702107,"mean":-0.712553600090041,"population_std":2.251066949438415e-06},"position_delta_u_m":{"min":0.4999998217062772,"max":0.4999998251431138,"mean":0.49999982344378907,"population_std":6.663890579253105e-10},"position_delta_h_m":{"min":1.5000004731675216,"max":1.500003245282906,"mean":1.500001716966555,"population_std":1.0285301837996017e-06},"position_delta_3d_m":{"min":1.5811392230891246,"max":1.5811418527914087,"mean":1.5811404031099006,"population_std":9.757571223832453e-07}}} | 1510 | [55.8,357.6] | {"changed_fields":{"height_m":1510,"lat_deg":1510,"lon_deg":1510},"delta":{"height_m":{"min":0.4999996779999947,"max":0.5000006759999991,"mean":0.5000001897311259,"population_std":2.795669059133261e-07},"lat_deg":{"min":1.1887629000284505e-05,"max":1.1887729002069136e-05,"mean":1.1887678766829474e-05,"population_std":2.829982639551307e-11},"lon_deg":{"min":-8.342490005475156e-06,"max":-8.342321990539858e-06,"mean":-8.342410294165344e-06,"population_std":3.8632798591022777e-11},"position_delta_n_m":{"min":1.3199437567853733,"max":1.3199548477366383,"mean":1.3199493528095916,"population_std":3.141739417937451e-06},"position_delta_e_m":{"min":-0.7125587118516089,"max":-0.7125501754700763,"mean":-0.7125544849135131,"population_std":2.426573861600345e-06},"position_delta_u_m":{"min":0.49999950005777005,"max":0.5000004995763281,"mean":0.5000000130352125,"population_std":2.795830255302845e-07},"position_delta_h_m":{"min":1.4999933450010714,"max":1.500006636045738,"mean":1.5000000626532162,"population_std":2.9880361139497446e-06},"position_delta_3d_m":{"min":1.5811324422505708,"max":1.5811451628165707,"mean":1.5811388936446409,"population_std":2.8411415729925242e-06}}} |
| D17_seed_00 | gnss_position | 303 | [55.206795,357.201323] | {"changed_fields":{"height_m":303,"lat_deg":303,"lon_deg":303},"delta":{"height_m":{"min":1.0000009999999975,"max":1.0000010000000046,"mean":1.0000010000000001,"population_std":3.466288890431753e-15},"lat_deg":{"min":2.3775399995429325e-05,"max":2.3775400002534752e-05,"mean":2.3775399999837972e-05,"population_std":3.448064808800077e-15},"lon_deg":{"min":-1.6684900003838266e-05,"max":-1.668469998605815e-05,"mean":-1.668482541242198e-05,"population_std":7.433562290185361e-11},"position_delta_n_m":{"min":2.639903515206681,"max":2.6399038814669913,"mean":2.639903697738602,"population_std":1.0177255035799468e-07},"position_delta_e_m":{"min":-1.4251131559079335,"max":-1.4251046503756024,"mean":-1.4251092351111025,"population_std":2.6324675678657617e-06},"position_delta_u_m":{"min":1.0000002908988117,"max":1.0000002954798723,"mean":1.000000293286775,"population_std":8.981501950940606e-10},"position_delta_h_m":{"min":3.00000230884827,"max":3.000006555624768,"mean":3.0000046442194295,"population_std":1.2988106039584997e-06},"position_delta_3d_m":{"min":3.162279943290745,"max":3.1622839726094654,"mean":3.162282158807457,"population_std":1.2322096374367433e-06}}} | 1510 | [55.8,357.6] | {"changed_fields":{"height_m":1510,"lat_deg":1510,"lon_deg":1510},"delta":{"height_m":{"min":1.000000207999996,"max":1.0000012080000005,"mean":1.0000007016516557,"population_std":2.962784273816149e-07},"lat_deg":{"min":2.3775302999240466e-05,"max":2.3775405004755612e-05,"mean":2.3775354594727142e-05,"population_std":2.901978648723507e-11},"lon_deg":{"min":-1.6684933001442914e-05,"max":-1.6684696987567804e-05,"mean":-1.668481989646911e-05,"population_std":5.966088803329277e-11},"position_delta_n_m":{"min":2.639893057284522,"max":2.639904155019433,"mean":2.6398986561796436,"population_std":3.217594059420686e-06},"position_delta_e_m":{"min":-1.425113157084042,"max":-1.4251046248617003,"mean":-1.425108775265479,"population_std":2.494938159570725e-06},"position_delta_u_m":{"min":0.999999500748067,"max":1.0000005005519648,"mean":0.9999999948911915,"population_std":2.962506495871681e-07},"position_delta_h_m":{"min":2.999993276361522,"max":3.000006592158809,"mean":2.9999999893741416,"population_std":3.081020194686134e-06},"position_delta_3d_m":{"min":3.162271270720128,"max":3.1622838894000873,"mean":3.162277648472419,"population_std":2.925450537222606e-06}}} |
| D18_seed_00 | gnss_position | 303 | [55.206795,357.201323] | {"changed_fields":{"lat_deg":303,"lon_deg":303,"height_m":292},"delta":{"lat_deg":{"min":0.0,"max":2.3775400002534752e-05,"mean":1.2139291089073574e-05,"population_std":7.487323501647608e-06},"lon_deg":{"min":-1.6684900003838266e-05,"max":0.0,"mean":-8.518974917616098e-06,"population_std":5.254362225113993e-06},"position_delta_n_m":{"min":0.0,"max":2.639903757791586,"mean":1.3478871815826847,"population_std":0.8313556174807984},"position_delta_e_m":{"min":-1.4251131559079335,"max":-0.0,"mean":-0.7276364246110549,"population_std":0.4487945336921379},"position_delta_u_m":{"min":0.0,"max":1.0000002948459272,"mean":0.5105828546716612,"population_std":0.3149194402597338},"position_delta_h_m":{"min":0.0,"max":3.000006555624768,"mean":1.53174887652375,"population_std":0.9447585385444933},"position_delta_3d_m":{"min":0.0,"max":3.1622839726094654,"mean":1.6146050514658759,"population_std":0.9958629172750336},"height_m":{"min":0.0007949999999965485,"max":1.0000010000000046,"mean":0.5298174041095892,"population_std":0.30449918502661216}}} | 1510 | [55.8,357.6] | {"changed_fields":{"height_m":1510,"lat_deg":1510,"lon_deg":1510},"delta":{"height_m":{"min":-4.560000022024724e-07,"max":1.0000011970000031,"mean":0.5122519082741722,"population_std":0.31406367490011605},"lat_deg":{"min":-4.899902705801651e-11,"max":2.3775398993564067e-05,"mean":1.2178966515277814e-05,"population_std":7.4669705088803256e-06},"lon_deg":{"min":-1.6684906000818955e-05,"max":4.800426722795237e-11,"mean":-8.546815260953453e-06,"population_std":5.2400788650904605e-06},"position_delta_n_m":{"min":-5.440655254597655e-06,"max":2.639903637682737,"mean":1.3522925460094017,"population_std":0.8290957220840908},"position_delta_e_m":{"min":-1.4251130829327132,"max":4.098679410234667e-06,"mean":-0.7300143665991875,"population_std":0.44757453473092534},"position_delta_u_m":{"min":-4.559906748671215e-07,"max":1.0000004906213582,"mean":0.5122516531092323,"population_std":0.3140634487217682},"position_delta_h_m":{"min":5.124872898597425e-07,"max":3.000005370393172,"mean":1.5367551655789549,"population_std":0.9421901862245999},"position_delta_3d_m":{"min":5.3027883202119e-07,"max":3.162282708309221,"mean":1.6198821616373447,"population_std":0.9931556646854623}}} |
| D19_seed_00 | gnss_position | 303 | [55.206795,357.201323] | {"changed_fields":{"height_m":303,"lat_deg":303,"lon_deg":303},"delta":{"height_m":{"min":-0.4999830000000003,"max":0.5,"mean":-0.014383009900989938,"population_std":0.3635416258587495},"lat_deg":{"min":-1.801220000174908e-05,"max":1.801100000164979e-05,"mean":-3.3255551156680713e-06,"population_std":1.1899529954861093e-05},"lon_deg":{"min":-2.3414800011778425e-05,"max":2.3415600011844617e-05,"mean":-6.736105606509822e-07,"population_std":1.7025022705105652e-05},"position_delta_n_m":{"min":-1.999985962860058,"max":1.999852565375405,"mean":-0.36925310264758787,"population_std":1.321265120503447},"position_delta_e_m":{"min":-1.9999334957837736,"max":2.0000040491108733,"mean":-0.057533594734853845,"population_std":1.4541665205698018},"position_delta_u_m":{"min":-0.499983312158096,"max":0.4999996871709024,"mean":-0.014383323549804528,"population_std":0.363541625764784},"position_delta_h_m":{"min":1.9999944422041664,"max":2.0000061850940245,"mean":1.9999999391340024,"population_std":2.6539965641432732e-06},"position_delta_3d_m":{"min":2.000001554309303,"max":2.0615566996698664,"mean":2.0327027480185995,"population_std":0.02210629776174574}}} | 1510 | [55.8,357.6] | {"changed_fields":{"height_m":1510,"lat_deg":1510,"lon_deg":1510},"delta":{"height_m":{"min":-0.49999894899999475,"max":0.4999999659999972,"mean":-0.016043632785430435,"population_std":0.36296864425894043},"lat_deg":{"min":-1.8012315003090862e-05,"max":1.8012308999004745e-05,"mean":-3.346336464879161e-06,"population_std":1.1913641569506562e-05},"lon_deg":{"min":-2.3415524992742576e-05,"max":2.341555800455808e-05,"mean":-7.513764530711564e-07,"population_std":1.6998188490636188e-05},"position_delta_n_m":{"min":-1.9999984887538496,"max":1.9999979008571787,"mean":-0.37156056172048735,"population_std":1.322832004745087},"position_delta_e_m":{"min":-1.9999986907160825,"max":2.000000464049832,"mean":-0.06417582854136103,"population_std":1.4518745431113154},"position_delta_u_m":{"min":-0.4999992634670737,"max":0.4999996535070652,"mean":-0.01604394652391831,"population_std":0.3629686442544207},"position_delta_h_m":{"min":1.9999933795644105,"max":2.000006524834731,"mean":1.9999999974249718,"population_std":2.7791227843271566e-06},"position_delta_3d_m":{"min":1.9999988244143527,"max":2.0615549816363354,"mean":2.0326130468797112,"population_std":0.022087016411036504}}} |
| D20_seed_00 | gnss_position | 6 | [74.200463,355.203544] | {"changed_fields":{"height_m":6,"lat_deg":6,"lon_deg":6},"delta":{"height_m":{"min":-1.0,"max":1.0,"mean":-0.3333333333333333,"population_std":0.9428090415820634},"lat_deg":{"min":-7.176699995170566e-06,"max":1.585020000050008e-05,"mean":6.804000000452485e-06,"population_std":8.36380700755026e-06},"lon_deg":{"min":-1.1123299998416769e-05,"max":2.3360800000205018e-05,"mean":1.4532399999230469e-05,"population_std":1.1859361521977425e-05},"position_delta_n_m":{"min":-0.7968650531630945,"max":1.7599284116936054,"mean":0.7554827324799462,"population_std":0.9286757895339708},"position_delta_e_m":{"min":-0.9500766627187593,"max":1.9953373327564048,"mean":1.2412643279407811,"population_std":1.0129489463160726},"position_delta_u_m":{"min":-1.000000312945907,"max":0.9999996876212409,"mean":-0.33333364610618127,"population_std":0.9428090413526803},"position_delta_h_m":{"min":1.9999960618955537,"max":2.0000035587080376,"mean":1.99999889519897,"population_std":2.435220800221802e-06},"position_delta_3d_m":{"min":2.2360645949560967,"max":2.2360713004330313,"mean":2.236067035864723,"population_std":2.2323687266673157e-06}}} | 30 | [71.8,352.8] | {"changed_fields":{"height_m":30,"lat_deg":30,"lon_deg":30},"delta":{"height_m":{"min":-1.000000104999998,"max":1.0000007370000006,"mean":0.06666695850000035,"population_std":0.9977753208235355},"lat_deg":{"min":-1.772672800370856e-05,"max":1.6166224000357943e-05,"mean":4.817200663846203e-07,"population_std":1.1285062159013787e-05},"lon_deg":{"min":-2.341533000560503e-05,"max":2.341543898864984e-05,"mean":2.1493248326009963e-06,"population_std":1.8112357800467736e-05},"position_delta_n_m":{"min":-1.9682887218677503,"max":1.795018015166902,"mean":0.0534879842131247,"population_std":1.2530376589869143},"position_delta_e_m":{"min":-1.999989520944508,"max":1.9999897444625032,"mean":0.18357893974293013,"population_std":1.5470405771810423},"position_delta_u_m":{"min":-1.0000004181764899,"max":1.0000004242718492,"mean":0.06666664518110768,"population_std":0.997775320695382},"position_delta_h_m":{"min":1.9999943945446457,"max":2.00000387861329,"mean":2.0000000284625856,"population_std":2.457129292186378e-06},"position_delta_3d_m":{"min":2.236062965299256,"max":2.2360715843995598,"mean":2.236068010150843,"population_std":2.2145775192980758e-06}}} |
| D21_seed_00 | gnss_position | 15 | [73.200665,346.21325] | {"changed_fields":{"height_m":15,"lat_deg":15,"lon_deg":15},"delta":{"height_m":{"min":-1.9999990000000025,"max":2.0000010000000046,"mean":0.40000099999999844,"population_std":1.959591794226542},"lat_deg":{"min":-2.772779999560271e-05,"max":3.170050000278479e-05,"mean":6.744720000521435e-06,"population_std":1.9958633507209623e-05},"lon_deg":{"min":-4.6830499996985964e-05,"max":4.672200000754856e-05,"mean":1.416166666861803e-05,"population_std":3.52496134765817e-05},"position_delta_n_m":{"min":-3.078758556728583,"max":3.5198686060048576,"mean":0.7489009284474524,"population_std":2.2161082794385867},"position_delta_e_m":{"min":-3.9999764374707443,"max":3.990677747586175,"mean":1.2095945524213891,"population_std":3.0107964924651385},"position_delta_u_m":{"min":-2.000000255640921,"max":1.9999997486239047,"mean":0.399999746148919,"population_std":1.9595917946158405},"position_delta_h_m":{"min":3.99999571043008,"max":4.000003174997317,"mean":4.000000375888509,"population_std":2.318995559665726e-06},"position_delta_3d_m":{"min":4.4721320057342595,"max":4.472138825906746,"mean":4.472136268670059,"population_std":2.087922134940402e-06}}} | 76 | [56,351] | {"changed_fields":{"height_m":76,"lat_deg":76,"lon_deg":76},"delta":{"height_m":{"min":-1.999999228,"max":2.0000017449999987,"mean":0.36842231352631605,"population_std":1.9657736522945572},"lat_deg":{"min":-3.601530499963701e-05,"max":3.600883299981206e-05,"mean":2.4643792495326305e-06,"population_std":2.294796813357232e-05},"lon_deg":{"min":-4.683088300794225e-05,"max":4.6830921007767756e-05,"mean":4.374703185343258e-06,"population_std":3.569049782258189e-05},"position_delta_n_m":{"min":-3.9989629175985746,"max":3.998244377920371,"mean":0.27363312598990824,"population_std":2.548029252895935},"position_delta_e_m":{"min":-3.9999771059682265,"max":3.999985245755245,"mean":0.37365862346524154,"population_std":3.048450557679677},"position_delta_u_m":{"min":-2.000000485048502,"max":2.0000004900304793,"mean":0.3684210589263521,"population_std":1.965773652266675},"position_delta_h_m":{"min":3.999994384791877,"max":4.000005114405762,"mean":3.999999966344025,"population_std":2.774189767944222e-06},"position_delta_3d_m":{"min":4.472130947055242,"max":4.472140529685338,"mean":4.472135939275564,"population_std":2.4590642501126092e-06}}} |
| D22_seed_00 | gnss_position | 4 | [348.205852,351.209991] | {"changed_fields":{"height_m":4,"lat_deg":4,"lon_deg":4},"delta":{"height_m":{"min":4.0000049999999945,"max":4.000005000000002,"mean":4.000004999999998,"population_std":3.552713678800501e-15},"lat_deg":{"min":6.340089999667953e-05,"max":6.340090000378495e-05,"mean":6.340089999845588e-05,"population_std":3.076740298213702e-15},"lon_deg":{"min":-4.449300000430867e-05,"max":-4.4492999990097815e-05,"mean":-4.4493000000755956e-05,"population_std":6.153480596427404e-15},"position_delta_n_m":{"min":7.039728757214119,"max":7.039728777436597,"mean":7.039728766004321,"population_std":7.465189509507199e-09},"position_delta_e_m":{"min":-3.800293452647045,"max":-3.8002930550844516,"mean":-3.800293158135581,"population_std":1.7008118077845355e-07},"position_delta_u_m":{"min":3.9999999743767773,"max":3.999999975770825,"mean":3.999999975013786,"population_std":5.537575635451136e-10},"position_delta_h_m":{"min":8.000000517479393,"max":8.000000715015329,"mean":8.000000574167531,"population_std":8.175072417876201e-08},"position_delta_3d_m":{"min":8.944272361800868,"max":8.944272538172223,"mean":8.94427241237604,"population_std":7.299696009772099e-08}}} | 20 | [348.4,352.2] | {"changed_fields":{"height_m":20,"lat_deg":20,"lon_deg":20},"delta":{"height_m":{"min":4.000004564999998,"max":4.000005487000003,"mean":4.000005010400001,"population_std":2.603267960295382e-07},"lat_deg":{"min":6.340087299605557e-05,"max":6.340094800094676e-05,"mean":6.340090239937979e-05,"population_std":2.1829535023101155e-11},"lon_deg":{"min":-4.449301600573108e-05,"max":-4.449291999719662e-05,"mean":-4.449296754955867e-05,"population_std":3.0977866205770504e-11},"position_delta_n_m":{"min":7.039725782436786,"max":7.039734102618957,"mean":7.039729037648956,"population_std":2.4224125267721775e-06},"position_delta_e_m":{"min":-3.8002944610701985,"max":-3.8002861860995756,"mean":-3.800290320998493,"population_std":2.665508543679051e-06},"position_delta_u_m":{"min":3.9999995407341764,"max":4.000000461732709,"mean":3.999999984944938,"population_std":2.6006749536440087e-07},"position_delta_h_m":{"min":7.999995068583689,"max":8.000005889148905,"mean":7.999999465462426,"population_std":2.572436456731457e-06},"position_delta_3d_m":{"min":8.944267394511243,"max":8.944277077704326,"mean":8.944271425161471,"population_std":2.2992546746903054e-06}}} |
| D23_seed_00 | gnss_position | 303 | [55.206795,357.201323] | {"changed_fields":{"std_d_m":303,"std_e_m":303,"std_n_m":303},"delta":{"std_d_m":{"min":0.004999999999999999,"max":0.018500000000000003,"mean":0.006534653465346534,"population_std":0.0018667545994852169},"std_e_m":{"min":0.007000000000000001,"max":0.009000000000000001,"mean":0.007107260726072608,"population_std":0.0003054187538286273},"std_n_m":{"min":0.007000000000000001,"max":0.009000000000000001,"mean":0.007107260726072608,"population_std":0.0003054187538286273},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} | 1510 | [55.8,357.6] | {"changed_fields":{"std_d_m":1510,"std_e_m":1510,"std_n_m":1510},"delta":{"std_d_m":{"min":0.004999999999999999,"max":0.018500000000000003,"mean":0.006616556291390728,"population_std":0.0019149959093752642},"std_e_m":{"min":0.007000000000000001,"max":0.009999999999999998,"mean":0.007122516556291391,"population_std":0.0003465386431306651},"std_n_m":{"min":0.007000000000000001,"max":0.009999999999999998,"mean":0.007122516556291391,"population_std":0.0003465386431306651},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} |
| D24_seed_00 | gnss_position | 303 | [55.206795,357.201323] | {"changed_fields":{"std_d_m":303,"std_e_m":303,"std_n_m":303},"delta":{"std_d_m":{"min":0.015000000000000001,"max":0.0555,"mean":0.019603960396039604,"population_std":0.005600263798455651},"std_e_m":{"min":0.021000000000000005,"max":0.027,"mean":0.021321782178217827,"population_std":0.0009162562614858816},"std_n_m":{"min":0.021000000000000005,"max":0.027,"mean":0.021321782178217827,"population_std":0.0009162562614858816},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} | 1510 | [55.8,357.6] | {"changed_fields":{"std_d_m":1510,"std_e_m":1510,"std_n_m":1510},"delta":{"std_d_m":{"min":0.015000000000000001,"max":0.0555,"mean":0.019849668874172187,"population_std":0.005744987728125792},"std_e_m":{"min":0.021000000000000005,"max":0.030000000000000002,"mean":0.021367549668874178,"population_std":0.0010396159293919957},"std_n_m":{"min":0.021000000000000005,"max":0.030000000000000002,"mean":0.021367549668874178,"population_std":0.0010396159293919957},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} |
| D25_seed_00 | gnss_position | 303 | [55.206795,357.201323] | {"changed_fields":{"std_d_m":303,"std_e_m":303,"std_n_m":303},"delta":{"std_d_m":{"min":0.03,"max":0.11099999999999999,"mean":0.03920792079207921,"population_std":0.011200527596911302},"std_e_m":{"min":0.042,"max":0.05399999999999999,"mean":0.04264356435643563,"population_std":0.0018325125229717652},"std_n_m":{"min":0.042,"max":0.05399999999999999,"mean":0.04264356435643563,"population_std":0.0018325125229717652},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} | 1510 | [55.8,357.6] | {"changed_fields":{"std_d_m":1510,"std_e_m":1510,"std_n_m":1510},"delta":{"std_d_m":{"min":0.03,"max":0.11099999999999999,"mean":0.03969933774834437,"population_std":0.011489975456251585},"std_e_m":{"min":0.042,"max":0.06,"mean":0.042735099337748335,"population_std":0.002079231858783993},"std_n_m":{"min":0.042,"max":0.06,"mean":0.042735099337748335,"population_std":0.002079231858783993},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} |
| D26_seed_00 | gnss_position | 303 | [55.206795,357.201323] | {"changed_fields":{"std_d_m":303,"std_e_m":303,"std_n_m":303},"delta":{"std_d_m":{"min":-0.027749999999999997,"max":-0.0075,"mean":-0.009801980198019802,"population_std":0.0028001318992278254},"std_e_m":{"min":-0.013499999999999998,"max":-0.0105,"mean":-0.010660891089108908,"population_std":0.0004581281307429413},"std_n_m":{"min":-0.013499999999999998,"max":-0.0105,"mean":-0.010660891089108908,"population_std":0.0004581281307429413},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} | 1510 | [55.8,357.6] | {"changed_fields":{"std_d_m":1510,"std_e_m":1510,"std_n_m":1510},"delta":{"std_d_m":{"min":-0.027749999999999997,"max":-0.0075,"mean":-0.009924834437086092,"population_std":0.002872493864062896},"std_e_m":{"min":-0.015,"max":-0.0105,"mean":-0.010683774834437084,"population_std":0.0005198079646959983},"std_n_m":{"min":-0.015,"max":-0.0105,"mean":-0.010683774834437084,"population_std":0.0005198079646959983},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} |
| D27_seed_00 | gnss_position | 303 | [55.206795,357.201323] | {"changed_fields":{"height_m":303,"lat_deg":303,"lon_deg":303,"std_d_m":303,"std_e_m":303,"std_n_m":303},"delta":{"height_m":{"min":-14.808676000000002,"max":13.649871000000005,"mean":-0.3017661221122109,"population_std":5.120924108533565},"lat_deg":{"min":-6.028909999855614e-05,"max":7.658659999520978e-05,"mean":3.8125191418930177e-06,"population_std":2.5279191712415646e-05},"lon_deg":{"min":-9.956670000121903e-05,"max":0.00010855019999667093,"mean":1.2832722775223817e-06,"population_std":3.549478724034095e-05},"std_d_m":{"min":-0.027749999999999997,"max":-0.0075,"mean":-0.009801980198019802,"population_std":0.0028001318992278254},"std_e_m":{"min":-0.013499999999999998,"max":-0.0105,"mean":-0.010660891089108908,"population_std":0.0004581281307429413},"std_n_m":{"min":-0.013499999999999998,"max":-0.0105,"mean":-0.010660891089108908,"population_std":0.0004581281307429413},"position_delta_n_m":{"min":-6.694203891054993,"max":8.503801135322817,"mean":0.423323745561575,"population_std":2.8068767836041055},"position_delta_e_m":{"min":-8.504327914935493,"max":9.271612537010407,"mean":0.10960883373621255,"population_std":3.0317332940159223},"position_delta_u_m":{"min":-14.808682945685954,"max":13.649869808760393,"mean":-0.30176747582631014,"population_std":5.120924221222505},"position_delta_h_m":{"min":0.153988298105034,"max":10.759832146787321,"mean":3.6805222078067144,"population_std":1.9274172906278615},"position_delta_3d_m":{"min":0.954155478506953,"max":17.54985299368945,"mean":6.029683225175052,"population_std":2.686825232013078}}} | 1510 | [55.8,357.6] | {"changed_fields":{"height_m":1510,"lat_deg":1510,"lon_deg":1510,"std_d_m":1510,"std_e_m":1510,"std_n_m":1510},"delta":{"height_m":{"min":-19.290170620999998,"max":17.900478550000003,"mean":0.08791365794304644,"population_std":4.964758063824832},"lat_deg":{"min":-0.00011715044699656119,"max":9.430410400312894e-05,"mean":7.448638662028379e-07,"population_std":2.7048266414867983e-05},"lon_deg":{"min":-0.00012447166498930073,"max":0.00010779323800136353,"mean":5.202446728848499e-07,"population_std":3.454703386978738e-05},"std_d_m":{"min":-0.027749999999999997,"max":-0.0075,"mean":-0.009924834437086092,"population_std":0.002872493864062896},"std_e_m":{"min":-0.015,"max":-0.0105,"mean":-0.010683774834437084,"population_std":0.0005198079646959983},"std_n_m":{"min":-0.015,"max":-0.0105,"mean":-0.010683774834437084,"population_std":0.0005198079646959983},"position_delta_n_m":{"min":-13.007820153550387,"max":10.471051860347785,"mean":0.08270668229494947,"population_std":3.0033061739325584},"position_delta_e_m":{"min":-10.631589944910854,"max":9.207007634017486,"mean":0.04443585374199328,"population_std":2.950783877141311},"position_delta_u_m":{"min":-19.290172880222936,"max":17.90047698936098,"mean":0.08791226674337246,"population_std":4.964758055639466},"position_delta_h_m":{"min":0.048313636705799766,"max":13.294010308296153,"mean":3.7416008135077004,"population_std":1.93292828545993},"position_delta_3d_m":{"min":0.19255481632992208,"max":20.02240502868436,"mean":5.905308309757771,"population_std":2.7422022698479593}}} |
| D28_seed_00 | gnss_position | 303 | [55.206795,357.201323] | {"changed_fields":{"std_d_m":303,"std_e_m":303,"std_n_m":303},"delta":{"std_d_m":{"min":0.03,"max":0.11099999999999999,"mean":0.03920792079207921,"population_std":0.011200527596911302},"std_e_m":{"min":0.042,"max":0.05399999999999999,"mean":0.04264356435643563,"population_std":0.0018325125229717652},"std_n_m":{"min":0.042,"max":0.05399999999999999,"mean":0.04264356435643563,"population_std":0.0018325125229717652},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} | 1510 | [55.8,357.6] | {"changed_fields":{"std_d_m":1510,"std_e_m":1510,"std_n_m":1510},"delta":{"std_d_m":{"min":0.03,"max":0.11099999999999999,"mean":0.03969933774834437,"population_std":0.011489975456251585},"std_e_m":{"min":0.042,"max":0.06,"mean":0.042735099337748335,"population_std":0.002079231858783993},"std_n_m":{"min":0.042,"max":0.06,"mean":0.042735099337748335,"population_std":0.002079231858783993},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} |
| D29_seed_00 | source_quality_metadata | 303 | [28855.2068,29157.2013] | {"changed_fields":{"audit_gnss_quality":303},"delta":{}} | 303 | [28855.2068,29157.2013] | {"changed_fields":{"audit_gnss_quality":303},"delta":{}} |
| D30_seed_00 | dual_yaw | 5 | [204.20564,208.204936] | {"changed_fields":{"source_status":5,"valid":5},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0}}} | 5 | [204,208] | {"changed_fields":{"source_status":5,"valid":5},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0}}} |
| D31_seed_00 | dual_yaw | 20 | [196.210194,215.205113] | {"changed_fields":{"source_status":20,"valid":20},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0}}} | 20 | [197,216] | {"changed_fields":{"source_status":20,"valid":20},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0}}} |
| D32_seed_00 | dual_yaw | 303 | [55.206795,357.201323] | {"changed_fields":{"yaw_deg":303},"delta":{"yaw_deg":{"min":-2.798550703999979,"max":2.542039238000001,"mean":0.03659263799009895,"population_std":1.0121035607953266}}} | 301 | [56,356] | {"changed_fields":{"yaw_deg":301},"delta":{"yaw_deg":{"min":-2.798550703999979,"max":2.542039238000001,"mean":0.03794069320265791,"population_std":1.0123196439275566}}} |
| D33_seed_00 | dual_yaw | 303 | [55.206795,357.201323] | {"changed_fields":{"yaw_deg":303},"delta":{"yaw_deg":{"min":-13.992753520999997,"max":12.710196187999998,"mean":0.18296318994719435,"population_std":5.060517804122706}}} | 301 | [56,356] | {"changed_fields":{"yaw_deg":301},"delta":{"yaw_deg":{"min":-13.992753520999997,"max":12.710196187999998,"mean":0.18970346600332175,"population_std":5.0615982197861396}}} |
| D34_seed_00 | dual_yaw | 15 | [73.200665,346.21325] | {"changed_fields":{"yaw_deg":15},"delta":{"yaw_deg":{"min":-10.0,"max":10.0,"mean":-2.0,"population_std":9.797958971132712}}} | 15 | [74,345] | {"changed_fields":{"yaw_deg":15},"delta":{"yaw_deg":{"min":-10.0,"max":10.0,"mean":-2.0,"population_std":9.797958971132712}}} |
| D35_seed_00 | dual_yaw | 30 | [70.199625,345.205017] | {"changed_fields":{"yaw_deg":30},"delta":{"yaw_deg":{"min":-10.0,"max":10.0,"mean":-1.3333333333333333,"population_std":9.910712498212337}}} | 30 | [71,344] | {"changed_fields":{"yaw_deg":30},"delta":{"yaw_deg":{"min":-10.0,"max":10.0,"mean":-1.3333333333333333,"population_std":9.910712498212337}}} |
| D36_seed_00 | dual_yaw | 303 | [55.206795,357.201323] | {"changed_fields":{"yaw_std_deg":303},"delta":{"yaw_std_deg":{"min":0.75,"max":0.75,"mean":0.75,"population_std":0.0}}} | 301 | [56,356] | {"changed_fields":{"yaw_std_deg":301},"delta":{"yaw_std_deg":{"min":0.75,"max":0.75,"mean":0.75,"population_std":0.0}}} |
| D37_seed_00 | dual_yaw | 303 | [55.206795,357.201323] | {"changed_fields":{"yaw_std_deg":303},"delta":{"yaw_std_deg":{"min":3.0,"max":3.0,"mean":3.0,"population_std":0.0}}} | 301 | [56,356] | {"changed_fields":{"yaw_std_deg":301},"delta":{"yaw_std_deg":{"min":3.0,"max":3.0,"mean":3.0,"population_std":0.0}}} |
| D38_seed_00 | dual_yaw | 303 | [55.206795,357.201323] | {"changed_fields":{"yaw_deg":303,"yaw_std_deg":303},"delta":{"yaw_deg":{"min":-27.985507041999995,"max":25.420392375999995,"mean":0.36592637995049465,"population_std":10.121035608191836},"yaw_std_deg":{"min":-1.125,"max":-1.125,"mean":-1.125,"population_std":0.0}}} | 301 | [56,356] | {"changed_fields":{"yaw_deg":301,"yaw_std_deg":301},"delta":{"yaw_deg":{"min":-27.985507041999995,"max":25.420392375999995,"mean":0.3794069320631222,"population_std":10.123196439518278},"yaw_std_deg":{"min":-1.125,"max":-1.125,"mean":-1.125,"population_std":0.0}}} |
| D39_seed_00 | dual_yaw | 7 | [82.204517,351.209991] | {"changed_fields":{"source_status":7,"valid":7},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0}}} | 7 | [83,352] | {"changed_fields":{"source_status":7,"valid":7},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0}}} |
| D40_seed_00 | dual_yaw | 303 | [55.206795,357.201323] | {"changed_fields":{"baseline_length_m":303},"delta":{"baseline_length_m":{"min":-0.08395652117442148,"max":0.07626117718617564,"mean":0.0010977791526696624,"population_std":0.030363106811572494}}} | 301 | [56,356] | {"changed_fields":{"baseline_length_m":301},"delta":{"baseline_length_m":{"min":-0.0839565208195695,"max":0.07626117757859674,"mean":0.0011382207847013752,"population_std":0.030369589292149477}}} |
| D41_seed_00 | dual_yaw | 303 | [55.206795,357.201323] | {"changed_fields":{"baseline_d_m":303,"baseline_e_m":303,"baseline_length_m":303,"baseline_n_m":303,"yaw_deg":303},"delta":{"baseline_d_m":{"min":-5.923473167465625,"max":6.181077621655096,"mean":0.24810253979925279,"population_std":1.9823057035782436},"baseline_e_m":{"min":-7.373291002643989,"max":8.18992184027473,"mean":0.1740338947187902,"population_std":3.060242720794076},"baseline_length_m":{"min":0.18852744699740193,"max":10.51751204119006,"mean":3.879398385070161,"population_std":1.9451587275558606},"baseline_n_m":{"min":-8.504324127750369,"max":6.644665773459491,"mean":-0.19431559260629214,"population_std":2.8846954031679646},"yaw_deg":{"min":-177.147137562,"max":179.818880766,"mean":-6.060860611069309,"population_std":102.3279896493059}}} | 301 | [56,356] | {"changed_fields":{"baseline_d_m":301,"baseline_e_m":301,"baseline_length_m":301,"baseline_n_m":301,"yaw_deg":301},"delta":{"baseline_d_m":{"min":-5.923473167056862,"max":6.181077621080358,"mean":0.253576322325115,"population_std":1.984730582670399},"baseline_e_m":{"min":-7.373291002881977,"max":8.189921840355094,"mean":0.17869360422053615,"population_std":3.0480002700746183},"baseline_length_m":{"min":0.18148958065504311,"max":10.516208927168838,"mean":3.874547129206628,"population_std":1.9481498160830102},"baseline_n_m":{"min":-8.504324127716838,"max":6.6446657731452206,"mean":-0.18804569328762935,"population_std":2.892165195503883},"yaw_deg":{"min":-177.139359409,"max":178.22809564,"mean":-16.146730388757476,"population_std":100.96913177226077}}} |
| D42_seed_00 | receiver_velocity | 20 | [196.210194,215.205113] | {"changed_fields":{"status":20,"valid":20},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"velocity_delta_norm_mps":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} | 100 | [196.2,216] | {"changed_fields":{"status":100,"valid":100},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"velocity_delta_norm_mps":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} |
| D43_seed_00 | receiver_velocity | 303 | [55.206795,357.201323] | {"changed_fields":{"vd":303,"ve":303,"vn":303},"delta":{"vd":{"min":-1.280553121,"max":1.363274525,"mean":-0.05435874534983498,"population_std":0.49742625477156927},"ve":{"min":-1.8912836080000002,"max":1.6071043,"mean":0.006435819613861396,"population_std":0.4737668942295528},"vn":{"min":-1.413602637,"max":1.349647056,"mean":-0.03232788230363037,"population_std":0.5269407856145142},"velocity_delta_norm_mps":{"min":0.12254337717908081,"max":2.003770870745069,"mean":0.7992284917794904,"population_std":0.3388653765439261}}} | 1510 | [55.8,357.6] | {"changed_fields":{"vd":1510,"ve":1510,"vn":1510},"delta":{"vd":{"min":-1.883004352,"max":1.730894529,"mean":-0.02471268247086093,"population_std":0.5126999541882948},"ve":{"min":-1.8912836080000002,"max":1.6071043,"mean":-0.002914148262251653,"population_std":0.49387495281882376},"vn":{"min":-1.70836885,"max":1.7216026809999998,"mean":0.005466534907947016,"population_std":0.5007515610867862},"velocity_delta_norm_mps":{"min":0.07387175429834392,"max":2.14385799733481,"mean":0.80082931477727,"population_std":0.34182939971511583}}} |
| D44_seed_00 | receiver_velocity | 6 | [74.200463,355.203544] | {"changed_fields":{"vd":6,"ve":6,"vn":6},"delta":{"vd":{"min":-1.9891437189999999,"max":0.390589816,"mean":-0.5763921616666666,"population_std":0.842899167076314},"ve":{"min":-1.9522701800000002,"max":1.7139927560000001,"mean":-0.310008871,"population_std":1.298567044658761},"vn":{"min":-1.967953,"max":0.953765395,"mean":-0.3454869868333333,"population_std":1.0273996025597263},"velocity_delta_norm_mps":{"min":1.9999999996936955,"max":2.0000000004231766,"mean":2.0000000002180642,"population_std":2.5299710972504067e-10}}} | 30 | [71.8,352.8] | {"changed_fields":{"vd":30,"ve":30,"vn":30},"delta":{"vd":{"min":-1.989143719,"max":1.9297541809999998,"mean":-0.10916226549999997,"population_std":1.0586667398660607},"ve":{"min":-1.971154197,"max":1.962490432,"mean":-0.31241775369999997,"population_std":1.3619614136033937},"vn":{"min":-1.967953,"max":1.891512814,"mean":-0.15962933093333334,"population_std":0.9430180624568071},"velocity_delta_norm_mps":{"min":1.9999999996297624,"max":2.000000000654448,"mean":2.000000000173312,"population_std":2.5667913000516434e-10}}} |
| D45_seed_00 | receiver_velocity | 303 | [55.206795,357.201323] | {"changed_fields":{"std_vd":303,"std_ve":303,"std_vn":303,"vd":303,"ve":303,"vn":303},"delta":{"std_vd":{"min":-0.037500000000000006,"max":-0.037500000000000006,"mean":-0.037500000000000006,"population_std":0.0},"std_ve":{"min":-0.037500000000000006,"max":-0.037500000000000006,"mean":-0.037500000000000006,"population_std":0.0},"std_vn":{"min":-0.037500000000000006,"max":-0.037500000000000006,"mean":-0.037500000000000006,"population_std":0.0},"vd":{"min":-1.280553121,"max":1.363274525,"mean":-0.05435874534983498,"population_std":0.49742625477156927},"ve":{"min":-1.8912836080000002,"max":1.6071043,"mean":0.006435819613861396,"population_std":0.4737668942295528},"vn":{"min":-1.413602637,"max":1.349647056,"mean":-0.03232788230363037,"population_std":0.5269407856145142},"velocity_delta_norm_mps":{"min":0.12254337717908081,"max":2.003770870745069,"mean":0.7992284917794904,"population_std":0.3388653765439261}}} | 1510 | [55.8,357.6] | {"changed_fields":{"std_vd":1510,"std_ve":1510,"std_vn":1510,"vd":1510,"ve":1510,"vn":1510},"delta":{"std_vd":{"min":-0.037500000000000006,"max":-0.037500000000000006,"mean":-0.0375,"population_std":6.938893903907228e-18},"std_ve":{"min":-0.037500000000000006,"max":-0.037500000000000006,"mean":-0.0375,"population_std":6.938893903907228e-18},"std_vn":{"min":-0.037500000000000006,"max":-0.037500000000000006,"mean":-0.0375,"population_std":6.938893903907228e-18},"vd":{"min":-1.883004352,"max":1.730894529,"mean":-0.02471268247086093,"population_std":0.5126999541882948},"ve":{"min":-1.8912836080000002,"max":1.6071043,"mean":-0.002914148262251653,"population_std":0.49387495281882376},"vn":{"min":-1.70836885,"max":1.7216026809999998,"mean":0.005466534907947016,"population_std":0.5007515610867862},"velocity_delta_norm_mps":{"min":0.07387175429834392,"max":2.14385799733481,"mean":0.80082931477727,"population_std":0.34182939971511583}}} |
| D46_seed_00 | raw_doppler | 100 | [196.2,216] | {"changed_fields":{"provider_status":100,"valid":100},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"velocity_delta_norm_mps":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} | 100 | [196.2,216] | {"changed_fields":{"provider_status":100,"valid":100},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"velocity_delta_norm_mps":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} |
| D47_seed_00 | raw_doppler | 1248 | [56,357.6] | {"changed_fields":{"vd":1248,"ve":1248,"vn":1248},"delta":{"vd":{"min":-1.883004352,"max":1.730894529,"mean":-0.02781043098157051,"population_std":0.5079505715915309},"ve":{"min":-1.8912836080000002,"max":1.6071043,"mean":-0.014329362310096152,"population_std":0.489226908600989},"vn":{"min":-1.70836885,"max":1.7216026810000002,"mean":0.013225619698717944,"population_std":0.5042259580465857},"velocity_delta_norm_mps":{"min":0.07387175429834393,"max":2.14385799733481,"mean":0.7984277035392541,"population_std":0.33951058596232786}}} | 1248 | [56,357.6] | {"changed_fields":{"vd":1248,"ve":1248,"vn":1248},"delta":{"vd":{"min":-1.883004352,"max":1.730894529,"mean":-0.02781043098157051,"population_std":0.5079505715915309},"ve":{"min":-1.8912836080000002,"max":1.6071043,"mean":-0.014329362310096152,"population_std":0.489226908600989},"vn":{"min":-1.70836885,"max":1.7216026810000002,"mean":0.013225619698717944,"population_std":0.5042259580465857},"velocity_delta_norm_mps":{"min":0.07387175429834393,"max":2.14385799733481,"mean":0.7984277035392541,"population_std":0.33951058596232786}}} |
| D48_seed_00 | raw_doppler | 25 | [69.2,357.2] | {"changed_fields":{"ve":25,"vn":25},"delta":{"ve":{"min":-1.498356746,"max":1.4970237480000002,"mean":-0.22054721292,"population_std":1.26690630164216},"vn":{"min":-1.499784284,"max":1.2922640859999999,"mean":-0.16628462892,"population_std":0.7540933442774969},"velocity_delta_norm_mps":{"min":1.4999999995569908,"max":1.5000000005576262,"mean":1.4999999999886924,"population_std":3.054743480269498e-10}}} | 25 | [69.2,357.2] | {"changed_fields":{"ve":25,"vn":25},"delta":{"ve":{"min":-1.498356746,"max":1.4970237480000002,"mean":-0.22054721292,"population_std":1.26690630164216},"vn":{"min":-1.499784284,"max":1.2922640859999999,"mean":-0.16628462892,"population_std":0.7540933442774969},"velocity_delta_norm_mps":{"min":1.4999999995569908,"max":1.5000000005576262,"mean":1.4999999999886924,"population_std":3.054743480269498e-10}}} |
| D49_seed_00 | raw_doppler | 1248 | [56,357.6] | {"changed_fields":{"std_vd":1248,"std_ve":1248,"std_vn":1248,"vd":1248,"ve":1248,"vn":1248},"delta":{"std_vd":{"min":-0.98865225,"max":-0.17204175,"mean":-0.2510751712740385,"population_std":0.10689923405734551},"std_ve":{"min":-0.98865225,"max":-0.17204175,"mean":-0.2510751712740385,"population_std":0.10689923405734551},"std_vn":{"min":-0.98865225,"max":-0.17204175,"mean":-0.2510751712740385,"population_std":0.10689923405734551},"vd":{"min":-1.883004352,"max":1.730894529,"mean":-0.02781043098157051,"population_std":0.5079505715915309},"ve":{"min":-1.8912836080000002,"max":1.6071043,"mean":-0.014329362310096152,"population_std":0.489226908600989},"vn":{"min":-1.70836885,"max":1.7216026810000002,"mean":0.013225619698717944,"population_std":0.5042259580465857},"velocity_delta_norm_mps":{"min":0.07387175429834393,"max":2.14385799733481,"mean":0.7984277035392541,"population_std":0.33951058596232786}}} | 1248 | [56,357.6] | {"changed_fields":{"std_vd":1248,"std_ve":1248,"std_vn":1248,"vd":1248,"ve":1248,"vn":1248},"delta":{"std_vd":{"min":-0.98865225,"max":-0.17204175,"mean":-0.2510751712740385,"population_std":0.10689923405734551},"std_ve":{"min":-0.98865225,"max":-0.17204175,"mean":-0.2510751712740385,"population_std":0.10689923405734551},"std_vn":{"min":-0.98865225,"max":-0.17204175,"mean":-0.2510751712740385,"population_std":0.10689923405734551},"vd":{"min":-1.883004352,"max":1.730894529,"mean":-0.02781043098157051,"population_std":0.5079505715915309},"ve":{"min":-1.8912836080000002,"max":1.6071043,"mean":-0.014329362310096152,"population_std":0.489226908600989},"vn":{"min":-1.70836885,"max":1.7216026810000002,"mean":0.013225619698717944,"population_std":0.5042259580465857},"velocity_delta_norm_mps":{"min":0.07387175429834393,"max":2.14385799733481,"mean":0.7984277035392541,"population_std":0.33951058596232786}}} |
| D50_seed_00 | raw_doppler | 1248 | [56,357.6] | {"changed_fields":{"ve":1248,"vn":1248},"delta":{"ve":{"min":-0.4750362970000004,"max":-0.4750362969999997,"mean":-0.47503629699999994,"population_std":9.104343020629299e-17},"vn":{"min":0.8799662019999999,"max":0.8799662020000003,"mean":0.8799662020000002,"population_std":2.0710846592749373e-16},"velocity_delta_norm_mps":{"min":1.0000000000648883,"max":1.0000000000648888,"mean":1.0000000000648885,"population_std":1.5215342778891414e-16}}} | 1248 | [56,357.6] | {"changed_fields":{"ve":1248,"vn":1248},"delta":{"ve":{"min":-0.4750362970000004,"max":-0.4750362969999997,"mean":-0.47503629699999994,"population_std":9.104343020629299e-17},"vn":{"min":0.8799662019999999,"max":0.8799662020000003,"mean":0.8799662020000002,"population_std":2.0710846592749373e-16},"velocity_delta_norm_mps":{"min":1.0000000000648883,"max":1.0000000000648888,"mean":1.0000000000648885,"population_std":1.5215342778891414e-16}}} |
| D51_seed_00 | go2_rp | 63278 | [44.887078,350.091049] | {"changed_fields":{"source_status":31639,"pitch_rad":31639,"roll_rad":31639},"delta":{"pitch_rad":{"min":-0.22741982215270282,"max":0.21092170343977434,"mean":-0.00042188340104737425,"population_std":0.05271377008415976},"roll_rad":{"min":-0.2006971265673367,"max":0.2663082452924954,"mean":3.3009292892587546e-07,"population_std":0.05256491967222284}}} | 63278 | [44.887078,350.091049] | {"changed_fields":{"source_status":31639,"pitch_rad":31639,"roll_rad":31639},"delta":{"pitch_rad":{"min":-0.22741982215270282,"max":0.21092170343977434,"mean":-0.00042188340104737425,"population_std":0.05271377008415976},"roll_rad":{"min":-0.2006971265673367,"max":0.2663082452924954,"mean":3.3009292892587546e-07,"population_std":0.05256491967222284}}} |
| D52_seed_00 | go2_rp | 63278 | [44.887078,350.091049] | {"changed_fields":{"pitch_rad":63278,"roll_rad":63278},"delta":{"pitch_rad":{"min":-0.016581894883210192,"max":-0.016581894882210204,"mean":-0.016581894882709298,"population_std":2.88941348777108e-13},"roll_rad":{"min":0.03071661506766115,"max":0.030716615068661114,"mean":0.030716615068161614,"population_std":2.885601824638434e-13}}} | 63278 | [44.887078,350.091049] | {"changed_fields":{"pitch_rad":63278,"roll_rad":63278},"delta":{"pitch_rad":{"min":-0.016581894883210192,"max":-0.016581894882210204,"mean":-0.016581894882709298,"population_std":2.88941348777108e-13},"roll_rad":{"min":0.03071661506766115,"max":0.030716615068661114,"mean":0.030716615068161614,"population_std":2.885601824638434e-13}}} |
| D53_seed_00 | go2_hv | 63278 | [44.887078,350.091049] | {"changed_fields":{"ve":63278,"vn":63278},"delta":{"ve":{"min":-4.159908727215755,"max":4.660997827092047,"mean":-0.006446645878185959,"population_std":0.9988203322782818},"vn":{"min":-4.6791625548839715,"max":4.26386359871997,"mean":-0.0014771425005450634,"population_std":1.0001399130444737},"velocity_delta_norm_mps":{"min":0.007421338862814932,"max":5.025911697505057,"mean":1.2525573816669477,"population_std":0.6550310287778672}}} | 63278 | [44.887078,350.091049] | {"changed_fields":{"ve":63278,"vn":63278},"delta":{"ve":{"min":-4.159908727215755,"max":4.660997827092047,"mean":-0.006446645878185959,"population_std":0.9988203322782818},"vn":{"min":-4.6791625548839715,"max":4.26386359871997,"mean":-0.0014771425005450634,"population_std":1.0001399130444737},"velocity_delta_norm_mps":{"min":0.007421338862814932,"max":5.025911697505057,"mean":1.2525573816669477,"population_std":0.6550310287778672}}} |
| D54_seed_00 | go2_hv | 63278 | [44.887078,350.091049] | {"changed_fields":{"ve":63278,"vn":63278},"delta":{"ve":{"min":-0.6868073668020456,"max":0.686748570271386,"mean":-0.007082864381852314,"population_std":0.4449748699030428},"vn":{"min":-0.6320594604517633,"max":0.6122094761770733,"mean":-0.013128082330090881,"population_std":0.3239149857165608},"velocity_delta_norm_mps":{"min":0.0002631259151891118,"max":0.7128281289542808,"mean":0.5285834802814238,"population_std":0.1540959788705876}}} | 63278 | [44.887078,350.091049] | {"changed_fields":{"ve":63278,"vn":63278},"delta":{"ve":{"min":-0.6868073668020456,"max":0.686748570271386,"mean":-0.007082864381852314,"population_std":0.4449748699030428},"vn":{"min":-0.6320594604517633,"max":0.6122094761770733,"mean":-0.013128082330090881,"population_std":0.3239149857165608},"velocity_delta_norm_mps":{"min":0.0002631259151891118,"max":0.7128281289542808,"mean":0.5285834802814238,"population_std":0.1540959788705876}}} |
| D55_seed_00 | source_quality_metadata | 106 | [28858.2101,29155.2035] | {"changed_fields":{"audit_go2_metadata":106},"delta":{}} | 106 | [28858.2101,29155.2035] | {"changed_fields":{"audit_go2_metadata":106},"delta":{}} |
| D56_seed_00 | source_quality_metadata | 91 | [28858.2101,29156.2105] | {"changed_fields":{"audit_go2_metadata":91},"delta":{}} | 91 | [28858.2101,29156.2105] | {"changed_fields":{"audit_go2_metadata":91},"delta":{}} |
| D57_seed_00 | gnss_position | 303 | [55.2964737,357.285637] | {"changed_fields":{"time":303},"delta":{"time":{"min":0.07867597915100077,"max":0.1293782996120285,"mean":0.10334998907562971,"population_std":0.014774163446669732},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} | 1510 | [55.8896786,357.69476] | {"changed_fields":{"time":1510},"delta":{"time":{"min":0.07847548653899139,"max":0.12961988098300026,"mean":0.1039860750106238,"population_std":0.014688014408464702},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} |
| D57_seed_00 | receiver_velocity | 303 | [55.3926955,357.415534] | {"changed_fields":{"time":303},"delta":{"time":{"min":0.16495543476099783,"max":0.22519231973598153,"mean":0.19449642059549124,"population_std":0.017217752424695473},"velocity_delta_norm_mps":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} | 1510 | [55.9859004,357.822929] | {"changed_fields":{"time":1510},"delta":{"time":{"min":0.16477689454501387,"max":0.22523354898299885,"mean":0.1952918156750812,"population_std":0.017256869892433333},"velocity_delta_norm_mps":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} |
| D57_seed_00 | dual_yaw | 303 | [55.5262432,357.446821] | {"changed_fields":{"time":303},"delta":{"time":{"min":0.22634496180899077,"max":0.3215590464229763,"mean":0.2747743941383851,"population_std":0.027499690276213035}}} | 301 | [56.3194482,356.28158] | {"changed_fields":{"time":301},"delta":{"time":{"min":0.22634496180899077,"max":0.3215590464229763,"mean":0.2748270252848138,"population_std":0.027528308591863827}}} |
| D57_seed_00 | raw_doppler | 1248 | [56.2663447,357.897645] | {"changed_fields":{"time":1248},"delta":{"time":{"min":0.22656665467897596,"max":0.3087850052270369,"mean":0.2674138034243279,"population_std":0.0242484173099568},"velocity_delta_norm_mps":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} | 1248 | [56.2663447,357.897645] | {"changed_fields":{"time":1248},"delta":{"time":{"min":0.22656665467897596,"max":0.3087850052270369,"mean":0.2674138034243279,"population_std":0.0242484173099568},"velocity_delta_norm_mps":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} |
| D57_seed_00 | go2_rp | 63278 | [45.0672644,350.320091] | {"changed_fields":{"time":63278},"delta":{"time":{"min":0.14863679255100237,"max":0.2444731054119984,"mean":0.19654100943075464,"population_std":0.027689050045953446}}} | 63278 | [45.0672644,350.320091] | {"changed_fields":{"time":63278},"delta":{"time":{"min":0.14863679255100237,"max":0.2444731054119984,"mean":0.19654100943075464,"population_std":0.027689050045953446}}} |
| D57_seed_00 | go2_hv | 63278 | [45.0117786,350.23853] | {"changed_fields":{"time":63278},"delta":{"time":{"min":0.11145321665799202,"max":0.1735707423609938,"mean":0.1426573319863385,"population_std":0.017905993290780447},"velocity_delta_norm_mps":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} | 63278 | [45.0117786,350.23853] | {"changed_fields":{"time":63278},"delta":{"time":{"min":0.11145321665799202,"max":0.1735707423609938,"mean":0.1426573319863385,"population_std":0.017905993290780447},"velocity_delta_norm_mps":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} |
| D58_seed_00 | gnss_position | 10 | [201.211278,210.205992] | {"changed_fields":{"status":10,"valid":10},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} | 50 | [201.2,211] | {"changed_fields":{"status":50,"valid":50},"delta":{"valid":{"min":-1.0,"max":-1.0,"mean":-1.0,"population_std":0.0},"position_delta_n_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_e_m":{"min":-0.0,"max":-0.0,"mean":0.0,"population_std":0.0},"position_delta_u_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_h_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0},"position_delta_3d_m":{"min":0.0,"max":0.0,"mean":0.0,"population_std":0.0}}} |
| D58_seed_00 | dual_yaw | 1 | [201.211278,201.211278] | {"changed_fields":{"yaw_deg":1},"delta":{"yaw_deg":{"min":-10.0,"max":-10.0,"mean":-10.0,"population_std":0.0}}} | 1 | [202,202] | {"changed_fields":{"yaw_deg":1},"delta":{"yaw_deg":{"min":-10.0,"max":-10.0,"mean":-10.0,"population_std":0.0}}} |
| D59_seed_00 | gnss_position | 303 | [55.206795,357.201323] | {"changed_fields":{"height_m":303,"lat_deg":303,"lon_deg":303},"delta":{"height_m":{"min":-14.808676000000002,"max":13.649871000000005,"mean":-0.3017661221122109,"population_std":5.120924108533565},"lat_deg":{"min":-6.028909999855614e-05,"max":7.658659999520978e-05,"mean":3.8125191418930177e-06,"population_std":2.5279191712415646e-05},"lon_deg":{"min":-9.956670000121903e-05,"max":0.00010855019999667093,"mean":1.2832722775223817e-06,"population_std":3.549478724034095e-05},"position_delta_n_m":{"min":-6.694203891054993,"max":8.503801135322817,"mean":0.423323745561575,"population_std":2.8068767836041055},"position_delta_e_m":{"min":-8.504327914935493,"max":9.271612537010407,"mean":0.10960883373621255,"population_std":3.0317332940159223},"position_delta_u_m":{"min":-14.808682945685954,"max":13.649869808760393,"mean":-0.30176747582631014,"population_std":5.120924221222505},"position_delta_h_m":{"min":0.153988298105034,"max":10.759832146787321,"mean":3.6805222078067144,"population_std":1.9274172906278615},"position_delta_3d_m":{"min":0.954155478506953,"max":17.54985299368945,"mean":6.029683225175052,"population_std":2.686825232013078}}} | 1510 | [55.8,357.6] | {"changed_fields":{"height_m":1510,"lat_deg":1510,"lon_deg":1510},"delta":{"height_m":{"min":-19.290170620999998,"max":17.900478550000003,"mean":0.08791365794304644,"population_std":4.964758063824832},"lat_deg":{"min":-0.00011715044699656119,"max":9.430410400312894e-05,"mean":7.448638662028379e-07,"population_std":2.7048266414867983e-05},"lon_deg":{"min":-0.00012447166498930073,"max":0.00010779323800136353,"mean":5.202446728848499e-07,"population_std":3.454703386978738e-05},"position_delta_n_m":{"min":-13.007820153550387,"max":10.471051860347785,"mean":0.08270668229494947,"population_std":3.0033061739325584},"position_delta_e_m":{"min":-10.631589944910854,"max":9.207007634017486,"mean":0.04443585374199328,"population_std":2.950783877141311},"position_delta_u_m":{"min":-19.290172880222936,"max":17.90047698936098,"mean":0.08791226674337246,"population_std":4.964758055639466},"position_delta_h_m":{"min":0.048313636705799766,"max":13.294010308296153,"mean":3.7416008135077004,"population_std":1.93292828545993},"position_delta_3d_m":{"min":0.19255481632992208,"max":20.02240502868436,"mean":5.905308309757771,"population_std":2.7422022698479593}}} |
| D59_seed_00 | raw_doppler | 1248 | [56,357.6] | {"changed_fields":{"ve":1248,"vn":1248},"delta":{"ve":{"min":-0.4750362970000004,"max":-0.4750362969999997,"mean":-0.47503629699999994,"population_std":9.104343020629299e-17},"vn":{"min":0.8799662019999999,"max":0.8799662020000003,"mean":0.8799662020000002,"population_std":2.0710846592749373e-16},"velocity_delta_norm_mps":{"min":1.0000000000648883,"max":1.0000000000648888,"mean":1.0000000000648885,"population_std":1.5215342778891414e-16}}} | 1248 | [56,357.6] | {"changed_fields":{"ve":1248,"vn":1248},"delta":{"ve":{"min":-0.4750362970000004,"max":-0.4750362969999997,"mean":-0.47503629699999994,"population_std":9.104343020629299e-17},"vn":{"min":0.8799662019999999,"max":0.8799662020000003,"mean":0.8799662020000002,"population_std":2.0710846592749373e-16},"velocity_delta_norm_mps":{"min":1.0000000000648883,"max":1.0000000000648888,"mean":1.0000000000648885,"population_std":1.5215342778891414e-16}}} |
| D60_seed_00 | gnss_position | 20 | [196.210194,215.205113] | {"changed_fields":{"height_m":20,"lat_deg":20,"lon_deg":20,"std_d_m":20,"std_e_m":20,"std_n_m":20},"delta":{"height_m":{"min":-10.358729000000004,"max":8.217666000000001,"mean":0.8469371500000001,"population_std":5.22129510910283},"lat_deg":{"min":-3.987839999552989e-05,"max":2.0930799998097882e-05,"mean":-8.691804999472198e-06,"population_std":1.6555264808328314e-05},"lon_deg":{"min":-5.868670000097609e-05,"max":6.913890000248557e-05,"mean":4.968454999243477e-06,"population_std":2.902802989664867e-05},"std_d_m":{"min":-0.015,"max":-0.00825,"mean":-0.009712500000000002,"population_std":0.001563799459649478},"std_e_m":{"min":-0.01125,"max":-0.0105,"mean":-0.010537500000000002,"population_std":0.00016345871038277507},"std_n_m":{"min":-0.01125,"max":-0.0105,"mean":-0.010537500000000002,"population_std":0.00016345871038277507},"position_delta_n_m":{"min":-4.427900773656379,"max":2.324052537330138,"mean":-0.9650947500589686,"population_std":1.8382149842711164},"position_delta_e_m":{"min":-5.012647247497757,"max":5.905399978036886,"mean":0.42437345260469445,"population_std":2.479390147471589},"position_delta_u_m":{"min":-10.358730833228396,"max":8.21766572105662,"mean":0.8469363158979182,"population_std":5.221295406872079},"position_delta_h_m":{"min":0.22040262192654828,"max":6.221380139372385,"mean":2.748692967092911,"population_std":1.7557327553756665},"position_delta_3d_m":{"min":1.0764689572454578,"max":11.430980535635452,"mean":5.626248358513179,"population_std":2.638648667970601}}} | 100 | [196.2,216] | {"changed_fields":{"height_m":100,"lat_deg":100,"lon_deg":100,"std_d_m":100,"std_e_m":100,"std_n_m":100},"delta":{"height_m":{"min":-8.367939884000002,"max":11.486957801000003,"mean":1.3314719070699996,"population_std":4.113915163620706},"lat_deg":{"min":-6.028901800192443e-05,"max":7.658661999698779e-05,"mean":-2.6247849702798476e-06,"population_std":2.6751428383402256e-05},"lon_deg":{"min":-7.377824599075211e-05,"max":8.953045900739198e-05,"mean":8.386668430517829e-06,"population_std":3.291989050701208e-05},"std_d_m":{"min":-0.0165,"max":-0.0075,"mean":-0.0099075,"population_std":0.0016130929142488969},"std_e_m":{"min":-0.012,"max":-0.0105,"mean":-0.010529999999999994,"population_std":0.00018124568960391845},"std_n_m":{"min":-0.012,"max":-0.0105,"mean":-0.010529999999999994,"population_std":0.00018124568960391845},"position_delta_n_m":{"min":-6.694197256166833,"max":8.503802057844306,"mean":-0.2914429525427675,"population_std":2.970347218701852},"position_delta_e_m":{"min":-6.301675724678226,"max":7.647128992242419,"mean":0.7163362522955136,"population_std":2.8118089668467805},"position_delta_u_m":{"min":-8.367941561324418,"max":11.486957341747338,"mean":1.3314705478460354,"population_std":4.113915223061283},"position_delta_h_m":{"min":0.7028911720593212,"max":8.503950585851744,"mean":3.7296371026422945,"population_std":1.8485442838145378},"position_delta_3d_m":{"min":1.1332688045894492,"max":11.73912999714729,"mean":5.631091652946569,"population_std":2.0773126786937155}}} |
| D60_seed_00 | receiver_velocity | 20 | [196.210194,215.205113] | {"changed_fields":{"std_vd":20,"std_ve":20,"std_vn":20,"vd":20,"ve":20,"vn":20},"delta":{"std_vd":{"min":-0.037500000000000006,"max":-0.037500000000000006,"mean":-0.0375,"population_std":6.938893903907228e-18},"std_ve":{"min":-0.037500000000000006,"max":-0.037500000000000006,"mean":-0.0375,"population_std":6.938893903907228e-18},"std_vn":{"min":-0.037500000000000006,"max":-0.037500000000000006,"mean":-0.0375,"population_std":6.938893903907228e-18},"vd":{"min":-0.920716415,"max":0.778358428,"mean":-0.008437187250000002,"population_std":0.4731832007810456},"ve":{"min":-0.7692106360000001,"max":1.5345140520000002,"mean":0.12242711730000003,"population_std":0.5652762521092517},"vn":{"min":-1.255214723,"max":1.1554919229999998,"mean":0.12503183835000004,"population_std":0.5842462304299698},"velocity_delta_norm_mps":{"min":0.24323351269677707,"max":1.8072107282965872,"mean":0.878893437708603,"population_std":0.37818264291836734}}} | 100 | [196.2,216] | {"changed_fields":{"std_vd":100,"std_ve":100,"std_vn":100,"vd":100,"ve":100,"vn":100},"delta":{"std_vd":{"min":-0.037500000000000006,"max":-0.037500000000000006,"mean":-0.0375,"population_std":6.938893903907228e-18},"std_ve":{"min":-0.037500000000000006,"max":-0.037500000000000006,"mean":-0.0375,"population_std":6.938893903907228e-18},"std_vn":{"min":-0.037500000000000006,"max":-0.037500000000000006,"mean":-0.0375,"population_std":6.938893903907228e-18},"vd":{"min":-1.3001948779999999,"max":1.123883943,"mean":-0.06616501463999999,"population_std":0.47140075483715227},"ve":{"min":-1.2785735729999999,"max":1.5345140519999998,"mean":-0.017209751069999987,"population_std":0.5282892754081859},"vn":{"min":-1.3486421000000002,"max":1.155491923,"mean":0.016031361890000005,"population_std":0.4629864173315112},"velocity_delta_norm_mps":{"min":0.1315217346911876,"max":1.8072107282965868,"mean":0.7810038395970786,"population_std":0.3326088462423731}}} |
| D60_seed_00 | dual_yaw | 20 | [196.210194,215.205113] | {"changed_fields":{"yaw_deg":20,"yaw_std_deg":20},"delta":{"yaw_deg":{"min":-17.02236532500001,"max":21.32401631199997,"mean":0.3259058220999961,"population_std":10.06805012871822},"yaw_std_deg":{"min":-1.125,"max":-1.125,"mean":-1.125,"population_std":0.0}}} | 20 | [197,216] | {"changed_fields":{"yaw_deg":20,"yaw_std_deg":20},"delta":{"yaw_deg":{"min":-17.02236532500001,"max":21.324016311999998,"mean":0.3259058220999975,"population_std":10.068050128718223},"yaw_std_deg":{"min":-1.125,"max":-1.125,"mean":-1.125,"population_std":0.0}}} |
| D60_seed_00 | raw_doppler | 100 | [196.2,216] | {"changed_fields":{"std_vd":100,"std_ve":100,"std_vn":100,"vd":100,"ve":100,"vn":100},"delta":{"std_vd":{"min":-0.3623115,"max":-0.21329625000000002,"mean":-0.224262075,"population_std":0.03174422903303647},"std_ve":{"min":-0.3623115,"max":-0.21329625000000002,"mean":-0.224262075,"population_std":0.03174422903303647},"std_vn":{"min":-0.3623115,"max":-0.21329625000000002,"mean":-0.224262075,"population_std":0.03174422903303647},"vd":{"min":-1.448045903,"max":1.312096291,"mean":-0.007519565290000013,"population_std":0.5015785873629058},"ve":{"min":-1.202387289,"max":1.455523945,"mean":0.03639808667000002,"population_std":0.5433198545838132},"vn":{"min":-1.2677633120000003,"max":0.9493567430000001,"mean":-0.07828687010000002,"population_std":0.513744424374204},"velocity_delta_norm_mps":{"min":0.2751739929487255,"max":1.8382287869117746,"mean":0.8305191153440495,"population_std":0.35841187886997466}}} | 100 | [196.2,216] | {"changed_fields":{"std_vd":100,"std_ve":100,"std_vn":100,"vd":100,"ve":100,"vn":100},"delta":{"std_vd":{"min":-0.3623115,"max":-0.21329625000000002,"mean":-0.224262075,"population_std":0.03174422903303647},"std_ve":{"min":-0.3623115,"max":-0.21329625000000002,"mean":-0.224262075,"population_std":0.03174422903303647},"std_vn":{"min":-0.3623115,"max":-0.21329625000000002,"mean":-0.224262075,"population_std":0.03174422903303647},"vd":{"min":-1.448045903,"max":1.312096291,"mean":-0.007519565290000013,"population_std":0.5015785873629058},"ve":{"min":-1.202387289,"max":1.455523945,"mean":0.03639808667000002,"population_std":0.5433198545838132},"vn":{"min":-1.2677633120000003,"max":0.9493567430000001,"mean":-0.07828687010000002,"population_std":0.513744424374204},"velocity_delta_norm_mps":{"min":0.2751739929487255,"max":1.8382287869117746,"mean":0.8305191153440495,"population_std":0.35841187886997466}}} |

完整摘要及哈希来源行：`02_PROVIDERS/<case_id>/PROVIDER_DIFF_SUMMARY.json`；CAL 与 V2S 共享同一注入后输入。

## A5/A6 独立统计核对

数据来自 `S/08_AGGREGATE/PAIRWISE_FOUR_COLUMN_COMPARISON.csv`、`PAIRWISE_CASE_LEVEL.csv`、`UNIQUE_EVALUATION_RESULTS.csv`。冻结源为合约固定的 `C/13_AGGREGATE/PAIRWISE_SUMMARY.csv` 和 `PAIRWISE_CASE_LEVEL.csv`，两文件 SHA-256 均与合约一致。10 个配对严格沿用冻结 PAIRWISE_SUMMARY 全部配对，差为 candidate − reference。冻结两列在 v2/v3 表中都保留原 Canonical v2。

核实四列表 100 行（10 配对 × 5 指标 × 2 版本），case 配对表 12200 行（再 × 2 新链 × 61 cases），其中 12010 AVAILABLE、190 UNAVAILABLE。CAL 每版本缺 40 个 case×指标×配对项，V2S 每版本缺 55 项；全部能回溯到上表 10 个失败 run，没有其他指标缺失。逐一核对 2684 个 EVALUATION_RESULT.json 的身份与 5 个指标来源。

冻结 50 个配对/指标组均为 541 个唯一 cases，过滤子集各为 61。全部 400 列组的 N、median、win/tie 及方向核对通过；100 行中的 200 个冻结原 median/win token 逐字一致。胜率使用 delta < −1e−12；tie 为 |delta|≤1e−12；分母含有限配对中的 ties。CAL 完整后才按 median 严格同号且 win rate 同处 0.5 严格同侧分类；CAL 缺失保留 `UNAVAILABLE_INCOMPLETE_PAIRS`。V2S 缺失单独进入决定的 missing_evidence。

| 主指标版本 | MAINTAINED | FLIPPED | UNAVAILABLE_INCOMPLETE_PAIRS | 合计 |
|---|---|---|---|---|
| v3 | 14 | 4 | 12 | 30 |
| v2 | 9 | 9 | 12 | 30 |
| 合计 | 23 | 13 | 24 | 60 |

包含副指标的 100 行：v3=18 MAINTAINED / 12 FLIPPED / 20 不完整；v2=11 / 19 / 20。决定文件的 13 项主指标翻转与 `PRIMARY_FLIPS.csv` 一致，66 项主指标 missing_evidence 逐项一致。`decision="HUMAN_DECISION_REQUIRED"`；`full_matrix_rerun_executed=false`；`full_matrix_rerun_authorized_automatically=false`。完整决定原文见“决定原文”节，来源为 `S/08_AGGREGATE/DEGRADATION_SUBSET_DECISION.json`；JSON token 保持原样。

独立复算 10 组 bootstrap/Wilcoxon：一次性生成 10000 个 paired-case 重采样，PCG64 seed=260910007，median 的 percentile 2.5/97.5（linear）；Wilcoxon two-sided / wilcox / correction=false / method=auto。覆盖冻结541、子集61、不完整59/60、维持/翻转、近零及全部三个主指标；10/10 与输出一致。检查脚本未调用 pipeline 产物函数。

| 独立复算样本 | N | CI95 | Wilcoxon p |
|---|---|---|---|
| full_vs_strong / H / 原全量 | 541 | [0.00228543093, 0.00228543093] m | 5.95835090e-24 |
| full_vs_strong / H / 子集冻结 | 61 | [0.00228202775, 0.00229006282] m | 0.000960754765 |
| full_vs_strong / H / v3 CAL | 59 | [-0.00121206291, -0.00109324015] m | 7.57494258e-06 |
| full_vs_strong / H / v3 V2S | 60 | [0.000339897027, 0.000370471527] m | 0.00193629531 |
| basic_vs_single / H / v2 CAL | 61 | [-0.00171299722, 0.00535249011] m | 0.0781177584 |
| basic_vs_single / H / v3 CAL | 61 | [0.00989896635, 0.0113330972] m | 1.39448798e-09 |
| full_vs_no_HV / Up / v3 CAL | 61 | [1.17805881e-07, 1.23987852e-07] m | 0.0127998750 |
| full_vs_no_HV / Up / v3 V2S | 61 | [6.50008248e-08, 8.50707758e-08] m | 0.000103173870 |
| full_vs_no_SA / yaw RMSE / v3 CAL | 61 | [-0.0136645633, -0.0136025664] deg | 9.78261858e-07 |
| full_vs_no_HV / yaw P95 / v3 CAL | 61 | [1.09627000e-05, 3.53898968e-05] deg | 0.113172508 |

## 逐对四列对照

每格：中位配对差；胜率；case 数；bootstrap 95% CI；Wilcoxon p。差值为 candidate − reference，负值更优。冻结全量和过滤子集列均保持原 v2；新 CAL/V2S 分别报告 v3 与 v2。

### 新链 v3

| 配对 | 指标 | Canonical_full_frozen | subset_frozen | subset_CAL | subset_V2S | 判定 |
|---|---|---|---|---|---|---|
| full_vs_strong | horizontal_rmse_m | 0.00228543093; 0.175600739; 541; [0.00228543093,0.00228543093]; 5.9583509e-24 | 0.00228543093; 0.213114754; 61; [0.00228202775,0.00229006282]; 0.000960754765 | -0.00109418016; 0.898305085; 59; [-0.00121206291,-0.00109324015]; 7.57494258e-06 | 0.000343895326; 0.2; 60; [0.000339897027,0.000370471527]; 0.00193629531 | UNAVAILABLE_INCOMPLETE_PAIRS |
| full_vs_strong | yaw_rmse_deg | -0.00745429261; 0.704251386; 541; [-0.00745429261,-0.00745429261]; 3.14929086e-08 | -0.00745429261; 0.704918033; 61; [-0.00797647268,-0.00745402696]; 0.00512955452 | -0.0471730735; 0.966101695; 59; [-0.0473415943,-0.0471729864]; 7.61030925e-10 | 0.0220003401; 0.2; 60; [0.0209441605,0.0220370753]; 0.000260144843 | UNAVAILABLE_INCOMPLETE_PAIRS |
| full_vs_strong | yaw_p95_absolute_deg | -0.0615004271; 0.829944547; 541; [-0.0615007489,-0.0611049015]; 1.59223407e-40 | -0.0615007489; 0.901639344; 61; [-0.0615768242,-0.0562693839]; 2.72811547e-08 | -0.139544455; 0.966101695; 59; [-0.140083635,-0.139524397]; 3.88592099e-10 | 0.080427137; 0.2; 60; [0.0784578048,0.08044507]; 0.000168219537 | UNAVAILABLE_INCOMPLETE_PAIRS |
| full_vs_strong | up_rmse_m | 0.0378981759; 0.0443622921; 541; [0.0378981759,0.0378981924]; 3.90115751e-64 | 0.0378981759; 0.0327868852; 61; [0.0378978798,0.0378985352]; 3.13228929e-09 | 0.0011986945; 0.220338983; 59; [0.00119782341,0.0011990008]; 0.0076993711 | 0.00344347327; 0.0833333333; 60; [0.00344329611,0.0034479351]; 3.38320596e-06 | UNAVAILABLE_INCOMPLETE_PAIRS |
| full_vs_strong | position_3d_rmse_m | 0.0357973187; 0.0905730129; 541; [0.0357973187,0.0357976536]; 2.69437477e-50 | 0.0357973187; 0.0983606557; 61; [0.0357973187,0.0358027823]; 1.79870055e-06 | -0.000454106342; 0.86440678; 59; [-0.000475570572,-0.000453597522]; 3.18555501e-05 | 0.00328396999; 0.133333333; 60; [0.00328298412,0.00330138922]; 0.000317582542 | UNAVAILABLE_INCOMPLETE_PAIRS |
| strong_vs_basic | horizontal_rmse_m | -0.00300896966; 0.95194085; 541; [-0.00301441428,-0.00300896966]; 1.36108028e-80 | -0.00300896966; 0.950819672; 61; [-0.00485083559,-0.00300896966]; 1.29276272e-11 | -0.0022416815; 0.86440678; 59; [-0.0036664114,-0.0022416815]; 6.15714594e-07 | -0.000800164602; 0.8; 60; [-0.00106758143,-0.000800164602]; 4.49576794e-05 | UNAVAILABLE_INCOMPLETE_PAIRS |
| strong_vs_basic | yaw_rmse_deg | -0.376013308; 0.883548983; 541; [-0.376013308,-0.376013308]; 2.49579938e-35 | -0.376013308; 0.868852459; 61; [-0.376013308,-0.375990318]; 0.000376758049 | -0.23774278; 0.966101695; 59; [-0.239050706,-0.23774278]; 4.73146139e-09 | -0.231465162; 0.866666667; 60; [-0.232637676,-0.231465162]; 1.50258867e-06 | UNAVAILABLE_INCOMPLETE_PAIRS |
| strong_vs_basic | yaw_p95_absolute_deg | -0.891389443; 0.878003697; 541; [-0.891496425,-0.889125935]; 3.16079211e-34 | -0.891496425; 0.868852459; 61; [-0.891496425,-0.885073218]; 0.000376758049 | -0.509628324; 0.966101695; 59; [-0.51127715,-0.509628324]; 3.94180911e-09 | -0.21090527; 0.833333333; 60; [-0.215967089,-0.21090527]; 3.59536373e-05 | UNAVAILABLE_INCOMPLETE_PAIRS |
| strong_vs_basic | up_rmse_m | -0.00144498798; 0.957486137; 541; [-0.00144498798,-0.00144498798]; 8.54812244e-73 | -0.00144498798; 0.93442623; 61; [-0.00146276838,-0.00144498798]; 1.79170264e-08 | -0.000194109902; 0.881355932; 59; [-0.000319680655,-0.000194109902]; 3.01645461e-07 | -0.00136094424; 0.95; 60; [-0.00137574645,-0.00136094424]; 4.46324715e-09 | UNAVAILABLE_INCOMPLETE_PAIRS |
| strong_vs_basic | position_3d_rmse_m | -0.00252069135; 0.964879852; 541; [-0.00252728735,-0.00252069135]; 3.2238981e-79 | -0.00252069135; 0.983606557; 61; [-0.00324970181,-0.00252069135]; 1.05884582e-11 | -0.00210684495; 0.86440678; 59; [-0.00338780658,-0.00210684495]; 7.77932178e-07 | -0.00156933008; 0.866666667; 60; [-0.00176066291,-0.00156933008]; 7.10525346e-07 | UNAVAILABLE_INCOMPLETE_PAIRS |
| basic_vs_single | horizontal_rmse_m | 0.000955679258; 0.11090573; 541; [0.000955679258,0.000973518468]; 1.10321011e-49 | 0.000955679258; 0.131147541; 61; [0.000955679258,0.000999868481]; 9.49649274e-07 | 0.00989896635; 0.0983606557; 61; [0.00989896635,0.0113330972]; 1.39448798e-09 | -0.0093957464; 0.737704918; 61; [-0.0093990591,-0.00741261276]; 0.0115539506 | MAINTAINED |
| basic_vs_single | yaw_rmse_deg | -4.58886114; 0.964879852; 541; [-4.58886114,-4.58886114]; 1.84682934e-73 | -4.58886114; 0.967213115; 61; [-4.58886114,-4.57643731]; 2.27765733e-09 | -5.7021454; 0.93442623; 61; [-5.7021454,-5.67704997]; 3.55809066e-10 | -5.6997019; 0.93442623; 61; [-5.70004446,-5.66393572]; 2.94987593e-07 | MAINTAINED |
| basic_vs_single | yaw_p95_absolute_deg | -7.3757816; 0.970425139; 541; [-7.3757816,-7.3757816]; 2.6117595e-78 | -7.3757816; 0.967213115; 61; [-7.3757816,-7.3757816]; 1.84864125e-10 | -7.62091848; 0.967213115; 61; [-7.62091848,-7.59399244]; 2.03415313e-10 | -8.37943197; 0.93442623; 61; [-8.3795384,-8.30922198]; 2.94987593e-07 | MAINTAINED |
| basic_vs_single | up_rmse_m | 0.00150038263; 0.0665434381; 541; [0.00150038263,0.00150038263]; 4.78551081e-60 | 0.00150038263; 0.114754098; 61; [0.00150038263,0.00150039574]; 3.86361275e-05 | 0.000178857979; 0.114754098; 61; [0.000178857979,0.000643972142]; 1.07267451e-07 | 0.00138447639; 0.0655737705; 61; [0.00138447639,0.00138447639]; 3.47371468e-08 | MAINTAINED |
| basic_vs_single | position_3d_rmse_m | 0.00175677013; 0.0831792976; 541; [0.00175677013,0.00176311199]; 2.33764826e-57 | 0.00175677013; 0.0819672131; 61; [0.00175677013,0.00189499393]; 1.31377555e-07 | 0.00894592377; 0.0983606557; 61; [0.00894592377,0.0104655233]; 1.66728613e-09 | -0.00270218323; 0.672131148; 61; [-0.00271135391,-0.00202696567]; 0.350770629 | MAINTAINED |
| full_vs_no_RD | horizontal_rmse_m | -0.000116055031; 0.939001848; 541; [-0.000118697146,-0.000115736295]; 3.52908985e-73 | -0.000116085315; 0.918032787; 61; [-0.000221750361,-0.000115701801]; 4.56155126e-10 | -0.000139863189; 0.803278689; 61; [-0.000146826335,-0.000139728124]; 0.000846840817 | -0.000204374415; 0.93442623; 61; [-0.000325668021,-0.000198435991]; 2.42858005e-11 | MAINTAINED |
| full_vs_no_RD | yaw_rmse_deg | -0.00415198457; 0.896487985; 541; [-0.00415198457,-0.00415197404]; 3.6739121e-49 | -0.00415198457; 0.918032787; 61; [-0.00415198457,-0.00413073389]; 3.99016101e-07 | 0.00194353795; 0.37704918; 61; [2.50285413e-05,0.00207139616]; 0.997133966 | 0.000130536486; 0.426229508; 61; [-0.000316465909,0.00016738903]; 0.402622243 | FLIPPED |
| full_vs_no_RD | yaw_p95_absolute_deg | -0.00443364659; 0.842883549; 541; [-0.00444647898,-0.00443364659]; 2.19344189e-40 | -0.00443364659; 0.819672131; 61; [-0.00489517893,-0.00443364659]; 4.8353643e-05 | -0.00122181651; 0.737704918; 61; [-0.00219221469,-0.000716534359]; 0.00127269304 | 0.00325953526; 0.344262295; 61; [0.00167461963,0.00334718769]; 0.22607934 | MAINTAINED |
| full_vs_no_RD | up_rmse_m | -8.70445816e-05; 0.959334566; 541; [-8.7181237e-05,-8.70262892e-05]; 1.45728356e-75 | -8.71661931e-05; 0.93442623; 61; [-8.99140074e-05,-8.70244549e-05]; 1.4138682e-07 | 0.000582999316; 0.213114754; 61; [0.000582965863,0.000583076215]; 0.00439266613 | -7.36305512e-05; 0.950819672; 61; [-7.58831641e-05,-7.36240761e-05]; 1.60175824e-08 | FLIPPED |
| full_vs_no_RD | position_3d_rmse_m | -0.000124872258; 0.953789279; 541; [-0.000127622444,-0.000124743331]; 7.87648961e-79 | -0.000124893091; 0.967213115; 61; [-0.000192511988,-0.000124705377]; 9.76050937e-11 | 0.00013353254; 0.245901639; 61; [0.000129671395,0.000133701488]; 0.182646739 | -0.000151274755; 0.93442623; 61; [-0.000207038036,-0.000147906379]; 2.20162508e-11 | FLIPPED |
| full_vs_no_SA | horizontal_rmse_m | 0.00241615363; 0.15896488; 541; [0.00241615363,0.00241615363]; 1.77542712e-30 | 0.00241615363; 0.196721311; 61; [0.00240446466,0.00242469005]; 0.000218178835 | 0.000436978927; 0.295081967; 61; [0.000190916896,0.000452447993]; 0.093447394 | 0.000707683166; 0.137931034; 58; [0.000703375669,0.00093254033]; 8.02870278e-06 | MAINTAINED |
| full_vs_no_SA | yaw_rmse_deg | 0.0208833687; 0.131238447; 541; [0.0208833687,0.0208842883]; 3.76794361e-33 | 0.0208804625; 0.147540984; 61; [0.0197943374,0.0208833687]; 0.00143853907 | -0.0136462642; 0.885245902; 61; [-0.0136645633,-0.0136025664]; 9.78261858e-07 | 0.0246903745; 0.155172414; 58; [0.0244995457,0.0249011716]; 7.63218271e-07 | FLIPPED |
| full_vs_no_SA | yaw_p95_absolute_deg | -0.0293945312; 0.752310536; 541; [-0.0293945312,-0.0293935612]; 3.41372318e-18 | -0.0293945312; 0.852459016; 61; [-0.0306387744,-0.0293945312]; 3.16442216e-06 | -0.0050567741; 0.770491803; 61; [-0.00526835092,-0.00489625607]; 0.0015150853 | 0.0818109097; 0.137931034; 58; [0.0783959976,0.0818186177]; 3.40686372e-07 | MAINTAINED |
| full_vs_no_SA | up_rmse_m | 0.0380840646; 0.0443622921; 541; [0.0380840646,0.0380840646]; 2.19644467e-64 | 0.0380840646; 0.0327868852; 61; [0.0380838404,0.0380844581]; 3.13228929e-09 | -0.00103916791; 0.918032787; 61; [-0.00111705591,-0.00102188859]; 3.75701687e-09 | 0.00357406364; 0.0517241379; 58; [0.00357403958,0.00358223696]; 7.85337363e-08 | FLIPPED |
| full_vs_no_SA | position_3d_rmse_m | 0.0360197674; 0.0794824399; 541; [0.0360197674,0.0360197674]; 3.07955451e-52 | 0.0360197674; 0.0819672131; 61; [0.0360197674,0.0360259592]; 3.17855619e-07 | -9.78354249e-05; 0.852459016; 61; [-0.000658727771,-6.38064876e-05]; 8.56516051e-06 | 0.00355389375; 0.0862068966; 58; [0.00355197549,0.0036699021]; 3.1926963e-06 | FLIPPED |
| full_vs_no_RP | horizontal_rmse_m | -4.07390017e-05; 0.84103512; 541; [-4.99846469e-05,-4.01987886e-05]; 1.18430494e-44 | -4.01841838e-05; 0.868852459; 61; [-7.05062525e-05,-4.01626204e-05]; 9.3828845e-07 | -0.00101415959; 0.93442623; 61; [-0.00103160321,-0.0010131118]; 1.53774083e-07 | -2.68470565e-05; 0.833333333; 60; [-3.11606054e-05,-1.86660005e-05]; 0.000245617907 | MAINTAINED |
| full_vs_no_RP | yaw_rmse_deg | -0.0210870956; 0.902033272; 541; [-0.0210953579,-0.0209981207]; 1.6739098e-55 | -0.0210942775; 0.93442623; 61; [-0.0210953579,-0.0209343118]; 1.02356559e-10 | -0.0398979512; 0.967213115; 61; [-0.0399094918,-0.0381245248]; 2.64846994e-09 | -0.00159056139; 0.8; 60; [-0.00261617519,-0.00106860079]; 0.000345664434 | MAINTAINED |
| full_vs_no_RP | yaw_p95_absolute_deg | -0.0219845987; 0.894639556; 541; [-0.0219845987,-0.0219259877]; 7.64783956e-52 | -0.0219845987; 0.93442623; 61; [-0.0224603881,-0.0219555269]; 6.28184685e-10 | -0.129834572; 0.967213115; 61; [-0.130098934,-0.126166067]; 2.89126743e-09 | -0.00211097958; 0.716666667; 60; [-0.00244129788,-0.000983055676]; 0.00469274538 | MAINTAINED |
| full_vs_no_RP | up_rmse_m | -2.7181134e-05; 0.931608133; 541; [-2.74915178e-05,-2.70504997e-05]; 1.77537897e-68 | -2.7048843e-05; 0.918032787; 61; [-2.74915178e-05,-2.7048843e-05]; 3.78584039e-08 | 0.000596333114; 0.213114754; 61; [0.000476088456,0.000598220785]; 0.00304221674 | 1.67043108e-06; 0.283333333; 60; [1.2880881e-06,1.89579631e-06]; 0.323816552 | FLIPPED |
| full_vs_no_RP | position_3d_rmse_m | -4.19633785e-05; 0.898336414; 541; [-4.45033383e-05,-4.03971425e-05]; 4.8357464e-58 | -4.03689834e-05; 0.918032787; 61; [-4.6343742e-05,-4.03689834e-05]; 2.96188689e-08 | -0.000648565637; 0.93442623; 61; [-0.000819952863,-0.000643868429]; 9.98441309e-08 | -1.00836344e-05; 0.783333333; 60; [-1.1497434e-05,-5.85284384e-06]; 0.000168219537 | MAINTAINED |
| full_vs_no_HV | horizontal_rmse_m | 2.14494236e-05; 0.306839187; 541; [1.95786255e-05,2.16270003e-05]; 0.00381054317 | 2.1100796e-05; 0.327868852; 61; [1.35277688e-05,2.17110674e-05]; 0.248793197 | -6.52794817e-05; 0.852459016; 61; [-6.90918574e-05,-6.51943373e-05]; 1.94124407e-07 | -2.41605409e-05; 0.93442623; 61; [-2.53599564e-05,-2.39592673e-05]; 7.56128035e-08 | FLIPPED |
| full_vs_no_HV | yaw_rmse_deg | -0.000165616345; 0.896487985; 541; [-0.000166408172,-0.000165601818]; 2.49590454e-58 | -0.0001660577; 0.901639344; 61; [-0.000182206436,-0.000165601818]; 2.0178155e-09 | -1.82384767e-05; 0.93442623; 61; [-2.07323195e-05,-1.81862344e-05]; 1.86100405e-09 | 3.65379051e-05; 0.147540984; 61; [3.63347682e-05,4.97169461e-05]; 1.2169545e-06 | MAINTAINED |
| full_vs_no_HV | yaw_p95_absolute_deg | -0.00040647315; 0.890942699; 541; [-0.000413083331,-0.000389266519]; 3.78294257e-59 | -0.000413083331; 0.950819672; 61; [-0.000413083331,-0.000370317087]; 3.97395688e-10 | 2.462515e-05; 0.278688525; 61; [1.09627e-05,3.53898968e-05]; 0.113172508 | 8.91938456e-05; 0.393442623; 61; [-2.159675e-05,0.000145081906]; 0.00777453717 | FLIPPED |
| full_vs_no_HV | up_rmse_m | -1.13401228e-07; 0.861367837; 541; [-1.1341926e-07,-1.13401228e-07]; 2.37603726e-39 | -1.13401228e-07; 0.803278689; 61; [-1.13401228e-07,-1.08116956e-07]; 0.00136868001 | 1.23807784e-07; 0.229508197; 61; [1.17805881e-07,1.23987852e-07]; 0.012799875 | 6.57770724e-08; 0.180327869; 61; [6.50008248e-08,8.50707758e-08]; 0.00010317387 | FLIPPED |
| full_vs_no_HV | position_3d_rmse_m | 8.12699259e-06; 0.306839187; 541; [7.75082299e-06,8.18281033e-06]; 0.0342448254 | 7.96593588e-06; 0.327868852; 61; [5.09149981e-06,8.21342782e-06]; 0.282713257 | -5.83757799e-05; 0.868852459; 61; [-6.18572438e-05,-5.83598157e-05]; 1.8153144e-08 | -9.791694e-06; 0.93442623; 61; [-1.0569223e-05,-9.71282266e-06]; 1.12392262e-07 | FLIPPED |
| full_vs_no_Go2 | horizontal_rmse_m | -2.64380607e-05; 0.835489834; 541; [-2.91712614e-05,-1.85897728e-05]; 6.44798605e-40 | -2.64380607e-05; 0.868852459; 61; [-4.91892559e-05,-1.82166467e-05]; 1.86403689e-06 | -0.00107371563; 0.93442623; 61; [-0.00115425429,-0.00107114567]; 1.36770112e-07 | -4.82963568e-05; 0.85; 60; [-5.43855909e-05,-4.26853883e-05]; 1.54554274e-05 | MAINTAINED |
| full_vs_no_Go2 | yaw_rmse_deg | -0.0213012358; 0.903881701; 541; [-0.0213621189,-0.0212096378]; 1.19360692e-55 | -0.0213625821; 0.93442623; 61; [-0.0213636681,-0.0212144541]; 9.76050937e-11 | -0.0399232671; 0.983606557; 61; [-0.0399268695,-0.0385420925]; 1.81908934e-10 | -0.00151073493; 0.766666667; 60; [-0.00251715326,-0.000972485242]; 0.00154497348 | MAINTAINED |
| full_vs_no_Go2 | yaw_p95_absolute_deg | -0.0224527402; 0.898336414; 541; [-0.0224614382,-0.0222391199]; 2.84331435e-52 | -0.0224614382; 0.93442623; 61; [-0.022816965,-0.0224502778]; 5.47845657e-10 | -0.129755516; 0.983606557; 61; [-0.13002151,-0.126365456]; 1.99770542e-10 | -0.00201756741; 0.716666667; 60; [-0.00212522623,-0.000866171636]; 0.0148030801 | MAINTAINED |
| full_vs_no_Go2 | up_rmse_m | -2.73721076e-05; 0.926062847; 541; [-2.77014167e-05,-2.72580176e-05]; 2.30763499e-66 | -2.72550391e-05; 0.885245902; 61; [-2.77014167e-05,-2.72550391e-05]; 5.31219681e-06 | 0.000596462893; 0.196721311; 61; [0.000531676112,0.000598278305]; 0.000687576913 | 1.72352306e-06; 0.283333333; 60; [1.3943172e-06,1.95306412e-06]; 0.289019258 | FLIPPED |
| full_vs_no_Go2 | position_3d_rmse_m | -3.58637777e-05; 0.885397412; 541; [-3.69353851e-05,-3.29360116e-05]; 2.70078839e-62 | -3.24043036e-05; 0.918032787; 61; [-4.88154656e-05,-3.21537926e-05]; 1.04465742e-08 | -0.000698311164; 0.918032787; 61; [-0.000778917262,-0.000696004533]; 9.78261858e-07 | -1.94795543e-05; 0.866666667; 60; [-2.19158121e-05,-1.55782178e-05]; 1.35179978e-05 | MAINTAINED |
| RD_only_vs_strong | horizontal_rmse_m | -0.000104880751; 0.911275416; 541; [-0.000106522691,-0.000104580293]; 9.23298588e-63 | -0.000104724693; 0.885245902; 61; [-0.000261334973,-0.000104580293]; 3.01000449e-08 | -0.000156716609; 0.711864407; 59; [-0.000156716609,-0.00014420666]; 0.117896967 | -0.000276725746; 0.915254237; 59; [-0.000363893421,-0.00027250041]; 8.18286635e-10 | UNAVAILABLE_INCOMPLETE_PAIRS |
| RD_only_vs_strong | yaw_rmse_deg | -0.00576981919; 0.905730129; 541; [-0.00576981919,-0.00576981919]; 6.90889886e-50 | -0.00576981919; 0.901639344; 61; [-0.00576981919,-0.0057688094]; 3.83047965e-06 | -0.000299726959; 0.711864407; 59; [-0.000299747778,-0.000226886582]; 0.410293313 | -0.000836670249; 0.830508475; 59; [-0.000836942676,-0.000808680249]; 0.000675671643 | UNAVAILABLE_INCOMPLETE_PAIRS |
| RD_only_vs_strong | yaw_p95_absolute_deg | -0.00656761085; 0.885397412; 541; [-0.0065754886,-0.00656761085]; 2.75558237e-46 | -0.00656761085; 0.885245902; 61; [-0.00765462193,-0.00656761085]; 7.33457233e-06 | -0.00278396088; 0.830508475; 59; [-0.00361180812,-0.00278394988]; 0.000279670961 | -0.00045570213; 0.593220339; 59; [-0.00045570213,0.000379745431]; 0.60221306 | UNAVAILABLE_INCOMPLETE_PAIRS |
| RD_only_vs_strong | up_rmse_m | -0.000155076034; 0.970425139; 541; [-0.000155076477,-0.000155076034]; 8.96740541e-80 | -0.000155076034; 0.967213115; 61; [-0.00016188886,-0.000155076034]; 1.56957434e-09 | 0.0015865643; 0.118644068; 59; [0.00158646289,0.00158664354]; 1.23832846e-07 | -0.000134631158; 0.966101695; 59; [-0.000144153977,-0.000134631158]; 2.64091539e-09 | UNAVAILABLE_INCOMPLETE_PAIRS |
| RD_only_vs_strong | position_3d_rmse_m | -0.000183931121; 0.940850277; 541; [-0.000184761322,-0.000183805291]; 6.27561139e-77 | -0.000184253777; 0.93442623; 61; [-0.000301458351,-0.000183805291]; 1.14122974e-10 | 0.000557089542; 0.169491525; 59; [0.000557089542,0.00056347964]; 0.000103296077 | -0.000237107342; 0.915254237; 59; [-0.000297395975,-0.000234378135]; 5.85756293e-10 | UNAVAILABLE_INCOMPLETE_PAIRS |
| SA_only_vs_strong | horizontal_rmse_m | 0.00241737814; 0.160813309; 541; [0.00241737814,0.00241737814]; 6.93436491e-31 | 0.00241737814; 0.196721311; 61; [0.00239796886,0.00241737814]; 7.98197264e-05 | 0.000102978445; 0.254237288; 59; [9.49390971e-05,0.000102978445]; 0.0193872061 | 0.000585026584; 0.13559322; 59; [0.000585026584,0.000651496806]; 6.15657768e-07 | UNAVAILABLE_INCOMPLETE_PAIRS |
| SA_only_vs_strong | yaw_rmse_deg | 0.0183235093; 0.146025878; 541; [0.0183235093,0.0183235093]; 2.13088217e-32 | 0.0183235093; 0.196721311; 61; [0.0183220797,0.0183235093]; 0.00381634125 | -0.00907311798; 0.86440678; 59; [-0.00914476719,-0.00907311798]; 5.05465436e-06 | 0.0241365641; 0.169491525; 59; [0.0226742098,0.0241365641]; 6.04838382e-06 | UNAVAILABLE_INCOMPLETE_PAIRS |
| SA_only_vs_strong | yaw_p95_absolute_deg | -0.0344221917; 0.763401109; 541; [-0.0344221917,-0.0344221917]; 1.52809191e-21 | -0.0344221917; 0.803278689; 61; [-0.0344221917,-0.0344221917]; 1.61481236e-05 | -0.00893609066; 0.86440678; 59; [-0.00971148785,-0.00893609066]; 5.33536102e-05 | 0.0799297161; 0.152542373; 59; [0.0785698983,0.0799297161]; 2.01731384e-06 | UNAVAILABLE_INCOMPLETE_PAIRS |
| SA_only_vs_strong | up_rmse_m | 0.03801635; 0.0443622921; 541; [0.03801635,0.03801635]; 3.27231247e-66 | 0.03801635; 0.0327868852; 61; [0.03801635,0.03801635]; 2.8358514e-09 | -1.52090211e-05; 0.949152542; 59; [-1.52424315e-05,-1.52090211e-05]; 4.48848959e-08 | 0.00351548461; 0.0338983051; 59; [0.00351548461,0.00351576893]; 4.12573851e-09 | UNAVAILABLE_INCOMPLETE_PAIRS |
| SA_only_vs_strong | position_3d_rmse_m | 0.0359570208; 0.0794824399; 541; [0.0359570208,0.0359570208]; 1.78052202e-52 | 0.0359570208; 0.0819672131; 61; [0.0359570208,0.0359570208]; 3.06482905e-07 | 8.62049861e-05; 0.254237288; 59; [7.74591542e-05,8.62049861e-05]; 0.0117490563 | 0.00344787759; 0.0677966102; 59; [0.00344787759,0.00354524031]; 1.64156222e-07 | UNAVAILABLE_INCOMPLETE_PAIRS |

### 新链 v2

| 配对 | 指标 | Canonical_full_frozen | subset_frozen | subset_CAL | subset_V2S | 判定 |
|---|---|---|---|---|---|---|
| full_vs_strong | horizontal_rmse_m | 0.00228543093; 0.175600739; 541; [0.00228543093,0.00228543093]; 5.9583509e-24 | 0.00228543093; 0.213114754; 61; [0.00228202775,0.00229006282]; 0.000960754765 | 0.0038445487; 0.237288136; 59; [0.00330768536,0.00388569811]; 0.00196614953 | 0.00014956651; 0.166666667; 60; [0.000148811763,0.000160509568]; 0.00158454097 | UNAVAILABLE_INCOMPLETE_PAIRS |
| full_vs_strong | yaw_rmse_deg | -0.00745429261; 0.704251386; 541; [-0.00745429261,-0.00745429261]; 3.14929086e-08 | -0.00745429261; 0.704918033; 61; [-0.00797647268,-0.00745402696]; 0.00512955452 | -0.0471730735; 0.966101695; 59; [-0.0473415943,-0.0471729864]; 7.61030925e-10 | 0.0220003401; 0.2; 60; [0.0209441605,0.0220370753]; 0.000260144843 | UNAVAILABLE_INCOMPLETE_PAIRS |
| full_vs_strong | yaw_p95_absolute_deg | -0.0615004271; 0.829944547; 541; [-0.0615007489,-0.0611049015]; 1.59223407e-40 | -0.0615007489; 0.901639344; 61; [-0.0615768242,-0.0562693839]; 2.72811547e-08 | -0.139544455; 0.966101695; 59; [-0.140083635,-0.139524397]; 3.88592099e-10 | 0.080427137; 0.2; 60; [0.0784578048,0.08044507]; 0.000168219537 | UNAVAILABLE_INCOMPLETE_PAIRS |
| full_vs_strong | up_rmse_m | 0.0378981759; 0.0443622921; 541; [0.0378981759,0.0378981924]; 3.90115751e-64 | 0.0378981759; 0.0327868852; 61; [0.0378978798,0.0378985352]; 3.13228929e-09 | 0.00123252211; 0.169491525; 59; [0.00122864505,0.00123257526]; 0.000160165512 | 0.00254538798; 0.0833333333; 60; [0.00254534198,0.00254632967]; 2.93208749e-06 | UNAVAILABLE_INCOMPLETE_PAIRS |
| full_vs_strong | position_3d_rmse_m | 0.0357973187; 0.0905730129; 541; [0.0357973187,0.0357976536]; 2.69437477e-50 | 0.0357973187; 0.0983606557; 61; [0.0357973187,0.0358027823]; 1.79870055e-06 | 0.00284980938; 0.220338983; 59; [0.00263424113,0.00285006653]; 0.0032367742 | 0.00238850565; 0.133333333; 60; [0.00238832718,0.00239948342]; 0.000317582542 | UNAVAILABLE_INCOMPLETE_PAIRS |
| strong_vs_basic | horizontal_rmse_m | -0.00300896966; 0.95194085; 541; [-0.00301441428,-0.00300896966]; 1.36108028e-80 | -0.00300896966; 0.950819672; 61; [-0.00485083559,-0.00300896966]; 1.29276272e-11 | -0.00124295486; 0.881355932; 59; [-0.00183195655,-0.00124295486]; 6.40275081e-07 | -0.00122163661; 0.9; 60; [-0.00137949888,-0.00122163661]; 4.37582846e-08 | UNAVAILABLE_INCOMPLETE_PAIRS |
| strong_vs_basic | yaw_rmse_deg | -0.376013308; 0.883548983; 541; [-0.376013308,-0.376013308]; 2.49579938e-35 | -0.376013308; 0.868852459; 61; [-0.376013308,-0.375990318]; 0.000376758049 | -0.23774278; 0.966101695; 59; [-0.239050706,-0.23774278]; 4.73146139e-09 | -0.231465162; 0.866666667; 60; [-0.232637676,-0.231465162]; 1.50258867e-06 | UNAVAILABLE_INCOMPLETE_PAIRS |
| strong_vs_basic | yaw_p95_absolute_deg | -0.891389443; 0.878003697; 541; [-0.891496425,-0.889125935]; 3.16079211e-34 | -0.891496425; 0.868852459; 61; [-0.891496425,-0.885073218]; 0.000376758049 | -0.509628324; 0.966101695; 59; [-0.51127715,-0.509628324]; 3.94180911e-09 | -0.21090527; 0.833333333; 60; [-0.215967089,-0.21090527]; 3.59536373e-05 | UNAVAILABLE_INCOMPLETE_PAIRS |
| strong_vs_basic | up_rmse_m | -0.00144498798; 0.957486137; 541; [-0.00144498798,-0.00144498798]; 8.54812244e-73 | -0.00144498798; 0.93442623; 61; [-0.00146276838,-0.00144498798]; 1.79170264e-08 | -0.000593793122; 0.915254237; 59; [-0.000618396254,-0.000593793122]; 3.38427366e-10 | -0.000885413867; 0.933333333; 60; [-0.000965632266,-0.000885315922]; 4.02552024e-08 | UNAVAILABLE_INCOMPLETE_PAIRS |
| strong_vs_basic | position_3d_rmse_m | -0.00252069135; 0.964879852; 541; [-0.00252728735,-0.00252069135]; 3.2238981e-79 | -0.00252069135; 0.983606557; 61; [-0.00324970181,-0.00252069135]; 1.05884582e-11 | -0.00108742234; 0.898305085; 59; [-0.00191764092,-0.00108742234]; 6.92259259e-07 | -0.00130504172; 0.916666667; 60; [-0.00153198761,-0.00130504172]; 3.55052209e-08 | UNAVAILABLE_INCOMPLETE_PAIRS |
| basic_vs_single | horizontal_rmse_m | 0.000955679258; 0.11090573; 541; [0.000955679258,0.000973518468]; 1.10321011e-49 | 0.000955679258; 0.131147541; 61; [0.000955679258,0.000999868481]; 9.49649274e-07 | -0.00171299722; 0.573770492; 61; [-0.00171299722,0.00535249011]; 0.0781177584 | 0.000542702153; 0.163934426; 61; [0.000542702153,0.000673031257]; 1.56298095e-05 | FLIPPED |
| basic_vs_single | yaw_rmse_deg | -4.58886114; 0.964879852; 541; [-4.58886114,-4.58886114]; 1.84682934e-73 | -4.58886114; 0.967213115; 61; [-4.58886114,-4.57643731]; 2.27765733e-09 | -5.7021454; 0.93442623; 61; [-5.7021454,-5.67704997]; 3.55809066e-10 | -5.6997019; 0.93442623; 61; [-5.70004446,-5.66393572]; 2.94987593e-07 | MAINTAINED |
| basic_vs_single | yaw_p95_absolute_deg | -7.3757816; 0.970425139; 541; [-7.3757816,-7.3757816]; 2.6117595e-78 | -7.3757816; 0.967213115; 61; [-7.3757816,-7.3757816]; 1.84864125e-10 | -7.62091848; 0.967213115; 61; [-7.62091848,-7.59399244]; 2.03415313e-10 | -8.37943197; 0.93442623; 61; [-8.3795384,-8.30922198]; 2.94987593e-07 | MAINTAINED |
| basic_vs_single | up_rmse_m | 0.00150038263; 0.0665434381; 541; [0.00150038263,0.00150038263]; 4.78551081e-60 | 0.00150038263; 0.114754098; 61; [0.00150038263,0.00150039574]; 3.86361275e-05 | 0.000610190566; 0.0819672131; 61; [0.000610190566,0.00100549528]; 1.46306642e-10 | 0.000941283543; 0.0819672131; 61; [0.000941283543,0.00100721709]; 2.34277197e-07 | MAINTAINED |
| basic_vs_single | position_3d_rmse_m | 0.00175677013; 0.0831792976; 541; [0.00175677013,0.00176311199]; 2.33764826e-57 | 0.00175677013; 0.0819672131; 61; [0.00175677013,0.00189499393]; 1.31377555e-07 | -0.000227890902; 0.573770492; 61; [-0.000227890902,0.00337215454]; 0.0521555614 | 0.00108062517; 0.147540984; 61; [0.00108062517,0.00108297822]; 4.36031629e-06 | FLIPPED |
| full_vs_no_RD | horizontal_rmse_m | -0.000116055031; 0.939001848; 541; [-0.000118697146,-0.000115736295]; 3.52908985e-73 | -0.000116085315; 0.918032787; 61; [-0.000221750361,-0.000115701801]; 4.56155126e-10 | 0.000179760181; 0.262295082; 61; [0.000179651383,0.000186805704]; 0.2518517 | -7.68214926e-05; 0.901639344; 61; [-0.000121157662,-7.64939634e-05]; 7.59452911e-10 | FLIPPED |
| full_vs_no_RD | yaw_rmse_deg | -0.00415198457; 0.896487985; 541; [-0.00415198457,-0.00415197404]; 3.6739121e-49 | -0.00415198457; 0.918032787; 61; [-0.00415198457,-0.00413073389]; 3.99016101e-07 | 0.00194353795; 0.37704918; 61; [2.50285413e-05,0.00207139616]; 0.997133966 | 0.000130536486; 0.426229508; 61; [-0.000316465909,0.00016738903]; 0.402622243 | FLIPPED |
| full_vs_no_RD | yaw_p95_absolute_deg | -0.00443364659; 0.842883549; 541; [-0.00444647898,-0.00443364659]; 2.19344189e-40 | -0.00443364659; 0.819672131; 61; [-0.00489517893,-0.00443364659]; 4.8353643e-05 | -0.00122181651; 0.737704918; 61; [-0.00219221469,-0.000716534359]; 0.00127269304 | 0.00325953526; 0.344262295; 61; [0.00167461963,0.00334718769]; 0.22607934 | MAINTAINED |
| full_vs_no_RD | up_rmse_m | -8.70445816e-05; 0.959334566; 541; [-8.7181237e-05,-8.70262892e-05]; 1.45728356e-75 | -8.71661931e-05; 0.93442623; 61; [-8.99140074e-05,-8.70244549e-05]; 1.4138682e-07 | 0.000157723325; 0.245901639; 61; [0.000156519952,0.000157793342]; 0.0141525134 | -3.96869693e-05; 0.93442623; 61; [-5.69148295e-05,-3.96506197e-05]; 1.60175824e-08 | FLIPPED |
| full_vs_no_RD | position_3d_rmse_m | -0.000124872258; 0.953789279; 541; [-0.000127622444,-0.000124743331]; 7.87648961e-79 | -0.000124893091; 0.967213115; 61; [-0.000192511988,-0.000124705377]; 9.76050937e-11 | 0.000222116446; 0.196721311; 61; [0.000221506787,0.000223985521]; 0.0446480854 | -6.72811365e-05; 0.918032787; 61; [-0.000103794543,-6.71523919e-05]; 5.78121479e-10 | FLIPPED |
| full_vs_no_SA | horizontal_rmse_m | 0.00241615363; 0.15896488; 541; [0.00241615363,0.00241615363]; 1.77542712e-30 | 0.00241615363; 0.196721311; 61; [0.00240446466,0.00242469005]; 0.000218178835 | -0.000532429456; 0.819672131; 61; [-0.000533411822,-0.000514556255]; 4.15787944e-05 | 0.000449588513; 0.137931034; 58; [0.000448979871,0.00045522724]; 8.02870278e-06 | FLIPPED |
| full_vs_no_SA | yaw_rmse_deg | 0.0208833687; 0.131238447; 541; [0.0208833687,0.0208842883]; 3.76794361e-33 | 0.0208804625; 0.147540984; 61; [0.0197943374,0.0208833687]; 0.00143853907 | -0.0136462642; 0.885245902; 61; [-0.0136645633,-0.0136025664]; 9.78261858e-07 | 0.0246903745; 0.155172414; 58; [0.0244995457,0.0249011716]; 7.63218271e-07 | FLIPPED |
| full_vs_no_SA | yaw_p95_absolute_deg | -0.0293945312; 0.752310536; 541; [-0.0293945312,-0.0293935612]; 3.41372318e-18 | -0.0293945312; 0.852459016; 61; [-0.0306387744,-0.0293945312]; 3.16442216e-06 | -0.0050567741; 0.770491803; 61; [-0.00526835092,-0.00489625607]; 0.0015150853 | 0.0818109097; 0.137931034; 58; [0.0783959976,0.0818186177]; 3.40686372e-07 | MAINTAINED |
| full_vs_no_SA | up_rmse_m | 0.0380840646; 0.0443622921; 541; [0.0380840646,0.0380840646]; 2.19644467e-64 | 0.0380840646; 0.0327868852; 61; [0.0380838404,0.0380844581]; 3.13228929e-09 | -0.000304779474; 0.918032787; 61; [-0.000319133602,-0.000300994306]; 1.74122692e-08 | 0.00261372095; 0.0517241379; 58; [0.00261367961,0.00263118565]; 7.52303217e-08 | FLIPPED |
| full_vs_no_SA | position_3d_rmse_m | 0.0360197674; 0.0794824399; 541; [0.0360197674,0.0360197674]; 3.07955451e-52 | 0.0360197674; 0.0819672131; 61; [0.0360197674,0.0360259592]; 3.17855619e-07 | -0.000510658655; 0.885245902; 61; [-0.000522329795,-0.000510007011]; 3.5819163e-07 | 0.00257265243; 0.0862068966; 58; [0.00257228698,0.00260375891]; 3.31495704e-06 | FLIPPED |
| full_vs_no_RP | horizontal_rmse_m | -4.07390017e-05; 0.84103512; 541; [-4.99846469e-05,-4.01987886e-05]; 1.18430494e-44 | -4.01841838e-05; 0.868852459; 61; [-7.05062525e-05,-4.01626204e-05]; 9.3828845e-07 | 0.00360148246; 0.213114754; 61; [0.00279036535,0.00367583271]; 3.34199929e-05 | -0.000110000167; 0.85; 60; [-0.000110312216,-0.000108803855]; 2.82867035e-06 | FLIPPED |
| full_vs_no_RP | yaw_rmse_deg | -0.0210870956; 0.902033272; 541; [-0.0210953579,-0.0209981207]; 1.6739098e-55 | -0.0210942775; 0.93442623; 61; [-0.0210953579,-0.0209343118]; 1.02356559e-10 | -0.0398979512; 0.967213115; 61; [-0.0399094918,-0.0381245248]; 2.64846994e-09 | -0.00159056139; 0.8; 60; [-0.00261617519,-0.00106860079]; 0.000345664434 | MAINTAINED |
| full_vs_no_RP | yaw_p95_absolute_deg | -0.0219845987; 0.894639556; 541; [-0.0219845987,-0.0219259877]; 7.64783956e-52 | -0.0219845987; 0.93442623; 61; [-0.0224603881,-0.0219555269]; 6.28184685e-10 | -0.129834572; 0.967213115; 61; [-0.130098934,-0.126166067]; 2.89126743e-09 | -0.00211097958; 0.716666667; 60; [-0.00244129788,-0.000983055676]; 0.00469274538 | MAINTAINED |
| full_vs_no_RP | up_rmse_m | -2.7181134e-05; 0.931608133; 541; [-2.74915178e-05,-2.70504997e-05]; 1.77537897e-68 | -2.7048843e-05; 0.918032787; 61; [-2.74915178e-05,-2.7048843e-05]; 3.78584039e-08 | 0.00107225112; 0.147540984; 61; [0.00107072556,0.00107240601]; 0.000106266263 | -1.80430541e-06; 0.816666667; 60; [-2.12557928e-06,-1.72654194e-06]; 0.000267706791 | FLIPPED |
| full_vs_no_RP | position_3d_rmse_m | -4.19633785e-05; 0.898336414; 541; [-4.45033383e-05,-4.03971425e-05]; 4.8357464e-58 | -4.03689834e-05; 0.918032787; 61; [-4.6343742e-05,-4.03689834e-05]; 2.96188689e-08 | 0.00258558894; 0.196721311; 61; [0.00224450538,0.00261315204]; 0.000341925504 | -4.60952286e-05; 0.833333333; 60; [-4.61175705e-05,-4.58506591e-05]; 6.58620777e-05 | FLIPPED |
| full_vs_no_HV | horizontal_rmse_m | 2.14494236e-05; 0.306839187; 541; [1.95786255e-05,2.16270003e-05]; 0.00381054317 | 2.1100796e-05; 0.327868852; 61; [1.35277688e-05,2.17110674e-05]; 0.248793197 | -4.67075757e-05; 0.901639344; 61; [-5.51019188e-05,-4.64773525e-05]; 9.59712332e-08 | -1.89095913e-05; 0.93442623; 61; [-1.96168204e-05,-1.88620742e-05]; 7.26543375e-08 | FLIPPED |
| full_vs_no_HV | yaw_rmse_deg | -0.000165616345; 0.896487985; 541; [-0.000166408172,-0.000165601818]; 2.49590454e-58 | -0.0001660577; 0.901639344; 61; [-0.000182206436,-0.000165601818]; 2.0178155e-09 | -1.82384767e-05; 0.93442623; 61; [-2.07323195e-05,-1.81862344e-05]; 1.86100405e-09 | 3.65379051e-05; 0.147540984; 61; [3.63347682e-05,4.97169461e-05]; 1.2169545e-06 | MAINTAINED |
| full_vs_no_HV | yaw_p95_absolute_deg | -0.00040647315; 0.890942699; 541; [-0.000413083331,-0.000389266519]; 3.78294257e-59 | -0.000413083331; 0.950819672; 61; [-0.000413083331,-0.000370317087]; 3.97395688e-10 | 2.462515e-05; 0.278688525; 61; [1.09627e-05,3.53898968e-05]; 0.113172508 | 8.91938456e-05; 0.393442623; 61; [-2.159675e-05,0.000145081906]; 0.00777453717 | FLIPPED |
| full_vs_no_HV | up_rmse_m | -1.13401228e-07; 0.861367837; 541; [-1.1341926e-07,-1.13401228e-07]; 2.37603726e-39 | -1.13401228e-07; 0.803278689; 61; [-1.13401228e-07,-1.08116956e-07]; 0.00136868001 | -1.79773954e-07; 0.852459016; 61; [-2.36555171e-07,-1.58420323e-07]; 2.21330614e-05 | -1.10928437e-07; 0.819672131; 61; [-1.14327925e-07,-1.10856965e-07]; 0.0029719561 | MAINTAINED |
| full_vs_no_HV | position_3d_rmse_m | 8.12699259e-06; 0.306839187; 541; [7.75082299e-06,8.18281033e-06]; 0.0342448254 | 7.96593588e-06; 0.327868852; 61; [5.09149981e-06,8.21342782e-06]; 0.282713257 | -2.13851358e-05; 0.918032787; 61; [-2.67561351e-05,-2.12456064e-05]; 1.00835967e-08 | -7.75885523e-06; 0.93442623; 61; [-8.99103157e-06,-7.71410251e-06]; 9.59712332e-08 | FLIPPED |
| full_vs_no_Go2 | horizontal_rmse_m | -2.64380607e-05; 0.835489834; 541; [-2.91712614e-05,-1.85897728e-05]; 6.44798605e-40 | -2.64380607e-05; 0.868852459; 61; [-4.91892559e-05,-1.82166467e-05]; 1.86403689e-06 | 0.00353649691; 0.213114754; 61; [0.00270585054,0.00362891858]; 0.000134348792 | -0.000128900461; 0.883333333; 60; [-0.000129379379,-0.000127779541]; 2.26443013e-07 | FLIPPED |
| full_vs_no_Go2 | yaw_rmse_deg | -0.0213012358; 0.903881701; 541; [-0.0213621189,-0.0212096378]; 1.19360692e-55 | -0.0213625821; 0.93442623; 61; [-0.0213636681,-0.0212144541]; 9.76050937e-11 | -0.0399232671; 0.983606557; 61; [-0.0399268695,-0.0385420925]; 1.81908934e-10 | -0.00151073493; 0.766666667; 60; [-0.00251715326,-0.000972485242]; 0.00154497348 | MAINTAINED |
| full_vs_no_Go2 | yaw_p95_absolute_deg | -0.0224527402; 0.898336414; 541; [-0.0224614382,-0.0222391199]; 2.84331435e-52 | -0.0224614382; 0.93442623; 61; [-0.022816965,-0.0224502778]; 5.47845657e-10 | -0.129755516; 0.983606557; 61; [-0.13002151,-0.126365456]; 1.99770542e-10 | -0.00201756741; 0.716666667; 60; [-0.00212522623,-0.000866171636]; 0.0148030801 | MAINTAINED |
| full_vs_no_Go2 | up_rmse_m | -2.73721076e-05; 0.926062847; 541; [-2.77014167e-05,-2.72580176e-05]; 2.30763499e-66 | -2.72550391e-05; 0.885245902; 61; [-2.77014167e-05,-2.72550391e-05]; 5.31219681e-06 | 0.00107202303; 0.131147541; 61; [0.00107054649,0.0010721084]; 1.60290833e-05 | -1.93578465e-06; 0.816666667; 60; [-2.25695466e-06,-1.85874232e-06]; 0.000300063579 | FLIPPED |
| full_vs_no_Go2 | position_3d_rmse_m | -3.58637777e-05; 0.885397412; 541; [-3.69353851e-05,-3.29360116e-05]; 2.70078839e-62 | -3.24043036e-05; 0.918032787; 61; [-4.88154656e-05,-3.21537926e-05]; 1.04465742e-08 | 0.00258409869; 0.180327869; 61; [0.00222739499,0.00259367869]; 7.21103549e-05 | -5.37754866e-05; 0.866666667; 60; [-5.41684421e-05,-5.34929391e-05]; 5.35569474e-06 | FLIPPED |
| RD_only_vs_strong | horizontal_rmse_m | -0.000104880751; 0.911275416; 541; [-0.000106522691,-0.000104580293]; 9.23298588e-63 | -0.000104724693; 0.885245902; 61; [-0.000261334973,-0.000104580293]; 3.01000449e-08 | 0.000320019166; 0.237288136; 59; [0.000320019166,0.00032105904]; 0.00429849879 | -0.000103272646; 0.898305085; 59; [-0.000143153148,-0.000102239274]; 1.99990646e-09 | UNAVAILABLE_INCOMPLETE_PAIRS |
| RD_only_vs_strong | yaw_rmse_deg | -0.00576981919; 0.905730129; 541; [-0.00576981919,-0.00576981919]; 6.90889886e-50 | -0.00576981919; 0.901639344; 61; [-0.00576981919,-0.0057688094]; 3.83047965e-06 | -0.000299726959; 0.711864407; 59; [-0.000299747778,-0.000226886582]; 0.410293313 | -0.000836670249; 0.830508475; 59; [-0.000836942676,-0.000808680249]; 0.000675671643 | UNAVAILABLE_INCOMPLETE_PAIRS |
| RD_only_vs_strong | yaw_p95_absolute_deg | -0.00656761085; 0.885397412; 541; [-0.0065754886,-0.00656761085]; 2.75558237e-46 | -0.00656761085; 0.885245902; 61; [-0.00765462193,-0.00656761085]; 7.33457233e-06 | -0.00278396088; 0.830508475; 59; [-0.00361180812,-0.00278394988]; 0.000279670961 | -0.00045570213; 0.593220339; 59; [-0.00045570213,0.000379745431]; 0.60221306 | UNAVAILABLE_INCOMPLETE_PAIRS |
| RD_only_vs_strong | up_rmse_m | -0.000155076034; 0.970425139; 541; [-0.000155076477,-0.000155076034]; 8.96740541e-80 | -0.000155076034; 0.967213115; 61; [-0.00016188886,-0.000155076034]; 1.56957434e-09 | 0.000291847382; 0.118644068; 59; [0.000291847382,0.000292883058]; 7.75196208e-06 | -6.71358207e-05; 0.949152542; 59; [-9.44185042e-05,-6.69891836e-05]; 3.03249753e-09 | UNAVAILABLE_INCOMPLETE_PAIRS |
| RD_only_vs_strong | position_3d_rmse_m | -0.000183931121; 0.940850277; 541; [-0.000184761322,-0.000183805291]; 6.27561139e-77 | -0.000184253777; 0.93442623; 61; [-0.000301458351,-0.000183805291]; 1.14122974e-10 | 0.000404179447; 0.169491525; 59; [0.000404087126,0.000408434734]; 0.000419215623 | -0.000103138852; 0.915254237; 59; [-0.00012290093,-0.000102671266]; 1.19504028e-09 | UNAVAILABLE_INCOMPLETE_PAIRS |
| SA_only_vs_strong | horizontal_rmse_m | 0.00241737814; 0.160813309; 541; [0.00241737814,0.00241737814]; 6.93436491e-31 | 0.00241737814; 0.196721311; 61; [0.00239796886,0.00241737814]; 7.98197264e-05 | 5.97474376e-05; 0.203389831; 59; [5.97474376e-05,5.97474376e-05]; 0.00756436682 | 0.000354987454; 0.13559322; 59; [0.000354987454,0.000356813746]; 6.9219593e-07 | UNAVAILABLE_INCOMPLETE_PAIRS |
| SA_only_vs_strong | yaw_rmse_deg | 0.0183235093; 0.146025878; 541; [0.0183235093,0.0183235093]; 2.13088217e-32 | 0.0183235093; 0.196721311; 61; [0.0183220797,0.0183235093]; 0.00381634125 | -0.00907311798; 0.86440678; 59; [-0.00914476719,-0.00907311798]; 5.05465436e-06 | 0.0241365641; 0.169491525; 59; [0.0226742098,0.0241365641]; 6.04838382e-06 | UNAVAILABLE_INCOMPLETE_PAIRS |
| SA_only_vs_strong | yaw_p95_absolute_deg | -0.0344221917; 0.763401109; 541; [-0.0344221917,-0.0344221917]; 1.52809191e-21 | -0.0344221917; 0.803278689; 61; [-0.0344221917,-0.0344221917]; 1.61481236e-05 | -0.00893609066; 0.86440678; 59; [-0.00971148785,-0.00893609066]; 5.33536102e-05 | 0.0799297161; 0.152542373; 59; [0.0785698983,0.0799297161]; 2.01731384e-06 | UNAVAILABLE_INCOMPLETE_PAIRS |
| SA_only_vs_strong | up_rmse_m | 0.03801635; 0.0443622921; 541; [0.03801635,0.03801635]; 3.27231247e-66 | 0.03801635; 0.0327868852; 61; [0.03801635,0.03801635]; 2.8358514e-09 | 8.01355012e-06; 0.237288136; 59; [7.85288871e-06,8.01355012e-06]; 0.0241477059 | 0.00258721542; 0.0338983051; 59; [0.00258721542,0.00259344398]; 3.5962068e-09 | UNAVAILABLE_INCOMPLETE_PAIRS |
| SA_only_vs_strong | position_3d_rmse_m | 0.0359570208; 0.0794824399; 541; [0.0359570208,0.0359570208]; 1.78052202e-52 | 0.0359570208; 0.0819672131; 61; [0.0359570208,0.0359570208]; 3.06482905e-07 | 3.38589294e-05; 0.203389831; 59; [3.38589294e-05,3.38589294e-05]; 0.00924596992 | 0.00250963233; 0.0677966102; 59; [0.00250963233,0.00251043269]; 1.93303676e-07 | UNAVAILABLE_INCOMPLETE_PAIRS |

## 翻转清单

| 配对 | 版本 | 指标 | 全量中位差 | CAL 中位差 | 中位差变化 | 全量胜率 | CAL 胜率 |
|---|---|---|---|---|---|---|---|
| basic_vs_single | v2 | horizontal_rmse_m | 0.000955679258 | -0.00171299722 | -0.00266867648 | 0.11090573 | 0.573770492 |
| full_vs_no_RD | v2 | horizontal_rmse_m | -0.000116055031 | 0.000179760181 | 0.000295815211 | 0.939001848 | 0.262295082 |
| full_vs_no_RD | v3 | yaw_rmse_deg | -0.00415198457 | 0.00194353795 | 0.00609552253 | 0.896487985 | 0.37704918 |
| full_vs_no_RD | v2 | yaw_rmse_deg | -0.00415198457 | 0.00194353795 | 0.00609552253 | 0.896487985 | 0.37704918 |
| full_vs_no_SA | v2 | horizontal_rmse_m | 0.00241615363 | -0.000532429456 | -0.00294858308 | 0.15896488 | 0.819672131 |
| full_vs_no_SA | v3 | yaw_rmse_deg | 0.0208833687 | -0.0136462642 | -0.0345296329 | 0.131238447 | 0.885245902 |
| full_vs_no_SA | v2 | yaw_rmse_deg | 0.0208833687 | -0.0136462642 | -0.0345296329 | 0.131238447 | 0.885245902 |
| full_vs_no_RP | v2 | horizontal_rmse_m | -4.07390017e-05 | 0.00360148246 | 0.00364222146 | 0.84103512 | 0.213114754 |
| full_vs_no_HV | v3 | horizontal_rmse_m | 2.14494236e-05 | -6.52794817e-05 | -8.67289053e-05 | 0.306839187 | 0.852459016 |
| full_vs_no_HV | v2 | horizontal_rmse_m | 2.14494236e-05 | -4.67075757e-05 | -6.81569992e-05 | 0.306839187 | 0.901639344 |
| full_vs_no_HV | v3 | yaw_p95_absolute_deg | -0.00040647315 | 2.462515e-05 | 0.0004310983 | 0.890942699 | 0.278688525 |
| full_vs_no_HV | v2 | yaw_p95_absolute_deg | -0.00040647315 | 2.462515e-05 | 0.0004310983 | 0.890942699 | 0.278688525 |
| full_vs_no_Go2 | v2 | horizontal_rmse_m | -2.64380607e-05 | 0.00353649691 | 0.00356293497 | 0.835489834 | 0.213114754 |

## 决定原文

```json
{
  "synthetic_data_used": false,
  "semisynthetic_data_used": false,
  "trace_used_online": false,
  "receiver_imu_as_body_imu": false,
  "final_v23_output_solver_input": false,
  "LegSA_output_solver_input": false,
  "per_case_tuning": false,
  "output_only_correction": false,
  "epoch_deleted_for_metric": false,
  "old_runtime_input_count": 0,
  "data_mode": "real_base_controlled_degradation",
  "code_commit": "24cc761e4085561888a9d8546df8b89300d340fe",
  "decision": "HUMAN_DECISION_REQUIRED",
  "selected_case_count": 61,
  "excluded_case_count": 480,
  "NOT_TRANSFERABLE": [],
  "primary_pair_version_count": 60,
  "maintained_primary_pair_version_count": 23,
  "unavailable_primary_pair_version_count": 24,
  "flip_count": 13,
  "flips": [
    {
      "comparison": "basic_vs_single",
      "metric_name": "horizontal_rmse_m",
      "evaluator_version": "v2",
      "canonical_median_delta": 0.0009556792577567474,
      "canonical_win_rate": 0.11090573012939002,
      "CAL_median_delta": -0.0017129972233906887,
      "CAL_win_rate": 0.5737704918032787,
      "median_delta_change": -0.002668676481147436
    },
    {
      "comparison": "full_vs_no_RD",
      "metric_name": "horizontal_rmse_m",
      "evaluator_version": "v2",
      "canonical_median_delta": -0.00011605503064815448,
      "canonical_win_rate": 0.9390018484288355,
      "CAL_median_delta": 0.00017976018076948375,
      "CAL_win_rate": 0.26229508196721313,
      "median_delta_change": 0.0002958152114176382
    },
    {
      "comparison": "full_vs_no_RD",
      "metric_name": "yaw_rmse_deg",
      "evaluator_version": "v3",
      "canonical_median_delta": -0.004151984573495415,
      "canonical_win_rate": 0.8964879852125693,
      "CAL_median_delta": 0.0019435379541037356,
      "CAL_win_rate": 0.3770491803278688,
      "median_delta_change": 0.006095522527599151
    },
    {
      "comparison": "full_vs_no_RD",
      "metric_name": "yaw_rmse_deg",
      "evaluator_version": "v2",
      "canonical_median_delta": -0.004151984573495415,
      "canonical_win_rate": 0.8964879852125693,
      "CAL_median_delta": 0.0019435379541037356,
      "CAL_win_rate": 0.3770491803278688,
      "median_delta_change": 0.006095522527599151
    },
    {
      "comparison": "full_vs_no_SA",
      "metric_name": "horizontal_rmse_m",
      "evaluator_version": "v2",
      "canonical_median_delta": 0.0024161536265318584,
      "canonical_win_rate": 0.1589648798521257,
      "CAL_median_delta": -0.0005324294564514054,
      "CAL_win_rate": 0.819672131147541,
      "median_delta_change": -0.0029485830829832638
    },
    {
      "comparison": "full_vs_no_SA",
      "metric_name": "yaw_rmse_deg",
      "evaluator_version": "v3",
      "canonical_median_delta": 0.020883368661180235,
      "canonical_win_rate": 0.13123844731977818,
      "CAL_median_delta": -0.013646264202509695,
      "CAL_win_rate": 0.8852459016393442,
      "median_delta_change": -0.03452963286368993
    },
    {
      "comparison": "full_vs_no_SA",
      "metric_name": "yaw_rmse_deg",
      "evaluator_version": "v2",
      "canonical_median_delta": 0.020883368661180235,
      "canonical_win_rate": 0.13123844731977818,
      "CAL_median_delta": -0.013646264202509695,
      "CAL_win_rate": 0.8852459016393442,
      "median_delta_change": -0.03452963286368993
    },
    {
      "comparison": "full_vs_no_RP",
      "metric_name": "horizontal_rmse_m",
      "evaluator_version": "v2",
      "canonical_median_delta": -4.073900174900169e-05,
      "canonical_win_rate": 0.8410351201478743,
      "CAL_median_delta": 0.0036014824563236347,
      "CAL_win_rate": 0.21311475409836064,
      "median_delta_change": 0.0036422214580726364
    },
    {
      "comparison": "full_vs_no_HV",
      "metric_name": "horizontal_rmse_m",
      "evaluator_version": "v3",
      "canonical_median_delta": 2.1449423564523507e-05,
      "canonical_win_rate": 0.3068391866913124,
      "CAL_median_delta": -6.527948172478648e-05,
      "CAL_win_rate": 0.8524590163934426,
      "median_delta_change": -8.672890528930999e-05
    },
    {
      "comparison": "full_vs_no_HV",
      "metric_name": "horizontal_rmse_m",
      "evaluator_version": "v2",
      "canonical_median_delta": 2.1449423564523507e-05,
      "canonical_win_rate": 0.3068391866913124,
      "CAL_median_delta": -4.670757567093453e-05,
      "CAL_win_rate": 0.9016393442622951,
      "median_delta_change": -6.815699923545804e-05
    },
    {
      "comparison": "full_vs_no_HV",
      "metric_name": "yaw_p95_absolute_deg",
      "evaluator_version": "v3",
      "canonical_median_delta": -0.0004064731499866525,
      "canonical_win_rate": 0.8909426987060998,
      "CAL_median_delta": 2.462515003021082e-05,
      "CAL_win_rate": 0.2786885245901639,
      "median_delta_change": 0.00043109830001686333
    },
    {
      "comparison": "full_vs_no_HV",
      "metric_name": "yaw_p95_absolute_deg",
      "evaluator_version": "v2",
      "canonical_median_delta": -0.0004064731499866525,
      "canonical_win_rate": 0.8909426987060998,
      "CAL_median_delta": 2.462515003021082e-05,
      "CAL_win_rate": 0.2786885245901639,
      "median_delta_change": 0.00043109830001686333
    },
    {
      "comparison": "full_vs_no_Go2",
      "metric_name": "horizontal_rmse_m",
      "evaluator_version": "v2",
      "canonical_median_delta": -2.6438060716449385e-05,
      "canonical_win_rate": 0.8354898336414048,
      "CAL_median_delta": 0.0035364969124748458,
      "CAL_win_rate": 0.21311475409836064,
      "median_delta_change": 0.003562934973191295
    }
  ],
  "missing_evidence": [
    {
      "comparison": "full_vs_strong",
      "metric_name": "horizontal_rmse_m",
      "chain": "CAL",
      "evaluator_version": "v3",
      "case_ids": [
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "full_vs_strong",
      "metric_name": "horizontal_rmse_m",
      "chain": "V2S",
      "evaluator_version": "v3",
      "case_ids": [
        "D14_seed_00"
      ]
    },
    {
      "comparison": "full_vs_strong",
      "metric_name": "horizontal_rmse_m",
      "chain": "CAL",
      "evaluator_version": "v2",
      "case_ids": [
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "full_vs_strong",
      "metric_name": "horizontal_rmse_m",
      "chain": "V2S",
      "evaluator_version": "v2",
      "case_ids": [
        "D14_seed_00"
      ]
    },
    {
      "comparison": "full_vs_strong",
      "metric_name": "yaw_rmse_deg",
      "chain": "CAL",
      "evaluator_version": "v3",
      "case_ids": [
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "full_vs_strong",
      "metric_name": "yaw_rmse_deg",
      "chain": "V2S",
      "evaluator_version": "v3",
      "case_ids": [
        "D14_seed_00"
      ]
    },
    {
      "comparison": "full_vs_strong",
      "metric_name": "yaw_rmse_deg",
      "chain": "CAL",
      "evaluator_version": "v2",
      "case_ids": [
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "full_vs_strong",
      "metric_name": "yaw_rmse_deg",
      "chain": "V2S",
      "evaluator_version": "v2",
      "case_ids": [
        "D14_seed_00"
      ]
    },
    {
      "comparison": "full_vs_strong",
      "metric_name": "yaw_p95_absolute_deg",
      "chain": "CAL",
      "evaluator_version": "v3",
      "case_ids": [
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "full_vs_strong",
      "metric_name": "yaw_p95_absolute_deg",
      "chain": "V2S",
      "evaluator_version": "v3",
      "case_ids": [
        "D14_seed_00"
      ]
    },
    {
      "comparison": "full_vs_strong",
      "metric_name": "yaw_p95_absolute_deg",
      "chain": "CAL",
      "evaluator_version": "v2",
      "case_ids": [
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "full_vs_strong",
      "metric_name": "yaw_p95_absolute_deg",
      "chain": "V2S",
      "evaluator_version": "v2",
      "case_ids": [
        "D14_seed_00"
      ]
    },
    {
      "comparison": "strong_vs_basic",
      "metric_name": "horizontal_rmse_m",
      "chain": "CAL",
      "evaluator_version": "v3",
      "case_ids": [
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "strong_vs_basic",
      "metric_name": "horizontal_rmse_m",
      "chain": "V2S",
      "evaluator_version": "v3",
      "case_ids": [
        "D14_seed_00"
      ]
    },
    {
      "comparison": "strong_vs_basic",
      "metric_name": "horizontal_rmse_m",
      "chain": "CAL",
      "evaluator_version": "v2",
      "case_ids": [
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "strong_vs_basic",
      "metric_name": "horizontal_rmse_m",
      "chain": "V2S",
      "evaluator_version": "v2",
      "case_ids": [
        "D14_seed_00"
      ]
    },
    {
      "comparison": "strong_vs_basic",
      "metric_name": "yaw_rmse_deg",
      "chain": "CAL",
      "evaluator_version": "v3",
      "case_ids": [
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "strong_vs_basic",
      "metric_name": "yaw_rmse_deg",
      "chain": "V2S",
      "evaluator_version": "v3",
      "case_ids": [
        "D14_seed_00"
      ]
    },
    {
      "comparison": "strong_vs_basic",
      "metric_name": "yaw_rmse_deg",
      "chain": "CAL",
      "evaluator_version": "v2",
      "case_ids": [
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "strong_vs_basic",
      "metric_name": "yaw_rmse_deg",
      "chain": "V2S",
      "evaluator_version": "v2",
      "case_ids": [
        "D14_seed_00"
      ]
    },
    {
      "comparison": "strong_vs_basic",
      "metric_name": "yaw_p95_absolute_deg",
      "chain": "CAL",
      "evaluator_version": "v3",
      "case_ids": [
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "strong_vs_basic",
      "metric_name": "yaw_p95_absolute_deg",
      "chain": "V2S",
      "evaluator_version": "v3",
      "case_ids": [
        "D14_seed_00"
      ]
    },
    {
      "comparison": "strong_vs_basic",
      "metric_name": "yaw_p95_absolute_deg",
      "chain": "CAL",
      "evaluator_version": "v2",
      "case_ids": [
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "strong_vs_basic",
      "metric_name": "yaw_p95_absolute_deg",
      "chain": "V2S",
      "evaluator_version": "v2",
      "case_ids": [
        "D14_seed_00"
      ]
    },
    {
      "comparison": "full_vs_no_SA",
      "metric_name": "horizontal_rmse_m",
      "chain": "V2S",
      "evaluator_version": "v3",
      "case_ids": [
        "D14_seed_00",
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "full_vs_no_SA",
      "metric_name": "horizontal_rmse_m",
      "chain": "V2S",
      "evaluator_version": "v2",
      "case_ids": [
        "D14_seed_00",
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "full_vs_no_SA",
      "metric_name": "yaw_rmse_deg",
      "chain": "V2S",
      "evaluator_version": "v3",
      "case_ids": [
        "D14_seed_00",
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "full_vs_no_SA",
      "metric_name": "yaw_rmse_deg",
      "chain": "V2S",
      "evaluator_version": "v2",
      "case_ids": [
        "D14_seed_00",
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "full_vs_no_SA",
      "metric_name": "yaw_p95_absolute_deg",
      "chain": "V2S",
      "evaluator_version": "v3",
      "case_ids": [
        "D14_seed_00",
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "full_vs_no_SA",
      "metric_name": "yaw_p95_absolute_deg",
      "chain": "V2S",
      "evaluator_version": "v2",
      "case_ids": [
        "D14_seed_00",
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "full_vs_no_RP",
      "metric_name": "horizontal_rmse_m",
      "chain": "V2S",
      "evaluator_version": "v3",
      "case_ids": [
        "D27_seed_00"
      ]
    },
    {
      "comparison": "full_vs_no_RP",
      "metric_name": "horizontal_rmse_m",
      "chain": "V2S",
      "evaluator_version": "v2",
      "case_ids": [
        "D27_seed_00"
      ]
    },
    {
      "comparison": "full_vs_no_RP",
      "metric_name": "yaw_rmse_deg",
      "chain": "V2S",
      "evaluator_version": "v3",
      "case_ids": [
        "D27_seed_00"
      ]
    },
    {
      "comparison": "full_vs_no_RP",
      "metric_name": "yaw_rmse_deg",
      "chain": "V2S",
      "evaluator_version": "v2",
      "case_ids": [
        "D27_seed_00"
      ]
    },
    {
      "comparison": "full_vs_no_RP",
      "metric_name": "yaw_p95_absolute_deg",
      "chain": "V2S",
      "evaluator_version": "v3",
      "case_ids": [
        "D27_seed_00"
      ]
    },
    {
      "comparison": "full_vs_no_RP",
      "metric_name": "yaw_p95_absolute_deg",
      "chain": "V2S",
      "evaluator_version": "v2",
      "case_ids": [
        "D27_seed_00"
      ]
    },
    {
      "comparison": "full_vs_no_Go2",
      "metric_name": "horizontal_rmse_m",
      "chain": "V2S",
      "evaluator_version": "v3",
      "case_ids": [
        "D27_seed_00"
      ]
    },
    {
      "comparison": "full_vs_no_Go2",
      "metric_name": "horizontal_rmse_m",
      "chain": "V2S",
      "evaluator_version": "v2",
      "case_ids": [
        "D27_seed_00"
      ]
    },
    {
      "comparison": "full_vs_no_Go2",
      "metric_name": "yaw_rmse_deg",
      "chain": "V2S",
      "evaluator_version": "v3",
      "case_ids": [
        "D27_seed_00"
      ]
    },
    {
      "comparison": "full_vs_no_Go2",
      "metric_name": "yaw_rmse_deg",
      "chain": "V2S",
      "evaluator_version": "v2",
      "case_ids": [
        "D27_seed_00"
      ]
    },
    {
      "comparison": "full_vs_no_Go2",
      "metric_name": "yaw_p95_absolute_deg",
      "chain": "V2S",
      "evaluator_version": "v3",
      "case_ids": [
        "D27_seed_00"
      ]
    },
    {
      "comparison": "full_vs_no_Go2",
      "metric_name": "yaw_p95_absolute_deg",
      "chain": "V2S",
      "evaluator_version": "v2",
      "case_ids": [
        "D27_seed_00"
      ]
    },
    {
      "comparison": "RD_only_vs_strong",
      "metric_name": "horizontal_rmse_m",
      "chain": "CAL",
      "evaluator_version": "v3",
      "case_ids": [
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "RD_only_vs_strong",
      "metric_name": "horizontal_rmse_m",
      "chain": "V2S",
      "evaluator_version": "v3",
      "case_ids": [
        "D14_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "RD_only_vs_strong",
      "metric_name": "horizontal_rmse_m",
      "chain": "CAL",
      "evaluator_version": "v2",
      "case_ids": [
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "RD_only_vs_strong",
      "metric_name": "horizontal_rmse_m",
      "chain": "V2S",
      "evaluator_version": "v2",
      "case_ids": [
        "D14_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "RD_only_vs_strong",
      "metric_name": "yaw_rmse_deg",
      "chain": "CAL",
      "evaluator_version": "v3",
      "case_ids": [
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "RD_only_vs_strong",
      "metric_name": "yaw_rmse_deg",
      "chain": "V2S",
      "evaluator_version": "v3",
      "case_ids": [
        "D14_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "RD_only_vs_strong",
      "metric_name": "yaw_rmse_deg",
      "chain": "CAL",
      "evaluator_version": "v2",
      "case_ids": [
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "RD_only_vs_strong",
      "metric_name": "yaw_rmse_deg",
      "chain": "V2S",
      "evaluator_version": "v2",
      "case_ids": [
        "D14_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "RD_only_vs_strong",
      "metric_name": "yaw_p95_absolute_deg",
      "chain": "CAL",
      "evaluator_version": "v3",
      "case_ids": [
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "RD_only_vs_strong",
      "metric_name": "yaw_p95_absolute_deg",
      "chain": "V2S",
      "evaluator_version": "v3",
      "case_ids": [
        "D14_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "RD_only_vs_strong",
      "metric_name": "yaw_p95_absolute_deg",
      "chain": "CAL",
      "evaluator_version": "v2",
      "case_ids": [
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "RD_only_vs_strong",
      "metric_name": "yaw_p95_absolute_deg",
      "chain": "V2S",
      "evaluator_version": "v2",
      "case_ids": [
        "D14_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "SA_only_vs_strong",
      "metric_name": "horizontal_rmse_m",
      "chain": "CAL",
      "evaluator_version": "v3",
      "case_ids": [
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "SA_only_vs_strong",
      "metric_name": "horizontal_rmse_m",
      "chain": "V2S",
      "evaluator_version": "v3",
      "case_ids": [
        "D14_seed_00",
        "D27_seed_00"
      ]
    },
    {
      "comparison": "SA_only_vs_strong",
      "metric_name": "horizontal_rmse_m",
      "chain": "CAL",
      "evaluator_version": "v2",
      "case_ids": [
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "SA_only_vs_strong",
      "metric_name": "horizontal_rmse_m",
      "chain": "V2S",
      "evaluator_version": "v2",
      "case_ids": [
        "D14_seed_00",
        "D27_seed_00"
      ]
    },
    {
      "comparison": "SA_only_vs_strong",
      "metric_name": "yaw_rmse_deg",
      "chain": "CAL",
      "evaluator_version": "v3",
      "case_ids": [
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "SA_only_vs_strong",
      "metric_name": "yaw_rmse_deg",
      "chain": "V2S",
      "evaluator_version": "v3",
      "case_ids": [
        "D14_seed_00",
        "D27_seed_00"
      ]
    },
    {
      "comparison": "SA_only_vs_strong",
      "metric_name": "yaw_rmse_deg",
      "chain": "CAL",
      "evaluator_version": "v2",
      "case_ids": [
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "SA_only_vs_strong",
      "metric_name": "yaw_rmse_deg",
      "chain": "V2S",
      "evaluator_version": "v2",
      "case_ids": [
        "D14_seed_00",
        "D27_seed_00"
      ]
    },
    {
      "comparison": "SA_only_vs_strong",
      "metric_name": "yaw_p95_absolute_deg",
      "chain": "CAL",
      "evaluator_version": "v3",
      "case_ids": [
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "SA_only_vs_strong",
      "metric_name": "yaw_p95_absolute_deg",
      "chain": "V2S",
      "evaluator_version": "v3",
      "case_ids": [
        "D14_seed_00",
        "D27_seed_00"
      ]
    },
    {
      "comparison": "SA_only_vs_strong",
      "metric_name": "yaw_p95_absolute_deg",
      "chain": "CAL",
      "evaluator_version": "v2",
      "case_ids": [
        "D15_seed_00",
        "D59_seed_00"
      ]
    },
    {
      "comparison": "SA_only_vs_strong",
      "metric_name": "yaw_p95_absolute_deg",
      "chain": "V2S",
      "evaluator_version": "v2",
      "case_ids": [
        "D14_seed_00",
        "D27_seed_00"
      ]
    }
  ],
  "full_matrix_rerun_executed": false,
  "full_matrix_rerun_authorized_automatically": false,
  "frozen_metric_recomputation_performed": false,
  "frozen_solver_rerun_count": 0,
  "frozen_case_delta_aggregation_only": true,
  "confidence_intervals": "case-paired median bootstrap 10000 resamples, seed260910007, percentile95%",
  "decision_versions": [
    "v3",
    "v2"
  ],
  "rule": "All main-metric pairs maintained in both reported evaluations => FULL_MATRIX_RERUN_NOT_REQUIRED. Any main-metric pair flip => HUMAN_DECISION_REQUIRED with version, magnitude and pair list. Missing evidence => HUMAN_DECISION_REQUIRED. No automatic full matrix rerun."
}
```

## C00 锚点及 22 配置独立 QA

完整消融锚点表为 `S/08_AGGREGATE/C00_FULL_ABLATION_ANCHORS.csv`：两链各 11 配置、各 v2/v3，共 44 行；每行保留指标、配置/输入哈希和评估来源。其 22 个 run 同时计入本子集，未为横向表或消融锚点重复求解。

两链 C00 各 11 个配置均 COMPLETED；独立使用 GNSS18/IMU 时间与有效位推导期望主/辅助计数，重新执行纯身份及计数检查，共 22/22 通过，且与保存的审计一致。CAL 的原 Canonical→新 config 实际字节差仅 vrw、abstd、五个 provider 路径及 outputpath；V2S 仅五个 provider 路径及 outputpath。V2S vrw=[0.077,0.077,0.077]、abstd=[77.8,77.8,77.8] 与其余科学参数字节不变；两链各11个源/新config哈希与逐行diff ledger一致。

| 链 | 新 C00 对应 | 既有来源 | NAV/STD 字节比较 |
|---|---|---|---|
| CAL | RUN_00001/00002/00003/00004/00006；F01/F02/F03/F04/A04 | `K/03_CALIBRATED_RUNS/CLEAN5_CALIBRATED_BY2_<method>`；`K/04_CALIBRATED_SEAL/CALIBRATED_OUTPUT_SEAL.json` | 20/20 SHA-256 相等 |
| V2S | RUN_00003/00006；F03/A04 | `P/10_IMU_PROCESSING/03_PARITY_RUNS/CLEAN5_PARITY_V2s_<method>`；`P/10_IMU_PROCESSING/04_PARITY_SEAL/PARITY_OUTPUT_SEAL.json` | 8/8 SHA-256 相等 |
| V2S | F01/F02/F04 | 明确 V2s 封存来源未含对应 run | NOT_COMPARED；未替换为 V2/其他链 |

每个对应 run 比较 `KF_GINS_Navresult.nav`、`KF_GINS_STD.txt`、`LegSA_PORT_NAV.nav`、`LegSA_PORT_STD.csv`；旧文件 hash 均与封存清单一致。全部 C00 的 44 个子集 v2/v3 capture.consistency 为 true。

## 评估 capture 一致性诊断与既有终态规则

以下按最终只读核查登记。它与纯 I/O、进程身份、计算终态分别记录。子集调用路径使用 `clean5_sequence/evaluation_process.py`，要求 capture.consistency 字典存在，但没有把其中 passed=true 作为终态门；横向路径使用 `clean5_parity/evaluation.py:_external_evaluate`，要求 passed=true。本次保留代码 `24cc761e4085561888a9d8546df8b89300d340fe` 的既有封装规则，不事后改变状态、删除 case 或修改四列表。

| 版本 | 链 | capture true | capture false | H 最大差 (m) |
|---|---|---|---|---|
| v2 | CAL | 591 | 78 | 0.367846724 |
| v2 | V2S | 591 | 72 | 0.113047048 |
| v3 | CAL | 595 | 74 | 0.367527291 |
| v3 | V2S | 592 | 71 | 0.112896122 |

子集 2664 个 COMPLETED 中，capture true=2369、false=295。295 false 均仅水平一致性差超过 0.01 m；Up/yaw 超阈值计数均为 0。加入 4 次横向调用的 3 true/1 false 后，总计 2372 true/296 false。源文件：`S/07_EVALUATION/<version>/CLEAN5_DEGSUBSET_<chain>/<run_id>/FROZEN_EVALUATOR/EVALUATOR_CAPTURE.json` 和 `S/09_HORIZONTAL_V3/<method>/FROZEN_EVALUATOR/EVALUATOR_CAPTURE.json`。

完整诊断来源为 `S/10_REVIEW/CAPTURE_CONSISTENCY_DIAGNOSTICS.csv` 与 `S/10_REVIEW/CAPTURE_CONSISTENCY_SUMMARY.json`。CSV 共 2668 行，逐行记录源 capture 路径、SHA-256 及诊断结果；汇总为 2372 true / 296 false。诊断汇总保持原 296 个 false 标记、原终态、指标及 case 选择；与最终封存的对应关系列入末节最终验证。

## 横向 GINav 评估审计

GINav 的评估器实际调用 1 次、exit_code=0；capture matched_epoch_count=77。capture.consistency：horizontal_max_m=0.328772659 m > 0.01 m，up_max_m=0.00397204515 m，yaw_max_deg=1.70530257e−13 deg，passed=false。因此横向外层 evaluation_status=`FAILED_EVALUATOR`，availability=`UNAVAILABLE_EVALUATION_FAILED`；没有重试，正式 H/3D/Up/yaw/体坐标指标均为空。exit 0 不替代 wrapper 的一致性门。

来源：`S/09_HORIZONTAL_V3/LC02_GINAV/EVALUATION_RESULT.json`、其 `FROZEN_EVALUATOR/EVALUATOR_CAPTURE.json` 与 `EVALUATOR_STRACE_AUDIT.json`。后者总体 passed=false；reviewer 对该调用的纯 I/O 与进程身份核查单独通过。

GINav 保留 77/275 配置支持元数据；77 配对数是失败调用诊断，不作为已通过的正式配对覆盖结果。

## 横向表 v3

| 方法 | 状态 | H RMSE (m) | 3D RMSE (m) | Up RMSE (m) | yaw RMSE (deg) | yaw P95 (deg) | 体前偏差 (m) | 体右偏差 (m) | 体上偏差 (m) | 来源 |
|---|---|---|---|---|---|---|---|---|---|---|
| LegSA_frozen | AVAILABLE | 0.301330664 | 0.775302238 | 0.714348228 | 1.93407566 | 3.51908971 | -0.189296784 | 0.00569675723 | -0.110569264 | S/09_HORIZONTAL_V3/LegSA_frozen/EVALUATION_RESULT.json |
| LegSA_V2S | COMPLETED | 0.140394817 | 0.343392293 | 0.313380858 | 1.92422017 | 3.72495887 | 0.0534168212 | 0.000642153964 | -0.00620817831 | S/07_EVALUATION/v3/CLEAN5_DEGSUBSET_V2S/RUN_00006/EVALUATION_RESULT.json |
| LegSA_CAL | COMPLETED | 0.097883052 | 0.109953104 | 0.0500858576 | 2.11623243 | 4.01109492 | 0.0437270588 | -0.000542094478 | -0.0174552468 | S/07_EVALUATION/v3/CLEAN5_DEGSUBSET_CAL/RUN_00006/EVALUATION_RESULT.json |
| LC01_EXT05A | AVAILABLE | 0.0975479714 | 0.109920334 | 0.0506643183 | 2.99482746 | 4.96814134 | 0.0442455984 | 0.000216921121 | -0.0351677247 | S/09_HORIZONTAL_V3/LC01_EXT05A/EVALUATION_RESULT.json |
| EXT05C | AVAILABLE_DIAGNOSTIC_DUAL_RX_INITIALIZATION | 0.0877508129 | 0.104350662 | 0.0564699523 | 12.0486417 | 16.8684958 | 0.0134716593 | 0.00341155669 | -0.036350684 | S/09_HORIZONTAL_V3/EXT05C/EVALUATION_RESULT.json |
| LC02_GINAV | UNAVAILABLE_EVALUATION_FAILED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | S/09_HORIZONTAL_V3/LC02_GINAV/EVALUATION_RESULT.json |
| EXT01 | UNAVAILABLE_NO_IMU_POINT_NAV | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | H/12_FINAL_EVIDENCE_INTEGRATION/FINAL_METHOD_REGISTRY.csv:2 |
| EXT02 | UNAVAILABLE_NO_IMU_POINT_NAV | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | H/12_FINAL_EVIDENCE_INTEGRATION/FINAL_METHOD_REGISTRY.csv:3 |
| EXT03 | UNAVAILABLE_NO_IMU_POINT_NAV | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | H/12_FINAL_EVIDENCE_INTEGRATION/FINAL_METHOD_REGISTRY.csv:4 |
| EXT04 | UNAVAILABLE_NO_IMU_POINT_NAV_ZERO_ACCEPTED_EPOCHS | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | H/12_FINAL_EVIDENCE_INTEGRATION/FINAL_METHOD_REGISTRY.csv:5 |
| Hartley | UNAVAILABLE_ABSOLUTE_METRICS_UNANCHORED_TRANSLATION_AND_YAW_GAUGE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | H/12_FINAL_EVIDENCE_INTEGRATION/FINAL_METHOD_REGISTRY.csv:8 |
| EXT05B | UNAVAILABLE_NOT_IMPLEMENTED | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | <CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/06_EXT05_PAVLASEK_TWO_RECEIVER/C00/EXT05B_C00_MEKF_NOT_IMPLEMENTED.json |

来源：`S/08_AGGREGATE/HORIZONTAL_TABLE_V3.csv`。EXT05C 保留诊断身份；无 IMU 点 NAV 的行保持 UNAVAILABLE。

## I/O、检查点与测试

provider 共 61/61 个 case，2744 项语义检查通过，204 个文件封存。各 case 的注入前后 diff 与冻结同 case 摘要均保留在 provider manifest/summary 及上方证据表。

| 阶段 | 会话/调用数 | trace 打开 | .bag/.fpl 打开 | raw write | 白名单外 write | 纯 I/O 审计 |
|---|---|---|---|---|---|---|
| provider | 1 | 0 | 0 | 0 | 0 | PASS |
| solver | 1342 | 0 | 0 | 0 | 0 | 1342/1342 PASS |
| evaluator | 2668 | 每调用 1 次，仅评估器子进程 | 0 | 0 | 0 | 2668/2668 PASS |

provider/solver 的全部 raw 打开数均为 0。写白名单沿用 C-04b，限本 run/家族目录以及既有设备/匿名管道例外。provider 来源为 `S/01_CHECKPOINTS/PROVIDER_STRACE_AUDIT.json`；solver 来源为逐 run `P07_RUN_TERMINAL.json` 内的 strace 审计字段及 `SOLVER_OPENAT.strace`。纯 I/O 通过不等于 capture 内容一致性通过，后者单独列于前节。

最终只读核查：2668 次实际评估调用的纯 I/O 与进程身份通过；20 个未调用目录仅含结果 JSON。子集 2664 个原 NAV/STD 记录与 solver seal 一致；v2 的 1332 个 eval NAV 与原 NAV 字节一致。v3 的 1332 个 eval NAV 与最终 evaluation seal 的对应验证见末节。

| 检查点 | 锁成员 | 每文件成功只读打开次数 | raw write |
|---|---|---|---|
| BEFORE_PROVIDER | 22/22 | 1 | 0 |
| AFTER_PROVIDER | 22/22 | 1 | 0 |
| BEFORE_SOLVER | 22/22 | 1 | 0 |
| AFTER_SOLVER | 22/22 | 1 | 0 |
| BEFORE_EVALUATION | 22/22 | 1 | 0 |
| AFTER_EVALUATION | 22/22 | 1 | 0 |

六个独立检查点会话合计 132 次只读 raw 文件打开，均为一次流式 SHA-256；依人类授权包括 trace/.bag/.fpl，与求解/评估科学使用的 I/O 规则分开记账。源：`S/01_CHECKPOINTS/<checkpoint>/CHECKPOINT_STRACE_AUDIT.json`；各会话 passed=true、exact path set、每成员 once、raw write=0。记录整理未打开 raw trace/.bag/.fpl。

预执行测试记录为 154 passed：providers 79、runtime 59、statistics 9、checkpoint 7；对应 `tests/paper_rebuild/test_clean5_degradation_{providers,runtime,statistics,checkpoint}.py`。此处保留既有测试记录。

## 完整提交链

| 完整 commit SHA | 用途/提交主题 |
|---|---|
| ff0631428102902702cf82b3a5030467be30f581 | 用户指定起点 |
| ace468ae7926cfbc156a0bdffd3e836ad621cec8 | docs(clean5): yaw change mechanism check |
| 967d6b396b95ef7ec416b187813e0872a1c7fd1b | docs(clean5): per-sequence yaw-change labels and human release for P-07 |
| b73fbaae7f8ef9da444c4320e1cd6d1a43df64f2 | docs(clean5): preregister corrected-chain degradation subset |
| 1b86020ca44d74049f1dcfd2161fc8421545fc75 | feat(clean5): implement preregistered degradation subset pipeline |
| 3326a9cbd50d80156fe46309cd1ee5336b5a3c3b | docs(clean5): record authorized P-07 checkpoint scope |
| 24cc761e4085561888a9d8546df8b89300d340fe | fix(clean5): enforce exact P-07 hash checkpoint sessions |

科学求解冻结：`64c81965b17ef1bf8ae2ce3e4dd7b1ae35110b00`；执行二进制 SHA-256：`9c00565c45b654453b2b378f3d5995e5dc21d1271323a9b683acdab75993235f`；评估器 SHA-256：`aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da`。

记录提交见本记录所属 Git commit。

## 最终验证

控制器三阶段全部正常退出，最终进程退出码 0，服务 inactive/dead，MainPID=0。最终状态文件原文：

```json
{
  "status": "COMPLETED",
  "code_commit": "24cc761e4085561888a9d8546df8b89300d340fe",
  "solver_terminal_count": 1342,
  "evaluation_terminal_count": 2684,
  "decision": "HUMAN_DECISION_REQUIRED",
  "full_matrix_rerun_executed": false
}
```

`seal_roots` 写出后逐文件回读验证：provider 204/204、solver 23474/23474、evaluation 28067/28067 通过。只读 reviewer 另核对 1332/1332 个 v3 eval NAV 与 evaluation seal、2668/2668 个 capture 的实际 SHA-256 / 诊断 CSV / evaluation seal 三方对应；v2 的 1332 个 eval NAV 与原 NAV 一致，2664 条原 NAV/STD 来源记录与 solver seal 一致。C00 的 44/44 个评估 capture 一致性为 true。封存与来源哈希通过不改变前述 295 个子集 capture false 和 GINav 的 UNAVAILABLE。

| 封存清单 | 文件数 | SHA-256 |
|---|---|---|
| `S/04_SEAL/PROVIDER_SEAL.json` | 204 | `00c24ff4230029035779def2b36b3556c241b3b73f77e12870a457b64cc16136` |
| `S/04_SEAL/SOLVER_OUTPUT_SEAL.json` | 23474 | `98d7289bdedbf919eb17d3e005ea332aa34a45e1b939d0532e54b080853309c3` |
| `S/04_SEAL/EVALUATION_ARTIFACT_SEAL.json` | 28067 | `d97ce4092ea99e36ad68a7b432e313c0371041f829479ed9ac5f8571c36c3a3f` |
| `S/10_REVIEW/REVIEW_SEAL.json` | 2 | `d437e9f01fc022f029a0ea58ded39afef0bca09aa30c1488aaa3a2c0d3b49b76` |

`S/10_REVIEW/REVIEW_SEAL.json` 单独封存两份诊断文件；源 capture 的 2668/2668 对应关系已验证，未改写原评估产物。终态后重新校验执行冻结的 74/74 源文件及执行合约 SHA-256 均相等；二进制、评估器和标定模型哈希保持冻结值。记录阶段没有新增 provider、solver、evaluator 调用或 raw 内容打开。

产物根为 `S`；`S/04_SEAL/` 保存封存清单，`S/01_CHECKPOINTS/` 保存检查点证据。统计、决定及横向来源位于 `S/08_AGGREGATE/`；capture 完整诊断位于 `S/10_REVIEW/`。
