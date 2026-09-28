# H-EXT-02 执行记录

状态：`HARD_STOP_EVALUATOR_CONSISTENCY`，完整 H-EXT-02 任务未完成。预注册提交冻结了 D1–D6、适配、评估、聚合与绘图代码。授权来源：`H-EXT-02 prompt 2026-09-16`。只新增外部对比行，协议 v2.1 保持冻结。

## 冻结前验证

起点 `736862d5df4403c9b7fd0946e5fe11b746340b6c`，分支 `stage/clean3-math-repair`。三序列 D4 检查全部通过。每序列 22 文件进行 size/metadata 检查，其中 21 个非 trace 文件进行 SHA-256 检查；trace 内容只在后续评估器子进程唯一读取句柄内核验。

测试：78 passed，0 failed。两个冻结文件 `ext05_pavlasek.py`、`phase5_runner.py` 的 git diff 为空。只读代码复核通过。

新增 H02 路径、FILE_START、文献参数的 BY2 身份复验：

| 方法 | SHA-256 | 原文件逐字节 |
| --- | --- | --- |
| LC01 | ccd25c2e1309ba2870e57e2208f476a6b48eaba69f0d038f26be2f168bb2c695 | PASS |
| EXT05C | 915192d6fcefaf7bef33c4028b571d1b723f7e0759063e2955aebd3d1ee7ace8 | PASS |

身份复验 2 native / 0 evaluator / 0 trace，单列验证预算，不入比较表。比较运行预算 14 native / 28 evaluator；实际 14 native 全部完成，17 evaluator 已调用，其中 16 通过、1 失败；11 次未调用。原 28 图及 pinned RENDER_MANIFEST 已逐文件建立前置哈希快照。

## 预注册定义

D1 按原始相邻 IMU dt 判定，整个无效区间不传播；GNSS 更新保持原始事件时刻；无效端点样本不成为保持样本；下一有效原始区间使用自身 dt 及最后保留的前一有效样本，之后恢复原方法的前一样本保持方式。无插值、无协方差膨胀。D2 FILE_START 主行；BY2H CONTRACT_START 为诊断；静态失败时按合约替换槽位。全部数值参数与选择规则见授权合约。

输出根 `<CLEAN_ROOT>/stages/CLEAN7_HEXT_EXTERNAL_SEQUENCES/`，ext4 暂存 `<HEXT_SCRATCH>/H_EXT_02/`。原始路径统一经 local YAML 和序列 registry 解析。

## 簿记裁定

1. 22 文件身份检查与 trace 仅评估器读取规则并存：21 payload SHA + 1 trace declared SHA/size，后者由评估器 capture 校验，绝不称为预运行完成了 22 payload SHA。
2. 必需的 BY2 身份复验 2 次单列于 14 条新比较行之外；零评估、不入性能表。
3. 静态失败在 native 前分类，CONTRACT_START 替换槽位；BY2H 已有诊断槽位去重，不超预算。
4. P-07 无对应 v2 横向表；BY2 v2 文献行复用已 pin 的 CLEAN5 parity 冻结标量汇总，保留真实来源，不重新评估。
5. 原测试要求审计文件必定 dirty，已改为显式 clean/dirty 两状态测试；未触碰冻结运行实现。
6. 冻结 v2.1 A04/F04 全速 NAV 已不在保留目录；09 项整项 UNAVAILABLE，不用 NAV_10HZ 或 P06 替代。内部体坐标偏差缺少全速证据时同样保留 UNAVAILABLE。
7. ZIP 内含 commit 2 与 commit 2 内含最终 ZIP SHA 会形成自引用。结果提交登记最终 receipt 路径；提交后打包并嵌入两个 commit hash，外部 receipt 记录真实 ZIP SHA、字节数、成员 SHA 与 CRC。包哈希不伪写进自身提交。

## 执行终态与硬停

科学代码冻结提交：`c9e5133d244e0e3ab1e1385f322fbbf5948ee6d5`，已 push。37 个冻结文件在执行、停止后均保持一致；结果提交只含文档及簿记代码。

| 项目 | 实际 |
| --- | --- |
| 预注册身份复验 | 2 native，0 evaluator，0 trace |
| 比较 native | 14/14 COMPLETED、已归档 |
| evaluator | 17/28 attempted：16 PASS、1 FAILED_EVALUATOR_CONSISTENCY、11 NOT_RUN_HARD_STOP |
| native trace/bag/fpl | 14 次均 0 |
| evaluator trace | 17 次均为评估器子进程内恰好 1 次；BY2=4、BY2H=13、BY2O=0 |
| evaluator 标准差参数 | 17 次均省略 --std |
| scientific retry / 参数修改 / gate 放宽 | 0 / 0 / 0 |
| 完整 v3/v2 主表、差值与遮挡分段表 | NOT_PRODUCED_HARD_STOP |
| FIG02S / QA | NOT_RUN_HARD_STOP；没有创建 FIG02S 或 HEXT_RENDER_MANIFEST |
| 原 28 图及 RENDER_MANIFEST | 前后逐文件哈希相同 |
| 09 LegSA gap 诊断 | 四项均 UNAVAILABLE：完整冻结 NAV 不在盘 |

失败调用为 `BY2H__EXT05C-S__FILE_START / v3`。评估器本体 exit=0；trace SHA、唯一读取句柄、进程及列身份均正确；capture.consistency.passed=false：

| consistency 项 | 实际 | 阈值 |
| --- | --- | --- |
| horizontal_max_m | 3.0600994997077376e17 | 0.01 m |
| up_max_m | 5.487427392938392e17 | 0.01 m |
| yaw_max_deg | 1.003047600534046e-08 | 0.01 deg |
| matched_epoch_count | 59934 | 失败调用诊断，非正式 coverage |

失败调用的 RMSE、偏差及 coverage 不准入正式结果。没有用 exit=0 覆盖 wrapper 失败，也没有重试、搜索参数、放宽门限或继续 BY2O 评估。已通过的 16 次评估只是部分证据。

BY2 已通过的 LC01-S v3 yaw RMSE=`1.5392385536245534°`，冻结 LC01=`2.9948274600591076°`，因此预注册选择规则指向 S；尚不构成完成的三序列对比。

## 证据路径与完整性

`S=<CLEAN_ROOT>/stages/CLEAN7_HEXT_EXTERNAL_SEQUENCES/`。

- `S/03_PREREG/CODE_FREEZE.json`：合约、37 文件冻结与新 H02 身份门；包含身份复验的完整缓存/native 输出。
- `S/04_NATIVE_RUNS/`、`S/04_ACCESS_AUDITS/`、`S/05_GEOMETRIC_AUDIT/`：14 native、访问记录与几何状态。
- `S/06_V3_NAV_INPUTS/`、`S/07_OFFLINE_EVALUATION/`：已调用的全部输入及通过/失败评估器输出。
- `S/99_HARD_STOP/STOP_REPORT.json`：硬停状态、预算、哈希及冻结保护结果。
- `S/99_HARD_STOP/EVALUATION_LEDGER.csv`：完整 28 槽状态；没有补造未执行结果。
- `S/99_HARD_STOP/GAP_EVENTS.csv`：56 条原生 gap 记录；只合并既有日志，不重算状态。
- `S/99_HARD_STOP/GEOMETRIC_AUDIT.csv`：14 行原生审计。BY2H 双接收机四行均因水平基线 ≤0.1 m 前置条件失败，median/P95 不可得，原始 UNAVAILABLE/error 保留；属于 D6 几何审计失败，不是指标零值。
- `S/09_LEGSA_GAP_DIAGNOSTIC/`：完整 NAV 缺失的四项、16 个 gap 子项，保留路径；NAV_10HZ 不替代。

原 `RENDER_MANIFEST.json` SHA-256：`800df76ad82b68e3fca7aded30081f6d1ad01241175978baf440c9e0f290dd4e`，前后相同。所有 raw 检查点保持 21 非 trace payload 哈希 + 1 trace 声明哈希/size 的诚实口径；BY2O trace 本次没有评估器读取验证。

## 执行后簿记附录

8. 缓存 BY2 进程 exit=0、native=0、evaluator=0；一次 `git status` 自动刷新工作树 index.lock，严格写入范围审计为 false。原记录与 `HARD_STOP_NATIVE.json` 保留，另写 `BOOKKEEPING_CACHE_ADJUDICATION.json`。之后环境设置 `GIT_OPTIONAL_LOCKS=0`，核验并复用缓存，不修改科学代码、不重跑缓存；后续 14 个 native 访问审计均通过。
9. 几何审计前置失败属于 D6。曾准备只改状态/notes、保留数值 token 的簿记脚本；评估器硬停发生后该脚本未执行，完整聚合也未执行。失败审计原文保留于 99 表。
10. 完整任务打包脚本已准备但未执行。使用独立硬停打包脚本，只封存既有部分证据，包内 `HARD_STOP_MANIFEST.json` 与外部 receipt 均显式标记 `NOT_FULL_TASK_DELIVERY`；包完整性通过不代表科学任务完成。
11. 停止后的操作限于既有输出归档、原始文件/冻结文件哈希复核、缺失 NAV 只读登记、文档及交接包；未再调用 native、评估器、完整聚合或绘图。

## 两次提交与部分证据包

预注册提交为上述 `c9e5133d244e0e3ab1e1385f322fbbf5948ee6d5`；结果提交为本记录所在提交，完整两次 commit hash 会嵌入 ZIP 的 `GIT_COMMITS.json`。

包路径：`<HANDOFF_ROOT>/hext_three_sequences_handoff.zip`；其状态限定为 `HARD_STOP_PARTIAL_EVIDENCE`。真实 SHA-256、字节数、逐成员 SHA、CRC 和两次提交见提交后生成的 `<HANDOFF_ROOT>/hext_three_sequences_handoff.validation.json`，简要副本 `S/FINAL_HANDOFF_RECEIPT.json`。采用先 ext4 构建、再 G: 独占复制和回读校验；仅 ENOMEM/EIO 归档复制最多重试三次。

恢复失败评估、继续剩余 11 次调用或改变冻结实现需要新的人工授权；本任务不自动继续。
