# HX-02 五类外部方法三序列结果

决策规则：无数值门槛，全部结果如实报告。LegSA 行只从 v3 封存表读取；本任务对 LegSA 的解算/评估调用为 0/0。

代码冻结提交：`3e8a43be928247da09ac4cca8a54178c3db9dadb`；运行记录的执行提交：`['3e8a43be928247da09ac4cca8a54178c3db9dadb', '88594ef27e20a8e660e2246218a6870a290f35ae']`。

## 1. 双天线模糊度航向（heading_only；分母 = 方法原生配对历元在窗内的数目：BY2 1370 / BY2H 1350 / BY2O 1885）

| method | config | BY2 (C00) | BY2H (CONTRACT_START [413,683]) | BY2O (FILE_START [3186,3563]) |
|---|---|---|---|---|
| EXT01 | LIT | avail 71.5% (980/1370); valid RMSE° 120.360; hold RMSE° 117.867; valid max° 179.97 | avail 78.4% (1059/1350); valid RMSE° 109.478; hold RMSE° 106.069; valid max° 179.89 | avail 65.1% (1228/1885); valid RMSE° 102.034; hold RMSE° 106.598; valid max° 179.88 |
| EXT02 | LIT | avail 70.4% (964/1370); valid RMSE° 120.529; hold RMSE° 117.946; valid max° 179.97 | avail 76.1% (1028/1350); valid RMSE° 109.269; hold RMSE° 106.500; valid max° 179.89 | avail 63.2% (1191/1885); valid RMSE° 100.813; hold RMSE° 106.351; valid max° 179.26 |
| EXT03 | LIT | avail 39.5% (541/1370); valid RMSE° 84.344; hold RMSE° 92.496; valid max° 179.35 | avail 34.6% (467/1350); valid RMSE° 76.924; hold RMSE° 80.640; valid max° 179.18 | avail 14.3% (269/1885); valid RMSE° 112.432; hold RMSE° 109.112; valid max° 179.49 |
| EXT04_FAR | LIT | avail 0.0% (0/1370); valid RMSE° UNAVAILABLE; hold RMSE° UNAVAILABLE; valid max° UNAVAILABLE | avail 0.0% (0/1350); valid RMSE° UNAVAILABLE; hold RMSE° UNAVAILABLE; valid max° UNAVAILABLE | avail 0.0% (0/1885); valid RMSE° UNAVAILABLE; hold RMSE° UNAVAILABLE; valid max° UNAVAILABLE |
| EXT04_PAR | LIT | avail 0.0% (0/1370); valid RMSE° UNAVAILABLE; hold RMSE° UNAVAILABLE; valid max° UNAVAILABLE | avail 0.0% (0/1350); valid RMSE° UNAVAILABLE; hold RMSE° UNAVAILABLE; valid max° UNAVAILABLE | avail 0.0% (0/1885); valid RMSE° UNAVAILABLE; hold RMSE° UNAVAILABLE; valid max° UNAVAILABLE |
| RTKLIB_UNMODIFIED_MOVING_BASE | - | avail 11.2% (153/1370); valid RMSE° 14.566; hold RMSE° 58.241; valid max° 124.73 | avail 13.3% (179/1350); valid RMSE° 27.011; hold RMSE° 55.118; valid max° 162.41 | avail 5.9% (112/1885); valid RMSE° 23.139; hold RMSE° 129.988; valid max° 173.42 |

EXT03 ratio-fixed 率与 RTKLIB Q=2 比例见长表（metric = ratio_fixed_rate / q2_float_rate）。

## 2. 松组合 GNSS/INS（imu_point_nav）

| method | config | BY2 (C00) | BY2H (CONTRACT_START [413,683]) | BY2O (FILE_START [3186,3563]) |
|---|---|---|---|---|
| LC01 | LIT | h RMSE m 0.0975; yaw RMSE° 2.995 | h RMSE m 0.0746; yaw RMSE° 2.209 | h RMSE m 0.0543; yaw RMSE° 2.454 |
| LC01-S | S | h RMSE m 0.1035; yaw RMSE° 1.539 | h RMSE m 0.0837; yaw RMSE° 1.943 | h RMSE m 0.0605; yaw RMSE° 4.016 |
| LC02_GINAV | - | row cov 0.280; span cov 0.620; max gap s 11.0; frozen evaluation status: NOT_RUN_ALGORITHM_FAILURE | h RMSE m 2.8949; yaw RMSE° 11.662; v2 h RMSE m 2.8732; v2 yaw RMSE° 11.662; row cov 0.007; span cov 0.004; max gap s 1.0 | row cov 0.013; span cov 0.034; max gap s 9.0; frozen evaluation status: NOT_RUN_ALGORITHM_FAILURE |
| EXT05B | - | 无实现 | 无实现 | 无实现 |
| LC01-M | - | 无实现 | 无实现 | 无实现 |
| LC01-S-M | - | 无实现 | 无实现 | 无实现 |
| LC01-2D | - | 无实现 | 无实现 | 无实现 |
| LC02_YIN2023_RAEKF | - | 无实现 | 无实现 | 无实现 |
| LC02_CHANG2021_FSTCKF | - | 无实现 | 无实现 | 无实现 |
| LC02A_JIANG2021_ADAPTIVE_FADING_CKF | - | 无实现 | 无实现 | 无实现 |
| LC02B_TAGHIZADEH2023_AHINF_CKF | - | 无实现 | 无实现 | 无实现 |
| EXT06_HAO2018_TWO_ANTENNA_LC_EKF | - | 无实现 | 无实现 | 无实现 |

LC01/LC01-S 为 v3 封存行（BY2H 取 CONTRACT_START；FILE_START 行见长表 notes=SUPPLEMENT）。

## 3. 单天线 GNSS/INS（imu_point_nav）

| method | config | BY2 (C00) | BY2H (CONTRACT_START [413,683]) | BY2O (FILE_START [3186,3563]) |
|---|---|---|---|---|
| EXT05C | LIT | h RMSE m 0.0878; yaw RMSE° 12.049 | h RMSE m 0.0692; yaw RMSE° 20.108 | h RMSE m 0.0520; yaw RMSE° 5.846 |
| EXT05C-S | S | h RMSE m 0.1142; yaw RMSE° 9.722 | h RMSE m 0.0854; yaw RMSE° 8.115 | h RMSE m 0.0751; yaw RMSE° 8.267 |
| EXT06 | - | 无实现 | 无实现 | 无实现 |

## 4. 足式状态估计（relative_pose；每支用自己的输出在窗首 10 s 内做一次 yaw+平移对齐，互不共用）

| method | config | BY2 (C00) | BY2H (CONTRACT_START [413,683]) | BY2O (FILE_START [3186,3563]) |
|---|---|---|---|---|
| Hartley-S | S | drift m/100m 34.077; °/min -101.193; h RMSE m 84.155; yaw RMSE° 78.68 | FAILED: ABNORMAL_EXIT | drift m/100m 9.048; °/min 495.077; h RMSE m 89.676; yaw RMSE° 94.41 |
| Hartley-LIT | LIT | drift m/100m 36.281; °/min 31.940; h RMSE m 53.400; yaw RMSE° 65.50 | FAILED: ABNORMAL_EXIT | drift m/100m 27.699; °/min 13.392; h RMSE m 77.552; yaw RMSE° 91.04 |

## 5. 其他

| method | config | BY2 | BY2H | BY2O |
|---|---|---|---|---|
| — | — | 该类无实现 | 该类无实现 | 该类无实现 |

## LegSA 参照（v3 封存 FULL_ABLATION_TABLE_V3.csv，只读）

| method | config | BY2 (C00) | BY2H (CONTRACT_START [413,683]) | BY2O (FILE_START [3186,3563]) |
|---|---|---|---|---|
| LegSA_F04 | - | h RMSE m 0.0979; yaw RMSE° 1.886 | h RMSE m 0.0684; yaw RMSE° 1.934 | h RMSE m 0.0545; yaw RMSE° 2.434 |
| LegSA_F02 | - | h RMSE m 0.1019; yaw RMSE° 2.232 | h RMSE m 0.0715; yaw RMSE° 2.283 | h RMSE m 0.0547; yaw RMSE° 2.309 |
| LegSA_F01 | - | h RMSE m 0.0918; yaw RMSE° 8.090 | h RMSE m 0.0629; yaw RMSE° 7.137 | h RMSE m 0.0628; yaw RMSE° 5.739 |

## 每类结论

- dual_antenna_ambiguity_heading：方法自身有效率在 0.0%（EXT04_FAR，BY2）到 78.4%（EXT01，BY2H）之间；有效历元 wrap-safe 航向 RMSE 在 14.57°（RTKLIB_UNMODIFIED_MOVING_BASE，BY2）到 120.53°（EXT02，BY2）之间（出处：EXTERNAL_FIVE_CATEGORY_TABLE.csv 对应行的 source 列）。
- loosely_coupled_gnss_ins：封存 v3 行（BY2/BY2H CONTRACT_START/BY2O）：LC01 yaw RMSE 2.995/2.209/2.454°，LC01-S yaw RMSE 1.539/1.943/4.016°；GINav 本任务：BY2 row_coverage=0.28；BY2 frozen_evaluation_status=NOT_RUN_ALGORITHM_FAILURE；BY2H row_coverage=0.00738；BY2H horizontal_rmse_m=2.895；BY2H yaw_rmse_deg=11.66；BY2O row_coverage=0.01323；BY2O frozen_evaluation_status=NOT_RUN_ALGORITHM_FAILURE（出处：MAIN_TABLE_V3.csv 第 17/43/50、40/47/52 行与本任务运行目录）。
- single_antenna_gnss_ins：封存 v3 行：EXT05C yaw RMSE 12.049/20.108/5.846°，EXT05C-S yaw RMSE 9.722/8.115/8.267°；BY2H FILE_START 的 EXT05C-S（第 48 行）为 ALGORITHM_FAILURE_DIVERGED；EXT06 无实现（出处：MAIN_TABLE_V3.csv 第 18/45/51、41/49/53、48 行）。
- legged_state_estimation：Hartley-S：BY2 34.077 m/100 m、-101.193°/min，BY2H ABNORMAL_EXIT，BY2O 9.048 m/100 m、495.077°/min；Hartley-LIT：BY2 36.281 m/100 m、31.940°/min，BY2H ABNORMAL_EXIT，BY2O 27.699 m/100 m、13.392°/min（相对位姿口径，各支自身对齐；出处：各分支运行目录 RELATIVE_POSE_METRICS.json）。
- other：该类无外部方法（HX_INVENTORY.md §2）。

## 复现检查（BY2 C00，只记录、不硬停）

| method | status | detail |
|---|---|---|
| EXT01 | NOT_REPRODUCED | `{"declared_scope_heading_tables": {"EXT01": {"clean4_declared_scope_table_sha256": "4077df65ab3e1b29474342e8cbacb947d8bd45b0e968f1f201e7078862352ed9", "hx02_table_sha256": "4077df65ab3e1b29474342e8cbacb947d8bd45b0e968f1f201e7078862352ed9", "identical": true}}, "hx02_native_freeze_sha256": "d11ed040cdc15527f49843f06dab367de3eb8a2d98ed7926de65f37cf3721e91", "known_reasons": ["the freeze JSON embeds run paths, the HX-02 sequence spec and the execution commit", "rtklib_bridge .so rebuilt after the CLEAN4 EXT01 R2 run (current liblegsa_rtklib_bridge.so 6df66600...); GPU/driver and library versions are not pinned by CLEAN4", "runtime files record wall-clock timings"], "method_output_identical_on_d` |
| EXT02 | NOT_REPRODUCED | `{"declared_scope_heading_tables": {"EXT02": {"clean4_declared_scope_table_sha256": "08fe64c3869d5391e7729b668f730ef2290e4cb5387c1668ed539e90089d199d", "hx02_table_sha256": "08fe64c3869d5391e7729b668f730ef2290e4cb5387c1668ed539e90089d199d", "identical": true}}, "hx02_native_freeze_sha256": "64e11583816853c26a64a96e22c22e48dac71070b155481ada55cd63d6811410", "known_reasons": ["the freeze JSON embeds run paths, the HX-02 sequence spec and the execution commit", "runtime files record wall-clock timings"], "method_output_identical_on_declared_scope": true, "registered_clean4_native_freeze_sha256": "c1d8260df693ed213c004ae90f3446e546e88f599b662ec40879711b8b3f060d"}` |
| EXT03 | NOT_REPRODUCED | `{"declared_scope_heading_tables": {"EXT03": {"clean4_declared_scope_table_sha256": "aaa3832b312ce104c5de1b464044704767ecf0f4ce5b89fbfa86d3df28b26296", "hx02_table_sha256": "aaa3832b312ce104c5de1b464044704767ecf0f4ce5b89fbfa86d3df28b26296", "identical": true}}, "hx02_native_freeze_sha256": "2acc0a075524081db38cd977cc30440abdd9e627428add973bcda9d63c80765b", "known_reasons": ["the freeze JSON embeds run paths, the HX-02 sequence spec and the execution commit", "HX-02 runs only the declared scope (EXT03 primary variant; EXT04 GPS_BDS_DUAL_FREQUENCY FAR + primary PAR), so whole-file outputs cover fewer rows than CLEAN4", "runtime files record wall-clock timings"], "method_output_identical_on_decl` |
| EXT04 | NOT_REPRODUCED | `{"declared_scope_heading_tables": {"EXT04_FAR": {"clean4_declared_scope_table_sha256": "9d2cb8eb9a450c7881f4cfbff239a48a3f83f17b662b38f3d5d59bdf45dcbf4d", "hx02_table_sha256": "9d2cb8eb9a450c7881f4cfbff239a48a3f83f17b662b38f3d5d59bdf45dcbf4d", "identical": true}, "EXT04_PAR": {"clean4_declared_scope_table_sha256": "9d2cb8eb9a450c7881f4cfbff239a48a3f83f17b662b38f3d5d59bdf45dcbf4d", "hx02_table_sha256": "9d2cb8eb9a450c7881f4cfbff239a48a3f83f17b662b38f3d5d59bdf45dcbf4d", "identical": true}}, "hx02_native_freeze_sha256": "cfe00b194b9e2e11169976355c4dd1eff12110faf4c151a65ea7c71095599849", "known_reasons": ["the freeze JSON embeds run paths, the HX-02 sequence spec and the execution commit", "HX-0` |
| HARTLEY_S | REPRODUCED | `{"hx02_nav_sha256": "dc4d95a1e634ea7f7c3aecfcb3cdd50ded8ebf4378dfcd46917ed4875338a600", "known_reasons": [], "registered_clean4_nav_sha256": "dc4d95a1e634ea7f7c3aecfcb3cdd50ded8ebf4378dfcd46917ed4875338a600", "role": "REGISTERED_CHECK"}` |
| HARTLEY_LIT | REPRODUCED | `{"hx02_nav_sha256": "b46ffe7cf930d96de53f165c54c06af6df6b48b626ccb0e103c1bb7d2e10430e", "known_reasons": [], "registered_clean4_nav_sha256": "b46ffe7cf930d96de53f165c54c06af6df6b48b626ccb0e103c1bb7d2e10430e", "role": "INFORMATION_ONLY"}` |
| GINAV | NOT_REPRODUCED | `{"coverage_aware_value_identical_on_common_columns": false, "identical": {"pos": true, "r4c_standard_nav": true, "v3_attempt_window_nav": true}, "known_reasons": ["MATLAB release/driver state on this host may differ from the CLEAN4 r4c run"], "note": "the coverage-aware file carries an extra status_name column, so it is compared value by value", "observed": {"pos": "39453826453515689416d3d32a8d39290b0fbb35b71525283b692f8fccb788b2", "r4c_standard_nav": "99f3b09ea4f3964df815cfc64b88cdfe7a3460a1fe305cca52e4acd63e666e06", "v3_attempt_window_nav": "f0fa3e71270cce08ce6174376a694a00a92f725116f8cec86eed4d8062529012"}, "registered": {"coverage_aware_standard_nav": "85902928bac61f4d717c3832d407f94f6d9` |
| RTKLIB | DIFFERENT | `{"clean4_diagnostic_output_sha256": "5ac90d26b025694ce18e1e303bc7cae39eb4165a10d2c0714140bcb511b44a9d", "hx02_pos_sha256": "f88f6ee233495c33e946ad8b5cbef1af2a0724f39d924a43ccee7305cc3ac960", "note": "the CLEAN4 file was produced by the EXT03 post-native diagnostic with the same configuration", "role": "INFORMATION_ONLY"}` |

## 约定诊断（方法 body yaw − 双 fixed HPPOSECEF 基线 body yaw）

| sequence | variant | compared | median° | within ±20° of 0 / ±90 / 180 | status |
|---|---|---|---|---|---|
| BY2/EXT01 | EXT01 | 1077 | 36.70815552525076 | 0.12349117920148561 / 0.12627669452181986 / 0.2776230269266481 | PASS |
| BY2/EXT02 | EXT02 | 1057 | 36.97838559208924 | 0.12204351939451277 / 0.12677388836329234 / 0.2781456953642384 | PASS |
| BY2/EXT03 | EXT03 | 609 | -16.71663920575645 | 0.2561576354679803 / 0.029556650246305417 / 0.12807881773399016 | PASS |
| BY2/EXT04 | EXT04_FAR | 0 | UNAVAILABLE | UNAVAILABLE / UNAVAILABLE / UNAVAILABLE | UNAVAILABLE_NO_METHOD_VALID_DUAL_FIXED_EPOCH |
| BY2/EXT04 | EXT04_PAR | 0 | UNAVAILABLE | UNAVAILABLE / UNAVAILABLE / UNAVAILABLE | UNAVAILABLE_NO_METHOD_VALID_DUAL_FIXED_EPOCH |
| BY2/RTKLIB | RTKLIB | 177 | 0.24094291617024055 | 0.9887005649717514 / 0.0 / 0.0 | PASS |
| BY2H/EXT01 | EXT01 | 1112 | -9.724604083180424 | 0.18255395683453238 / 0.14928057553956833 / 0.18794964028776978 | PASS |
| BY2H/EXT02 | EXT02 | 1081 | -9.48000494697149 | 0.18316373728029603 / 0.1498612395929695 / 0.18593894542090658 | PASS |
| BY2H/EXT03 | EXT03 | 513 | -19.814650850963233 | 0.15789473684210525 / 0.24366471734892786 / 0.04483430799220273 | PASS |
| BY2H/EXT04 | EXT04_FAR | 0 | UNAVAILABLE | UNAVAILABLE / UNAVAILABLE / UNAVAILABLE | UNAVAILABLE_NO_METHOD_VALID_DUAL_FIXED_EPOCH |
| BY2H/EXT04 | EXT04_PAR | 0 | UNAVAILABLE | UNAVAILABLE / UNAVAILABLE / UNAVAILABLE | UNAVAILABLE_NO_METHOD_VALID_DUAL_FIXED_EPOCH |
| BY2H/RTKLIB | RTKLIB | 180 | 0.5392950582533445 | 0.9333333333333333 / 0.027777777777777776 / 0.005555555555555556 | PASS |
| BY2O/EXT01 | EXT01 | 1513 | -13.418657570043706 | 0.15598149372108394 / 0.23331130204890946 / 0.0991407799074686 | PASS |
| BY2O/EXT02 | EXT02 | 1462 | -13.917135276787747 | 0.15800273597811218 / 0.23666210670314639 / 0.09370725034199727 | PASS |
| BY2O/EXT03 | EXT03 | 493 | 45.92095301976053 | 0.05476673427991886 / 0.02231237322515213 / 0.05273833671399594 | PASS |
| BY2O/EXT04 | EXT04_FAR | 0 | UNAVAILABLE | UNAVAILABLE / UNAVAILABLE / UNAVAILABLE | UNAVAILABLE_NO_METHOD_VALID_DUAL_FIXED_EPOCH |
| BY2O/EXT04 | EXT04_PAR | 0 | UNAVAILABLE | UNAVAILABLE / UNAVAILABLE / UNAVAILABLE | UNAVAILABLE_NO_METHOD_VALID_DUAL_FIXED_EPOCH |
| BY2O/RTKLIB | RTKLIB | 165 | 1.1095636346372544 | 0.9878787878787879 / 0.0 / 0.012121212121212121 | PASS |

## 失败清单（带分母）

| run | classification | denominator | note |
|---|---|---|---|
| BY2/LC02_GINAV | ALGORITHM_FAILURE_DIVERGED | UNAVAILABLE | {"all_numeric_rows_finite": true, "bounds": {"height_displacement_m": 1000.0, "position_displacement_m": 10000.0, "speed_mps": 50.0}, "failure_classification": "ALGORITHM_FAILURE_DIVERGED", "first_vio |
| BY2O/LC02_GINAV | ALGORITHM_FAILURE_DIVERGED | UNAVAILABLE | {"all_numeric_rows_finite": true, "bounds": {"height_displacement_m": 1000.0, "position_displacement_m": 10000.0, "speed_mps": 50.0}, "failure_classification": "ALGORITHM_FAILURE_DIVERGED", "first_vio |
| BY2H/Hartley-S | ABNORMAL_EXIT | UNAVAILABLE | no relative-pose metrics for this branch |
| BY2H/Hartley-LIT | ABNORMAL_EXIT | UNAVAILABLE | no relative-pose metrics for this branch |
| BY2H/EXT05C-S | ALGORITHM_FAILURE_DIVERGED | UNAVAILABLE | sealed v3 row; role=SUPPLEMENT; evaluation_status=NOT_RUN_ALGORITHM_FAILURE; geometric_audit_status=NOT_APPLICABLE_SINGLE_RECEIVER |
| BY2/EXT04_FAR | NO_METHOD_VALID_EPOCH | 0/1370 | method-native availability 0 |
| BY2/EXT04_PAR | NO_METHOD_VALID_EPOCH | 0/1370 | method-native availability 0 |
| BY2H/EXT04_FAR | NO_METHOD_VALID_EPOCH | 0/1350 | method-native availability 0 |
| BY2H/EXT04_PAR | NO_METHOD_VALID_EPOCH | 0/1350 | method-native availability 0 |
| BY2O/EXT04_FAR | NO_METHOD_VALID_EPOCH | 0/1885 | method-native availability 0 |
| BY2O/EXT04_PAR | NO_METHOD_VALID_EPOCH | 0/1885 | method-native availability 0 |

## 原生运行清单与墙钟时间（COMMAND.json 起止 UTC）

| run | 分类 | 退出码 | 起（UTC） | 止（UTC） | 墙钟 [s] | runner 终态 |
|---|---|---|---|---|---|---|
| BY2__EXT01__LIT__C00__NA | COMPLETED | 0 | 2026-09-24T12:23:29.270787+00:00 | 2026-09-24T12:29:20.969905+00:00 | 351.699 | UNSUPPORTED_EXT01_ON_BY2_WITHOUT_PHASE_BIAS_CALIBRATION |
| BY2__EXT02__LIT__C00__NA | COMPLETED | 0 | 2026-09-24T12:30:00.730807+00:00 | 2026-09-24T12:30:29.649083+00:00 | 28.918 | PASS_PHASE2_EXT02_CWLS_C00_READY_FOR_NATIVE_COMPARISON |
| BY2__EXT03__LIT__C00__NA | COMPLETED | 0 | 2026-09-24T12:30:30.847737+00:00 | 2026-09-24T12:30:44.711800+00:00 | 13.864 | PASS_PHASE3_EXT03_YANG2024_C00_READY_FOR_NATIVE_COMPARISON |
| BY2__EXT04__LIT__C00__NA | COMPLETED | 0 | 2026-09-24T12:30:45.883910+00:00 | 2026-09-24T12:32:43.265334+00:00 | 117.381 | PASS_PHASE4_EXT04_NATIVE_FROZEN_READY_FOR_POST_NATIVE |
| BY2__RTKLIB__NONE__C00__NA | COMPLETED | 0 | 2026-09-24T12:33:19.694804+00:00 | 2026-09-24T12:33:24.244109+00:00 | 4.549 | — |
| BY2__HARTLEY_S__S__C00__NA | COMPLETED | 0 | 2026-09-24T12:33:25.423374+00:00 | 2026-09-24T12:33:27.401721+00:00 | 1.978 | — |
| BY2__HARTLEY_LIT__LIT__C00__NA | COMPLETED | 0 | 2026-09-24T12:33:27.875913+00:00 | 2026-09-24T12:33:29.941095+00:00 | 2.065 | — |
| BY2__GINAV__NONE__C00__NA | COMPLETED | 0 | 2026-09-24T12:33:30.307282+00:00 | 2026-09-24T12:35:41.337746+00:00 | 131.030 | — |
| BY2H__EXT01__LIT__CONTRACT_START__NA | COMPLETED | 0 | 2026-09-24T12:45:13.704485+00:00 | 2026-09-24T12:49:09.377695+00:00 | 235.673 | UNSUPPORTED_EXT01_ON_BY2_WITHOUT_PHASE_BIAS_CALIBRATION |
| BY2H__EXT02__LIT__CONTRACT_START__NA | COMPLETED | 0 | 2026-09-24T12:49:46.506897+00:00 | 2026-09-24T12:50:01.326770+00:00 | 14.820 | PASS_PHASE2_EXT02_CWLS_C00_READY_FOR_NATIVE_COMPARISON |
| BY2H__EXT03__LIT__CONTRACT_START__NA | COMPLETED | 0 | 2026-09-24T12:50:02.370499+00:00 | 2026-09-24T12:50:18.106226+00:00 | 15.736 | PASS_PHASE3_EXT03_YANG2024_C00_READY_FOR_NATIVE_COMPARISON |
| BY2H__EXT04__LIT__CONTRACT_START__NA | COMPLETED | 0 | 2026-09-24T12:50:19.126745+00:00 | 2026-09-24T12:52:43.843465+00:00 | 144.717 | PASS_PHASE4_EXT04_NATIVE_FROZEN_READY_FOR_POST_NATIVE |
| BY2H__RTKLIB__NONE__CONTRACT_START__NA | COMPLETED | 0 | 2026-09-24T12:53:21.047312+00:00 | 2026-09-24T12:53:25.764721+00:00 | 4.717 | — |
| BY2H__HARTLEY_S__S__CONTRACT_START__NA | ABNORMAL_EXIT | 1 | 2026-09-24T12:53:26.958842+00:00 | 2026-09-24T12:53:26.977689+00:00 | 0.019 | — |
| BY2H__HARTLEY_LIT__LIT__CONTRACT_START__NA | ABNORMAL_EXIT | 1 | 2026-09-24T12:53:27.228415+00:00 | 2026-09-24T12:53:27.244549+00:00 | 0.016 | — |
| BY2H__GINAV__NONE__CONTRACT_START__NA | COMPLETED | 0 | 2026-09-24T12:53:27.390497+00:00 | 2026-09-24T12:55:33.942543+00:00 | 126.552 | — |
| BY2O__EXT01__LIT__FILE_START__NA | COMPLETED | 0 | 2026-09-24T12:57:58.488643+00:00 | 2026-09-24T13:21:14.345725+00:00 | 1395.857 | UNSUPPORTED_EXT01_ON_BY2_WITHOUT_PHASE_BIAS_CALIBRATION |
| BY2O__EXT02__LIT__FILE_START__NA | COMPLETED | 0 | 2026-09-24T13:22:59.206270+00:00 | 2026-09-24T13:23:33.103562+00:00 | 33.897 | PASS_PHASE2_EXT02_CWLS_C00_READY_FOR_NATIVE_COMPARISON |
| BY2O__EXT03__LIT__FILE_START__NA | COMPLETED | 0 | 2026-09-24T13:23:34.513491+00:00 | 2026-09-24T13:23:51.504011+00:00 | 16.991 | PASS_PHASE3_EXT03_YANG2024_C00_READY_FOR_NATIVE_COMPARISON |
| BY2O__EXT04__LIT__FILE_START__NA | COMPLETED | 0 | 2026-09-24T13:23:52.868523+00:00 | 2026-09-24T13:27:00.341316+00:00 | 187.473 | PASS_PHASE4_EXT04_NATIVE_FROZEN_READY_FOR_POST_NATIVE |
| BY2O__RTKLIB__NONE__FILE_START__NA | COMPLETED | 0 | 2026-09-24T13:27:33.125096+00:00 | 2026-09-24T13:27:39.846405+00:00 | 6.721 | — |
| BY2O__HARTLEY_S__S__FILE_START__NA | COMPLETED | 0 | 2026-09-24T13:27:41.584505+00:00 | 2026-09-24T13:27:45.403198+00:00 | 3.819 | — |
| BY2O__HARTLEY_LIT__LIT__FILE_START__NA | COMPLETED | 0 | 2026-09-24T13:27:46.170888+00:00 | 2026-09-24T13:27:50.010382+00:00 | 3.839 | — |
| BY2O__GINAV__NONE__FILE_START__NA | COMPLETED | 0 | 2026-09-24T13:27:50.657147+00:00 | 2026-09-24T13:30:02.563049+00:00 | 131.906 | — |

24 次登记原生运行墙钟合计 2974.2 s（不含空闲等待、评估与归档；冻结前冒烟的用时见 00_CONTROL/PREFREEZE_SMOKE_SUMMARY*.json）。

## EXT01 搜索预算（原生 SEARCH_CERTIFICATES 逐历元标记）

| 序列 | 原生历元 | 窗内历元 | 触及节点上限（全表 / 窗内） | 触及运行时间预算（全表 / 窗内） | 节点上限 | 最大展开节点 | 终止原因 | 文件 SHA-256 |
|---|---|---|---|---|---|---|---|---|
| BY2 | 1509 | 1370 | 0 / 0 | 0 / 0 | 1000000 | 511 | GLOBAL_BOUND_CERTIFIED 1077、NO_FEASIBLE_MODEL 432 | `2a5989a5c341fed4…` |
| BY2H | 1423 | 1350 | 0 / 0 | 0 / 0 | 1000000 | 221 | GLOBAL_BOUND_CERTIFIED 1112、NO_FEASIBLE_MODEL 311 | `84c66e601fae9c2b…` |
| BY2O | 2231 | 1885 | 0 / 0 | 0 / 0 | 1000000 | 415 | GLOBAL_BOUND_CERTIFIED 1566、NO_FEASIBLE_MODEL 665 | `7316edddf210a12d…` |

## 补充说明

### 报告层改动证据（hx02_aggregate.py）

`hx02_aggregate.py` 在代码冻结（`88594ef`）后只增加了报告渲染：原生运行清单与墙钟时间、EXT01 搜索预算、补充说明、修正记录、事故五节，以及 Outcome 块中的修正数与事故数；长表的行与列不变。用冻结版代码树（`git archive 88594ef`，该文件 SHA-256 `7e73aa216b66f1a77610ba6378ba74902a7f9ac31a499ab18585d0dfeb36f18a`）与改后的代码（`f66dc59001d5b2757526620f807cc932539790b14974e21ac3f878187f5fcebb`），在 scratch 的两个影子阶段目录中各汇总一次。两个目录只读链接同一份 RUNS、00_CONTROL、00_CONTRACT 与 01_INPUT_PINS，不写 docs。
- 冻结版生成的 `EXTERNAL_FIVE_CATEGORY_TABLE.csv`：`7475d7ef9780cdc9b2d82943dc786d58732076b9bad819f945f5010346190fba`（480 行）
- 改后版生成的 `EXTERNAL_FIVE_CATEGORY_TABLE.csv`：`7475d7ef9780cdc9b2d82943dc786d58732076b9bad819f945f5010346190fba`（480 行）
- 结论：两份 SHA-256 相同，改动只影响渲染。正式汇总 `$HX02/90_AGGREGATE/EXTERNAL_FIVE_CATEGORY_TABLE.csv` 由改后版生成，其 SHA-256 见 AGGREGATE_MANIFEST.json；汇总后另行核对它与上面两份相同。
- 第一次正式汇总（2026-09-24T13:40:03.946970+00:00）的 CSV 为 `7475d7ef9780cdc9b2d82943dc786d58732076b9bad819f945f5010346190fba`，与上面两份相同。之后为在补充说明中加入“复现检查的逐文件差异”与“失败清单的分母”两节，重新汇总一次；第一次汇总的全部输出原样保留在 `$HX02/00_CONTROL/AGGREGATE_RENDER_1_SUPERSEDED/`。两次汇总的代码、RUNS 与长表相同，只有 HX02_RESULTS.md 不同。

### Hartley BY2H 两支失败：静止初始化门

BY2H（CONTRACT_START）Hartley-S 与 Hartley-LIT 两支的原生运行都在 0.02 s 内结束，失败类别均为 **ABNORMAL_EXIT**，退出码 1。stderr 原文如下：
- `BY2H__HARTLEY_LIT__LIT__CONTRACT_START__NA`：`FAIL_HARTLEY_H5_NATIVE error=static gyro gate failed`（ABNORMAL_EXIT，退出码 1，原生用时 0.016 s）
- `BY2H__HARTLEY_S__S__CONTRACT_START__NA`：`FAIL_HARTLEY_H5_NATIVE error=static gyro gate failed`（ABNORMAL_EXIT，退出码 1，原生用时 0.019 s）
这是 `hartley_h5_runner` 的静止初始化门（`run_h5.cpp:304-317`）：输入首条记录起 [t0, t0 + 5 s) 内陀螺模长中位须 < 0.05 rad/s，且 |加计模长中位 − 9.81| 须 < 0.5 m/s²，运行器先查陀螺门。按该代码在钉住的 BY2H 输入缓存（`732d45c70815ba65c7832ecbfb41edf5c571fd4e80fb13df497a99fe9863436e`）上逐字复现（中位数算法同 `run_h5.cpp:129`），结果如下：

| 序列 | 初始化窗 [s] | 行数 | 陀螺模长中位 [rad/s]（门 < 0.05） | 加计模长中位 [m/s²] | \|加计模长中位 − 9.81\| [m/s²]（门 < 0.5） | 登记运行 |
|---|---|---|---|---|---|---|
| BY2 | 44.887–49.887 | 1031 | 0.015289（通过） | 9.507909 | 0.302091（通过） | 两支完成 |
| BY2H | 413.037–418.037 | 929 | 0.475127（未通过） | 9.104866 | 0.705134（未通过） | 两支 ABNORMAL_EXIT |
| BY2O | 3101.557–3106.557 | 1035 | 0.015289（通过） | 9.515264 | 0.294736（通过） | 两支完成 |

BY2H 陀螺模长中位 0.475127 rad/s，约为门限的 9.5 倍，陀螺门不通过；加计一项 0.705134 m/s² 也超过 0.5，但运行器在陀螺门处已终止，没有走到这一门。机器人在合约起点 413 s 处于运动中，这是 CONTRACT_START 对 Hartley 的影响。4.7 s IMU 缺口在 413 s 之前，不在输入内。两支使用同一输入缓存、同一初始化门，同因同果。按规则记为失败，附完整 stderr，不重试、不改参数。BY2 与 BY2O 的同一复现都通过两门，与其登记运行完成一致，说明复现与运行器的判定一致。
复现记录：`$HX02/00_CONTROL/HARTLEY_STATIC_GATE_REPLICATION.json`（SHA-256 `25387acb346c92f7aa04e848e928992f0d9060771b89e33d8dd90fd3d2510b24`）。

### GINav BY2 未进入冻结评估器（D8）与 CLEAN4 coverage_aware_c00 的对照

本任务 BY2 的 GINav 原生输出 `.pos` 为 `39453826453515689416d3d32a8d39290b0fbb35b71525283b692f8fccb788b2`，与 CLEAN4 r4c 的 `.pos` 逐字节相同；窗口 NAV 为 `f0fa3e71270cce08ce6174376a694a00a92f725116f8cec86eed4d8062529012`，与 v3 尝试 NAV（由 coverage_aware 标准 NAV 导出）相同。窗内 77 行全部有限。
冻结评估器之前登记的 D8 有界门（§4.3，界同规则 6）只有**速度**一条越界：窗口 NAV 第 32 行（文件第 32 行），t = 244.999 s，速度 50.638686 m/s，门限 50 m/s。全窗最大值：速度 50.682022 m/s，位置位移 336.777 m（门限 10000 m），高度位移 235.872 m（门限 1000 m）。因此记 ALGORITHM_FAILURE_DIVERGED（`NOT_RUN_ALGORITHM_FAILURE`），按登记规则不调用冻结评估器，只有不开参考的覆盖统计。
BY2H 窗内只有 2 行（最大速度 1.772 m/s），D8 通过，覆盖统计与冻结评估器 v3、v2 三种都跑了。BY2O 窗内 5 行，D8 同样只有速度一条越界（第 5 行，t = 3561.999 s，68.772 m/s；位移 202.9 m、高度 199.7 m 在界内），同样记 ALGORITHM_FAILURE_DIVERGED，未调用冻结评估器。

| 口径 | 窗内行 / 闭窗整数秒 | 行覆盖 | 时间跨度覆盖 | 最大缺口 [s] | 段数 | 水平 RMSE [m] | yaw RMSE [deg] | 出处 |
|---|---|---|---|---|---|---|---|---|
| 本任务 HX-02 | 77/275 | 0.28 | 0.6204270072992701 | 11.0 | 38 | 未评估（D8） | 未评估（D8） | `$HX02/RUNS/BY2__GINAV__NONE__C00__NA/eval/GINAV_EVALUATION.json` |
| CLEAN4 coverage_aware_c00 FORMAL_WINDOW | 77/275 | 0.28 | 0.6204270072992701 | 11.0 | 38 | 130.8187259110151 | 69.75333248293973 | `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/11_LC02_GINAV2021_OFFICIAL_REPRODUCTION/coverage_aware_c00/GINAV_C00_FORMAL_WINDOW_EVALUATION.csv` 第 2 行，SHA-256 `5581b0c84942f7d47695e612f2ca80b32be848d3c4039d6c65f4c3f6fb0e3f2d` |

差异来源：数据完全相同，覆盖统计逐项相同，差别只在评估流程。CLEAN4 的覆盖感知评估在纯评估事务中直接对这 77 行调用冻结评估器，得到 130.8 m / 69.75°。同一数据在那次事务中产出了误差指标，说明它没有施加本任务的 D8 有界门；其状态记为 `EXACT_OFFICIAL_ROUTE_WITH_POOR_BY2_ACCURACY_AND_AVAILABILITY`，报告也写明精度超出评估器的描述性阈值。HX-02 在冻结评估器之前登记了 D8 有界门，第 32 行 50.639 m/s 越过 50 m/s 速度界，于是按失败记录，不产生误差指标。差异不是精度或数据变化造成的，而是本任务登记的门控规则所致。
参照：v3 封存表 `MAIN_TABLE_V3.csv` 第 19 行 LC02_GINAV BY2 记为 `UNAVAILABLE_EVALUATION_FAILED` / `UNAVAILABLE`（文件 SHA-256 `cd734338cf89518679d78179f410a79ecad3060535d3b80e43a62545cee9b21c`，只读）。

### 复现检查的逐文件差异（BY2 C00）与一条原因更正

判定按登记规则：登记文件的 SHA-256 一致记 REPRODUCED，不一致记 NOT_REPRODUCED；上面复现检查表的 detail 列为截断显示，逐文件清单与哈希全文见 REPRODUCTION_CHECKS.json。下面对 BY2 C00 的不一致文件逐项核对（只读 HX-02 原生产物与 CLEAN4 产物，未打开参考轨迹），并更正一条自动写入的原因。

- **EXT01**：登记 `PHASE1R_NATIVE_FREEZE.json` `6da2b5a05b9f…`，本任务 `d11ed040cdc1…`，记 NOT_REPRODUCED。产物目录同名文件 14 份，7 份逐字节相同，其中有 NATIVE_HEADING_RESULTS、DD_DIAGNOSTICS、SEARCH_CERTIFICATES、TRACKING_DIAGNOSTICS；声明范围航向表相同（`4077df65ab3e…`）。不同的 7 份：FAILURE_LEDGER 只差 runtime_seconds 列；RUNTIME 只差 runtime_seconds 与 worker_pid 列；PROXY_DIAGNOSTICS 只差 3 个 trace 列：CLEAN4 有值，本任务原生运行禁用 trace，这 3 列全为空（BY2 1509 行、BY2H 1423 行、BY2O 2231 行；三次运行的原生 open 审计参考文件打开数与 old_runtime_input_count 均为 0）；RTKLIB_DIAGNOSTIC_GPS_L1.pos 共 588 行，只有 4 行 `% inp file` 输入路径头不同，解算正文相同；RTKLIB 诊断摘要、SUMMARY 与 freeze JSON 的差异都在运行元数据：命令与路径、提交与运行器源码哈希、耗时与进程号、资源探针、trace 块（本任务禁用）、provider 哈希，以及 convbin 重建的 4 份 RINEX 的哈希；这 4 份 RINEX 只差第 2 行生成日期（PGM / RUN BY / DATE）与第 4 行 log 路径注释，观测与星历正文相同。provider 中只有 rtklib_bridge 不同：.so 由 CLEAN4 记录的 `6cc83e59ec01…` 变为当前的 `6df666008924…`（CLEAN4 之后改过源码 .c/.h 并重编译，本任务内未重编译），convbin、rnx2rtkp、LAMBDA 库与 IERS 档案的哈希相同。方法输出逐字节相同，说明 bridge 的这一差异在 BY2 C00 的方法输出上没有可见影响。
- **EXT02**：登记 `c1d8260df693…`，本任务 `64e115838168…`，记 NOT_REPRODUCED。同名文件 12 份，6 份逐字节相同；NATIVE_HEADING_RESULTS（1509 行）只差 runtime_seconds 列；RUNTIME 只差 runtime_seconds、worker_pid、worker_max_rss_bytes 列；NATIVE_SUMMARY、RESOURCE_DETERMINISM_PROBE、ATTEMPT_IDENTITY 与 freeze JSON 的差异在运行元数据（耗时、内存、进程号、资源、提交与运行器源码哈希、缓存指纹、路径与序列规格）与 provider 哈希：rtklib_bridge .so（`6cc83e59ec01…` → `6df666008924…`）与 bridge 源码 .c/.h 不同，重建的 4 份 RINEX 同样只差第 2、4 行头。声明范围航向表相同（`08fe64c3869d…`）。CLEAN4 目录另有 5 份文件（EXT02_C00_FRACTIONAL_DD_DIAGNOSTICS.csv、EXT02_C00_POST_NATIVE_DIAGNOSTICS_MANIFEST.json、EXT02_C00_POST_NATIVE_OBJECTIVE_DIAGNOSTICS.csv、EXT02_C00_PROXY_DIAGNOSTICS.csv、EXT02_C00_TRACE_DIAGNOSTICS.csv），是 CLEAN4 的事后诊断，本任务原生阶段不生成。
- **EXT03**：登记 `e172100ad64a…`，本任务 `2acc0a075524…`，记 NOT_REPRODUCED。本任务只跑声明范围（主模式 GPS_BDS_DUAL_FREQUENCY / CONSTRAINED / σ = 0.010），CLEAN4 跑了全部系统模式与策略：NATIVE_HEADING_RESULTS 本任务 1509 行、CLEAN4 15090 行，同名文件 15 份中 2 份逐字节相同（参数登记表与信号可用性），其余按行范围不同。声明范围内的航向表相同（EXT03 `aaa3832b312c…`）。
- **EXT04**：登记 `5f74a0928939…`，本任务 `cfe00b194b9e…`，记 NOT_REPRODUCED。本任务只跑声明范围（GPS_BDS_DUAL_FREQUENCY 模式的 FAR + 主 PAR 策略），CLEAN4 跑了全部系统模式与策略：NATIVE_HEADING_RESULTS 本任务 3018 行、CLEAN4 40743 行，同名文件 16 份中 3 份逐字节相同（参数登记表与信号可用性），其余按行范围不同；本任务不跑敏感性策略，SENSITIVITY_SUMMARY 只有表头（0 行）。声明范围内的航向表相同（EXT04_FAR `9d2cb8eb9a45…`、EXT04_PAR `9d2cb8eb9a45…`）。CLEAN4 目录另有 8 份事后诊断与 trace 诊断文件，本任务原生阶段不生成。
- **Hartley-S**：NAV `dc4d95a1e634…` 与登记值相同，REPRODUCED；Hartley-LIT（仅记录）NAV `b46ffe7cf930…` 同样相同。
- **GINav**：`.pos` `394538264535…`、r4c 标准 NAV `99f3b09ea4f3…`、v3 尝试窗口 NAV `f0fa3e71270c…` 三份都与登记值逐字节相同。coverage_aware 标准 NAV（`85902928bac6…`）不是逐字节相同，按登记规则保留 NOT_REPRODUCED；逐项核对：两份都是 80 行，28 个共同列在全部行上数值相等；有 70 个单元格文字不同，只是小数位写法不同（CLEAN4 文件补零到固定位数，如 `0.00000` 对 `0.0`、`4076711.9800` 对 `4076711.98`）；CLEAN4 文件另有 10 列（status_name、native_pitch_rfu_enu_deg、native_roll_rfu_enu_deg、native_emitted_yaw_deg、position_physical_point、native_body_frame、project_body_frame、native_navigation_frame、project_navigation_frame、alignment_row）。**更正**：上表 GINav 的 known_reasons 写的是“MATLAB release/driver state on this host may differ from the CLEAN4 r4c run”，这条不成立：`.pos` 逐字节相同，MATLAB 一侧已复现；不一致只来自 CLEAN4 覆盖感知写出器的列集合与数字格式。
- **RTKLIB**（仅记录，不在登记复现清单内）：上表记 DIFFERENT。两份 `.pos` 都是 685 行，660 行解算正文逐字相同，只有 4 行 `% inp file` 输入路径头不同（CLEAN4 的尝试目录与本任务 scratch 运行目录）。

### 失败清单的分母

失败清单里分母列为 UNAVAILABLE 的几行，分母如下（取自长表与运行记录）：

| 运行 | 失败类别 | 分母 | 说明 |
|---|---|---|---|
| BY2/LC02_GINAV | ALGORITHM_FAILURE_DIVERGED | 窗内 77/275 （原生输出行 / 闭窗整数秒） | D8 速度界：第 32 行，t = 244.999 s，50.639 m/s |
| BY2O/LC02_GINAV | ALGORITHM_FAILURE_DIVERGED | 窗内 5/378 （原生输出行 / 闭窗整数秒） | D8 速度界：第 5 行，t = 3561.999 s，68.772 m/s |
| BY2H/Hartley-S | ABNORMAL_EXIT | 0 / 2701（相对位姿网格 0.1 s，窗 [413, 683]；BY2 与 BY2O 同一规则为 2741 与 3771） | 静止初始化陀螺门，原生无输出 |
| BY2H/Hartley-LIT | ABNORMAL_EXIT | 0 / 2701（相对位姿网格 0.1 s，窗 [413, 683]；BY2 与 BY2O 同一规则为 2741 与 3771） | 静止初始化陀螺门，原生无输出 |
| BY2H/EXT05C-S（FILE_START） | ALGORITHM_FAILURE_DIVERGED | v3 封存行，本任务不评估 | MAIN_TABLE_V3.csv 第 48 行，补充行 |

## 修正记录（结果之前登记，详见 HX02_PREREG.md §16）

| 修正 | 登记时间（UTC） | 内容 | 修正提交 | 修正后合约 SHA-256 |
|---|---|---|---|---|
| 1 | 2026-09-24T12:42:44Z | per-branch relative-pose alignment; 6 relative-pose calls | `88594ef27e20` | `85b13d489d29…` |
| 2 | 2026-09-24T12:42:44Z | quiet-machine wait cap 600 s; load at launch in COMMAND.json | `88594ef27e20` | `85b13d489d29…` |

- 指令写法：等当前原生运行（EXT01 BY2）完成并归档后、下一次原生启动前，在账本上正常停止控制器；不要中断进行中的原生运行
- 实际停止点：GINav BY2 评估完成后（2026-09-24T12:35:42.707Z 记 EVALUATED）、BY2 相对位姿评估启动前（2026-09-24T12:35:42.734Z 冻结，12:35:42.844Z 退出）
- 与指令不同的原因：Hartley 两支为批末成对评估：批内先依次跑完 EXT01、EXT02、EXT03、EXT04、RTKLIB、Hartley-S、Hartley-LIT、GINav 的原生运行，控制器在批末才对 Hartley 两支做相对位姿评估，其间没有原生启动。修正到达时 BY2 批已进行到 GINav 原生（12:33:30Z 启动），指令假设的“下一次原生启动前”且早于相对位姿评估的边界已不存在：下一次原生启动（BY2H EXT01）之前，BY2 的相对位姿评估会先按旧规则执行。因此改停在 GINav 评估完成之后、相对位姿评估启动之前；未中断任何原生运行，停止时无原生进程、无相对位姿评估子进程。
- 停止时按原例程归档：BY2__EXT01__LIT__C00__NA、BY2__EXT02__LIT__C00__NA、BY2__EXT03__LIT__C00__NA、BY2__EXT04__LIT__C00__NA、BY2__RTKLIB__NONE__C00__NA、BY2__GINAV__NONE__C00__NA；修正后按新规则评估：BY2__HARTLEY_S__S__C00__NA、BY2__HARTLEY_LIT__LIT__C00__NA

| 账本事件 | UTC | 要点 |
|---|---|---|
| CONTROLLER_START | 2026-09-24T12:23:28.585108+00:00 | `{"code_commit": "3e8a43be928247da09ac4cca8a54178c3db9dadb"}` |
| FROZEN_CODE_CHECK | 2026-09-24T12:23:28.664314+00:00 | `{"files": 53}` |
| CONTROLLER_STOPPED_FOR_AMENDMENT | 2026-09-24T12:36:49.942259+00:00 | `{"exited_utc": "2026-09-24T12:35:42.844146+00:00", "frozen_utc": "2026-09-24T12:35:42.734368+00:00", "reason": "HX-02 pre-registration amendment (per-branch relative-pose alignment; idle-wait cap 600 s)"}` |
| PREREG_AMENDMENT | 2026-09-24T12:44:55.521643+00:00 | `{"amendment_commit": "88594ef27e20a8e660e2246218a6870a290f35ae"}` |
| CONTROLLER_START | 2026-09-24T12:45:00.478920+00:00 | `{"code_commit": "88594ef27e20a8e660e2246218a6870a290f35ae"}` |
| FROZEN_CODE_CHECK | 2026-09-24T12:45:00.547089+00:00 | `{"files": 53}` |
| CONTROLLER_DONE | 2026-09-24T13:33:55.797866+00:00 | `{}` |

## 事故

| # | 阶段 | 时间（UTC） | 事件 | 发现 | 处理 | 后果 |
|---|---|---|---|---|---|---|
| 1 | 修正 1–2 的控制器停止 | 约 2026-09-24T12:34:40Z–12:35:36Z | 停止程序第一次抓错 PID：`pgrep -f` 匹配到 tmux 服务进程（PID 25892），而不是控制器的 Python 进程（PID 25899，strace 25895 的子进程） | 触发条件出现前，用 ps 核对进程树时发现 | 触发前撤下该停止程序（只结束停止程序本身），未向任何进程发送信号；随后核对 /proc/25899 的命令行与进程名，按控制器 Python 进程 PID 25899 重挂。重挂时第一次核对命令因 /proc/PID/cmdline 以 NUL 分隔而未匹配，停止程序没有启动；改用 tr 转换后核对通过，12:35:36Z 重挂成功，12:35:42.734Z 按设计触发 | 无后果：tmux 服务进程与控制器均未收到任何来自该停止程序的信号，运行记录不受影响 |

## Outcome

```
{
  "amendments": 2,
  "decision_rule": "none; all results reported",
  "evaluator_calls_reference": 21,
  "evaluator_calls_reference_free": 3,
  "failures": 11,
  "identity_gate": {
    "IDENTITY_GATE_BEFORE_RESULTS.json": "PASS",
    "IDENTITY_GATE_START.json": "PASS"
  },
  "incidents": 1,
  "legsa_evaluator_calls": 0,
  "legsa_native_calls": 0,
  "method_body_pins": {
    "METHOD_BODY_SHA256_AFTER.json": "PASS",
    "METHOD_BODY_SHA256_BEFORE.json": "PASS"
  },
  "native_calls": 24,
  "native_runs_registered": 24
}
```
