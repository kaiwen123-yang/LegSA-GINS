# HX-03 执行登记：LC01 与 EXT05C 的 A2 和 Classic-18

本任务仅新增外部方法退化实验。代码登记提交并 push、本文全文回报后，才启动身份门与矩阵；当前真实原生/评估为 0/0。起点为 stage/clean3-math-repair 的 3c36d776b5c6826d156414a34edc564b341d17ae；git pull --rebase 已同步，含 ac2d9e4e7b2f69cc8c27a930d32b5854d3fe5317。

路径：$W=/home/kaiwen/research/LegSA-GINS-WORKTREES/clean3-math-repair；$STAGES=/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages；$V3=$STAGES/CLEAN8_PROTOCOL_V3；$HX02=$STAGES/CLEAN9_EXTERNAL_COMPARISON/HX02_FIVE_CATEGORY；$HX03=$STAGES/CLEAN9_EXTERNAL_COMPARISON/HX03_DEGRADATION；$SCRATCH=/home/kaiwen/research/LegSA-GINS-SCRATCH/CLEAN9_EXTERNAL_COMPARISON。

## 硬规则

1. v3 是论文唯一实验链，7d43b9a / fb39cb8 / 4d932c9 已封存。LegSA 的 F01/F02/F03/A04/F04 结果只读 $V3/07_AGGREGATE/CORE_541_DISTRIBUTION_V3.csv 与 ADDENDUM_TABLE_V3.csv；F04 C00 仅按任务要求从 MAIN_TABLE_V3.csv 做身份读出。任何 LegSA 解算或评估调用立即硬停。
2. HX-02 登记的 423 项方法本体逐文件 SHA256 保持不变，清单见 HX03/METHOD_BODY_PINS.json。LC01 主行、EXT05C 所有传播与原生更新均调用未改动的 ext05_pavlasek.py；LC01-BR 的相对更新在新文件 hx03_relative_update.py，所有表明确标为“改动过的 LC01”，仅用于 A2 补充。注入仅在 provider/cache 建成后修改 p1/p2/valid/time；本清单不改 pAcc。缓存以注入规格和输出数组哈希重新绑定。原始输入层、$HX02、v3 封存目录不改。
3. 参考轨迹仅在登记评估器子进程打开。复用未修改的 hext/hx02_evaluation_process.py，登记 HX03_FROZEN 子进程 hx03_evaluation.py；该进程运行未修改的 aa049248 冻结评估器和既有捕获观察器。每次 strace openat 恰好成功 O_RDONLY 打开 trace 一次，并由同一读取句柄核 SHA256；控制器、原生进程、单元检查不开 trace/bag/fpl。
4. E: 不写。运行输出只在 $SCRATCH/HX03，按族组织原生批，确认结果先归档再处理依赖它的等价行；每批前 E: 可用至少 40 GB、G: 至少 30 GB，scratch 至多 20 GB。原生并发至多 22，控制器每 15 s 更新状态，不作超过 600 s 的空闲等待；单个原生或评估子进程等待上限 600 s，超时按环境失败保留，不重试。tmux 控制器将 PROGRESS.txt、STATE.json、LEDGER.jsonl 写到 $HX03/00_CONTROL。每个 RUNS/<SEQ>__<METHOD>__<CONFIG>__<CASE>__<SEED> 归档逐文件核 SHA256 后删对应 scratch。中断后复用已封账项；已预留但未形成终态的调用硬停待审计，不自动重跑。不做交接包。
5. 身份门任一不过硬停：LC01 BY2 C00 空操作 NAV 必须等于 MAIN_TABLE_V3.csv 第 17 行 source_nav 完整哈希，v3 yaw 舍入为 2.994827460；EXT05C 第 18 行 NAV 哈希及 yaw 12.048642 同理；F04 C00 yaw 读出 1.886272；LC01-BR 无故障 C00 NAV 必须逐字节等于 LC01。开始与结果提交前核全部 65 pin，登记提交前也复核。开始检查 65/65（59 CSV），方法本体 423/423，既有 29 个未跟踪文件保留。
6. 失败也是结果：D8 按相对初始化位置的三维位移 >10 km、速度模 >50 m/s、高度变化 >1 km 或非有限，记 ALGORITHM_FAILURE_DIVERGED；其余按 NO_OUTPUT、ABNORMAL_EXIT、RUN_FAILED_ENVIRONMENT 保留完整 stderr。首个越界事件之前的 NAV 截断段仍按相同窗及评估点给 PRE_FAILURE 指标，不并入有限样本分布；不足两行窗内 NAV 则该项为空。D12 对有界 NAV 的一致性失败记 UNAVAILABLE_EVALUATION_FAILED，不改阈值、不重试；参考访问/哈希身份等技术失败硬停。所有失败保留行，不删行、不换参数。
7. 无性能数值门槛，全部结果如实报告。配对只取双方有限样本，同时列配对数、失败数、登记分母。A1 等价报告和 C00 等价种子明确为复用，不算新的独立运行。
8. 新写报告沿用本任务要求的术语限制；不改封存科学内容。身份门失败、65 pin 不一致、任何 LegSA 调用、非子进程开参考、方法本体改变、参数或映射偏离本登记、C00 等价型哈希不一致、df 低于守卫线均硬停，写报告、提交并等待。

## 输入、方法与映射

复用已建成的 $STAGES/CLEAN7_HEXT_EXTERNAL_SEQUENCES/02_BY2_IDENTITY/PROVIDER_CACHE，逐个验证 CACHE_MANIFEST.json 和 11 个 npy；固定原点、静止校准、历元索引与原始序列化规则保持不变。主输入是两接收机 HPPOSECEF 位置和 pAcc、Go2 IMU；不读取速度、多普勒、标量 yaw/std 或 Go2 RP/HV 作为更新。

文献参数取 $W/configs/paper_rebuild/horizontal_literature/PHASE5_EXT05_PAVLASEK_CONTRACT_V1.yaml 的 process_noise_psd_paper_experiment：gyro PSD=[0.0004,0.0004,0.000324] rad²/s，accel PSD=[0.0289,0.0225,0.0576] m²/s³。初始姿态标准差 60°，速度/位置标准差均 0.1（m/s、m）；速度零，姿态取冻结重力均值和首次有效基线，位置为 p1−C·lever，陀螺扣冻结静态偏置；加速度比例 1。R1/R2 分别为 pAcc1²·I / pAcc2²·I。原生上一 IMU 样本保持、事件顺序及 NAV 写出格式继承 H-EXT-01；不替换成其他 IMU 间隔策略。

工况身份取 CANONICAL541_CASE_MANIFEST.csv（ac58b992a56f3ab05c585973fa6ceef1493d0d5cd6a9f0a9e18dae8edd998cb2）；实现值由 V3_PROVIDER_SOURCE_INDEX.json（130f93315d504bd7daddefc7eeabdbbeb10b763011531ade2766a0448a689a0e）指向的逐例 PROVIDER_BUNDLE.json 与 GNSS18.gnss 给出。基准 GNSS18 的完整哈希为 b98b48979d509bce1429b360c6e0d675c028ff42e3158d4c97dd63df61d62663。A2 清单/窗口/种子同时核对附加族 YAML case_rows 与 CASE_REGISTRY.csv。

来源澄清：$V3/07E_UNIFIED_FAILURE/DUAL_YAW_INJECTION_MAPPING.csv 是算子映射表，没有逐秒数值列。与 v3 providers.py:frozen_cells 一致，实际 1 s 增量从基准 GNSS18 的有效 1 Hz yaw 行与 bundle 钉住的 dual_yaw_AUDIT.csv 逐行 wrap 差恢复，覆盖 [t_i,t_i+1)；不重新随机。所有源文件的逐项哈希登记在 configs/paper_rebuild/hext/HX03/INPUT_PINS.json（397 项）。

下表的 B/C/A 分别为该例 bundle、case GNSS18、dual_yaw_AUDIT；G 为基准 GNSS18，M 为上述航向映射表。每例完整路径、SHA256 与角色在 CASES.json:sources。

| 型 | 源文件与字段 | 操作与作用对象 | 不使用的通道 |
|---|---|---|---|
| D14 | C−G 的 time/lat/lon/height | iTOW 对齐后，WGS84 ECEF 差投到缓存固定 NED；同一位移加 p1、p2 | GNSS18 std、速度、多普勒 |
| D21 | C−G 的 time/lat/lon/height | 同上，复用已实现尖峰位置与方向 | 同上 |
| D16 | C−G 的 time/lat/lon/height | 同上，复用已实现静偏 | 同上 |
| D18 | C−G 的 time/lat/lon/height | 同上，复用已实现漂移 | 同上 |
| D03 | B:components[gnss_position].details.interval | 半开窗；LC01 两台 valid=False，EXT05C valid1=False | 速度、多普勒 |
| D04 | B 同上 | 同上，20 s 窗 | 同上 |
| D43 | B/C 的 receiver_velocity | 不修改有效输入；只跑 seed_00 确认，9 行填封存 C00 指标 | 接收机速度 |
| D42 | B:receiver_velocity interval | 同上 | 接收机速度 |
| D05 | B:gnss_position interval | 与同种子 D03 同锚点生成；seed_00 原生 NAV 核相等后复用其余 8 个同种子 D03，否则独立跑剩余 8 个 | 接收机速度 |
| D33 | M；G yaw；A time/yaw_deg | wrap 增量按原 1 s 单元提升；p2 绕 p1 在 NED 水平面正 yaw 方向旋转，z 不变、基线长度不变 | 标量 yaw/std 更新；EXT05C 的 p2 仅参与初始化 |
| D35 | 同上 | 同上，使用已实现尖峰单元 | 同上 |
| D32 | 同上 | 同上，使用已实现 1° 噪声单元 | 同上 |
| D31 | B:dual_yaw interval | valid2=False；LC01 原生跳过整次更新，EXT05C 不受更新影响且每次 NAV 核 C00 | EXT05C 的 p2 更新 |
| D06 | B:gnss_position interval | 两台 valid=False | 速度、标量航向 |
| D46 | B:raw_doppler interval | 不修改有效输入；seed_00 确认后 9 行填封存 C00 指标 | 原始多普勒 |
| D47 | B/C 的 raw_doppler 实现值 | 同上 | 原始多普勒 |
| D50 | B/C 的 raw_doppler 偏置 | 同上 | 原始多普勒 |
| D57 | B:gnss_position latency_s/jitter_max_s；C 的 position_valid 行 time | 从 C 已实现位置行与 G 按顺序/原位置及精度字段一一核对，恢复逐行偏移；加到两台历元后稳定排序，IMU 不移 | 其他源的延迟/抖动 |
| D62/A2 | B:gnss_position interval；附加合约/登记表 | LC01 两台 valid=False，EXT05C valid1=False；BR 窗内仅相对更新、窗外原生更新 | 接收机速度、原始多普勒 |

GNSS18 的相对 UTC 毫秒键通过缓存的固定 iTOW−UTC 偏移转成 iTOW 键，逐项检查不重复且偏移恒定。D57 不重新生成 jitter：seed_00 延迟 0.10401432335291612 s、jitter 上限 0.025616545567535644 s；各自种子取对应 bundle 和已实现表行。v3 LegSA 在 D57 的有效航向为 0；本实验只移动位置输入，暴露不同，不能将配对差解释为同等全部输入暴露下的单一算法效应。

## LC01-BR（改动过的 LC01，仅 A2）

新文件 src/legsa_gins/paper_rebuild/hext/hx03_relative_update.py：z_rel=Cᵀ((p2−p1)−Cb)，H_rel=[skew(b),0,0]，R_rel=Cᵀ(R1+R2)C；S=H_rel P H_relᵀ+R_rel，K=solve(S,H_rel P)ᵀ；Joseph 更新后调用原生 pose.right_correct(K z_rel)，同原生 X←X Exp(−(Kz)^) 及协方差对称化。相对量测没有直接位置/速度观测块；已有状态交叉协方差仍可能产生间接修正。窗外直接调用 filter.update，不复制传播数学。三维基线包含垂向分量，保持与原生相对块一致，不改成标量 yaw 更新。

LC01 A2 主行按同种子同时长另列 D61/A1 等价报告，共 18 行，复用同一运行，不新增原生或评估。它在窗内同时失去绝对与基线信息，这一架构行为在报告中注明。

## 精确运行与调用预算

方法 LC01、EXT05C 各覆盖 Classic-18 的 162 逻辑工况和 A2 的 18 工况；BR 仅 A2 的 18 工况。矩阵共 378 逻辑运行；另列 A1 等价报告 18 行，逐例表共 396 行（每评估点）。C00 身份门 3 次原生，其中 BR 仅检查无故障等价；LC01/EXT05C 各 v3/v2 评估，合计 4 次身份评估，BR C00 不另评估。

按未合并 D05 的上界：LC01=13×9+5×1+18=140，EXT05C=140，BR=18，矩阵原生最多 298；加身份门最多 301。若 D05 两方法均哈希相等，矩阵原生 282，加身份门 285。5 个不使用通道型的 10 次确认仅核 NAV，不再开参考，全部 9 种子使用封存 C00 v3 指标（第 17/18 行）；并行 v2 指标复用本次身份门。

因此有完整输出时参考评估预计 548 次，上界 580 次；失败/无输出可减少次数，不能补跑凑数。运行清单 RUN_MANIFEST.csv 共 381 行（含 3 身份门），逐项登记 NATIVE、IDENTITY_NATIVE、REUSE_C00_AFTER_TYPE_HASH_GATE 或 D05 条件路径。原生统一 --trace-mode disabled。

Classic-18 精确 case_id（每行同时适用于 LC01、EXT05C；五个确认型仅 seed_00 原生，其余按上条复用）：

| 型 | 精确 case_id |
|---|---|
| D14 | D14_seed_00, D14_seed_01, D14_seed_02, D14_seed_03, D14_seed_04, D14_seed_05, D14_seed_06, D14_seed_07, D14_seed_08 |
| D21 | D21_seed_00, D21_seed_01, D21_seed_02, D21_seed_03, D21_seed_04, D21_seed_05, D21_seed_06, D21_seed_07, D21_seed_08 |
| D16 | D16_seed_00, D16_seed_01, D16_seed_02, D16_seed_03, D16_seed_04, D16_seed_05, D16_seed_06, D16_seed_07, D16_seed_08 |
| D18 | D18_seed_00, D18_seed_01, D18_seed_02, D18_seed_03, D18_seed_04, D18_seed_05, D18_seed_06, D18_seed_07, D18_seed_08 |
| D03 | D03_seed_00, D03_seed_01, D03_seed_02, D03_seed_03, D03_seed_04, D03_seed_05, D03_seed_06, D03_seed_07, D03_seed_08 |
| D04 | D04_seed_00, D04_seed_01, D04_seed_02, D04_seed_03, D04_seed_04, D04_seed_05, D04_seed_06, D04_seed_07, D04_seed_08 |
| D43 | D43_seed_00, D43_seed_01, D43_seed_02, D43_seed_03, D43_seed_04, D43_seed_05, D43_seed_06, D43_seed_07, D43_seed_08 |
| D42 | D42_seed_00, D42_seed_01, D42_seed_02, D42_seed_03, D42_seed_04, D42_seed_05, D42_seed_06, D42_seed_07, D42_seed_08 |
| D05 | D05_seed_00, D05_seed_01, D05_seed_02, D05_seed_03, D05_seed_04, D05_seed_05, D05_seed_06, D05_seed_07, D05_seed_08 |
| D33 | D33_seed_00, D33_seed_01, D33_seed_02, D33_seed_03, D33_seed_04, D33_seed_05, D33_seed_06, D33_seed_07, D33_seed_08 |
| D35 | D35_seed_00, D35_seed_01, D35_seed_02, D35_seed_03, D35_seed_04, D35_seed_05, D35_seed_06, D35_seed_07, D35_seed_08 |
| D32 | D32_seed_00, D32_seed_01, D32_seed_02, D32_seed_03, D32_seed_04, D32_seed_05, D32_seed_06, D32_seed_07, D32_seed_08 |
| D31 | D31_seed_00, D31_seed_01, D31_seed_02, D31_seed_03, D31_seed_04, D31_seed_05, D31_seed_06, D31_seed_07, D31_seed_08 |
| D06 | D06_seed_00, D06_seed_01, D06_seed_02, D06_seed_03, D06_seed_04, D06_seed_05, D06_seed_06, D06_seed_07, D06_seed_08 |
| D46 | D46_seed_00, D46_seed_01, D46_seed_02, D46_seed_03, D46_seed_04, D46_seed_05, D46_seed_06, D46_seed_07, D46_seed_08 |
| D47 | D47_seed_00, D47_seed_01, D47_seed_02, D47_seed_03, D47_seed_04, D47_seed_05, D47_seed_06, D47_seed_07, D47_seed_08 |
| D50 | D50_seed_00, D50_seed_01, D50_seed_02, D50_seed_03, D50_seed_04, D50_seed_05, D50_seed_06, D50_seed_07, D50_seed_08 |
| D57 | D57_seed_00, D57_seed_01, D57_seed_02, D57_seed_03, D57_seed_04, D57_seed_05, D57_seed_06, D57_seed_07, D57_seed_08 |

A2 精确清单（每行适用于 LC01、LC01-BR、EXT05C；窗口均半开）：

| case_id | 种子值 | 中断窗 s |
|---|---:|---|
| D62_10s_seed_00 | 260306001 | [201.2, 211.2) |
| D62_10s_seed_01 | 260306002 | [102.20639, 112.20639) |
| D62_10s_seed_02 | 260306003 | [184.207044, 194.207044) |
| D62_10s_seed_03 | 260306004 | [222.201927, 232.201927) |
| D62_10s_seed_04 | 260306005 | [143.204964, 153.204964) |
| D62_10s_seed_05 | 260306006 | [221.215803, 231.215803) |
| D62_10s_seed_06 | 260306007 | [253.20826699999998, 263.208267) |
| D62_10s_seed_07 | 260306008 | [242.210403, 252.210403) |
| D62_10s_seed_08 | 260306009 | [294.203403, 304.203403) |
| D62_20s_seed_00 | 260306001 | [196.2, 216.2) |
| D62_20s_seed_01 | 260306002 | [97.20639, 117.20639) |
| D62_20s_seed_02 | 260306003 | [179.207044, 199.207044) |
| D62_20s_seed_03 | 260306004 | [217.201927, 237.201927) |
| D62_20s_seed_04 | 260306005 | [138.204964, 158.204964) |
| D62_20s_seed_05 | 260306006 | [216.215803, 236.215803) |
| D62_20s_seed_06 | 260306007 | [248.20826699999998, 268.208267) |
| D62_20s_seed_07 | 260306008 | [237.210403, 257.21040300000004) |
| D62_20s_seed_08 | 260306009 | [289.203403, 309.203403) |

## 评估、汇总与验证

冻结评估器 aa049248 的完整 SHA256 见 CONTRACT.json:evaluator_sha256；BY2 base_time=1772784000.0，闭区间 [66,340]。复用 hext/external_evaluation.py 的 NAV 点变换、指标与 D12 判别。v3 点为主，v2 点并行；保持源 NAV 裁窗前索引、固定表头/LF、.17g 写出与固定 NED 原点。每个评估点单独一个子进程、一个 trace 读取句柄；不用 STD，不补外推，不按误差删历元。

逐例表保留 yaw/水平/高程 RMSE、yaw P95、失败类别、PRE_FAILURE 三项、输入等价说明、运行目录和源 NAV 哈希。按型与族给三个 RMSE 的中位数、P95、最大、有限数、失败数、登记分母，使用 numpy 默认 linear 分位数。与 F04、F02、F03、A04 按 case_id/seed 配对，差=外部−LegSA，只在双方有限时统计中位数与 P95，给配对数；A1 等价行单列分母。

已完成无参考单元检查 74 项通过、18 项按 BR 范围跳过（UNIT_FINAL.xml）。包括每型 seed_00 的 p1/p2/valid/time 与规格逐项断言，IMU/pAcc 不变；位置共同平移、航向旋转角与长度、D57 逐行偏移；全部种子 D05/D03 映射相同；18 个 A2/A1 窗相同；BR 窗外单步状态/协方差字节等于原生，窗内共同平移不影响相对新息、Joseph 协方差有效。整条 C00 的 NAV 哈希及 yaw 身份门在本提交后执行，结果未预填。先前检查 47 通过、18 跳过，后增 27 个跨种子窗口检查；两份回执均保留，无真实原生或评估调用。

各运行保留 COMMAND.json、PARAMS_ECHO.json、INPUT_HASHES.json（含注入规格哈希）、native/、OUTPUT_HASHES.json、eval/、DONE.json 或 FAILURE.json；等价行明确记录调用为零及来源。源 NAV 与错误序列用于核验和后续不确定度分析。逐例表、汇总表、配对表与 HX03_RESULTS.md 同时保存在 $HX03/90_AGGREGATE 和 $W/docs/paper_rebuild/hext/HX03；不打包。

## 文件身份

以下清单均随本登记提交，逐项值作为合约的一部分；CODE_PINS.json 覆盖新代码、既有运行/评估依赖与合约/清单，执行前每批核对。397 个源 pin 的清单包含 case bundle、GNSS18、航向 audit、A1 对应 bundle、基准缓存及规格文件；423 项方法本体清单与 HX-02 逐项比较一致。

| 文件 | SHA256 |
|---|---|
| $W/configs/paper_rebuild/hext/HX03/CONTRACT.json | `dd3c0ea8788dfea735ffef5f11b3c3f7a9d0abac1e0d3125c4d064e967102cd8` |
| $W/configs/paper_rebuild/hext/HX03/CASES.json | `420610b4d2c770d8d506e9ae52443646aa9f08b28428170160fc593e4a1a09c9` |
| $W/configs/paper_rebuild/hext/HX03/INPUT_PINS.json | `afe13025b2dd866f3ce552bc5b22b2a2a6fc116bbabdb430048fe56895e4d3c1` |
| $W/configs/paper_rebuild/hext/HX03/RUN_MANIFEST.csv | `6ba7d4e933ffa4aa4f9cdf2d28898f20e6ae5b2cbc35e202fa4f57015a575b0d` |
| $W/configs/paper_rebuild/hext/HX03/CODE_PINS.json | `4d84be8a682440ebdae9a6ef998bd5eb1dc927126f8dba27999a1f6af09a206e` |
| $W/docs/paper_rebuild/hext/HX03/METHOD_BODY_PINS.json | `f665380f2c63cc1de3f8ff09a673d75fd19159bcdd6686e28a6a5ea296ab9d2a` |
| $W/src/legsa_gins/paper_rebuild/hext/hx03_injection.py | `bf43d2c3f06b1790134147a3e948bef19c0a246d97e887c5696d3861509dbfe7` |
| $W/src/legsa_gins/paper_rebuild/hext/hx03_relative_update.py | `c6559410a7e79346df7d1c3401293187fa713575f426d15bfa777d50ce0c3d0f` |
| $W/src/legsa_gins/paper_rebuild/hext/hx03_native.py | `7646e4ccacf136908b8c148353d406ee31279b1fae84dea3db85772b4e479481` |
| $W/src/legsa_gins/paper_rebuild/hext/hx03_evaluation.py | `ec00ae56b2a996688206298f18473082e533a58981326309ff53c0ac3a0dcd59` |
| $W/src/legsa_gins/paper_rebuild/hext/hx02_evaluation_process.py | `c94093d1fbf94c9f4db9f6f59334666ea8897c59bcd67654afd4a9914c7764fb` |
| $W/src/legsa_gins/paper_rebuild/hext/external_evaluation.py | `55f2ca5c1c14703c2a4af5cf80b1ca5176e19487aa3f645f3e9efb1e78060df4` |
| $W/scripts/paper_rebuild/hx03_execute.py | `22ecedd2620ee903a29b2d0c75d17e4150a5244f248413bddb50845c792e2a64` |
| $W/scripts/paper_rebuild/hx03_report.py | `e0d811e085457774b519e1bc63f9af3903c930b87edc829f0797e68002e9a231` |

身份门目标：LC01 NAV ccd25c2e1309ba2870e57e2208f476a6b48eaba69f0d038f26be2f168bb2c695；EXT05C NAV 915192d6fcefaf7bef33c4028b571d1b723f7e0759063e2955aebd3d1ee7ace8。

决策规则：无数值门槛，全部结果与失败照实报告；不调参、不重新抽样、不重试。

## 矩阵前调度记录修正（2026-09-26）

用户要求身份门原生若超过 200 s 才将单个原生上限改为 3600 s。原控制器未单独记录原生退出墙钟，账本给出的保守上界为 LC01 ≤21.863835 s、EXT05C ≤20.854462 s、LC01-BR ≤20.753577 s（NATIVE_RESERVED 到该运行首个 EVALUATOR_RESERVED，BR 到 RUN_TERMINAL；见 HX03/IDENTITY_TIMING_AND_ENVIRONMENT.json）。三者均小于 200 s，原生与评估等待上限均保留 600 s，不执行等待上限修正。

每个原生实际已通过未改动的 hx02_evaluation_process.py:37–44 以 OMP_NUM_THREADS=1、OPENBLAS_NUM_THREADS=1、MKL_NUM_THREADS=1 启动。此次将 child_environment 的明确覆盖项写入每个 COMMAND.json 的 environment_whitelist；身份门原 COMMAND 和归档清单保留于 $HX03/00_CONTROL/SCHEDULING_AMENDMENT，补充元数据后重新核归档清单，科学输出逐字节保留。后续原生新增 time.monotonic 墙钟回执 NATIVE_TIMING.json 与 NATIVE_COMPLETED 账本事件。线程数为调度参数，不是科学参数；本次新增解算/评估均为 0。

仅调度记录代码 scripts/paper_rebuild/hx03_execute.py 变更：`22ecedd2620ee903a29b2d0c75d17e4150a5244f248413bddb50845c792e2a64` → `552a5dbe92c7da1551d1bd472fe756e8d8d264f33504dbfdf5bc9aad76f3ea28`；CODE_PINS.json：`4d84be8a682440ebdae9a6ef998bd5eb1dc927126f8dba27999a1f6af09a206e` → `4bf98c7dc357065d4a8a100b5c5da49c4b19a25b62ceae802a3a0f45ae4ff44b`。原登记提交 13d8553ccfd4862284dd54f5fb392f92e99fd2f5 保留；397 项输入、方法数学、注入与评估定义、运行清单、所有科学参数均不变。
