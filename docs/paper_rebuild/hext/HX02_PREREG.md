# HX-02 预注册：五类外部方法在三条序列上的数值结果

状态：代码冻结文件。本文件随提交 `prereg(hx02): five-category external comparison on three sequences` 冻结，该提交记为 **code_freeze**；之后的运行只执行这里登记的内容。起点提交 `0f972b9`（盘点 `docs/paper_rebuild/hext/HX_INVENTORY.csv` 与 `HX_INVENTORY.md`）。方法清单、入口、文献参数、输出类型与指标口径一律取自这两份盘点，不重新盘点。

路径别名：`$W` = 本工作树（分支 stage/clean3-math-repair）；`<CLEAN_ROOT>`、`<RAW_ROOT>` 同盘点；`$V3` = `<CLEAN_ROOT>/stages/CLEAN8_PROTOCOL_V3`；`$CLEAN4` = `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON`；`$HX02` = `<CLEAN_ROOT>/stages/CLEAN9_EXTERNAL_COMPARISON/HX02_FIVE_CATEGORY`；`<HX02_SCRATCH>`、`<EXTERNAL>`、`<MATLAB_EXE>` 分别由被忽略的本地配置 `configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml` 的键 `hx02_scratch`、`hx02_external_root`、`hx02_matlab_executable` 给出（跟踪文件中不写本机绝对路径）。

## 0. 冻结标识

| 对象 | SHA-256 |
|---|---|
| 合约 `configs/paper_rebuild/hext/HX02_CONTRACT_V1.yaml` | `3d5638245b0a0f4fb6468f2ca5720cfa3951ccd53bfdd04d769f4560c50c7831` |
| 输入钉 `$HX02/01_INPUT_PINS/INPUT_PINS.json` | `723ae92bbe4a2622ad5a1f254c504439ac015e9705495eb9c8310b3e1c8a670f` |
| 参数回显参照 `$HX02/01_INPUT_PINS/PARAMS_ECHO_REFERENCE.json`（由 CLEAN4 BY2 记录抽取） | `02c707a5e0a7ed7b43849cbce5d29f0c1f486fce8306d46dc7dffdbdb01a671f` |
| 冻结评估器 `evaluate_nav_trace_kfgins_v2.py` | `aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da` |
| Hartley 运行器（由未改动源码 Release 构建，钉在 `01_INPUT_PINS/HARTLEY/hartley_h5_runner`） | `8bad8d8722c82f3aaa873908b79267b54dc5cc040ae4bf2fb4cc24d8656962fe` |
| MATLAB `<MATLAB_EXE>` | `6dc32276086121e44edf4846f033066ba5b0fae9bad002d8917a411e0a59afa9` |

运行时代码与配置的 SHA-256 全表登记在合约 `code_sha256`（53 项），控制器启动时逐项核对，任一不符即硬停；运行时还要求跟踪文件无改动、`INPUT_PINS.json` 与参数回显参照的哈希与合约一致。

## 1. 硬规则（逐条写入，全部由代码执行）

1. v3 是论文唯一实验链且已封存（科学冻结 7d43b9a、结果提交 fb39cb8、FC-01 收尾 4d932c9）。LegSA 的任何行（F01/F02/F03/A04/F04 及其余配置）只从 v3 封存表读取；本任务不对任何 LegSA 配置做解算或评估（控制器计数器 `legsa_native_calls`、`legsa_evaluator_calls` 恒为 0，出现即硬停）。冻结二进制（前缀 96ae436d）、冻结评估器（前缀 aa049248）、v3 评估点、各序列 base_time 与评估窗不变。
2. 只新增外部方法行。外部方法参数取文献值（第 2 节），不调参。方法本体文件（第 9 节清单）在任务前后 SHA-256 不变；rtklib_bridge 两个 .so 记录当前值、任务内不重编译。允许改动的只有 runner、序列适配层、评估层、NAV 适配器、合约与文档；本提交的改动为 runner 的序列规格分支、序列适配层、评估层、NAV 适配器、控制器与检查工具、合约、测试与文档，不触及方法本体。
3. 参考轨迹（trace/bag/fpl）只在登记的评估器子进程里打开：每次评估恰好 1 次、只读、同一字节核 SHA-256，子进程在 `strace -f -yy -e trace=openat,execve` 下运行，父进程事后从 openat 日志核验（复用 `hext/external_evaluation._evaluate_process` 的方式）；方法原生进程在 `strace --seccomp-bpf -f -e trace=openat,execve` 下运行；控制器进程本身在 `strace -e trace=openat,execve`（不跟随子进程，以免与原生/评估子进程各自的审计嵌套冲突）下运行，并在每次运行后与每批归档前自查该日志，日志缺失即硬停。任一进程打开文件名匹配 `trace_vrtk`、`^trace_`、`.fpl`、`.bag` 或序列 trace 路径的文件即硬停；MATLAB 另有 fopen 台账，出现同类文件即硬停。
4. 存储：运行输出只在 `<HX02_SCRATCH>`（ext4，≤20 GB）产生，每批（每条序列）结束后逐文件复制到 `$HX02/RUNS/`、逐文件 SHA-256 复核、写 `ARCHIVE_MANIFEST.json` 后删除 scratch；E: 上不存任何输出。开跑前与每批前（及每批归档前）检查 `df --output=avail /mnt/e ≥ 40 GB`、`/mnt/g ≥ 30 GB`、scratch ≤ 20 GB，低于守卫线硬停。原生进程并发 1、内部 worker ≤ 16（≤ 22）。不做交接包。目录结构见第 12 节；运行在 tmux 独立进程中，进度写 `$HX02/00_CONTROL/PROGRESS.txt`、`STATE.json` 与 `LEDGER.jsonl`，中断后从账本续作，已归档的运行不重跑。
5. 身份门（只读）：MAIN_TABLE_V3.csv 第 17 行 LC01 BY2 C00 yaw = 2.994827460、第 18 行 EXT05C BY2 C00 yaw = 12.048642、F04 三序列 yaw = 1.886272 / 1.933770 / 2.433815（按表中位数舍入比对）；`$V3/07_AGGREGATE/`、`07C_FAILURE_FAMILY_CONFIG/`（及 BASELINE.json 登记的 07D）全部文件 SHA-256 对照 BASELINE.json（65 项，自身前缀 7830a1a5）。任务开始前与结果提交前各比对一次，写进回报。
6. 失败也是结果：发散（位移 > 10 km、速度 > 50 m/s、高度 > 1 km 或非有限）记 ALGORITHM_FAILURE_DIVERGED；无输出记 NO_OUTPUT；异常退出记 ABNORMAL_EXIT；环境失败（如 MATLAB 无法调用）记 RUN_FAILED_ENVIRONMENT；均附完整 stderr；不删行、不换参数、不重试到通过为止。
7. 决策规则：无数值门槛，全部结果如实报告。
8. 新写文档不使用规则 8 所列词语；已有文件名和提交信息照原样。

任务开始时的身份门（`$HX02/00_CONTROL/IDENTITY_GATE_START.json`，SHA-256 `3b835e1321938d846fbb895f2d1c3e7128bc2a6094d9b60e0867d35f414ef1da`）：**PASS**，2026-09-24T10:40:51.056427+00:00；数值 5/5 一致（17 行 2.994827460、18 行 12.048642、4 行 1.886272、9 行 1.933770、13 行 2.433815），封存文件 MATCH 65、MISMATCH 0、MISSING 0、UNREGISTERED 0（其中 CSV 59/59），BASELINE.json `7830a1a596077558d0f2289c066dbd81b1f53e6c25adc8ec0c8833ee055a503b`；解算 0、评估 0、参考打开 0。

## 2. (a) 方法清单与参数

参数值逐项取自 HX_INVENTORY.csv `param_source` 所指合约（行号为跟踪文件行号，已在本提交前逐行核对）。每次原生运行结束后，控制器从原生输出抽取参数回显，与 CLEAN4 BY2 记录抽取的回显逐项比较（`hext/hx02_params_echo.py`），任一项不同或无法读取即硬停（合约文件本身的哈希只作信息记录：EXT02/EXT04 合约在 CLEAN4 运行后增补了原生后章节）。

### EXT01（dual_antenna_ambiguity_heading，heading_only，config LIT）

| 项 | 登记值 |
|---|---|
| runner | scripts/paper_rebuild/run_horizontal_literature_phase1r.py |
| runner_arguments | `["--trace-mode", "disabled", "--workers", "16"]` |
| valid_flag | integer_solution_returned == true (no ambiguity acceptance test exists) |

| 参数 | 值 | 出处 |
|---|---|---|
| baseline_length_m | 0.35 | EXTERNAL_METHOD_CONTRACTS_V1.yaml:9; PHASE1R_VALIDATION_CONTRACT_V2.yaml:35 |
| sigma_floors | pseudorange 0.50 m, carrier 0.004 cycle, doppler 0.02 Hz | EXTERNAL_METHOD_CONTRACTS_V1.yaml:73-84 |
| pseudorange_sigma_m | max(0.50,0.01*2^prStdev) | PHASE1R_VALIDATION_CONTRACT_V2.yaml:64 |
| carrier_sigma_cycles | max(0.004,0.004*cpStdev) | PHASE1R_VALIDATION_CONTRACT_V2.yaml:65 |
| doppler_sigma_hz | max(0.02,0.002*2^doStdev) | PHASE1R_VALIDATION_CONTRACT_V2.yaml:66 |
| lambda_seed_count | 8 | PHASE1R_VALIDATION_CONTRACT_V2.yaml:74 |
| deterministic_node_budget | 1000000 | PHASE1R_VALIDATION_CONTRACT_V2.yaml:77 |
| ambiguity_acceptance_test | none (ratio_threshold null) | PHASE1R_VALIDATION_CONTRACT_V2.yaml:80-81 |

### EXT02（dual_antenna_ambiguity_heading，heading_only，config LIT）

| 项 | 登记值 |
|---|---|
| runner | scripts/paper_rebuild/run_horizontal_literature_phase2.py |
| runner_arguments | `["--mode", "native-only", "--trace-mode", "disabled", "--workers", "16"]` |
| valid_flag | method_native_accepted == true |

| 参数 | 值 | 出处 |
|---|---|---|
| K_policy | ALL_UNIQUE_CANDIDATES | PHASE2_EXT02_CWLS_CONTRACT_V1.yaml:48 |
| delta_Delta | 0.05 | PHASE2_EXT02_CWLS_CONTRACT_V1.yaml:50 (paper value) |
| baseline_length_m | 0.35 | PHASE2_EXT02_CWLS_CONTRACT_V1.yaml:53 |
| refinement | tolerance 1.0e-10, max 20 iterations | PHASE2_EXT02_CWLS_CONTRACT_V1.yaml:55-56 |
| elevation_mask_deg | 10.0 | PHASE2_EXT02_CWLS_CONTRACT_V1.yaml:87 |
| code_sigma_m | max(0.50, 0.01*2^prStdev) | PHASE2_EXT02_CWLS_CONTRACT_V1.yaml:124 |
| carrier_sigma_cycles | max(0.004, 0.004*cpStdev); cpStdev=15 invalid | PHASE2_EXT02_CWLS_CONTRACT_V1.yaml:125 |
| dd_covariance | SD variance = receiver1 + receiver2; DD = diag(nonpivot SD) + pivot SD * 11^T; objective weight full Q_DD^-1 | PHASE2_EXT02_CWLS_CONTRACT_V1.yaml:126-128 |

### EXT03（dual_antenna_ambiguity_heading，heading_only，config LIT）

| 项 | 登记值 |
|---|---|
| runner | scripts/paper_rebuild/run_horizontal_literature_phase3.py |
| runner_arguments | `["--mode", "native-only", "--trace-mode", "disabled", "--workers", "16"]` |
| declared_scope | `{"variant_ids": ["GPS_BDS_DUAL_FREQUENCY__CONSTRAINED__0.010"]}` |
| valid_flag | solution_state != invalid; paper_ratio_fixed reported separately (ratio-fixed rate) |

| 参数 | 值 | 出处 |
|---|---|---|
| baseline_length_m | 0.35 | PHASE3_EXT03_YANG2024_CONTRACT_V1.yaml:40 |
| ratio_threshold | 3.0 | PHASE3_EXT03_YANG2024_CONTRACT_V1.yaml:44 (paper) |
| initial_baseline_covariance_m2 | 900.0 | PHASE3_EXT03_YANG2024_CONTRACT_V1.yaml:46 (paper) |
| initial_ambiguity_covariance_cycle2 | 900.0 | PHASE3_EXT03_YANG2024_CONTRACT_V1.yaml:47 (paper) |
| baseline_sigma_m | 0.01 | PHASE3_EXT03_YANG2024_CONTRACT_V1.yaml:48 (declared primary; sensitivity values :49 not run) |
| elevation_mask_deg | 15.0 | PHASE3_EXT03_YANG2024_CONTRACT_V1.yaml:115-116 (RTKLIB default) |
| unspecified_noise | RTKLIB 180043ee defaults: phase 0.003 m + 0.003 m/sin(el), code/phase ratio 100, GPS/BDS factor 1.0 | PHASE3_EXT03_YANG2024_CONTRACT_V1.yaml:161-178 |

### EXT04（dual_antenna_ambiguity_heading，heading_only，config LIT）

| 项 | 登记值 |
|---|---|
| runner | scripts/paper_rebuild/run_horizontal_literature_phase4.py |
| runner_arguments | `["--mode", "native-only", "--trace-mode", "disabled", "--workers", "16"]` |
| declared_scope | `{"system_modes": ["GPS_BDS_DUAL_FREQUENCY"], "policy_ids": ["FAR_ALL_AMBIGUITIES", "EXT04_PAR_DECLARED_POLICY_V1"]}` |
| valid_flag | accepted_by_policy == true (FAR and primary PAR reported as EXT04_FAR / EXT04_PAR) |

| 参数 | 值 | 出处 |
|---|---|---|
| baseline_length_m | 0.35 | PHASE4_EXT04_WU2025_CONTRACT_V1.yaml:74 |
| elevation_mask_deg | 10.0 | PHASE4_EXT04_WU2025_CONTRACT_V1.yaml:118 |
| minimum_cno_dbhz | 20 | PHASE4_EXT04_WU2025_CONTRACT_V1.yaml:119 |
| ratio_threshold | 3.0 | PHASE4_EXT04_WU2025_CONTRACT_V1.yaml:158-163 (paper experimental value, second/best >= 3) |
| baseline_tolerance_m | 0.05 | PHASE4_EXT04_WU2025_CONTRACT_V1.yaml:164-168 |
| posterior_chi_square_alpha | 0.01 | PHASE4_EXT04_WU2025_CONTRACT_V1.yaml:169-173 (declared, not in paper) |
| ADOP_threshold_cycles | 0.12 | PHASE4_EXT04_WU2025_CONTRACT_V1.yaml:174-177 (declared, not in paper) |

### RTKLIB（dual_antenna_ambiguity_heading，heading_only，config -）

| 项 | 登记值 |
|---|---|
| valid_flag | associated Q=1 solution; Q=2 reported separately |
| executable | `{"path_alias": "<EXTERNAL>/RTKLIB/app/consapp/rnx2rtkp/gcc/rnx2rtkp", "sha256": "3a0ad1c55435b45e1f83b2e713a0b0fb837a5f0a118d76ead3df1f9e3e531eda"}` |
| configuration | `{"file": "RTKLIB_UNMODIFIED_MOVING_BASE.conf", "sha256": "97f0fe4157ce31909538e696184a7faadad059c3099ab912cbe2e97b0fc9e14f", "key_values": "pos1-posmode=movingbase, pos1-frequency=l1+l2, pos2-armode=continuous, pos2-arthres=3, pos2-baselen=0.350"}` |
| argv | `["rnx2rtkp", "-k", "<conf>", "-o", "<pos>", "[-ts <first selected exact pair, GPST ms> for CONTRACT_START]", "gnss2.obs", "gnss1.obs", "gnss1.nav", "gnss2.nav"]` |
| body_yaw | GNSS2-GNSS1 baseline heading + 90 deg |
| inventory_id | RTKLIB_UNMODIFIED_MOVING_BASE |

### HARTLEY_LIT（legged_state_estimation，relative_pose，config LIT）

| 项 | 登记值 |
|---|---|
| run_id | H5_PAPER_TABLE1_PROCESS_REGRESSION_WITH_GO2_FK_PROXY |
| process_policy | PAPER_TABLE1_FIVE_PROCESS_EQ61 |
| backend_id | HARTLEY_IJRR2020_REPORTED_BACKEND |
| inventory_id | Hartley |

| 参数 | 值 | 出处 |
|---|---|---|
| linear_acceleration_noise_std | 0.04 m/s^2 | HARTLEY_PARAMETER_SOURCE_REGISTRY.csv:4 (IJRR 2020 Table 1) |
| angular_velocity_noise_std | 0.002 rad/s | registry :5 |
| accelerometer_bias_random_walk_std | 0.001 m/s^3 | registry :6 |
| gyroscope_bias_random_walk_std | 0.001 rad/s^2 | registry :7 |
| contact_linear_velocity_noise_std | 0.05 m/s | registry :8 |
| joint_encoder_noise_std | 1.0 deg (not applicable: no joint encoder data in the Go2 log) | registry :9 |
| initial_std | orientation 30 deg, velocity 1.0 m/s, IMU position 0.1 m, feet 0.1 m, gyro bias 0.005 rad/s, accel bias 0.05 m/s^2 | registry :10-16 |
| fk_measurement_std_m | 0.01 | registry :44 (BY2 instantiation, not re-calibrated) |
| contact_force_on | FR 34.2, FL 33.8, RR 30.6, RL 32.0 | registry :48 |
| contact_force_off | FR 24.8, FL 25.2, RR 23.4, RL 24.0 | registry :49 |
| contact_minimum_dwell_s | 0.012035608291625977 | registry :50 |

### HARTLEY_S（legged_state_estimation，relative_pose，config S）

| 项 | 登记值 |
|---|---|
| run_id | H5_PRIMARY_GO2_ALLAN_EQ61_FK10MM |
| process_policy | GO2_CONTINUOUS_IMU_PAPER_NATIVE_CONTACT_EQ61 |
| backend_id | HARTLEY_IJRR2020_REPORTED_BACKEND |
| runner_static_initialisation | first 5 s of the input: median gyro norm < 0.05 rad/s and |median accel norm - 9.81| < 0.5 m/s^2, else the runner exits non-zero (runner behaviour, unchanged) |
| runner_gap_behaviour | no maximum-dt rule; an IMU gap is one zero-order-hold propagation step. BY2H 4.74 s gap at 407.017-411.757 s (then 0.722 s and 0.558 s gaps to 413.037 s) lies before the 413 s contract start and is not in the CONTRACT_START input |
| inventory_id | Hartley |

| 参数 | 值 | 出处 |
|---|---|---|
| imu_noise | GO2_IMU_ALLAN_90MIN_RECOVERED_V1: gyro 2.865130e-04 rad/s/sqrt(Hz), accel 1.285395e-03 m/s^2/sqrt(Hz), gyro bias RW 2.996871e-05 rad/s^2/sqrt(Hz), accel bias RW 1.594412e-04 m/s^3/sqrt(Hz) | HARTLEY_PARAMETER_SOURCE_REGISTRY.csv:37-40 |
| contact_linear_velocity_noise_std | 0.05 m/s | registry :8 (CLEAN4 primary branch) |
| initial_std | same as HARTLEY_LIT | registry :10-16 |
| fk_measurement_std_m | 0.01 | registry :44 |
| contact_thresholds | same as HARTLEY_LIT | registry :48-50 |

### GINAV（loosely_coupled_gnss_ins，imu_point_nav，config -）

| 项 | 登记值 |
|---|---|
| configuration | `{"template": "BY2_GINAV_SPP_LC.ini", "template_sha256": "688ea8acaa910971b9cc3a37861328d6be1b678e82f8a409a1385207ebc66975", "replaced_fields": ["data_dir", "start_time", "end_time"], "non_sequence_lines_sha256": "0c148b7300a9ca8d86dddaeb49d8534558c6a61437e28e1d7c317ad5198c2b22"}` |
| matlab | `{"path_alias": "<MATLAB_EXE>", "sha256": "6dc32276086121e44edf4846f033066ba5b0fae9bad002d8917a411e0a59afa9"}` |
| inputs | GNSS1 RAWX/SFRBX -> convbin RINEX 3.04 + broadcast ephemeris; single-constant RAWX/NAV-PVT epoch normalisation; Go2 body IMU FLU->RFU format-2 increments |
| nav_adapter | .pos -> coverage-aware standard CSV -> 11-column NAV (clean5_degradation/evaluation.ginav_nav order), clipped to the window |
| inventory_id | LC02_GINAV |

EXT03 只跑主模式 GPS_BDS_DUAL_FREQUENCY / CONSTRAINED / σ = 0.010；EXT04 只跑 GPS_BDS_DUAL_FREQUENCY 模式的 FAR（FAR_ALL_AMBIGUITIES）与主 PAR 策略（EXT04_PAR_DECLARED_POLICY_V1），两者分别成行 EXT04_FAR / EXT04_PAR；敏感性变体不跑。Hartley-LIT 与 Hartley-S 的 FK 量测 std（0.010 m）与接触阈值相同，后端固定 HARTLEY_IJRR2020_REPORTED_BACKEND。GINav 配置由 BY2 派生配置（688ea8ac…）只替换 data_dir、start_time、end_time 三行，其余 92 行逐字节相同（非序列行 SHA-256 `0c148b73…`，三份差异见第 10 节）。

## 3. (b) 运行清单（24 次原生运行，三序列一个不少）

| 运行目录 `RUNS/<SEQ>__<METHOD>__<CONFIG>__<CASE>__<SEED>` | 序列 | 方法 | 起点 | 评估窗 [s] |
|---|---|---|---|---|
| `BY2__EXT01__LIT__C00__NA` | BY2 | EXT01 | FILE_START | [66.0, 340.0] |
| `BY2__EXT02__LIT__C00__NA` | BY2 | EXT02 | FILE_START | [66.0, 340.0] |
| `BY2__EXT03__LIT__C00__NA` | BY2 | EXT03 | FILE_START | [66.0, 340.0] |
| `BY2__EXT04__LIT__C00__NA` | BY2 | EXT04 | FILE_START | [66.0, 340.0] |
| `BY2__RTKLIB__NONE__C00__NA` | BY2 | RTKLIB | FILE_START | [66.0, 340.0] |
| `BY2__HARTLEY_S__S__C00__NA` | BY2 | HARTLEY_S | FILE_START | [66.0, 340.0] |
| `BY2__HARTLEY_LIT__LIT__C00__NA` | BY2 | HARTLEY_LIT | FILE_START | [66.0, 340.0] |
| `BY2__GINAV__NONE__C00__NA` | BY2 | GINAV | FILE_START | [66.0, 340.0] |
| `BY2H__EXT01__LIT__CONTRACT_START__NA` | BY2H | EXT01 | CONTRACT_START | [413.0, 683.0] |
| `BY2H__EXT02__LIT__CONTRACT_START__NA` | BY2H | EXT02 | CONTRACT_START | [413.0, 683.0] |
| `BY2H__EXT03__LIT__CONTRACT_START__NA` | BY2H | EXT03 | CONTRACT_START | [413.0, 683.0] |
| `BY2H__EXT04__LIT__CONTRACT_START__NA` | BY2H | EXT04 | CONTRACT_START | [413.0, 683.0] |
| `BY2H__RTKLIB__NONE__CONTRACT_START__NA` | BY2H | RTKLIB | CONTRACT_START | [413.0, 683.0] |
| `BY2H__HARTLEY_S__S__CONTRACT_START__NA` | BY2H | HARTLEY_S | CONTRACT_START | [413.0, 683.0] |
| `BY2H__HARTLEY_LIT__LIT__CONTRACT_START__NA` | BY2H | HARTLEY_LIT | CONTRACT_START | [413.0, 683.0] |
| `BY2H__GINAV__NONE__CONTRACT_START__NA` | BY2H | GINAV | CONTRACT_START | [413.0, 683.0] |
| `BY2O__EXT01__LIT__FILE_START__NA` | BY2O | EXT01 | FILE_START | [3186.0, 3563.0] |
| `BY2O__EXT02__LIT__FILE_START__NA` | BY2O | EXT02 | FILE_START | [3186.0, 3563.0] |
| `BY2O__EXT03__LIT__FILE_START__NA` | BY2O | EXT03 | FILE_START | [3186.0, 3563.0] |
| `BY2O__EXT04__LIT__FILE_START__NA` | BY2O | EXT04 | FILE_START | [3186.0, 3563.0] |
| `BY2O__RTKLIB__NONE__FILE_START__NA` | BY2O | RTKLIB | FILE_START | [3186.0, 3563.0] |
| `BY2O__HARTLEY_S__S__FILE_START__NA` | BY2O | HARTLEY_S | FILE_START | [3186.0, 3563.0] |
| `BY2O__HARTLEY_LIT__LIT__FILE_START__NA` | BY2O | HARTLEY_LIT | FILE_START | [3186.0, 3563.0] |
| `BY2O__GINAV__NONE__FILE_START__NA` | BY2O | GINAV | FILE_START | [3186.0, 3563.0] |

批次顺序 BY2 → BY2H → BY2O；批内顺序 EXT01、EXT02、EXT03、EXT04、RTKLIB、Hartley-S、Hartley-LIT、GINav，一次一个原生进程。

## 4. (c) 指标定义与评估器

三种子进程与启动器的代码路径与 SHA-256（同时登记在合约 `code_sha256`）：

| 文件 | 角色 | SHA-256 |
|---|---|---|
| `src/legsa_gins/paper_rebuild/hext/hx02_heading_evaluation.py` | heading_only 评估子进程（B） | `eedb3faf56ccffca222d915c401d3075dc64583ce68a10f08add9f8b705fa994` |
| `src/legsa_gins/paper_rebuild/hext/hx02_relative_pose_evaluation.py` | relative_pose 评估子进程（C） | `0d9ce68cd1212c66a95efe0e3f635aa5bd954a2937f02924fcbacaabacbff8e4` |
| `src/legsa_gins/paper_rebuild/hext/hx02_coverage_evaluation.py` | 覆盖感知统计子进程（不开参考） | `1f5afe16ff12327e6915dcfbea8adb5a730b7556eed8add920542f6170dbdeec` |
| `src/legsa_gins/paper_rebuild/hext/hx02_evaluation_process.py` | 登记子进程启动器与 openat 审计 | `c94093d1fbf94c9f4db9f6f59334666ea8897c59bcd67654afd4a9914c7764fb` |
| `src/legsa_gins/paper_rebuild/hext/external_evaluation.py` | 冻结评估器封装（imu_point_nav，v3/v2，D12） | `55f2ca5c1c14703c2a4af5cf80b1ca5176e19487aa3f645f3e9efb1e78060df4` |
| `src/legsa_gins/paper_rebuild/horizontal_literature/phase2_runner.py` | 复用的统计函数 `_wrapsafe_error_metrics`/`_continuity_metrics`/`_circular_statistics_deg` | `85112d34e27f1fa8c3043bdcdeb2f418232cd2fffacb40cab3f387f179db6c9b` |
| `src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h7.py` | 复用的 SO(3) 工具（`interpolate_so3` 等） | `84ee803f7c707d6568227107cc7bfb317725ea9bd5f3a2bd3aac032b1f10beb7` |
| `src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h7c.py` | 复用的 `relative_pose_metrics`/`fixed_primary_yaw_translation_gauge`/`apply_fixed_gauge_to_pose` | `41db1e79cb439a9dbee0b972a69f42e0b8e74885f24a7b277848a4cf59cc5233` |

**4.1 heading_only（EXT01–EXT04、RTKLIB）。** 输入为方法原生航向表（每个原生配对历元一行，方法自身有效标志，body yaw = GNSS2−GNSS1 基线航向 + 90°）。参考 yaw = wrap360(90 − interp(unwrap(yaw_ENU)))，只在前后括住的参考样本之间插值、不外推；误差 = wrap180(方法 − 参考)。分母 = 方法原生配对历元表在窗内的历元数（BY2 1370、BY2H 1350、BY2O 1885，见第 10 节）。指标：可用率（窗内有效历元/分母）；有效历元 wrap-safe RMSE、最大绝对误差、P95、圆均值偏差、段数与最大缺口（`_continuity_metrics`）；保持上一有效值的全窗 RMSE、最大绝对误差与 P95（从原生起点因果保持；首个有效值之前的窗内历元单独计为无航向历元，不记零）；EXT03 另报 ratio-fixed 率（及其 RMSE）；RTKLIB 以 Q=1 计有效，Q=2 比例与其误差另报。输出只有 `HEADING_METRICS.json` 与逐历元误差序列 CSV。不导入、不使用带 NOT_AUTHORIZED_FOR_EXECUTION 标记的文件。

**4.2 relative_pose（Hartley-S、Hartley-LIT）。** Hartley 输出点按人工声明为 Go2 body IMU 原点 = LegSA 的 IMU 点，按 FRD 杠杆 [0.03, 0.03 − 0.5·b_med, −0.30] m （Hartley 体坐标为 Go2 FLU，即 FLU 杠杆 [0.03, −(0.03 − 0.5·b_med), 0.30]）平移到天线中点；b_med：BY2 0.356191491865984、BY2H 0.35418777593777223、BY2O 0.35013463864843675。10 Hz 网格 t_j = w0 + 0.1·j（闭窗）；参考 LLH 线性插值、yaw 用 unwrap 后插值，估计位置线性插值、姿态 SO(3) 测地插值，均只在括住处取值。在评估窗起始 10 s（BY2 [66,76]、BY2H [413,423]、BY2O [3186,3196]）内做一次最小二乘对齐，只解绕重力轴的 yaw（逐历元 yaw 偏差的圆均值）与三维平移（给定 yaw 后的均值），不解 roll/pitch/尺度/时间偏移；对齐由 Hartley-S 导出，原样用于两个分支，全窗不再调整（H7_EVALUATION_CONTRACT.yaml:99-117）。Hartley-S 无可用输出时，两分支的相对位姿指标均记 UNAVAILABLE，不做自对齐替代。指标：每 100 m 位置漂移（水平误差模长对参考累计水平路程的 OLS 斜率 ×100，带截距）、每分钟航向漂移（wrap-safe 航向误差按时间 unwrap 后对分钟的 OLS 斜率）、对齐后全窗水平/高程/yaw RMSE、最大水平误差、窗内参考路程，另报 1/5/10 s 相对位姿误差。发散界（第 1 节规则 6）在评估前对原生 NAV 检查。

**4.3 imu_point_nav（GINav）。** `.pos` → 覆盖感知标准 CSV（纬经度 12 位、高度 6 位、ENU 速度 9 位、时间 3 位小数）→ 11 列 NAV（`clean5_degradation/evaluation.ginav_nav` 列序，`%.17g`），按窗裁剪；冻结评估器 aa049248，v3 点（天线中点变换）并行 v2 点（IMU 点），`consistency_failure_policy = D12_BOUNDED_UNAVAILABLE`：先过 D8 有界门（同一发散界），一致性门失败时该版本单列为评估失败类别 UNAVAILABLE_EVALUATION_FAILED（不记零、不删历元）；同时由不开参考的子进程报覆盖感知指标：行覆盖（窗内输出行 / 闭窗整数秒数）、时间跨度覆盖（(末行 − 首行)/窗长）、最大缺口、段数（缺口 > 1.5 s 断段）、首个有效行时刻。窗内无输出记 NO_OUTPUT。

**4.4 评估调用预算。** heading_only 15 次（5 方法 × 3 序列，EXT04 两策略同一次调用）、冻结评估器 ≤ 6 次（GINav v3/v2 × 3，D8 门未过则不调用）、relative_pose 3 次（每序列一次，两分支同一次调用）、不开参考的覆盖统计 3 次；LegSA 0/0。实际次数由账本计数器报告。

## 5. (d) LegSA 参照行与已封存外部行的来源（原样引用，不重算）

| 表 | 行（1 起） | 内容 | 文件 SHA-256 |
|---|---|---|---|
| `$V3/07C_FAILURE_FAMILY_CONFIG/FULL_ABLATION_TABLE_V3.csv` | 27 / 12 / 23 | F04 BY2 / BY2H / BY2O | `44aeaa0302afab54c8179bbb977c9fdac11ebf4f013ac9becdc731840342f4b1` |
| 同上 | 25 / 10 / 21 | F02 BY2 / BY2H / BY2O | 同上 |
| 同上 | 24 / 9 / 20 | F01 BY2 / BY2H / BY2O | 同上 |
| `$V3/07_AGGREGATE/MAIN_TABLE_V3.csv` | 17 / 43 / 50 | LC01 BY2 FILE_START / BY2H CONTRACT_START / BY2O | `cd734338cf89518679d78179f410a79ecad3060535d3b80e43a62545cee9b21c` |
| 同上 | 40 / 47 / 52 | LC01-S BY2 / BY2H CONTRACT_START / BY2O | 同上 |
| 同上 | 18 / 45 / 51 | EXT05C BY2 / BY2H CONTRACT_START / BY2O | 同上 |
| 同上 | 41 / 49 / 53 | EXT05C-S BY2 / BY2H CONTRACT_START / BY2O | 同上 |
| 同上 | 42 / 44 / 46 / 48 | BY2H FILE_START 补充行：LC01 / EXT05C / LC01-S / EXT05C-S（第 48 行为发散，作失败记录） | 同上 |

汇总时逐行核对 (method_id, sequence_id, start_convention) 与上表一致，否则停止；每行附文件路径、行号与文件 SHA-256。BY2H 手稿行用 CONTRACT_START，FILE_START 行进补充。

## 6. (e) 身份门与复现检查

身份门按硬规则 5：`scripts/paper_rebuild/hx02_identity_gate.py`，任务开始前（已完成，PASS）与结果提交前各运行一次，结果写进回报；任一不过即硬停。

复现检查（只记录、不硬停），全部在 BY2 C00：

| 方法 | 对照 | 判定 |
|---|---|---|
| EXT01 | CLEAN4 native_freeze `6da2b5a05b9f784d35e288b64398182e77c235605d9aa90375bac9b166106493` | 本任务 native freeze 文件 SHA-256 相同记 REPRODUCED，否则 NOT_REPRODUCED 并附逐文件差异（freeze 内逐文件哈希表）与声明范围航向表是否一致 |
| EXT02 | `c1d8260df693ed213c004ae90f3446e546e88f599b662ec40879711b8b3f060d` | 同上 |
| EXT03 | `e172100ad64a2c20ee6772f9b7cb1e212cfb940fde8c3ac94c970b101671b3f0` | 同上（本任务只跑主变体，整文件必然少行；另比较主变体航向表） |
| EXT04 | `5f74a0928939c7e630bf8540d1259aeb51c86cf3fc07440fa43503ffc2d2bd46` | 同上（只跑一模式两策略；另比较两策略航向表） |
| Hartley-S | NAV `dc4d95a1e634ea7f7c3aecfcb3cdd50ded8ebf4378dfcd46917ed4875338a600` | NAV.csv SHA-256 相同记 REPRODUCED |
| GINav | .pos `39453826…`；r4c 标准 NAV `99f3b09e…`（用原 `outputs.write_standard_nav` 重生成比较）；coverage_aware NAV `85902928…`（多一列 status_name，按公共列逐值比较）与由其导出的 v3 尝试窗 NAV `f0fa3e71…` | 全部一致记 REPRODUCED |

已知可能原因预先登记：freeze JSON 内嵌运行路径、HX-02 序列规格与执行提交；EXT01/EXT04 依赖的 rtklib_bridge .so 在 CLEAN4 EXT01 R2 之后重建（当前 `liblegsa_rtklib_bridge.so` 6df66600…）；Hartley 运行器由未改动源码重新构建（CLEAN4 二进制 6cc27e04… 已不存在）；MATLAB/驱动状态；runtime 文件含墙钟时间。

## 7. (f) 失败判定

| 类别 | 判定（代码 `hx02_execution.classify` 与发散门） |
|---|---|
| COMPLETED | 原生输出完整且退出码 0 |
| COMPLETED_ABNORMAL_EXIT | 原生输出完整但退出码非 0（例如 runner 自身验证判定 BLOCKED）：照常评估，另加一行 runner_exit_status（退出码与 runner 终态），失败标记 ABNORMAL_EXIT_WITH_COMPLETE_NATIVE_OUTPUT |
| NO_OUTPUT | 退出码 0 但无登记输出；GINav 官方解无可用行或窗内无输出 |
| ABNORMAL_EXIT | 非 0 退出、信号或超时（EXT 6 h、Hartley/RTKLIB/GINav 2 h），无完整输出 |
| RUN_FAILED_ENVIRONMENT | 启动器/环境失败，例如 MATLAB 不可调用、身份不符或未进入登记 harness（fopen 台账无记录） |
| ALGORITHM_FAILURE_DIVERGED | Hartley NAV 或 GINav 窗 NAV 越过发散界（位移 > 10 km、速度 > 50 m/s、高度 > 1 km）或非有限 |

失败运行照样归档，附完整 stderr（`native/NATIVE_stderr.log`）与 FAILURE.json；不删行、不换参数、不重试。中断恢复不是重试：原生运行中断时把未完成目录移入 `<HX02_SCRATCH>/INTERRUPTED/` 并重新启动（计数照记）；评估中断时把部分评估输出移入运行目录内 `INTERRUPTED_EVALUATION_<ts>/` 后重做登记评估（计数照记）。

## 8. (g) 决策规则

无数值门槛，全部结果如实报告。

## 9. (h) 方法本体文件 SHA-256（任务前值）

记录 `$HX02/00_CONTROL/METHOD_BODY_SHA256_BEFORE.json`（2026-09-24T10:41:19.933295+00:00；共 423 项；清单 SHA-256 `7b13420a5b8f74b8a47ad38e1e8146af8eb25b479ef0458b969497908c179bb2`；副本 `docs/paper_rebuild/hext/HX02/METHOD_BODY_SHA256_BEFORE.json`）。结果提交前用 `scripts/paper_rebuild/hx02_method_body_pins.py --compare` 重算，任一变化即硬停。

| 文件 | SHA-256 |
|---|---|
| `$EXTERNAL/RTKLIB/app/consapp/rnx2rtkp/gcc/rnx2rtkp` | `3a0ad1c55435b45e1f83b2e713a0b0fb837a5f0a118d76ead3df1f9e3e531eda` |
| `$EXTERNAL/rtklib_bridge/lib/liblegsa_rtklib_bridge.so` | `6df66600892404dd1c892879fe6e10693e808995fe359e32a6afc983629f8a3b` |
| `$EXTERNAL/rtklib_bridge/lib/librtklib_legsa.so` | `28c25b1cc7fade9b956bfdf77005de8fcb0a382c8411ae6e608c83b82bff53f2` |
| `$W/src/legsa_gins/paper_rebuild/horizontal_literature/ext01_clambda.py` | `a68f5d7988dbe6fbb838562c3d389f8473ef994028a84f76fcfd035f77a2c13d` |
| `$W/src/legsa_gins/paper_rebuild/horizontal_literature/ext02_cwls.py` | `ea65b90282fdeee943eca4764da18fb05fcb9a46b9a7cf44d477d3ff60976f2c` |
| `$W/src/legsa_gins/paper_rebuild/horizontal_literature/ext03_yang2024.py` | `0cf9bc29b9d47f58d17098c6c8e25ff1b1f8d8af06cb265850d401b9c09b4af9` |
| `$W/src/legsa_gins/paper_rebuild/horizontal_literature/ext04_wu2025.py` | `3bfd09e76f84f9dda08818752557146ce317c25e9994f8869638193532e7d56b` |
| `$W/src/legsa_gins/paper_rebuild/horizontal_literature/ext05_pavlasek.py` | `89d5496ac2da1dd7d1fd0d194d47f7f49499ed8984915a31156ae53f669fbab5` |
| `$W/src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h5.py` | `3b9e57d5470cf33360564b0736a81a31ee67c1274c9a87b7e335921f58a399c2` |
| `$W/src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/CMakeLists.txt` | `77812d0814872bac0913c50c5eb97dbf88a91ba6de4d498a273540869d382ed4` |
| `$W/src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/include/hartley_inekf/backend.hpp` | `271a579c716a9c398e16152db923d1730298063a582bf9e048415af49f5bb94a` |
| `$W/src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/src/backend.cpp` | `a84f143d88af2cabbbf6536fb93b8de483946ed9e00a729eaeeab40665522bc3` |
| `$W/src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/tests/backend_tests.cpp` | `095ec41bfded392abdcac7e3f6d2313955668260196d9b74e6e7b632d3b22895` |
| `$W/src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/tests/h5_backend_tests.cpp` | `ea9950b52c77a3cc9e7d55ad00494e6c37d1368e3dec6a67d940ccd77af7f68c` |
| `$W/src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/tools/official_regression.cpp` | `3e5e079c21d9b1b9ce3a4f78c13d24fc5121be48220b192e849ef57125476ba7` |
| `$W/src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/tools/run_h5.cpp` | `60a00cfe42f950d248c8fa7d06a9a49bd7fd36f22c28ab999422e5cdc472fc28` |
| `$W/src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/tools/validate_backend.cpp` | `dd55dda1dd456dde7fc690084b6b796819c135626052e998acd0a17955892480` |

`$EXTERNAL/GINav` 整棵树：406 个文件（含 26 个 `.git` 内文件；只做清单比对，不在该树内运行任何 git 命令），逐文件值见副本 JSON；该子表的规范 JSON SHA-256 为 `975bc4882a5dc75a14055d4b9a13ef34304d80247948e58407ce3bae824f13bc`。

## 10. 序列适配、起点约定与输入钉

序列适配层（`horizontal_literature/sequence_override.py` 与 `hext/hx02_sequence.py`）把 phase1r/phase2/phase3/phase4 原写死的 1509 对、评估窗、base_time、原始流与星历路径改为从序列规格读取；无规格时各 runner 保持原 BY2 行为（相关既有测试 351 项通过，见第 14 节）。精确配对（容差 0）只用原始 GNSS：

| 序列 | 起点 | 整文件配对 | 选取 | 窗内（分母） | 选取首/末 [s] |
|---|---|---|---|---|---|
| BY2 | FILE_START | 1509 | 1509 | 1370 | 55.998 / 357.598 |
| BY2H | CONTRACT_START | 1483 | 1423 | 1350 | 413.198 / 697.598 |
| BY2O | FILE_START | 2231 | 2231 | 1885 | 3143.398 / 3589.398 |

CONTRACT_START（BY2H，起点 413 s）的逐方法实施：

- EXT01_EXT04：keep exact pairs whose receiver-1 RAWX time minus base_time >= 413.0 s (1423 of 1483 pairs)
- RTKLIB：rnx2rtkp -ts at the first selected exact pair, 2026/03/06 08:07:11.198 GPST (RTKLIB start tolerance would otherwise admit the 412.998 s epoch)
- EXT01_IN_RUN_RTKLIB_DIAGNOSTIC：same -ts as RTKLIB, so its rows cover exactly the selected pairs
- GINAV：start_time = max(RINEX/IMU overlap start, ceil GPST(base_time + 413 s)) = 2026/03/06 08:07:11
- HARTLEY：cache holds Go2 records at or after base_time + 413 s; contact hysteresis restarts at the first kept record

EXT01 在其原生运行中带一个 RTKLIB GPS L1 诊断（非 EXT01 输出、非解算输入），其行数须与选取配对逐行匹配；CONTRACT_START 时该诊断与 RTKLIB 方法用同一个 `-ts`，FILE_START 与原 BY2 行为不变。

Go2 完整记录前缀（前缀止于最后一个 `---` 行；原始文件不改动）：

| 序列 | 原始文件 | 完整记录 | 前缀字节 | 前缀 SHA-256 |
|---|---|---|---|---|
| BY2 | by2.txt | 63277 | 92351234 | `03cd96cd65d7f5af30f6a0c78d37f07ae4d32c65e78531807db7192454dff097` |
| BY2H | by3.txt | 63221 | 92274111 | `05923ca83845d205bad24d2794543ea3552987737d8df0e260fc72a746b015f5` |
| BY2O | by1.txt | 95859 | 140872746 | `e27b94c42fc2392019929d8789b54dd64599259fda30c50cec36154bd36fe020` |

Hartley 输入缓存（`01_INPUT_PINS/HARTLEY/<SEQ>/H5_INPUT_CACHE.bin`；接触力阈值与 FK std 沿用 BY2 实例化值，不重标）：

| 序列 | 记录数 | 首/末记录 [s] | dt 中位 / 最大 [s] | dt > 0.1 s 个数 | 缓存 SHA-256 |
|---|---|---|---|---|---|
| BY2 | 63277 | 44.887 / 350.085 | 0.004012 / 0.091676 | 0 | `c169e26d66f35fe200bb17a695353cd2d751482df1cd97996a7a8afff8662065` |
| BY2H | 60541 | 413.037 / 692.911 | 0.004006 / 0.175715 | 1 | `732d45c70815ba65c7832ecbfb41edf5c571fd4e80fb13df497a99fe9863436e` |
| BY2O | 95859 | 3101.557 / 3572.835 | 0.004016 / 0.345999 | 6 | `8786456127571475e88a89a47ab30f118b09a789e521690b82170985e4aaec35` |

BY2 缓存与 CLEAN4 主分支缓存 `c169e26d…` 逐字节相同。BY2H 的 4.7 s IMU 缺口：完整 Go2 记录中缺口位于 407.017–411.757 s（4.740 s），随后 411.757–412.479 s（0.722 s）与 412.479–413.037 s（0.558 s）两个缺口，全部在 413 s 合约起点之前；CONTRACT_START 缓存从 413.037 s 的记录开始，因此该缺口不进入 Hartley 输入。hartley_h5_runner 现有行为：无最大 dt 规则，缺口按一次零阶保持传播处理；首 5 s 须满足静止初始化门（陀螺模长中位 < 0.05 rad/s、|加计模长中位 − 9.81| < 0.5 m/s²），否则运行器非 0 退出（记 ABNORMAL_EXIT，附 stderr）。该缺口对本任务运行的影响在结果中报告。另：`run_h5.cpp:517` 在 NATIVE_SUMMARY.json 中把 data_mode 写死为 real_by2_raw（方法本体，不改）；各运行的 COMMAND.json/DONE.json 溯源块记录序列自身的 data_mode（real_by2_raw / real_by2h_raw / real_by2o_raw）。

GINav 输入（GNSS1 RAWX/SFRBX → 重建 UBX → convbin RINEX 3.04 + 广播星历，argv `-r ubx -v 3.04 -f 5 -od -os -oi -ot -ol`；单常数 RAWX/NAV-PVT 时间归一；Go2 body IMU FLU→RFU format-2 增量，dt > 0.1 s 丢弃）与三份派生配置：

| 序列 | RINEX/IMU 重叠（GPST） | 配置 SHA-256 |
|---|---|---|
| BY2 | 2026-03-06 08:01:14 – 2026-03-06 08:06:08 | `55211d04462d5933aa7367ac21978240c1cf9f72ef9283eceac85c47aade1c30` |
| BY2H | 2026-03-06 08:07:00 – 2026-03-06 08:11:50 | `c9f1b27e1b39c7112cb8c4cfc5ab5599bf2365ae13194d90f308cd646353ceaa` |
| BY2O | 2026-03-06 07:52:42 – 2026-03-06 07:59:50 | `e892247def5c6ad51fac192649c876fba54b2b3f30acfd1de96e6518320ae4fe` |

BY2 配置相对 BY2 派生配置（688ea8ac）的差异：

```diff
--- BY2_GINAV_SPP_LC.ini (688ea8ac)
+++ BY2_GINAV_SPP_LC.ini
@@ -15,7 +15,7 @@
 #
 #
 #************************************************************************************************************************************************************
-data_dir      =      <CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/11_LC02_GINAV2021_OFFICIAL_REPRODUCTION/runtime/r4b/s                               % data directory,the directory should includes all required data files
+data_dir      =      <CLEAN_ROOT>/stages/CLEAN9_EXTERNAL_COMPARISON/HX02_FIVE_CATEGORY/01_INPUT_PINS/GINAV/BY2                               % data directory,the directory should includes all required data files
 site_name     =      by2_gnss1                                                  % rover name,the name of rover observation file should include the site_name for automatic identification
 
 
```

BY2H 配置相对 BY2 派生配置（688ea8ac）的差异：

```diff
--- BY2_GINAV_SPP_LC.ini (688ea8ac)
+++ BY2H_GINAV_SPP_LC.ini
@@ -15,13 +15,13 @@
 #
 #
 #************************************************************************************************************************************************************
-data_dir      =      <CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/11_LC02_GINAV2021_OFFICIAL_REPRODUCTION/runtime/r4b/s                               % data directory,the directory should includes all required data files
+data_dir      =      <CLEAN_ROOT>/stages/CLEAN9_EXTERNAL_COMPARISON/HX02_FIVE_CATEGORY/01_INPUT_PINS/GINAV/BY2H                               % data directory,the directory should includes all required data files
 site_name     =      by2_gnss1                                                  % rover name,the name of rover observation file should include the site_name for automatic identification
 
 
 # GNSS opstions**********************************************************************************************************************************************
-start_time    =      1  2026/03/06 08:01:14    % start time(0:from obs  1:from opt)
-end_time      =      1  2026/03/06 08:06:08    % end time  (0:from obs  1:from opt)
+start_time    =      1  2026/03/06 08:07:11    % start time(0:from obs  1:from opt)
+end_time      =      1  2026/03/06 08:11:50    % end time  (0:from obs  1:from opt)
 t_interval    =      1                         % time interval(0:from obs non-zero:specified interval)
 
 gnss_mode     =      1                      % positioning mode(1:SPP 2:PPD(post-processing differenced) 3:PPK(post-processing kinematic) 4:PPS(post-processing static) 5:PPP_KINE 6:PPP_STATIC)
```

BY2O 配置相对 BY2 派生配置（688ea8ac）的差异：

```diff
--- BY2_GINAV_SPP_LC.ini (688ea8ac)
+++ BY2O_GINAV_SPP_LC.ini
@@ -15,13 +15,13 @@
 #
 #
 #************************************************************************************************************************************************************
-data_dir      =      <CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/11_LC02_GINAV2021_OFFICIAL_REPRODUCTION/runtime/r4b/s                               % data directory,the directory should includes all required data files
+data_dir      =      <CLEAN_ROOT>/stages/CLEAN9_EXTERNAL_COMPARISON/HX02_FIVE_CATEGORY/01_INPUT_PINS/GINAV/BY2O                               % data directory,the directory should includes all required data files
 site_name     =      by2_gnss1                                                  % rover name,the name of rover observation file should include the site_name for automatic identification
 
 
 # GNSS opstions**********************************************************************************************************************************************
-start_time    =      1  2026/03/06 08:01:14    % start time(0:from obs  1:from opt)
-end_time      =      1  2026/03/06 08:06:08    % end time  (0:from obs  1:from opt)
+start_time    =      1  2026/03/06 07:52:42    % start time(0:from obs  1:from opt)
+end_time      =      1  2026/03/06 07:59:50    % end time  (0:from obs  1:from opt)
 t_interval    =      1                         % time interval(0:from obs non-zero:specified interval)
 
 gnss_mode     =      1                      % positioning mode(1:SPP 2:PPD(post-processing differenced) 3:PPK(post-processing kinematic) 4:PPS(post-processing static) 5:PPP_KINE 6:PPP_STATIC)
```

RTKLIB 动基线：配置 `RTKLIB_UNMODIFIED_MOVING_BASE.conf`（97f0fe41…，钉在 `01_INPUT_PINS`），rnx2rtkp 3a0ad1c5…；两台接收机 RINEX 按 EXT03 源后端方式重建（convbin 同 phase2 argv）。

## 11. 约定诊断（只读）

对每个 heading_only 方法、每条序列（EXT04 两策略各一），在方法有效且两台接收机 NAV-PVT carrSoln = 2（均 fixed）的配对历元上，计算方法 body yaw 与接收机自身 NAV-HPPOSECEF 基线 body yaw（GNSS2 − GNSS1 向量航向 + 90°；HPPOSECEF iTOW = RAWX + 2 ms，三序列同一登记关系）的 wrap-safe 角差：中位数与落在 0°、±90°、±180° 各 ±20° 内的比例。只用接收机输出，不开参考。中位数落在 ±90° 或 ±180° 的 ±20° 内 = 硬停并报告，任务内不修改任何约定；无可比历元记 UNAVAILABLE（不停）。诊断在该运行的航向评估之前完成。

## 12. 执行、存储与目录

`$HX02`：`00_CONTRACT`（合约副本与哈希）、`00_CONTROL`（身份门、方法本体钉、冻结前冒烟摘要、删除清单、PROGRESS/STATE/LEDGER）、`01_INPUT_PINS`、`RUNS/<run_id>/`（COMMAND.json、SEQUENCE_SPEC/参数、PARAMS_ECHO.json、INPUT_HASHES.json、`native/`、OUTPUT_HASHES.json、`eval/`、FAILURE.json 或 DONE.json、ARCHIVE_MANIFEST.json）、`90_AGGREGATE`、`99_HARD_STOP`。COMMAND.json 与 DONE.json 的溯源块记录 data_mode、合成与半合成数据标志（均 false）、trace_used_online、receiver_imu_as_body_imu、final_v23_output_solver_input、LegSA_output_solver_input、per_case_tuning、output_only_correction、epoch_deleted_for_metric（均 false）、old_runtime_input_count（由原生 openat 审计计数，`<CLEAN_ROOT>` 下 `01_RAW_HASH_LOCK/` 与 `$HX02` 之外的文件打开即计入，非 0 硬停）、code_commit 与 config_hash（合约 SHA-256）。每次原生启动前等待机器空闲（load1 ≤ 8 且 load5 ≤ 10，最多 7200 s，等待时间入账）。

产出：`$HX02/90_AGGREGATE/EXTERNAL_FIVE_CATEGORY_TABLE.csv`（长表，列 category, method_id, config, sequence, start_mode, output_type, metric, value, denominator_or_valid_epochs, failure_flag, source, notes；五类全部有行，无实现的 EXT05B、LC01-M、LC01-S-M、LC01-2D、Yin、Chang、Jiang、Taghizadeh、HAO2018、EXT06 各一行、状态写“无实现”及盘点原因；other 类一行；D01/D02 不进表）与 `HX02_RESULTS.md`（五类宽表、每类一句结论、复现检查、约定诊断、失败清单、Outcome），复制到 `$W/docs/paper_rebuild/hext/HX02/`。汇总代码 `hext/hx02_aggregate.py`。

## 13. 冻结前技术冒烟（截断输入，未评估，输出已删）

为避免适配层缺陷首次出现在登记运行中，冻结前用 `scripts/paper_rebuild/hx02_prefreeze_smoke.py` 在截断输入上跑通每条原生路径：EXT01–EXT04 用 BY2H CONTRACT_START 选取后的前 20 对（第 1 轮 4 对）；RTKLIB 用 BY2H 登记 `-ts` 加 10 s 的 `-te`；Hartley-S/LIT 用 BY2 缓存的前 3000 条记录；GINav 用 BY2 钉住的输入、end_time = start_time + 120 s。仅冒烟时：EXT01 的已提交源码检查被旁路、其固定的 worker 确定性子集（0,1,2,100,431,432,994,末）裁到截断输入、其诊断加 `-te`；登记运行在冻结提交之后执行，这三处均按原样。冒烟不做任何评估、不开参考，输出按精确清单删除（`00_CONTROL/PREFREEZE_SMOKE_DELETION_MANIFEST.json`），摘要保留在 `00_CONTROL/PREFREEZE_SMOKE_SUMMARY*.json`。发现并在冻结前修正的缺陷：

1. EXT04：HX-02 预检只建了原生根的上级目录，指纹尝试目录无法创建（已改为预检直接建原生根）。
2. EXT01：BY2H 的 RTKLIB 诊断处理整份 RINEX，413 s 前的行无法与选取配对连接，runner 会判 BLOCKED（已加与 RTKLIB 方法相同的 `-ts`）。
3. RTKLIB 起点：`-ts 08:07:11` 会因 RTKLIB 起点容差收入 412.998 s 的历元（早于合约起点 2 ms）；已改为首个选取配对 08:07:11.198。
4. GINav 适配器：官方解无数据行时抛异常；已改为记 NO_OUTPUT（并加单元测试）。

| 方法 | 最终冒烟记录 | 退出码 | 输出 | 参数回显一致 | 参考打开 | 旧运行材料打开 |
|---|---|---|---|---|---|---|
| EXT01 | PREFREEZE_SMOKE_SUMMARY_R5.json | 0 | `{"EXT01": {"rows": 20, "valid": 20}}` | 9/9 | 0 | 0 |
| EXT02 | PREFREEZE_SMOKE_SUMMARY_R2.json | 0 | `{"EXT02": {"rows": 20, "valid": 19}}` | 8/8 | 0 | 0 |
| EXT03 | PREFREEZE_SMOKE_SUMMARY_R2.json | 0 | `{"EXT03": {"rows": 20, "valid": 20}}` | 4/4 | 0 | 0 |
| EXT04 | PREFREEZE_SMOKE_SUMMARY_R2.json | 0 | `{"EXT04_FAR": {"rows": 20, "valid": 0}, "EXT04_PAR": {"rows": 20, "valid": 0}}` | 5/5 | 0 | 0 |
| RTKLIB | PREFREEZE_SMOKE_SUMMARY_R5.json | 0 | `{"q_counts": {"1": 3, "2": 45}}` | 1/1 | 0 | 0 |
| HARTLEY_S | PREFREEZE_SMOKE_SUMMARY.json | 0 | `{"nav_rows": 3000}` | 9/9 | 0 | 0 |
| HARTLEY_LIT | PREFREEZE_SMOKE_SUMMARY.json | 0 | `{"nav_rows": 3000}` | 9/9 | 0 | 0 |
| GINAV | PREFREEZE_SMOKE_SUMMARY.json | 0 | `{"pos_files": 1, "fopen_lines": 9}` | - | 0 | 0 |

冒烟原生调用共 16 次（5 轮合计，含失败轮次），评估调用 0、参考打开 0；这些调用不计入 24 次登记原生运行，在结果中单独报告。

## 14. 单元检查（随本提交）

`tests/paper_rebuild/test_hx02_heading_evaluation.py`（合成序列：已知误差与已知缺口下的可用率、有效 RMSE、保持 RMSE 与无航向历元、最大绝对误差、段数与缺口、圆均值偏差、Q/ratio 分列、参考只开一次与哈希核对）；`test_hx02_relative_pose_evaluation.py`（合成轨迹：规范偏移精确恢复、3.0°/min 航向漂移恢复、位置漂移按登记 OLS 定义、主分支对齐原样用于另一分支、不外推）；`test_hx02_adapters.py`（序列规格与 CONTRACT_START 选取、航向表适配、约定诊断各带、覆盖统计、RTKLIB 起点、BY2 现存 .pos 转换与 v3 尝试 NAV 逐字节一致 f0fa3e71 且覆盖 77/275、GINav 配置只改三行、MATLAB 只从本地键解析、无数据行 .pos）；`test_hx02_execution.py`（运行命名、溯源标志、原生 openat 审计、失败分类、账本续作、归档复核与中断续档、评估中断处理、输入钉哈希、参数回显比较、登记子进程在真实 strace 下的审计）；`test_hx02_aggregate.py`（模拟阶段的全量汇总：五类、封存行值、无实现行、失败行、文档词语检查）。HX-02 测试 41 项通过；与改动 runner 相关的既有测试 351 项通过、16 项因环境跳过、1 项为任务前已存在的失败（`test_horizontal_phase4_c00.py::test_preflight_hash_only_collision_and_paper_closure_when_available`，需要执行锁）。

## 15. 硬停清单

- identity gate failure (sealed values or 65 sealed-file SHA-256) at start or before the results commit
- any solver or evaluator call on a LegSA configuration
- a non-evaluator process opening a reference trajectory (trace/bag/fpl)
- a method-body file SHA-256 change
- a parameter echo differing from the registered CLEAN4 BY2 echo (or unreadable)
- convention diagnostic median within 20 deg of +/-90 or 180 deg
- disk below a guard line
- a native process opening old runtime material under <CLEAN_ROOT> (AGENTS.md old_runtime_input_count must be 0)
- evaluator child technical or access-audit failure
- 代码冻结核对失败：合约 `code_sha256` 任一文件不符、跟踪文件有改动、`INPUT_PINS.json` 或参数回显参照哈希不符。
- 控制器自身 openat 日志缺失，或控制器进程打开参考轨迹。
- 控制器技术故障（未预期异常）同样写 `99_HARD_STOP` 报告并停止，等待处理。

硬停后：写报告、提交、等待，不自行续作。

