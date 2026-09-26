# HX-03R-2 登记：WGS84 观察器更正后的审计重评

本任务是结果之后的审计工具修正。起点 592e10543b7e64093d6c6f35c6d32483850e4715；HX-03 的表、原生输出和目录全部保留，只向 HX03R2_AUDIT_REEVAL 写新文件。冻结评估器、原生算法、D8、D12 阈值均不改。

## 1. 原因与身份门裁定

HX-03R-1 的 146 个逻辑不可用行，水平不一致量中位数 0.03913079253370084 m；不一致量/水平 RMSE 中位数 0.022802420226922474（2.280242%）；按 113 个实际目录去重后，不一致量与最大水平误差回归 R²=0.9469042880015941。20 个 v3 对照的水平不一致约 1e-14 m。出处：HX03R/DIAGNOSTIC_STATISTICS.json:logical,unique_cross_run_regressions,controls。

按最新用户裁定，身份门为每个 v3/v2 槽位的冻结原始 summary.json 与 error_series.csv 两文件逐字节 SHA256 等于 HX-03 归档值；任一个不同即硬停。EVALUATION_RESULT.json 包含处置和审计状态，仅作 R1 记录引用，不要求其字节不变。旧可用行另核数值科学字段逐项相等，并对旧逻辑表四个主指标再核一次。

## 2. 观察器来源与接线

直接调用 src/legsa_gins/paper_rebuild/clean6_canonical_v2/evaluation.py:39–85 的 _ecef / wgs84_consistency_check；SHA256 为 8dfacf094879e7c091f1ddf1d5dcb3164f43923dc0903734cb6d29e05eeccc10。本次文件与 v3 科学冻结提交 7d43b9af26120ed5dde21f53e515386361072ba6 内该文件的字节 SHA256 相同。v3 接入点为 protocol_v3/runtime.py:244，policy=canonical_v2_wgs84_full_support；20 个既存 capture 也均记录该策略。原观察器源文件 diff 为空。

冻结评估器 SHA256 仍为 aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da。新增 hx03r2_observer.py 只在 capture 配置中选择上述策略，并在冻结 main 返回后，用已在内存中的 NAV、参考和冻结误差再调用同一观察器函数一次，通过 profile 返回事件保存该函数的实际局部残差数组。没有新增投影公式，没有替换或修改冻结评估器函数、数组或已有观察器。参考不增加打开次数。

逐历元保存 time、东/北残差、水平残差向量范数、水平误差模长差、高程差、圆周 yaw 差；符号为 observer−evaluator。同时保存三个最大值的首个 argmax 索引/时刻及该行两方误差、观察器 RMSE 和 yaw P95。压缩文件仅为逐例数据文件，不是交接包。

新增接线相对 hx03_evaluation.py 的完整 diff 为 HX03R2/REGISTRATION_R2/OBSERVER_FULL_DIFF_R2.diff，作为本登记附件全文保存；已有观察器与冻结评估器没有源码改动。

## 3. 登记前验证

20 个 v3 对照仅复核旧 WGS84 审计和代码身份，不重新评估 LegSA；旧水平最大残差的最大值 3.351623381340333e-14 m。NAV 已按 v3 留存策略清理，本项按用户裁定复用旧记录。BR C00 的 NAV SHA256 与 LC01 C00 完全相同，为 ccd25c2e1309ba2870e57e2208f476a6b48eaba69f0d038f26be2f168bb2c695，BR 不另评估。

实际验证如下。位置门是 H/Up 都 ≤1e-9 m；每个槽位两文件哈希均相同，每次参考只读打开并核哈希各 1 次。两个 R1 不可用行采用主表 v3 点；其 v2 点留在矩阵内。

| 方法/工况/点 | H max/m | Up max/m | yaw max/° | 原始两文件 |
| --- | --- | --- | --- | --- |
| LC01 / C00 / v3 | 2.8529002078843539e-14 | 1.3874318360862503e-14 | 4.0927261579781771e-12 | SHA256 相同 |
| LC01 / C00 / v2 | 2.8921778754749802e-14 | 1.2656542480726785e-14 | 4.0927261579781771e-12 | SHA256 相同 |
| EXT05C / C00 / v3 | 2.9437831114535091e-14 | 1.2934098236883074e-14 | 4.0927261579781771e-12 | SHA256 相同 |
| EXT05C / C00 / v2 | 2.893603953645793e-14 | 1.3156142841808105e-14 | 4.0927261579781771e-12 | SHA256 相同 |
| LC01 / D04_seed_00 / v3 | 2.8529002078843539e-14 | 2.1316282072803006e-14 | 4.0927261579781771e-12 | SHA256 相同 |
| EXT05C / D62_20s_seed_00 / v3 | 2.9437831114535091e-14 | 2.8421709430404007e-14 | 4.0927261579781771e-12 | SHA256 相同 |

6/6 槽位通过，最大位置残差 2.943783111453509e-14 m；4 个旧可用 C00 槽位各 138 个数值字段逐项相等。来源：VALIDATION_RESULTS_R2.json；每槽位 SCIENTIFIC_IDENTITY_R2.json、RESULT_R2.json、EVALUATOR_STRACE_AUDIT_R2.json。合成单元共 6 个不同检查通过：残差保存/符号/argmax、时间支持门、原始字节身份门、数值字段门和未执行启动计数；UNIT_GATE_R2.xml 与 UNIT_IDENTITY_FINAL_R2.xml 保留。

首次工具启动时外层 strace -f 与子进程 strace 冲突，PTRACE_TRACEME 在 Python 子进程执行前被系统拒绝；无 execve/openat、无 OUTPUT、参考打开 0，科学调用 0。原错误、HARD_STOP 记录和只读证据保留在 PREEXEC_FAILURE_01_R2。仅去掉外层控制器 strace 的 -f，子进程原启动器完全不改，随后执行尚未开始的槽位。账本区分工具启动尝试与实际评估；不把此启动拒绝记成一次成功评估或删除记录。

## 4. 固定范围、存储及执行

RUN_MAPPING_R2.json 覆盖原 RUN_MANIFEST 的 381 行，其中 285 次既有原生（282 矩阵+3 身份门）、96 个复用目录。246 个目录留有 v3/v2 评估，共 492 槽位；6 个验证槽位计入其中，提交后仅执行其余 486 个，不重复做。其余 39 个原生目录为：28 个在评估窗前发散而无可评输出、10 个 C00 等价类型确认、1 个 BR C00。等价行继续按旧登记及原生哈希复用，A1 等价行不新增运行。逐项清单 EVALUATION_SLOTS_R2.json、RUN_MAPPING_R2.json。

每个实际评估重用已归档的 v3/v2 NAV 字节，不重新生成物理点变换。冻结窗口 [66,340]、BY2 base_time=1772784000、yaw_truth_mode=enu、STD 不提供，均与 HX-03 相同。PRE_FAILURE 只使用原来截断并已评估的 NAV，不变更截断点；发散状态保留，不并入有限分布。

所有评估经未改动的 hext/hx02_evaluation_process.py 运行，子进程 strace -f -yy 审计，参考每次恰好打开 1 次、只读、核 SHA256；控制器/汇总进程禁止打开 raw/trace/bag/fpl。原生调用 0，LegSA 解算/评估 0/0。观察器调用内存数组不是新增参考读取。

矩阵每族一批、评估并发 6（代码上限 8），数值库线程均为 1，单次评估上限 600 s；tmux 独立控制器写 STATE_R2.json、PROGRESS_R2.txt、LEDGER_R2.jsonl。已保留的实际评估槽位不重试；启动前先预留，任何中断且已执行的槽位不得自动再评。

每批前 E 可用≥40 GB、G 可用≥30 GB；E 不写文件。scratch 限 $SCRATCH/HX03R2 且≤20 GB，归档到 $HX03R2/RUNS 后逐文件核 SHA256，再清理该槽位 scratch；原始误差 CSV 压缩归档时另核解压字节 SHA256。按验证槽位估计，492 个归档约 3.9 GB，汇总残差副本约 1.3 GB，按实际磁盘守卫执行。不做交接包。

65 pin 在任务开始、登记提交前、结果提交前各核一次；423 项方法本体、29 个既有未跟踪文件保持哈希不变。HX-03 全部 14525 个既存文件（含 R1 诊断）清单/大小/mtime_ns 不变，所读记录和每个实际输入 NAV 另核内容哈希。

## 5. 处置、汇总与硬停

D12 位置阈值仍为 0.01 m，yaw 阈值仍为 0.01°，三项都通过才接纳；仍不过的行继续 UNAVAILABLE_EVALUATION_FAILED，不放宽门。D8 不变；原生发散保持 ALGORITHM_FAILURE_DIVERGED，即使 PRE_FAILURE 审计通过也不改成有限运行。所有有限与失败照实报告，无性能门槛。

观察器验证不过、任一冻结原始输出哈希不同、旧可用科学指标不同、65 pin/方法本体不同、任何原生调用、非子进程开参考均硬停；不以改阈值、换输入或重跑算法恢复。

逐例主表与并行 v2 表、逐型/逐族汇总、与 F04/F02/F03/A04 的配对差均输出新 _R2 文件；LegSA 数值只读 V3 的 CORE_541_DISTRIBUTION_V3.csv 与 ADDENDUM_TABLE_V3.csv。统计仍为有限样本中位数/P95/最大值，配对只取双方有限，报告配对数。

三张表保留 HX-03 原列并增加 audit_status_R1、audit_status_R2、observer_discrepancy_R2；逐例状态为 PASS/FAIL/NOT_EVALUATED，残差列为 H/Up/yaw 三个最大值的 JSON。汇总/配对表状态列为组内计数 JSON，残差列为组内三轴最大值 JSON。

结果归档 $HX03R2/90_AGGREGATE 并复制到 $W/docs/paper_rebuild/hext/HX03R2/：逐例、汇总、配对、状态变化、仍不可用清单、492 槽位原始文件身份表、AUDIT_RESIDUALS/ 及 HX03R2_RESULTS.md。AGENTS.md 结果时追加一行。

## 6. 代码身份

| 新增文件 | SHA256 |
| --- | --- |
| src/legsa_gins/paper_rebuild/hext/hx03r2_observer.py | 23bf6050af32cd63ce140350dae3048ca8125eac00efca32185a5f00b4037cf8 |
| scripts/paper_rebuild/hx03r2_execute.py | 06b6a77406acf4976e5d104eade6c98e23aeab7307f9b04811c4da8621090463 |
| scripts/paper_rebuild/hx03r2_prepare.py | d3a938a1ae05e9fad7e46132ee8eea4486b4c56a661191607f021dd5e094ec6e |
| tests/paper_rebuild/test_hx03r2_observer.py | 1128b57b02b2268378c155f71fc079842460179375015b2855497d37265d602e |
| tests/paper_rebuild/test_hx03r2_identity.py | 1e091fbea6f8879e002075991340771458977b3839cea002f8c9041e6a94f8c2 |
| scripts/paper_rebuild/hx03r2_report.py | 45ec71257894f65e24c320522913c56e059916fda0d0819e043f2aa906c79191 |
| scripts/paper_rebuild/hx03r2_verify.py | 991abab6c10bea874959bcbab3abcc9aa7465167e9927497985919c6fb74595e |

其余依赖、完整输入/槽位身份见 CODE_PINS_R2.json（42 项）、OLD_RECORD_PINS_R2.json、EVALUATION_SLOTS_R2.json；所有旧源码保持不变。开始与登记前封存核验见 PREREQUISITE_START_R2.json、BEFORE_REGISTRATION_R2.json。

附件完整接线 diff SHA256：298230350c6fb2f9a1d3755cb1cd90415f0ae6df9dc8ed2528027b83dc411055。

登记附件完整副本在 `$W/docs/paper_rebuild/hext/HX03R2/REGISTRATION_R2/`，对应 `$HX03R2/00_CONTROL/` 的登记前记录。开始/登记前 65 pin 均 65/65（CSV 59/59），423/423 方法本体与 29/29 既有未跟踪文件一致。
