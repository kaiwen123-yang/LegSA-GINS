# P-08 B：全航向拒绝失败刻画与分类规则草案

仅检查 P-07 原 10 个 `FAILED_TECHNICAL` run 及其同链、同 case 的 F02。10/10 均完成配置窗口内的 56642 个 IMU 循环和 1369 个 GNSS 更新，273 次航向尝试全部拒绝，accepted=0；同输入 F02 的 273 次尝试均为 NORMAL、accepted=273。本文将这 10 个结果登记为 **`ALGORITHM_FAILURE_ALL_YAW_REJECTED` 草案**，原 P-07 终态、评估占位、指标、配对表及决定文件保持原样。

本文没有执行求解、评估、provider 生成、重试或阈值修改；没有读取 raw trace、`.bag`、`.fpl`。未来全量分类器和新配对统计均未实现。

## 范围与封存来源

`S = <CLEAN_ROOT>/stages/CLEAN5_DEGSUBSET_BY2`；`B = S/11_PREFULL_CLEARANCE`；`R(chain,run) = S/03_RUNS/CLEAN5_DEGSUBSET_<chain>/<run>`。时间为该序列相对时间，单位 s；角度和角度 STD 单位 deg。日志时刻 token 原样保留，不增加有效精度。

P-07 执行代码：`24cc761e4085561888a9d8546df8b89300d340fe`；本次只读源码起点：`410f75e7ea07a02e8baf0564386940554f044756`。科学源码冻结：`64c81965b17ef1bf8ae2ce3e4dd7b1ae35110b00`；执行二进制 SHA-256：`9c00565c45b654453b2b378f3d5995e5dc21d1271323a9b683acdab75993235f`。

输入为 `R/PORT_GNSS_UPDATE_TRACE.csv`、`PORT_RUNTIME_LOOP_TRACE.csv`、`P07_RUN_TERMINAL.json`、`DEGRADATION_RUNTIME_CONFIG.yaml`、`stderr.log`，以及 F02 的 `RUN_MANIFEST.json`；这些文件均按 `S/04_SEAL/SOLVER_OUTPUT_SEAL.json` 核对。相关 case/C00 provider manifest 按 `PROVIDER_SEAL.json` 核对，GNSS18 内容按各 manifest 的 provider pin 核对。四个所引用 C++ 源文件与科学冻结 commit 无差异，当前内容哈希同时写入 `B/B_EVIDENCE.json`。

总计 102 个源文件的哈希检查通过。对照是 6 个唯一 F02 run，在 10 个失败方法行中按同链同 case 重复引用，不作为 10 个独立 F02 实验。

## 十个失败 run 的时序与 F02 对照

下表计数顺序为 **attempt / normal / downweight / reject / accepted**。连续段以相邻有效航向尝试定义；穿插的 5 Hz GNSS `yaw_mode=NONE` 行不切断航向拒绝段。所有行只有 1 段，首拒绝 67 s，末拒绝 339 s，273 次尝试的端点时间跨度是 272 s，不写成 273 s 持续时间。相邻尝试最大间隔均为 1 s；首拒绝相对配置起点 66 s 为 +1 s。

| 链 | case | 失败 run / 方法 | 首拒绝 (s) | 末拒绝 (s) | 连续拒绝尝试 | 失败计数 A/N/D/R/Ac | 同 case F02 run | F02 计数 A/N/D/R/Ac |
|---|---|---|---|---|---|---|---|---|
| CAL | D15_seed_00 | RUN_01400 / F03 | 67.000000000 | 339.000000000 | 273 | 273 / 0 / 0 / 273 / 0 | RUN_01399 | 273 / 273 / 0 / 0 / 273 |
| CAL | D59_seed_00 | RUN_05756 / F03 | 67.000000000 | 339.000000000 | 273 | 273 / 0 / 0 / 273 / 0 | RUN_05755 | 273 / 273 / 0 / 0 / 273 |
| V2S | D14_seed_00 | RUN_01301 / F03 | 67.000000000 | 339.000000000 | 273 | 273 / 0 / 0 / 273 / 0 | RUN_01300 | 273 / 273 / 0 / 0 / 273 |
| V2S | D14_seed_00 | RUN_01304 / A04 | 67.000000000 | 339.000000000 | 273 | 273 / 0 / 0 / 273 / 0 | RUN_01300 | 273 / 273 / 0 / 0 / 273 |
| V2S | D15_seed_00 | RUN_01403 / A04 | 67.000000000 | 339.000000000 | 273 | 273 / 0 / 0 / 273 / 0 | RUN_01399 | 273 / 273 / 0 / 0 / 273 |
| V2S | D27_seed_00 | RUN_02592 / A05 | 67.000000000 | 339.000000000 | 273 | 273 / 0 / 0 / 273 / 0 | RUN_02587 | 273 / 273 / 0 / 0 / 273 |
| V2S | D27_seed_00 | RUN_02594 / A07 | 67.000000000 | 339.000000000 | 273 | 273 / 0 / 0 / 273 / 0 | RUN_02587 | 273 / 273 / 0 / 0 / 273 |
| V2S | D27_seed_00 | RUN_02596 / A09 | 67.000000000 | 339.000000000 | 273 | 273 / 0 / 0 / 273 / 0 | RUN_02587 | 273 / 273 / 0 / 0 / 273 |
| V2S | D59_seed_00 | RUN_05759 / A04 | 67.000000000 | 339.000000000 | 273 | 273 / 0 / 0 / 273 / 0 | RUN_05755 | 273 / 273 / 0 / 0 / 273 |
| V2S | D59_seed_00 | RUN_05763 / A08 | 67.000000000 | 339.000000000 | 273 | 273 / 0 / 0 / 273 / 0 | RUN_05755 | 273 / 273 / 0 / 0 / 273 |

10 个失败 run 原生 exit_code 均为 1、retry_count 均为 0；stderr 原文完全相同：

```text
legsa_v23_port_core_demo failed: FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH: actual formal module activation counters mismatch
```

每个失败 run 的 position/RV 更新数均为 1369/1369，GNSS 更新日志的首末时刻为 `66.200000048` / `339.799999952` s。每个 run 的循环日志均有 56642 行，最后 `timestamp_after_process` 原 token 为 `339.997` s；封存输入调度期望为 `339.997056` s。循环日志精度较低，因此不把后者冒充为日志中观察到的精确时刻。循环日志的 `nav_written=1` 是内循环调试字段，不能证明最终 NAV 文件已落盘。

10 个失败 run 均未产生最终 `RUN_MANIFEST.json`、`KF_GINS_Navresult.nav` 或 `KF_GINS_STD.txt`。其计数来自按冻结 counter 增量写入的更新时序，不伪称为缺失的最终 native manifest 计数。

## F02 完整执行行为

| 链 | case | F02 run | 原终态 | P / RV | attempt / normal / down / reject / accepted | 首末 yaw (s) |
|---|---|---|---|---|---|---|
| CAL | D15_seed_00 | RUN_01399 | COMPLETED | 1369 / 0 | 273 / 273 / 0 / 0 / 273 | 67.000000000 – 339.000000000 |
| CAL | D59_seed_00 | RUN_05755 | COMPLETED | 1369 / 0 | 273 / 273 / 0 / 0 / 273 | 67.000000000 – 339.000000000 |
| V2S | D14_seed_00 | RUN_01300 | COMPLETED | 1369 / 0 | 273 / 273 / 0 / 0 / 273 | 67.000000000 – 339.000000000 |
| V2S | D15_seed_00 | RUN_01399 | COMPLETED | 1369 / 0 | 273 / 273 / 0 / 0 / 273 | 67.000000000 – 339.000000000 |
| V2S | D27_seed_00 | RUN_02587 | COMPLETED | 1369 / 0 | 273 / 273 / 0 / 0 / 273 | 67.000000000 – 339.000000000 |
| V2S | D59_seed_00 | RUN_05755 | COMPLETED | 1369 / 0 | 273 / 273 / 0 / 0 / 273 | 67.000000000 – 339.000000000 |

6 个 F02 对照均为 exit_code=0、COMPLETED，56642 循环、1369 GNSS 更新；时序计数与封存 native manifest 一致。每个失败 run 与对应 F02 的五个 provider pin 相同，273 个 yaw attempt 时刻完全相同。F02 使用固定 1.5 deg yaw STD 的 basic update，不应用 Scheme-C 拒绝/降权门；其 RV 关闭。F02 的这些执行与接受计数不证明航向准确性，也不是仅改变门控开关的单变量对照。

## Provider 与阈值证据

D14、D15、D27、D59 的 GNSS18 provider 各有 1510 行，其中 301 行 A1 有效；273 行在本次调度窗口被尝试。与同链共用的 C00 输入相比，时间、yaw、yaw STD、yaw_valid 四列逐 token 相同；provider 注入摘要的 `dual_yaw.affected_row_count=0`。有效 A1 的 STD 全部为 1.5 deg。provider、终态及 F02 对照共同证明存在同一组有效航向观测，不能把 273 次全拒绝解释为“没有航向观测”。

| case | 原注入 | 航向注入 |
|---|---|---|
| D14_seed_00 | position Gaussian noise：h_sigma=1.5 m，v_sigma=2.5 m | 无；yaw/STD/有效位不变 |
| D15_seed_00 | position Gaussian noise：h_sigma=3 m，v_sigma=5 m | 无；yaw/STD/有效位不变 |
| D27_seed_00 | bad position：h_sigma=3 m，v_sigma=5 m；position STD×0.25 | 无；yaw/STD/有效位不变 |
| D59_seed_00 | bad position：h_sigma=3 m，v_sigma=5 m；Raw Doppler conflict=1 m/s，receiver velocity 不变 | good_yaw_preserved；yaw/STD/有效位不变 |

来源：预注册合约 `configs/paper_rebuild/clean5/CLEAN5_DEGRADATION_SUBSET_CONTRACT.yaml` 与 `S/02_PROVIDERS/<case>/DEGRADATION_PROVIDER_MANIFEST.json`。这张表仅登记已注入的观测变化，不根据结果重新解释或修改幅值。

10 个失败 run 的冻结配置一致：yaw STD 最小值 0.5 deg、软阈值 3 deg、硬阈值 6 deg；残差软阈值 6 deg、硬阈值 15 deg；downweight scale=2.5；`source_aware_reject_extreme=false`。F02 的固定 STD=1.5 deg。阈值取原配置，不调整。

## 冻结代码可证明的执行顺序及不可观测项

1. `cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp:931` 的 `applyYawUpdate` 先将 attempt 计数加一；残差定义为 `wrap(predicted_yaw − observed_yaw)`。若 `yaw_std >= 6 deg` **或** `abs(residual) >= 15 deg`，reject 加一并返回；低于硬门才继续软降权和 Source-Aware。另一个 Source-Aware `weight.rejected` 分支也增加 reject。边界为 `>=`，不是 `>`。
2. 同文件 `:979` 的 basic update 不采用上述 robust gate，执行 EKF update 后 normal 加一；解释了为何 F02 的接受计数不能用于反推失败 run 的残差。
3. `cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp:1503` 根据 normal/downweight/reject 计数增量决定 `yaw_mode`；`:1516` 写出的 `yaw_update` 是 attempt 增量，`REJECT` 时也可为 1。该行使用 `",,,"` 将 yaw/position/velocity 残差字段留空。因此不能把 `yaw_update=1` 当作 accepted。
4. 同文件 `:124` 将正式 yaw 更新计数设置为 `attempt − reject`；`:206` 要求对应方法 `yaw_active = accepted > 0`；`:1543` 在循环结束后复制计数并检查合约，检查失败抛出 stderr 中的异常，发生在 `writeAll` 之前。这足以说明本 10 行为何没有最终 NAV/STD/manifest：accepted=0 已构成一个可证的合约失败条件。不宣称它是唯一可能不匹配的模块项，因为失败 run 的其他最终辅助计数没有写出。

逐拒绝事件的数值残差、预测 yaw、创新方差/NIS、实际 R、Source-Aware reason code 以及所走 reject 分支没有记录。`B/B_REJECT_EVENTS.csv` 的 `yaw_residual_deg` 留空，并带 `UNAVAILABLE_NOT_LOGGED`，每行同时列原配置硬阈值；不填 0，不以 F02 状态替代，不用 GNSS yaw 充当残差，不重建失败 run 的 NAV。已知 provider STD=1.5 deg 小于 6 deg，排除了 provider 原始 yaw STD 本身超过该阈值的情形；这不补出逐次残差，也不把未记录的 reject 分支数量宣称为实测。

## 分类与未来 pair-case 处理规则草案

这些规则只形成文档草案；本次不实现全量分类、不重算 P-07 四列表，也不改其已有 `FAILED_TECHNICAL` 或 `UNAVAILABLE_FAILED_SOLVER` 字段。

`ALGORITHM_FAILURE_ALL_YAW_REJECTED` 需要同时具有：正确且封存的输入/方法身份，配置窗口处理完成，有正数且与调度有效位一致的 yaw attempts，所有尝试均拒绝，accepted=0，以及可回溯的完整日志。本次 10/10 满足。未来分层登记为 `method_outcome=ALGORITHM_FAILURE_ALL_YAW_REJECTED`、`evaluator_status=NOT_RUN_ALGORITHM_FAILURE`，计入该方法算法失败率；不只留下科学缺失标记而将 case 从配对分母漏掉。原 10 个通用技术终态字符串保留供追溯。

其他超时、进程启动失败、输入/哈希不符、日志不完整、协方差/数值异常、无可用观测或评估技术失败必须独立分类；不能仅凭 exit 非零或 accepted=0 套用“全航向拒绝”。本次算法分类证据不构成对任意其他失败的自动归类。

| pair-case 情形 | 失败感知胜负草案 | 有限数值差 / 统计 |
|---|---|---|
| 双方成功且该指标均为有限数值 | 按 candidate−reference：<−1e−12 candidate 胜；>+1e−12 reference 胜；其余数值平局 | 保留实际 delta，进入有限数值 median/CI/Wilcoxon |
| candidate 算法全拒绝，reference 成功 | reference 胜；candidate 失败率计入该 case | delta=非数值缺项；不伪造 +∞ RMSE |
| candidate 成功，reference 算法全拒绝 | candidate 胜；reference 失败率计入该 case | delta=非数值缺项；不伪造 −∞ RMSE |
| 双方算法全拒绝 | 失败平局；两方法失败率均计入该 case；单列 FAILURE_TIE | 无有限 delta；不得和数值零差混为一类 |
| 任一方其他技术失败或未闭合缺失 | 独立技术/缺失行，不能冒充算法胜负；全 case 结论待闭合 | 不填零或无穷大，不删除注册 case |

全 case 的 failure-aware 胜率与有限指标统计分开报告。技术证据均闭合时，failure-aware 胜率为 `wins / 全部注册 paired cases`，分母包括单方算法失败、双方失败平局和数值平局；平局不计为任一方胜，两个平局种类分别列计数。算法失败率为该方法算法失败 cases / 注册 cases，双方失败分别进入双方失败率。若仍有技术未闭合 case，应保留其行、总 N、已判 N 和缺失数；不将未知胜负暗计为胜/负，不发布已闭合的全 case 方向结论。

有限数值 median、bootstrap CI、Wilcoxon **只使用双方成功且指标有限的 case**，公开 `N_finite/N_total`、算法失败数、技术缺失数及其 case 清单；这些有限子集统计不替代全 case 的 failure-aware 胜率。将来若给 failure-aware 胜率计算 CI，应另行预注册分类结果的 case 重采样规则，不能把“无限 RMSE”塞入当前数值差 bootstrap。这里没有计算新的失败感知胜率或 CI。

## 派生产物与可复核方式

| 文件 | 内容 |
|---|---|
| `B/B_ALL_YAW_REJECTED_RUNS.csv` | 10 行时序、计数、F02 对照、原终态及草案类别 |
| `B/B_F02_CONTROLS.csv` | 6 个唯一 F02 的完整计数、native manifest 与来源 |
| `B/B_REJECT_STREAKS.csv` | 10 段；相邻 yaw attempts 定义，端点跨度与最大间隔 |
| `B/B_REJECT_EVENTS.csv` | 2730 个拒绝事件；残差明确不可观测，阈值与来源逐行列出 |
| `B/B_EVIDENCE.json`、`B/B_SUMMARY.json` | 102 个源文件/哈希、定义、来源与边界 |
| `B/B_IO_AUDIT.json`、`B/B_ANALYSIS_OPENAT.strace` | 本次后处理 I/O 与 16 个原 run 已登记的 solver I/O 审计 |
| `B/B_analyze_all_yaw_rejected.py` | 可复现分析；默认输出使用独占创建，拒绝覆盖 |

分析器已运行一次生成派生结果，并用 `--check-existing` 在零写入模式重算比较，6 个数据 CSV/JSON 产物完全相同。本次 strace 审计共 303 个可解析 open，raw trace/.bag/.fpl 打开均 0；6 次数据写入全部位于 B 区。10 个失败 run 加 6 个 F02 原始终态中保存的 solver I/O 审计均通过。该核对不重启它们的进程。

用已设置为本机别名路径的 `P08_STAGE` / `P08_CODE` 复核已有派生产物：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 "${P08_STAGE}/11_PREFULL_CLEARANCE/B_analyze_all_yaw_rejected.py" --stage-root "${P08_STAGE}" --code-root "${P08_CODE}" --check-existing
```

所有新内容只属于 P-08 B 后处理；旧 seal、主链、Outcome、AGENTS 和交接记录未由本工作修改。后续由主任务整合审查分类草案；本文不放行全量执行。
