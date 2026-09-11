# P-09c Canonical-541 protocol v2：首批停止记录

终态：`STOPPED_GATE_FAILURE`。首批仅完成 33/256 个求解终态；序列一致性门 `FAIL` 后停止，现场保留。没有重试科学 run、补填字段后重判或自动重生成。

## 冻结与前置门

- 首份预注册提交：`56ae6021fd7fe8a88b250e1d5169fca26293340b`。
- v1 对照源 pin 的预注册补充提交：`fcf3558fde97d2b97b06ca3da6eae741f0039880`。
- 合约 SHA-256：`15ba185d4ad274fbda29a1292dda7ecf1ba2b2b9608e353166b40b27c460e7a8`。
- 执行代码：`b26569185638fabdd2ad121fc25cf784d5a8fdb3`；检查 `225 passed, 2 skipped`。跳过项不替代实际运行门。
- 求解器：`9c00565c45b654453b2b378f3d5995e5dc21d1271323a9b683acdab75993235f`；评估器：`aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da`，均未修改。
- P-09ab C1–D PASS；任务开始 live G 可用 `597126021120` bytes，ext4 可用 `945011499008` bytes；前置容量门 PASS。
- 前置 raw hash 检查点 `22/22 PASS`；首批 provider 任务 `24/24 PASS`；求解器 open 审计 `33/33 PASS`。后置 raw 检查点 `NOT_EXECUTED`。

## Run 终态和停止原因

| 范围 | COMPLETED | FAILED_TECHNICAL | ALGORITHM_FAILURE_ALL_YAW_REJECTED | NOT_STARTED |
|---|---:|---:|---:|---:|
| BY2 C00，11 配置 | 11 | 0 | 0 | 0 |
| BY2H 一致性组，11 配置 | 0 | 11 | 0 | 0 |
| BY2O 一致性组，11 配置 | 0 | 11 | 0 | 0 |
| BY2 D01–D60，540 × 11 | 0 | 0 | NOT_EXECUTED | 5940 |

已启动 33 个 native solver，exit_code 全部为 0。BY2H/BY2O 共 22 个外层 run 在 `clean5_degradation.runtime.validate_identity` 读取 `config['runtime_role']` 时产生 `KeyError: 'runtime_role'`，终态保留为 `FAILED_TECHNICAL`；对应模板没有该键，未执行后续外层 counter 校验。

- P-07 CAL C00：11 × 7 = `77/77` hash equal。
- P-06 CAL：15 × 7 = `105/105` hash equal。
- 合计：`182/182` hash equal；零 hash mismatch。因 22 个外层技术失败，`all_33_completed_same_freeze=false`，序列一致性门仍为 `FAIL`。
- 首批剩余 223 个求解未启动；其余批次未启动；评估 0、归档 0、清理文件 0、科学重试 0。
- 全部 5973 个注册身份按族 × 配置计数：[P09C_RUN_TERMINALS_BY_FAMILY_CONFIG.csv](clean6/P09C_RUN_TERMINALS_BY_FAMILY_CONFIG.csv)。已启动 run 逐行计时/字节：[P09C_ATTEMPTED_RUNS.csv](clean6/P09C_ATTEMPTED_RUNS.csv)。全航向拒绝按族：[P09C_ALL_YAW_REJECTED_BY_FAMILY.csv](clean6/P09C_ALL_YAW_REJECTED_BY_FAMILY.csv)；未启动族留空并标 `NOT_EXECUTED`。

## C00 anchors

| 配置 | P-07 CAL C00 七文件 | 外层终态 | v3/v2 指标 |
|---|---|---|---|
| F01 | 7/7 hash equal | COMPLETED | UNAVAILABLE_NOT_EVALUATED |
| F02 | 7/7 hash equal | COMPLETED | UNAVAILABLE_NOT_EVALUATED |
| F03 | 7/7 hash equal | COMPLETED | UNAVAILABLE_NOT_EVALUATED |
| F04 | 7/7 hash equal | COMPLETED | UNAVAILABLE_NOT_EVALUATED |
| A03 | 7/7 hash equal | COMPLETED | UNAVAILABLE_NOT_EVALUATED |
| A04 | 7/7 hash equal | COMPLETED | UNAVAILABLE_NOT_EVALUATED |
| A05 | 7/7 hash equal | COMPLETED | UNAVAILABLE_NOT_EVALUATED |
| A06 | 7/7 hash equal | COMPLETED | UNAVAILABLE_NOT_EVALUATED |
| A07 | 7/7 hash equal | COMPLETED | UNAVAILABLE_NOT_EVALUATED |
| A08 | 7/7 hash equal | COMPLETED | UNAVAILABLE_NOT_EVALUATED |
| A09 | 7/7 hash equal | COMPLETED | UNAVAILABLE_NOT_EVALUATED |

## 关键配对（AGENTS §7A 的中位差 / CI / 胜率字段）

两个评估版本均未调用。下表没有从 v1 或 P-07 替代指标；完整逐版本、逐指标行见 [P09C_KEY_PAIRWISE_SUMMARY.csv](clean6/P09C_KEY_PAIRWISE_SUMMARY.csv)。

| 配对 | 指标 | 中位差 | 95% CI | 胜率 | 状态 |
|---|---|---|---|---|---|
| full_vs_strong | H / yaw / yaw P95 / Up / 3D | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_EVALUATED |
| strong_vs_basic | H / yaw / yaw P95 / Up / 3D | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_EVALUATED |
| basic_vs_single | H / yaw / yaw P95 / Up / 3D | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_EVALUATED |
| full_vs_no_RD | H / yaw / yaw P95 / Up / 3D | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_EVALUATED |
| full_vs_no_SA | H / yaw / yaw P95 / Up / 3D | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_EVALUATED |
| full_vs_no_RP | H / yaw / yaw P95 / Up / 3D | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_EVALUATED |
| full_vs_no_HV | H / yaw / yaw P95 / Up / 3D | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_EVALUATED |
| full_vs_no_Go2 | H / yaw / yaw P95 / Up / 3D | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_EVALUATED |
| RD_only_vs_strong | H / yaw / yaw P95 / Up / 3D | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_EVALUATED |
| SA_only_vs_strong | H / yaw / yaw P95 / Up / 3D | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_EVALUATED |
| A04_vs_F03 | H / yaw / yaw P95 / Up / 3D | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_EVALUATED |
| A04_vs_F02 | H / yaw / yaw P95 / Up / 3D | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_EVALUATED |
| F04_vs_F02 | H / yaw / yaw P95 / Up / 3D | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_EVALUATED |
| F04_vs_F01 | H / yaw / yaw P95 / Up / 3D | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_EVALUATED |
| A04_vs_F01 | H / yaw / yaw P95 / Up / 3D | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | NOT_EVALUATED |


v1↔v2 维持/翻转清单：`UNAVAILABLE_NOT_EVALUATED`，不是零翻转结论。登记表：[P09C_V1_V2_PAIRWISE_COMPARISON.csv](clean6/P09C_V1_V2_PAIRWISE_COMPARISON.csv)。

## 实测（停止前 33-run 前缀）

这些数值不构成完整 256-run 首批实测，不用于全量外推或第 2 批并发判定。

| 项目 | 实测值 |
|---|---:|
| nproc / affinity CPUs | 24 |
| 首批开始可用内存 bytes | 23980089344 |
| MemTotal bytes | 25197424640 |
| 采样 CPU 利用率 | 34.650302846% |
| 采样内存峰值 bytes | 14060580864 |
| 内存峰值 / MemTotal | 55.801658562% |
| 执行前缀总墙钟 s（freeze → STOP） | 68.495169 |
| 首批前缀墙钟 s | 63.59407629799989 |
| 单 solver 时长 min / mean / median / max s | 7.363290665000022 / 9.434318625606073 / 9.617725538000059 / 14.245861545000025 |
| 单 run solver 文件字节 min / mean / median / max | 70152149 / 81349358.36363636 / 74721109 / 101459526 |
| 33 run solver 文件字节合计 | 2684528826 |
| scratch 文件系统占用增长峰值 bytes | 2686046208 |
| G 文件系统占用增长峰值 bytes | 154664960 |
| 保留现场逻辑字节（scratch / G，记录写入前快照） | 2684616392 / 122366285 |

每 2 s 采样；CPU/内存为可见主机范围，文件系统 free-space 差可能包含同期活动。`64 workers` 为池上限，一致性屏障仅发出 33 个 solver，不将此前缀称为完整 64 并发/256-run 试运行。

全量时长外推、全量峰值外推、完整首批墙钟、归档后单 run 大小：`UNAVAILABLE_PILOT_NOT_COMPLETED`。第 2 批 64/128 判定：`NOT_REACHED`。

## 现场、交接与 Git

- `<CANONICAL541_V2_ROOT> = <CLEAN_ROOT>/stages/CLEAN6_BY2_CANONICAL_541_PROTOCOL_V2`。
- `<CANONICAL541_V2_SCRATCH>`：ignored local config 的 `canonical541_v2_scratch`；33 个完整原生输出及 seal 均保留于 `BATCH_001/03_RUNS/`。
- stage 的 `STOPPED.json`、`SEQUENCE_CONSISTENCY_GATE.json`、`BATCH_LEDGER.jsonl`、`BATCHES/BATCH_001/SOLVER_GROUP_0.json`、`RESOURCE_SAMPLES.jsonl` 和 `99_STOP_REPORT/` 保留。
- 原生首次启动前，另有相对合约路径校验失败：`clean6-c541-v2-batch01.service`；发生在 stage/scratch 创建前，provider/solver 均为 0。改为绝对参数后，仍使用同一代码 freeze；两条 service journal 均归档于 `99_STOP_REPORT/`。
- 实际执行 service：`clean6-c541-v2-batch01-absolute.service`，`failed/failed`、`MainPID=0`、`ExecMainStatus=1`；所有 worker 已退出。
- 聚合与 v3 handoff 打包代码已提交，但未执行。`~/c541_v2_handoff.zip`：`NOT_PRODUCED`，SHA-256：`UNAVAILABLE`。
- 主稿协议 v2 是本次预注册选择；数值切换未执行。v1 作为原预注册记录保留；主链 v1、Outcome 与决定规则字节不变。
- 本停止记录提交：本文件所属 Git commit；不把执行代码 freeze 改写为记录提交。

## 证据 SHA-256

| 文件（相对新 stage） | SHA-256 |
|---|---|
| `STOPPED.json` | `02a258dcc1a3579ca831b23bcf100f21857758ec3aa224f7516872bd14c7ef2f` |
| `SEQUENCE_CONSISTENCY_GATE.json` | `b9ba635ce4284d1a2687a896fc45c121179fa80b12131eacfa6966a4dd340100` |
| `BATCHES/BATCH_001/SOLVER_GROUP_0.json` | `0fc8898732050cc8a63e57dfb51b3f6eee1f8f6daba313042fee0be54e1c3aa5` |
| `BATCHES/BATCH_001/RESOURCE_SAMPLES.jsonl` | `475f14d9f74064ee51f6db4c7e9d069001b227ca436c178d1d0bfe8a472e576c` |
| `00_PREREGISTRATION/EXECUTION_FREEZE.json` | `9464557fbe7d1df28f230c2c5e4d770ceea868b67fcf171f923b08dee4651718` |
| `99_STOP_REPORT/STOP_REPORT.json` | `bcc09ae2160633e6a32ddf6d8dd6d712529e77eae65b2ecd7877703614efc2f6` |
