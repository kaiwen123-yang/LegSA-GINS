# CLEAN6 BY2 Canonical-541 protocol v2 执行方案草案

状态：`DRAFT_ONLY / NOT_EXECUTED`。P-08 起点为 `410f75e7ea07a02e8baf0564386940554f044756`。本文件不形成全量执行授权；没有创建拟议 stage、生成 provider、启动求解/评估、归档或删除。本草案的“protocol v2”是新实验协议身份；其评估器版本仍分别写作 v3（主）与 v2（并行对照），两者不得混称。

## 固定范围与来源

| 别名 | 定义 |
|---|---|
| A | `<CLEAN_ROOT>/stages/CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX/.attempt_20260808T200855P0800` |
| S | `<CLEAN_ROOT>/stages/CLEAN5_DEGSUBSET_BY2` |
| N | 拟议 `<CLEAN_ROOT>/stages/CLEAN6_BY2_CANONICAL_541_PROTOCOL_V2`，本任务未创建 |

case 集为原 Canonical 全部 541 个，顺序、60 种退化定义及九个 seed 均保留。配置为 F01/F02/F03/F04/A03/A04/A05/A06/A07/A08/A09 共 11 个有效配置；F03=A02、F04=A01 仅为逻辑别名，不重复求解。因此登记 5951 个唯一求解身份及每评估版本 7033 个逻辑行。

仅 CAL 链：V2s 输入、冻结输入侧 s 和 vrw[3]/abstd[3] 标定值，其余科学配置不变。标定模型来源 `configs/paper_rebuild/clean5/CLEAN5_CALIBRATED_SENSOR_MODEL.yaml`，SHA-256 `4ce6ca6c544c2ba39988ea0b0631a60207a4cea36987c3a2139052fedd3a4871`。冻结科学求解 commit `64c81965b17ef1bf8ae2ce3e4dd7b1ae35110b00`；binary SHA-256 `9c00565c45b654453b2b378f3d5995e5dc21d1271323a9b683acdab75993235f`；评估器 SHA-256 `aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da`。

评估 v3 为主、v2 为并行对照；各登记 5951 个唯一评估身份，共 11902 条记录。没有 NAV 的算法失败仍登记方法失败及评估未调用，不能为凑调用数启动评估器。每版本保持独立目录、字段和来源。BY2 窗口 66–340 s、base_time=1772784000，v3 使用冻结点变换及其原 STD 政策；不重新拟合变换或参数。

## 并行、阶段顺序和运行身份

拟议上限为 **48 个进程**；每个 run 有独立输出、strace 会话及临时目录。求解阶段和评估阶段顺序执行；评估 v3/v2 共用 48 个并发名额，不是各 48 个。每个评估器子进程设置 `OMP_NUM_THREADS=1`、`OPENBLAS_NUM_THREADS=1`、`MKL_NUM_THREADS=1`、`NUMEXPR_NUM_THREADS=1`，并分配独立 `TMPDIR`、`MPLCONFIGDIR`、`XDG_CACHE_HOME`。当前可见 CPU/affinity 均为 24；48 进程不等于 48 个独占 CPU。

拟议顺序：正式预注册与代码冻结 → provider 生成/effect 门 → C00 11 配置锚点 → 其余 5940 个求解 → 输出封存 → v3/v2 离线评估 → 分版本聚合 → 仅归档。C00 已计入 5951，不额外重跑。每个阶段保留可恢复进度及终态；一次生成/一次求解，不按结果重试或调参。

pre/post 原始哈希检查点各为独立 strace 会话：22 个锁文件（含 trace/.bag/.fpl）每文件恰好一次成功 O_RDONLY、仅用于流式 SHA-256，路径集合严格等于锁集合、零写。provider/solver 阶段 trace/.bag/.fpl 打开为 0，raw 零写；评估 trace 仅评估器子进程每次调用打开一次，.bag/.fpl 为 0。写目录沿用 C-04b 白名单。本任务没有执行这些未来阶段。

## Readiness 与公共门逐项迁移

下表源码路径均相对 `src/legsa_gins/paper_rebuild/`，配置另标。未完成这些等价改写前，不能沿用旧 readiness PASS。

| 门 | 原来源 | 新协议草案处理 |
|---|---|---|
| 授权与冻结身份 | `configs/paper_rebuild/canonical541_repaired_execution_authorization.yaml` | 单独预注册 N；保留 binary/evaluator/CAL 模型冻结，本草案不授权执行 |
| Case 闭合 | `canonical541/case_manifest.py:25,89` | 原顺序 541 个、无 placeholder、无结果驱动删选 |
| 方法/别名闭合 | `canonical541/preflight.py:24` | 5951 唯一身份、7033 逻辑行，别名不重复运行 |
| Release/test/preflight | `canonical541/readiness.py:160–183` | 保留零失败及身份/路由重复、缺失、无效数均为零；绑定新基础设施冻结 |
| Native 身份与外层协议 | `canonical541/preflight.py:49–76`；`clean5_degradation/runtime.py:299–331` | 显式登记冻结 native stage/role 与 N 外层身份映射；不能简单替换字符串或冒充 C00 |
| AB0000 数值锚点 | `canonical541/readiness.py:185–214` | 旧噪声链 NAV/STD 数值相等门不适用于 CAL；拟改为 P-07 同协议 CAL/C00 及全部 11 配置锚点核查，字节差与参数差单独登记 |
| clean18 覆盖 | `canonical541/readiness.py:93–157` | 旧门为 F01/F02 + 16 位组合共 18 配置。11 配置不能标成 clean18 PASS；若要求补 7 配置，须额外登记预算与授权，不在当前 5951 内 |
| 输出/封存 | 同上；`compact_readiness_runner.py:156` | 保留输出存在、有限、身份、计数、seal/hash 对应及封存前零 trace |
| Provider 闭合 | `canonical541/execution_plan.py:122–201` | 541 ready/effect 记录及源身份闭合；旧 541×8=4328 源账本保留，新 IMU/压平 GNSS 身份另列 |
| Effect 公共项 | `configs/paper_rebuild/canonical_by2_effect_validation.yaml`；`canonical541/effect_validation.py:373–451` | identity、seed replay、哈希、受影响/未受影响源、影响数、单调/有限/物理合理性、零 trace/算法输出/raw 修改及 60 handler 闭合 |
| 精确计数 | `clean5_degradation/runtime.py:169`；P-07合约 `runtime.counter_expectation` | 按 IMU/GNSS 调度及列15/16/17有效位重放 P/RV/A1 机会；辅助源按静态选择门推导，accepted/rejected/SA 用状态闭合与界限检查 |
| 失败与重试 | effect 合约 `failure_policy`；P-07 `runtime.failed_runs` | 原 `repair_and_regenerate_same_case:true` 不能静默继承；草案一次尝试，失败保留终态，不调参 |
| 评估输入及自检 | `clean5_sequence/evaluation_process.py:27–109`；P-08 A | 统一使用实际评估 NAV、完整共同清洗后的参考支持和 WGS84 ECEF→ENU；在新协议中明确技术门，不能继续两种 wrapper 的隐式不同政策 |

AB0000/CAL 锚点与 clean18 覆盖如何构成等价 readiness，须在未来执行合约中明确；本文件只提出改写，不宣称新门已通过。

## Seed/anchor 与 18 列 5 Hz effect 门

源为 `A/03_SEEDS_AND_ANCHORS/CANONICAL_BY2_ANCHOR_SELECTION_MANIFEST.csv`。九个时刻原样沿用，不在 5 Hz 输入上重选；通用 YAML 示例时刻不能替代该表。

| seed | seed value | 时刻 s | 封存状态 |
|---|---:|---:|---|
| 00 | 260306001 | 206.2 | selected |
| 01 | 260306002 | 107.20639 | fallback_percentile |
| 02 | 260306003 | 189.207044 | selected |
| 03 | 260306004 | 227.201927 | selected |
| 04 | 260306005 | 148.204964 | fallback_percentile |
| 05 | 260306006 | 226.215803 | selected |
| 06 | 260306007 | 258.208267 | fallback_percentile |
| 07 | 260306008 | 247.210403 | selected |
| 08 | 260306009 | 299.203403 | selected |

`canonical_by2_seed_anchor_policy.yaml` 和 `canonical541/seed_anchor.py:125–205,282–310` 规定 PCG64、排序后的 component 命名子流、半开时间窗及先平移后裁剪，均保留。全量适配须扩展 540 个故障 case 的冻结支持映射，不能复制 seed00 清单。

| 族/范围 | 保留参数与等价改写 |
|---|---|
| GNSS18 共通 | 0基列15/16/17为位置/RV/A1有效位；P/RV名义5 Hz，A1仅原有效行，不能保持航向值制造新测量 |
| D01–07、D30–31、D42、D46、D58、D60 | 原秒窗和恢复窗不动；影响计数改为对应源窗内有效机会数 |
| D08–10 | 保留5/2/1 Hz目标和冻结相位；按每源原有效速率判定幂等，不上采样A1，不要求每族恰好5倍影响数 |
| D11–12及概率选点族 | 保留概率/命名子流；按新有效测量数精确重放。跨频率实现不要求逐值相同，新协议自身重放必须完全相同 |
| D13–28、D32–38、D41、D43–45、D47–50、D53、D59–60 | 每测量std、偏置/尖峰幅值、std倍率和物理公式不动；重验各轴、wrap-safe幅值、作用范围和新有效测量数 |
| D22 | 九个seed逐一读取冻结影响历元，登记等时长秒窗；“连续3–5行”改为秒窗有效测量门，8m水平/4m垂直幅值不变 |
| D39 | 九个seed各登记三段冻结秒窗；“每段2–4有效行”改为等时长门，三段及间隔不动 |
| D29、D40、D55、D56 | 保留 NO_ACTIVE_PATH；五项 solver 输入不变；D40 不把缺失 rel_acc 米单位映射为 yaw std 度 |
| D51–52 | RP保持源频率；D51精确50%有效位缺失及余下3°噪声、D52常量2°向量不变 |
| D54 | seed00–03 scale1.5/no dropout；04–07 scale1/dropout0.5；08 scale1.5/dropout0.5，各分支均需验证 |
| D56 | 保留偶数/奇数/seed08 metadata分支 |
| D57 | 六源独立延迟0.1–0.3s、jitter上界20–50ms；保留行身份/稳定排序/事件守恒，18列采用不规则时间并集，不能吸附回规则5 Hz网格 |
| 缺失类 | 有效位=0、行身份及有限载荷保留，不启用原无效观测；冻结库已经使用有效位，删行对照不适用 |

具体依据：`canonical541/effect_validation.py:97–370`、`canonical541/matrix_spec.py:169–224`、`clean5_degradation/providers.py:235,456,486–666`。逐族证据仍必须输出受影响行数、时段、幅值与冻结同 case 对照；参数法则相同不意味着跨频率随机样本逐值相同。

## 失败分类与配对统计草案

完整条件及可观测边界见 [ALL_YAW_REJECTED_CHARACTERIZATION.md](ALL_YAW_REJECTED_CHARACTERIZATION.md)。满足完整窗口处理、航向启用、有效尝试数大于零且全部拒绝等条件时，方法终态拟登记 `ALGORITHM_FAILURE_ALL_YAW_REJECTED`，计入算法失败。评估层若无 NAV，登记 `NOT_RUN_ALGORITHM_FAILURE`；不能仅将该 case 当作缺失而从失败率或配对比较中排除。技术错误、未启动、输入无效和 `EVALUATION_SUSPECT` 分开登记。

一方成功/一方算法失败：成功方赢；双方算法失败：失败平局、各自失败率均计入该 case。另保留双成功有限指标的中位差、bootstrap CI、Wilcoxon 及 N；不将算法失败填成无穷大或伪造 RMSE。全 case 的失败感知胜率与有限数值胜率分列，分母、双失败、技术缺失和疑似评估条目均显式列出。该规则是未来草案，不改写 P-07 原终态/配对表。

## 与 Canonical 同名的输出表结构

每版本分别输出 `N/12_OFFLINE_EVALUATION/<v3|v2>/` 与 `N/13_AGGREGATE/<v3|v2>/`，避免混表；原指标字段/单位/来源保留，协议、评估版本及新增失败分类字段显式附加并在 FIELD_DEFINITIONS 中定义。

| 层 | 保留名称 |
|---|---|
| Case/来源 | CANONICAL541_CASE_MANIFEST.csv；CANONICAL_BY2_DEGRADATION_TYPE_REGISTRY.csv；CANONICAL_BY2_CASE_FAMILY_SUMMARY.csv；PARAMETER_PROVENANCE_REGISTRY.csv；FROZEN_GENERATOR_SOURCE_MAP.csv |
| Seed | CANONICAL_BY2_RANDOM_SEED_MANIFEST.csv；CANONICAL_BY2_ANCHOR_SELECTION_MANIFEST.csv；CANONICAL541_ANCHOR_SOURCE_PROVENANCE.json |
| Effect/provider | CANONICAL_BY2_EFFECT_VALIDATION_RULES.csv；CANONICAL541_PROVIDER_READY_MANIFEST.csv；CANONICAL541_EFFECT_VALIDATION_RESULTS.csv；COMPONENT_VALIDATION_TABLE.csv；EFFECT_VALIDATION_DETAIL_TABLE.csv；EFFECT_VALIDATION_FAILURES.csv；PROVIDER_SHA256_MANIFEST.csv；PROVIDER_GATE.json |
| 执行注册 | CANONICAL541_UNIQUE_RUN_REGISTRY.csv；CANONICAL541_LOGICAL_ALIAS_REGISTRY.csv；FULL_ALGORITHM_QUEUE.csv；INTERNAL_ABLATION_QUEUE.csv；PROVIDER_CONFIG_EXECUTABLE_HASH_REGISTRY.csv；EXECUTION_PLAN.json |
| 评估 | UNIQUE_EVALUATION_RESULTS.csv；LOGICAL_EVALUATION_RESULTS.csv；EVALUATION_FAILURES.csv；EVALUATION_STATUS.json；FIELD_DEFINITIONS.md；逐run summary.json、error_series.csv、error_series.csv.gz |
| 聚合15项 | UNIQUE_METHOD_SUMMARY.csv；LOGICAL_METHOD_SUMMARY.csv；CASE_SUMMARY.csv；DEGRADATION_TYPE_SUMMARY.csv；FAMILY_SUMMARY.csv；PAIRWISE_CASE_LEVEL.csv；PAIRWISE_SUMMARY.csv；SEED_SUMMARY.csv；RECOVERY_SUMMARY.csv；UNCERTAINTY_CALIBRATION_SUMMARY.csv；MODULE_ACTION_SUMMARY.csv；RUNTIME_SUMMARY.csv；METRIC_COVERAGE_REPORT.csv；FINAL_EVALUATION_SUMMARY.json；EVALUATION_AND_AGGREGATE_STATUS.json |

来源：`scripts/paper_rebuild/build_canonical541_manifest.py:424–455`、`canonical541/trusted_direct.py:309–360`、`canonical541/offline_eval_aggregate.py:1089–1192,1305–1430`。协议迁移、自检诊断及失败感知配对字段另有定义，不覆盖原科学指标。

## 时长与磁盘预算

P-07 实测计时来源：`S/03_RUNS/RUN_RECORDS.json`、`S/07_EVALUATION/EVALUATION_RECORDS.json`，原并行数为12。评估计时仅含评估器子进程，不含后续压缩、指标处理及封存。

| 项目 | 样本数 | 均值 s | 中位 s | P95 s |
|---|---:|---:|---:|---:|
| CAL 求解 | 671 | 30.9178586535 | 30.0307371390 | 40.3637391380 |
| CAL v2 评估 | 669 | 7.59853830248 | 7.58227073800 | 8.19086849800 |
| CAL v3 评估 | 669 | 7.09169687770 | 6.92047938300 | 9.12861302100 |

线性推算：`5951 × mean_solver / effective_parallelism`，评估为 `5951 × (mean_v2+mean_v3) / effective_parallelism`。

| 有效并行度情景 | 求解 h | 两版本评估 h | 合计 h |
|---|---:|---:|---:|
| 48 | 1.065 | 0.506 | 1.571 |
| 24 | 2.130 | 1.012 | 3.141 |
| 12 | 4.259 | 2.024 | 6.283 |

以上保持单 run 时延不变，未实测48进程。当前24个可见CPU下，48进程存在超额并发；1.571 h仅为子进程理想情景，不能当作完整流水线时间。

为计入I/O及封存，另按P-07 service journal分块估算。`clean5-degsubset-20260910.service` 从2026-09-10 19:41:01.299942+08的 `PHASE_START prepare` 到22:59:38.423463+08的 `CONTROLLER_COMPLETE`，实测11917.124s，即3h18m37.124s。

| journal分段 | P-07墙钟s | 外推方式 |
|---|---:|---|
| provider前后检查点之间 | 391.096 | 按541/61放大 |
| solver前检查点→最后solver终态 | 3432.881 | 按5951/1342及12/有效并行度放大 |
| 最后solver→封存完成/评估阶段开始 | 1385.333 | 按5951/1342放大，不计并行加速 |
| 评估阶段开始→首个评估完成 | 697.070 | 含封存校验/首批评估，按5951/1342放大，不计并行加速 |
| 首个→最后一个评估完成 | 4082.361 | 按5951/1342及12/有效并行度放大 |
| 最后评估→聚合、横向、封存及controller完成 | 1898.815 | 混合块按5951/1342放大，不计并行加速 |
| 其余外层启动/阶段间隙 | 29.568 | 固定 |

封存复核对应 `clean5_degradation/evaluation.py:69`、`scripts/paper_rebuild/clean5_run_degradation_subset.py:89–110`、`clean5_degradation/common.py:92–103`。未分离的检查点及后处理开销保守留在混合块中；未来协议不要求横向重评，但因该旧尾块不能完全分解，没有假定可扣除它的耗时。

| 有效并行度情景 | provider h | 串行/未分解块 h | 并行工作块 h | 固定外层 h | 完整流水线估算 h |
|---|---:|---:|---:|---:|---:|
| 48 | 0.963 | 4.904 | 2.314 | 0.008 | 8.190 |
| 24 | 0.963 | 4.904 | 4.629 | 0.008 | 10.504 |
| 12 | 0.963 | 4.904 | 9.257 | 0.008 | 15.133 |

因此完整流水线预算可登记为**约8–16小时的条件情景**，包含provider、求解、评估后处理、聚合和封存；不假定封存/不可分解I/O随48进程加速。该范围不是48进程实测、统计置信区间或保证上限；假设单任务成本、存储吞吐、后处理复杂度仍与P-07同量级。新增全量门实施、人工审阅/Git交付和额外归档副本制作不在运行预算内。磁盘容量门仍须先满足。时间块、缩放参数与完整精度计算值另存 `S/11_PREFULL_CLEARANCE/C_PIPELINE_ESTIMATE.json`。

磁盘 stat 样本为 CAL/C00/A04 `RUN_00006`，另抽查D22/D39/D57/D60量级一致。单位 GB 为十进制；同时保留原 CSV 与 gz。

| 内容 | 单run字节 | ×5951 |
|---|---:|---:|
| Solver全部文件 | 70,194,383 | 417.727 GB |
| v2全部文件 | 19,042,448 | 113.322 GB |
| v3全部文件 | 28,267,106 | 168.218 GB |
| 合计 | 117,503,937 | 699,265,929,087 B = 699.266 GB |

未含provider、聚合、临时目录及额外归档副本。加15%规划余量约804.156 GB。2026-09-11检查时 G: 可用56,611,831,808 B，基础预算缺口约642.654 GB，未来 N 的磁盘启动门为 `NOT_SATISFIED`。WSL ext4约945.486 GB虚拟可用不等于G:可用；没有授权迁移stage，归档副本不能计作释放空间。

## 仅归档、不删除的清单

保留原/派生 NAV、STD、IMU_ERR；PORT_GNSS_UPDATE_TRACE、PORT_RUNTIME_LOOP_TRACE、PORT_SKIPPED_GNSS_TRACE；所有 strace/stdout/stderr、原生与外层 manifest、运行/评估终态、原 CSV 及 gz；provider、注入差分、注册表、聚合、检查点与封存清单。失败 run 的有限诊断产物同样保留；归档逐项登记来源、尺寸、哈希和目标，不进行移动或删除。

旧 `canonical541/offline_eval_aggregate.py:396–399` 的 gzip 后 `unlink(error_series.csv)` 不能继承；采用 `clean5_sequence/evaluation_process.py:106–109` 保留两份的行为。当前 P-08 仅提交清单和方案，没有实际创建归档或释放磁盘。
