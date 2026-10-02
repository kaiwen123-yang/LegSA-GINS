# D15：输入、调度入口与既有拒绝门

范围为 BY2 `D15_seed_00` 的 A04 `RUN_01403` 与 F04 `RUN_01401`，原运行全窗 `[66,340] s`。本说明只读取已生成的输入资格表、调度派生表及小型 witness JSON；所有事件值均为 `replay_observed`，`available_time=UNKNOWN`。`data_mode=semisynthetic`、`synthetic_data_used=false`、`semisynthetic_data_used=true`。本说明整理新增 native/evaluator 调用均为 0，不将这两个对象由主管记录的 4 次真实重放计作 0 次。

D15 在全序列 GNSS 位置注入 N/E 各 σ=3 m、Up σ=5 m 的高斯噪声；std/status 和其余通道继承原输入。它没有 A1/A2 的局部中断窗，anchor 不能解释为局部噪声边界。来源为 [INPUT_LINEAGE.md](../../INPUT_LINEAGE.md) 的 D15 生成链说明及 [DIAGNOSTIC_QUEUE.csv](../../DIAGNOSTIC_QUEUE.csv) 的两个 `run_id` 行。本次不重新读取 provider 正文或执行生成器。

两对象在 [INPUT_USES.csv](../../INPUT_USES.csv) 对应相同五份直接输入：I001 IMU、I011 GNSS、I003 RD、I004 RP、I005 HV，10 个引用的已有 hash 状态均为 `MATCH`。GNSS 实际位置为 `<PROTOCOL_V3_SCRATCH>/02_PROVIDERS/CASES/BY2__D15_seed_00__18a349c6d122820244c40bcf78ff92b9221060ceb5a04b1c115b2194402e343c/GNSS18.gnss`；其完整 1,510 行的三个 valid 字段各有 1,510 个 `1`，见 [INPUT_FIELD_QUALITY.csv](../../INPUT_FIELD_QUALITY.csv)，键为 `input_id=I011,field=position_valid/velocity_valid/yaw_valid`。A04/F04 的辅助源开关均开启，Source-Aware 总开关分别关闭/开启，见 [INPUT_ECHO_CHECKS.csv](../../INPUT_ECHO_CHECKS.csv)。

**入口与分母。** 两对象各有 1,370 个 GNSS input 事件，实际 position/velocity/yaw 三位及 OR 均为真；各有 1,369 次实际 GNSS 调度。所有源的 `qualified_but_entry_blocked_events=0`，没有 N09 所指“合格辅助量测因 GNSS 整体有效位入口被阻断”的事件。该结论由实际 flags 和调度链支持，并非仅由 enable 推出。

完整派生入口表为 `<MECHANISM_ROOT>/analysis/RUN_01403/schedule/GNSS_CANDIDATE_FUNNEL.csv` 与 `RUN_01401` 同路径，各 8,220 行（1,370 输入 × 6 源），本说明已实际读取。末项 `gnss_input_seq=1370,time=340` 三位仍为真，但 `time_condition_without_validity=false`、`actual_gnss_scheduled=false`；原 GNSS_INPUT 事件号分别为 402571/408323。故 1,370 与 1,369 的差不是有效位阻断。这里只记录时机条件未成立，不另猜终止原因。

各有 56,642 次 IMU 调度机会：`res=2` 已调度 595 次、`res=3` 已调度 774 次、`NOT_DUE` 54,687 次、`GNSS_INPUT_NOT_PENDING` 586 次。IMU 机会、GNSS input 和更新函数入口各为不同分母。来源为 [A04 OPPORTUNITIES](RUN_01403_OPPORTUNITIES.csv) 与 [F04 OPPORTUNITIES](RUN_01401_OPPORTUNITIES.csv)。

|全窗实际量|A04 RUN_01403|F04 RUN_01401|
|---|---:|---:|
|yaw 函数入口 / 已选量测|1,369 / 1,369|1,369 / 1,369|
|yaw 接受|957|1,346|
|yaw 组合门拒绝 `YAW_HARD_STD_OR_RESIDUAL_GATE`|412|23|
|RD 函数入口 / 已选量测|1,369 / 1,108|1,369 / 1,108|
|RD 接受|59|1,108|
|RD `RAW_DOPPLER_RESIDUAL_GATE_SA_OFF` 拒绝|1,049|0|
|RD `NO_TIME_MATCH`，未选中量测|261|261|
|position / RV / RP / HV 各自接受|各 1,369|各 1,369|

来源为 [A04 SCHEDULING](RUN_01403_SCHEDULING.csv) 与 [F04 SCHEDULING](RUN_01401_SCHEDULING.csv)，行键 `window=full,source=<对应源>`；两个 [A04 receipt](RUN_01403_SCHEDULE_RECEIPT.json)、[F04 receipt](RUN_01401_SCHEDULE_RECEIPT.json) 均记录 `stream_complete=true`。RD 闭合关系为 A04 `59+1049+261=1369`、F04 `1108+261=1369`。RD 的 1,109 个输入级合格候选与实际选中 1,108 也使用不同分母，不能把末项未调度输入算作一次残差拒绝。这里的质量资格是创新前资格，不等于接受，更不等于真值准确。

**首个拒绝 witness 能说明到哪一步。** 以下都来自已保存的小型 `<MECHANISM_ROOT>/analysis/<run_id>/schedule/SCHEDULE_WITNESSES.json`，公开入口为 [A04 witness 索引](RUN_01403_SCHEDULE_WITNESSES.csv) 与 [F04 witness 索引](RUN_01401_SCHEDULE_WITNESSES.csv)。

|对象 / JSON 顶层键|decision event / attempt|GNSS 时间 s|state 时间 s / res|实际保存的拒绝原因|
|---|---|---:|---|---|
|A04 / `full:dual_antenna_yaw:YAW_HARD_STD_OR_RESIDUAL_GATE`|1734 / 32|67.200000048|67.200000048 / 3|`YAW_HARD_STD_OR_RESIDUAL_GATE`|
|F04 / 同上键|302154 / 6110|269.799999952|269.799529 / 2|`YAW_HARD_STD_OR_RESIDUAL_GATE`|
|A04 / `full:raw_doppler_velocity:RAW_DOPPLER_RESIDUAL_GATE_SA_OFF`|899 / 16|66.599999905|66.599999905 / 3|`RAW_DOPPLER_RESIDUAL_GATE_SA_OFF`；RD row_id=53|

两份 yaw witness 的 `event.data.snapshot` 只有 `accepted=false` 和组合 `reason`，另有 context 与 attempt 键；没有该事件的 yaw std、wrap 后残差或各门限值。receipt 虽统计了 `YAW_GATE_INPUT` 事件数量，但当前小 JSON 没有保存这些输入值。本次没有打开大 event 流补取，所以连这两个首例也不能拆成 std 拒绝或 residual 拒绝，更不能把整段 412/23 次归到单一子门。`sa_seq=0` 仅说明这些拒绝在相应 SA 评价前返回。RD 首例证实 A04 选到 row 53 后命中 SA-off 残差门；全部 1,049 次的计数仍来自完整派生表，不能由一个 witness 替代。

F04 本组未命中 RD 的 SA-off 残差门，与其实际 SA 开关开启及已选 1,108 次均接受的调度记录一致；261 次无时间匹配仍保留。接受更多只描述实际更新路径，不证明更准确，也不证明这一个门解释全部性能差异。A04 与 F04 经历不同的状态和更新历史，同一 GNSS 时刻也不能把两者 NIS 当作同状态反事实。本说明不使用创新分析结果，不重算 RMSE，不作修正后闭环效果结论。
