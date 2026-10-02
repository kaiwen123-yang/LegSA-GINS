# A2 保留航向时的输入资格与实际辅助更新

已分别读取 A04 `ADD_RUN_00402`、F04 `ADD_RUN_00400`、F03 `ADD_RUN_00399` 完成后的调度小表、回执及少量已有 witness，完整回执均 stream_complete=true。创新窗口与入口窗口的边界差异按文末新增的实际源行链分别保留。case 为 BY2 `D62_20s_seed_00`，原全程66..340 s；与本次A1对象同seed、同anchor **206.2 s**、同注册半开区间 **[196.2,216.2) s**。`data_mode=semisynthetic`，synthetic_data_used=false、semisynthetic_data_used=true；观察值为 replay_observed，不冒充旧创新日志。本小项没有native/evaluator/provider调用、没有重开大events、原provider或旧2308份误差序列。

## 输入层：保留的 yaw 与基础 HV 支持确有身份依据

[INPUT_USES.csv](../../INPUT_USES.csv) 中A2三对象均绑定 `I001` IMU、`I009` GNSS、`I010` RD、`I004` RP、`I005` HV，全部pin状态MATCH。按已全文读取的 [INPUT_FIELD_QUALITY.csv](../../INPUT_FIELD_QUALITY.csv)：

- I009的1,510行中，position_valid/velocity_valid各100行为0，yaw_valid全部1,510行为1。
- I010的1,248行中，provider_status=controlled_outage与valid=0各100行；available/valid=1各1,148行。原行和数值仍在，失效标志不等于缺行或缺值。
- I004 RP全63,278行active。I005 HV沿用与C00同一固定文件，全63,278行active，其中update_flag=true 60,867、false 2,411；valid分布对应。

这不是仅据“A2保留heading”的标签推定可用：[INPUT_LINEAGE.md](../../INPUT_LINEAGE.md) 已登记HV由旧status heading准备，A2的该heading保留，因此HV继承base字节身份。它不改用V3 raw主航向重算HV。输入总行数是provider分母，不是下面100次GNSS机会，也不等于接受次数。

## A04 / F04：各100个中断期GNSS输入保持入口，RP/HV实际各接受100次

分别按 [A04 SCHEDULING](ADD_RUN_00402_SCHEDULING.csv) 与 [F04 SCHEDULING](ADD_RUN_00400_SCHEDULING.csv) 的 `window=during` 查行。以下每个数量在两对象独立记录中一致，仍以每对象100个GNSS输入为分母。position/velocity两位false、yaw位true，OR=true；时间条件与实际GNSS调度各100，整体validity入口阻断0。

|源|时间候选|预创新质量资格|实际helper入口|实际选中|实际接受|原拒绝/不调用原因|
|---|---:|---:|---:|---:|---:|---|
|yaw|100|100|100|100|100|无|
|RP|100|100|100|100|100|无|
|HV|100|100|100|100|100|无|
|RD|100|0|100|100|0|PROVIDER_VALIDITY_LINEAGE_OR_SATELLITE_REJECT=100|
|GNSS position|100|0|0|0|0|has_position=false，原dispatch未调用|
|receiver velocity|100|0|0|0|0|has_velocity=false，原dispatch未调用|

“预创新资格”沿 [analyze_schedule.py](../../analyze_schedule.py) 的实际字段判据：RD须valid/lineage/provider available/sat门均合格；RP须active且两std>0；HV须update_flag、active、允许模式且无truth claim，并均要求原匹配成立。enable与solver_enabled独立于这些条件。这里RP/HV不止有资格，已有真实accepted记录；RD有匹配但资格不符，仍实际进入helper、选中行，然后在provider/validity/lineage/sat组合门返回。其100次拒绝不是没有进入GNSS入口，也不是SA/OIM创新拒绝。

入口开放依赖三valid位的OR，发生在后续yaw创新判别之前；这两个对象本窗yaw也确实各接受100，但不能把“yaw已被接受”误写为入口开放的先决条件。A1的全失效入口条件没有在本A2窗触发，`qualified_but_entry_blocked_events=0`。这说明本批具体路径，不能据此宣称所有中断均不受N09影响。

A04 full 的RD计数另为 **1369 helper入口 = 970接受 + 100 provider组合门拒绝 + 38 SA-off残差门拒绝 + 261无时间匹配**，分母与during100分开。不能把100个受控失效RD行加到接受数，也不能把261无匹配叫作创新拒绝。

F04的独立full记录为 **1369 helper入口 = 1008接受 + 100 provider组合门拒绝 + 261无时间匹配**。这里没有A04的38次SA-off残差门返回；不能把两方法接受数量差直接当作同状态反事实或性能提升。during的受控失效100行在两方法都先由provider门拒绝，未因F04的SA开启而变为有效更新。

## 真实事件键与时间边界

`<MECHANISM_ROOT>/analysis/ADD_RUN_00402/schedule/GNSS_CANDIDATE_FUNNEL.csv` 是已生成的8,220行小派生表；按 `(gnss_input_seq,source)` 查记录。首个during的GNSS_INPUT是event **196883**、seq **651**、time **196.200000048 s**，三位为false/false/true；同时RP/HV已匹配row31924，RD匹配row598但质量资格false。

已保存的小 [SCHEDULE_WITNESSES](ADD_RUN_00402_SCHEDULE_WITNESSES.csv) 对应 JSON 为 `<MECHANISM_ROOT>/analysis/ADD_RUN_00402/schedule/SCHEDULE_WITNESSES.json`：

|JSON key|decision event|attempt|实际row_id|原decision|
|---|---:|---:|---:|---|
|during:dual_antenna_yaw:ACCEPTED|197110|3901|-1（GNSS原行号未传入）|ACCEPTED|
|during:raw_doppler_velocity:PROVIDER_VALIDITY_LINEAGE_OR_SATELLITE_REJECT|197113|3902|598|PROVIDER_VALIDITY_LINEAGE_OR_SATELLITE_REJECT|
|during:go2_horizontal_velocity:ACCEPTED|197120|3903|31924|ACCEPTED|
|during:go2_attitude_roll_pitch:ACCEPTED|197127|3904|31924|ACCEPTED|

F04自己的首个during记录来自 GNSS_INPUT event **196927**、seq651；对应 `<MECHANISM_ROOT>/analysis/ADD_RUN_00400/schedule/SCHEDULE_WITNESSES.json` 的同名四个JSON key（独立读取，不使用A04事件代替）：

|源|decision event|attempt|row_id|decision|
|---|---:|---:|---:|---|
|yaw|197154|3901|-1|ACCEPTED|
|RD|197157|3902|598|PROVIDER_VALIDITY_LINEAGE_OR_SATELLITE_REJECT|
|HV|197164|3903|31924|ACCEPTED|
|RP|197171|3904|31924|ACCEPTED|

这些事件的GNSS/trigger/state time均为196.200000048 s，res=3；前/当前IMU时刻为196.195062 / 196.201064 s。实际row_id是各源已加载vector的zero-based位置；RP和HV数字相同不表示两种观测相同。

A04的边界原记录如下（RP/HV在列出的每行均match=true、quality=true、entry_blocked=false）：

|GNSS seq|GNSS time (s)|GNSS_INPUT event|position/velocity/yaw valid|RP/HV row_id|RD row_id / quality|
|---:|---:|---:|---|---:|---|
|650|196|196613|true/true/true|31888|597 / true|
|651|196.200000048|196883|false/false/true|31924|598 / false|
|750|216|222095|false/false/true|35569|697 / false|
|751|216.200000048|222329|true/true/true|35601|698 / true|
|752|216.400000095|222581|true/true/true|35632|699 / true|

F04自己的 `<MECHANISM_ROOT>/analysis/ADD_RUN_00400/schedule/GNSS_CANDIDATE_FUNNEL.csv` 同五个seq的GNSS_INPUT event依次为 **196657、196927、222139、222373、222625**；各时间、valid位、RP/HV/RD的row_id与质量字段和上表对应。只认这些同字段事实，不宣称两方法滤波状态相同。

在已到时的GNSS机会与原update_flag/容差匹配规则下，A2这些HV边界有实际候选，和A1同边界缺候选分别记录；不扩展为全部20秒任何Go2行/任意异步机会均可接受。196.200000048归during，216.200000048归after，不能先取整再换窗。

调度小表的window按原 **GNSS trigger time**；创新小表可能按 **metadata measurement_time**，IMU机会按 **imu_current_time**。本节decision witness的measurement_time是helper入口时刻，不是所选RP/HV原行的源时间；没有把它改名为provider时刻。不同源的原时间列、RD source_time、真实到达时间互不替代。本版已补A04两条SA派生行与first-after witness的对应，见文末；没有从row_id或上一批A1数值补填。**available_time始终UNKNOWN**。源和入口跨窗口时逐事件另列，不把分窗差异静默当作缺行。

## 两种分母以及末尾一个尚未满足时间条件的输入

[A04 OPPORTUNITIES](ADD_RUN_00402_OPPORTUNITIES.csv) 的during有40个res=2与60个res=3调度机会、3,539个NOT_DUE、39个GNSS_INPUT_NOT_PENDING，共 **3,678个IMU机会**，GNSS_ALL_FLAGS_FALSE为0。它们不是3,678次量测，也不能加到100个GNSS输入中。F04及F03的同窗IMU分组计数分别核对后均对应，但F03的辅助配置不同。

A04 full为1,370 GNSS输入、1,369实际调度；末项seq1370、time340、inputevent406379的三valid全true，RP/HV匹配row61178、RD匹配row1159且质量都合格，但 `time_condition_without_validity=false`、`actual_gnss_scheduled=false`、`qualified_but_entry_blocked=false`。可从同funnel逐source核对。F04独立的末项是同seq1370/time340、inputevent **406531**，三valid、候选row_id和资格/时间/调度标志与此对应。它不是质量拒绝/整体validity阻断；小表没有提供完整读循环终止原因，本笔记不猜终止分支。

F03 during的yaw接受100；RP/HV/RD各有100 helper入口，但全部 **DISABLED_BY_CONFIG**，选中0/接受0、loaded-input存在0、blocked0。这是进入GNSS入口后配置关闭的返回，不是100个合格辅助源受N09阻断。见 [F03 SCHEDULING](ADD_RUN_00399_SCHEDULING.csv)；不能把function_entries叫成100次有效观测更新。

## RP/HV：按源量测时间during各101，按入口时间during各100

已读取公开 [INNOVATION_COMPACT.csv](INNOVATION_COMPACT.csv)：对 A04 `ADD_RUN_00402` 和 F04 `ADD_RUN_00400`，`source=go2_horizontal_velocity|go2_attitude_roll_pitch,fixed_window=during` 的 **SA_events均为101**，其固定窗口按SA metadata measurement_time分类。调度表按GNSS trigger time的during实际接受仍各为100；两种分母及时钟均保留。

A04已逐行绑定的额外两条都来自 **after首个GNSS入口**：seq751、trigger/state time **216.200000048 s**、res=3。所选provider measurement_time为 **216.197080612183 s**，落在during，row_id均为各源vector的35601。

|源|attempt|SA event / sa_seq|源measurement_time (s)|after ACCEPTED decision event|trigger/state time (s)|原events byte offset / line bytes|
|---|---:|---|---:|---:|---:|---|
|HV|4305|222563 / 4091|216.197080612183|222566|216.200000048|463435939 / 10097|
|RP|4306|222570 / 4092|216.197080612183|222573|216.200000048|463473452 / 10218|

SA的精确单行来源为 `<MECHANISM_ROOT>/analysis/ADD_RUN_00402/innovation/SA_EVENT_ANALYSIS.csv`（按event/attempt查）；这些源measurement_time、offset和行长度由根代理已读取核对并传递，本worker未再扫描该大派生事件表或events。accepted链由本worker读取小 `<MECHANISM_ROOT>/analysis/ADD_RUN_00402/schedule/SCHEDULE_WITNESSES.json` 的 `after:go2_horizontal_velocity:ACCEPTED` / `after:go2_attitude_roll_pitch:ACCEPTED` 核实：其attempt、row_id、sa_seq、GNSS/state time分别与表对应。前/当前IMU时刻为216.197081 / 216.203063 s；source time与IMU时间的小数精度原样保留。

因此这里的101不是“中断入口内额外执行一次”，不是漏记调度，也不是把half-open终点改入窗内；它是将 **100个during入口 + 1个after入口选中的during源量测** 按不同时间列归组。两个源分别各多一条，不把它们合成两个额外GNSS入口。真实到达时间仍未知，不能由较早的provider时标直接证明到达顺序或因果支持。

F04公开汇总也支持RP/HV各101，但本笔记未做F04对应两条SA与decision的逐行联结，**不复用A04的event_seq/offset/attempt作为F04证据**。其具体边界单行保持未核查；汇总与100个trigger窗接受次数同时展示。

本版只对已核小表、摘要和上述明确来源的单行链给出事实。任何配置/输入/调度对照都不单独证明辅助信息的独立性、修复后的闭环收益或投稿层面的因果机制。
