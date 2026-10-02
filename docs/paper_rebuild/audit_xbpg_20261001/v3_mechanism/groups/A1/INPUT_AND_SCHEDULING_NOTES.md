# A1 中断窗的输入资格与调度入口

已完成并读取的对象为 A04 `ADD_RUN_00105` 和 F04 `ADD_RUN_00103`，两份调度回执均 stream_complete=true；F03 `ADD_RUN_00102` 的同批小表作为配置关闭对照。case 为 BY2 `D61_20s_seed_00`，原运行范围 66..340 s，注册中断为 **[196.2,216.2) s**。证据属于 `replay_observed`，`data_mode=semisynthetic`，synthetic_data_used=false、semisynthetic_data_used=true；本笔记仅转录和解释既有小表，没有 native/evaluator/provider 调用，没有重开完整 events、原输入或旧保留误差序列。

## 资格、入口和接受是不同层次

[analyze_schedule.py](../../analyze_schedule.py) 的 `candidate_quality` 明确检查已匹配的行及原质量字段，不是只检查 enable：

|层次/源|实际检查|
|---|---|
|effective_enabled|config_enabled AND solver_enabled；这一项与候选质量分开记录|
|有输入|loaded_rows>0，表示载入列表存在；不是在该 GNSS 时刻出现了新到达数据|
|时间候选|原绝对时差匹配、原容差、等距最后一行；HV 先跳过 update_flag=false 的行|
|RD 预创新资格|match_found，valid、lineage_valid 均真，provider_status=available，sat_count≥原配置阈值|
|RP 预创新资格|match_found，source_status=active，std_roll_rad 和 std_pitch_rad 均>0|
|HV 预创新资格|match_found，update_flag=true、source_status=active、diagnostic_only 或允许的水平控制模式，且无 truth claim|
|仅按时间可触发|对原 GNSS 时刻与前/当前 IMU 计算原 TIME_ALIGN_ERR 分支，暂不使用三 valid 位；按每个 GNSS 输入是否曾满足计一次|
|qualified_but_entry_blocked|effective_enabled AND 预创新合格 AND 仅按时间可触发 AND GNSS 三位 OR=false|
|实际接受|必须另见真实 helper 选择、创新/质量处理及 accepted 事件；前面任一数量都不能代替它|

因此“合格但入口阻断”表示有具备上述字段和时间条件的源在该 GNSS 机会没有进入辅助更新；它不证明绕过入口后必然接受，更不是修改调度后的性能增益。实际真实到达时间无字段，保持 **available_time=UNKNOWN**。

## A04 / F04：各 100 个中断期 GNSS 机会的逐层结果

[A04 SCHEDULING](ADD_RUN_00105_SCHEDULING.csv) 和 [F04 SCHEDULING](ADD_RUN_00103_SCHEDULING.csv) 按 `window=during`、`source` 查行；以下三行在两对象逐字段相同，分别计数而不将两次运行合成一个分母。每对象的分母为 **100 个 GNSS 输入事件**，GNSS time 从196.200000048到216 s。每个的 position/velocity/yaw 三位都为false；仅按时间可触发100，实际 GNSS 调度0，辅助 helper 入口0、接受0。

|源|enable+solver|载入列表存在|时间候选|预创新合格|合格但入口阻断|实际接受|
|---|---:|---:|---:|---:|---:|---:|
|RP|100|100|100|100|100|0|
|HV|100|100|0|0|0|0|
|RD|100|100|100|0|0|0|

RP 是这两个对象中均明确的 **有创新前合格候选而被整体 GNSS validity 入口挡住**。HV 这100个已到时GNSS机会没有满足原 update_flag 与时间容差的候选，不能也写成“100次合格HV被阻断”；这个0不表示整个20秒全部Go2源行不存在，也不覆盖另设的任意异步更新机会。RD 虽有时间匹配行，预创新资格为0；不能把“载入+匹配”说成有效 RD。三源都与 `enable=true` 不等价。

直接输入沿 [INPUT_LINEAGE.md](../../INPUT_LINEAGE.md)、[INPUT_FIELD_QUALITY.csv](../../INPUT_FIELD_QUALITY.csv) 和 [INPUT_USES.csv](../../INPUT_USES.csv)：RP `I004` 是63,278行、source_status全active的同一固定文件；A1 RD `I007` 保留1,248行，100行valid=0、其余1,148有效；A1 HV `I008` 保留63,278行，其中update_flag/valid有效57,024、无效6,254。必需数值字段没有缺失/非有限，因此本处的无效位和支持空隙不是把缺数值当零的证据。以上总行数是provider分母，不能与100个GNSS机会或接受次数相加。

F03 的 during 三辅助源为配置关闭，source_enabled_input_events=0、loaded_input_exists_events=0、qualified_but_entry_blocked_events=0。这说明 F03 是配置负对照，不把它的0接受计为 N09 的合格辅助源触发。

每对象 [OPPORTUNITIES](ADD_RUN_00105_OPPORTUNITIES.csv) 的 during 另有 **3,646 个 IMU 机会为 GNSS_ALL_FLAGS_FALSE、32 个为 NOT_DUE**，都是res=0，共3,678个IMU机会。F04的对应小表也给出同样计数。它们按IMU当前时间分窗，不能将3,646加到100个GNSS输入中，也不能把3,646称为独立RP拒绝次数。

## RP 的确切 witness：原 GNSS 时间与源行时间分开

[ADD_RUN_00105_SCHEDULE_WITNESSES.csv](ADD_RUN_00105_SCHEDULE_WITNESSES.csv) 中 `witness=BLOCKED:go2_attitude_roll_pitch` 指向：

`<MECHANISM_ROOT>/analysis/ADD_RUN_00105/schedule/SCHEDULE_WITNESSES.json#/BLOCKED:go2_attitude_roll_pitch`

该小 JSON 中的 `input` 指向原 GNSS_INPUT event **196883**、gnss_input_seq **651**；其 `event` 是实际 IMU_OPPORTUNITY event **197095**。此处只读取已保存 witness，未重开完整 events.jsonl。

F04 的独立对应入口是 `<MECHANISM_ROOT>/analysis/ADD_RUN_00103/schedule/SCHEDULE_WITNESSES.json#/BLOCKED:go2_attitude_roll_pitch`；GNSS_INPUT event **196927**、IMU_OPPORTUNITY event **197139**、gnss_input_seq651。已读取该小witness：候选同为row31924，以下源行时间、原容差、质量及三valid位一致。相同的是这些入口字段，不据此称两方法全状态相同。

|字段|原记录|
|---|---|
|GNSS/measurement time|196.200000048 s|
|IMU previous/current time|196.195062 / 196.201064 s|
|实际 res / effective_update_time|0 / -1|
|GNSS has_position/has_velocity/has_yaw/OR|false / false / false / false|
|原 RP vector row_id|31924（zero-based，已加载vector）|
|RP selected_input.time|196.201063871384 s|
|原 selected_abs_dt|0.0010638233840154498 s|
|RP 匹配容差|0.02 s|
|RP source_status|active|
|RP std_roll_rad / std_pitch_rad|0.027925268031909273 / 0.027925268031909273 rad|
|RP roll_rad / pitch_rad|0.009115084074437618 / -0.006962357088923454 rad|
|config_enabled / solver_enabled / match_found|true / true / true|

该 RP 行比 GNSS 量测时刻略晚，但落在原绝对时差容差内；原 helper 是最近时刻匹配，**这不是此行在 GNSS 时刻已经真实到达的证明**。IMU 的六位小数时刻与 RP 更长的小数时刻也不是两个独立时钟偏差的估计。源行与 GNSS 输入的时间列按各自原值保存，不取整合并，不用 source_time 替换 time。

## HV 窗口边界：窗内没有可匹配候选，入口恢复后也不能马上断言 HV 恢复

小型派生表 `<MECHANISM_ROOT>/analysis/ADD_RUN_00105/schedule/GNSS_CANDIDATE_FUNNEL.csv`（8,220行；由根代理已完成的事件解析产生）可按 `(gnss_input_seq,source=go2_horizontal_velocity)` 打开以下原行：

|GNSS seq|GNSS time (s)|source_event_seq|HV selected_loaded_row_id|time_matched / qualified|GNSS OR / scheduled|
|---:|---:|---:|---:|---|---|
|650|196|196613|31887|true / true|true / true|
|651|196.200000048|196883|-1|false / false|false / false|
|750|216|218870|-1|false / false|false / false|
|751|216.200000048|219069|-1|false / false|true / true|
|752|216.400000095|219312|-1|false / false|true / true|

在这100个已到时GNSS输入的原匹配规则下，seq651..750 全部无HV候选，不存在应当另算的同规则窗内合格边界行；不扩展为任意Go2行或异步机会均无候选。216.200000048 已按半开窗归入 after；GNSS三位恢复和入口开放是其实际记录，但 seq751/752 的 HV 候选仍不存在。本版只确认这些已核边界行，不推定首个恢复 HV 候选的更晚时刻，也不把 after 当作已经测得的恢复时间。

F04 在同五个seq的候选/资格/OR/调度字段及row_id完全对应；其 source_event_seq 依次是 **196657、196927、218914、219113、219360**。可从 `<MECHANISM_ROOT>/analysis/ADD_RUN_00103/schedule/GNSS_CANDIDATE_FUNNEL.csv` 同键打开，未用A04替代F04证据。

源生成语义解释了为何两种支持不能混同：A1 HV 是使用故障后的**旧status heading**准备的，不是用 V3 raw 主航向重新旋转；准备流程按固定base_time转相对时间、毫秒关联、unwrap后线性插值，并在gap>1.2s时去掉内部开区间，最终 update_flag 是 Go2 源有效与准备航向有效的合取。原 GNSS 主航向的时间格、RP/IMU时间格、HV准备支持各自保留。生成语义与此处已观察的候选状态相容，但不构成重新执行生成器或重新验证物理同步。

口径提醒：SCHEDULING 的 during 按 **GNSS input time** 分类；OPPORTUNITIES 的窗口按 **IMU current time** 分类。这里100个输入机会不是IMU机会数，也不是100次辅助创新拒绝。中断时没有进入helper，因而无该时刻的RP/HV/RD创新、SA判别或EKF更新；不能用不存在的残差归因拒绝。

## 余下一个GNSS输入：字段合格，但没有观察到满足时间条件的调度机会

A04/F04 的 full 各为 **1,370 GNSS输入 = 1,269 实际调度 + 100 中断时整体validity阻断 + 1 未满足时间触发条件**。最后一项可从各自 GNSS_CANDIDATE_FUNNEL 按 `gnss_input_seq=1370,source=go2_attitude_roll_pitch` 找到：

|对象|原GNSS_INPUT event|GNSS time|RP row_id|match / quality|三valid与OR|time_condition_without_validity|actual_gnss_scheduled|qualified_but_entry_blocked|
|---|---:|---:|---:|---|---|---|---|---|
|A04|403095|340 s|61178|true / true|全true|false|false|false|
|F04|403251|340 s|61178|true / true|全true|false|false|false|

因此 after 的RP **620 个质量合格候选、619个时间条件、619次实际接受** 是闭合的，不是1条质量拒绝或漏记接受。这里能直接确认的是保存的运行机会内时间条件未成立；小表没有给出完整读循环终止原因，本笔记不猜是哪个终止分支或最后IMU采样造成。它不属于全失效入口阻断，不能把它加入100，也不能因质量合格直接填accepted=620。

## 一个RP事件的两种时间分窗：恢复入口after，源量测时间during

A04 首个恢复的RP实际更新来自同一条已保存记录：

- 调度 witness：`<MECHANISM_ROOT>/analysis/ADD_RUN_00105/schedule/SCHEDULE_WITNESSES.json#/after:go2_attitude_roll_pitch:ACCEPTED`。decision event **219304**、attempt **3906**、trigger/state time **216.200000048 s**，selected row **35601**；本worker实际读取该小witness。
- 原SA派生行：`<MECHANISM_ROOT>/analysis/ADD_RUN_00105/innovation/SA_EVENT_ANALYSIS.csv`，event **219301**、attempt3906、sa_seq **3790**，source/measurement time **216.197080612183 s**，原events byte offset **450633246**、line bytes **10207**。此单行由根代理已读取核对并传递；本worker没有再次扫描SA事件文件或原大日志。

前一个时间在after，后一个在during，二者属于同一次首个恢复更新。故创新小表按metadata.measurement_time分窗可出现 **1次RP during**，同时调度小表按GNSS trigger time的during仍是 **0次RP更新**，并不矛盾。不能把该1次称为中断入口关闭期间发生更新；也不能为了表面对齐把源时间改成入口时间。此具体一条只在A04取得单行对应，不在未做同条关联的F04上预填相同细节。arrival依然UNKNOWN。

结论只覆盖已核的A1 20s seed_00三方法及上述限定分母，不外推全部A1种子、时长或关闭入口后的性能。
