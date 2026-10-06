# N09：A1 两对象的实际事件与关联更正

本小项仅覆盖 BY2 `D61_20s_seed_00` 的 A04 `ADD_RUN_00105` 和 F04 `ADD_RUN_00103`。两对象各完整读取既有 observed baseline 与新 `N09_RP_ONLY` 事件流一次，共 **4 次全文读取、2 次缓存比较**；本小项新增 native/evaluator/provider/reference 调用或读取均为0。数据为 `semisynthetic`，synthetic_data_used=false、semisynthetic_data_used=true。所有辅助连接更正只读已完成缓存，未重开事件流。N09 仍是[定义文件](../V3_DEFINITION_DECISIONS.md)限定的可选更新能力扩展；本结果不证明原 V3 违反历史设计要求。

每对象的入口如下。原 `SUMMARY.json` 保留了辅助分析器的80条文本键关联结果；请连同新更正表阅读，不能把80当成实际尝试/接受总数。

|对象|完整原比较摘要|新增100条精确关联|独立调度计数及首状态证据|
|---|---|---|---|
|A04|[SUMMARY](summaries/N09_RP_ONLY__ADD_RUN_00105/SUMMARY.json)|[A1_JOIN_VALIDATION.csv](summaries/N09_RP_ONLY__ADD_RUN_00105/A1_JOIN_VALIDATION.csv)|[COUNTS](summaries/N09_RP_ONLY__ADD_RUN_00105/A1_RP_ONLY_COUNTS.csv)、[DETAILS](summaries/N09_RP_ONLY__ADD_RUN_00105/A1_EVENT_DETAILS.json)|
|F04|[SUMMARY](summaries/N09_RP_ONLY__ADD_RUN_00103/SUMMARY.json)|[A1_JOIN_VALIDATION.csv](summaries/N09_RP_ONLY__ADD_RUN_00103/A1_JOIN_VALIDATION.csv)|[COUNTS](summaries/N09_RP_ONLY__ADD_RUN_00103/A1_RP_ONLY_COUNTS.csv)、[DETAILS](summaries/N09_RP_ONLY__ADD_RUN_00103/A1_EVENT_DETAILS.json)|

## 实际机会、原门与消费次数

固定中断窗为 **[196.2,216.2) s**。下表按 `RP_ONLY` 记录的 `snapshot.gnss_event_time` 分类，每列是一个对象自己的100个 GNSS 输入身份651..750，不是IMU采样分母。`COUNTS`另存固定 before `[66,196.2)`、fault `[196.2,216.2)`、after `[216.2,340]` 的事件/原因计数和原派生表入口。

|中断窗内记录|A04|F04|
|---|---:|---:|
|GNSS三位全失效、RP事前合格的输入|100|100|
|到时 RP_ONLY_OPPORTUNITY|100|100|
|调用原 RP helper 的 ATTEMPT|100|100|
|实际 RESULT=ACCEPTED，且有 EKF_AFTER|100|100|
|实际拒绝|0|0|
|分支后统一反馈|100|100|
|RP_ONLY_BRANCH_COMPLETE 消费|100|100|
|消费身份数 / 每身份消费次数|100 / 1|100 / 1|
|res1 / res2 / res3|0 / 40 / 60|0 / 40 / 60|

事前合格使用原 RP enable+solver、最近时刻/容差/tie 与 active、正的 roll/pitch std 资格，不等于仅配置开启，也不预先保证通过创新门。此处接受100来自独立的真实决策和 EKF_AFTER，而非资格推断。候选仍调用原 RP helper；未把GNSS有效位改真，未在RP-only分支调用position/yaw/RV/RD/HV。

两对象**全运行**各有1,370条登记输入、1,369个唯一已消费身份（每个一次），其中原有效GNSS路径1,269、RP-only100。最后 input_id1370、GNSS time340的登记保持pending=true，没有消费事件；不能把1,370都写成已消费。它对应原调度中未见满足时间条件的最后输入，不猜读循环终止原因。全运行RP原接受1,269→候选1,369，GNSS update count始终1,269。A04的SA active count始终0；F04为7,328→7,428。记录了SA调用不表示SA开关已启用。

全运行position/RV各1,269、yaw尝试1,269且拒绝21、HV接受1,265均保持原计数；RD接受A04为969、F04为1,008，各自候选与基线相同。这些是全运行数量，不冒充中断窗计数。各比较有7,614条原measurement记录配对和100条新增候选measurement。

## 辅助分析器的文本键漏联：保留80，另表闭合100

原缓存的 measurement stable key 可保存整数时间，例如 `[655,"go2_attitude_roll_pitch",197]`；GNSS SQLite REAL 列读出197.0后，原比较构造 `[655,"go2_attitude_roll_pitch",197.0]`。两者数值相同而文本不同，导致各对象有20条真实尝试未关联。遗漏恰为整数秒197..216、GNSS id655、660、…、750。它们不是原门拒绝、不是未调用，也不是原V3运行数据或算法新增故障。

[a1_join_validation.py](a1_join_validation.py)仅支持本次两个A1缓存。它先检查缓存完成/身份/元数据、时间有限和连接键唯一，再按 `(gnss_input_seq, exact source, Decimal time)` **精确数值相等**关联，不设容差、不插值、不按行号。输出保留缓存JSON时间、SQLite时间、原CSV时间、两边原字符串键，以及真实attempt/decision/EKF_AFTER事件的路径、行号、byte offset和长度。每对象100行中80行为原关联确认、20行为 `TEXT_KEY_OMISSION_CORRECTED`；**100次唯一尝试、100次实际接受**。这两张表仅替代原摘要 `original_RP_opportunities` 的连接计数，原摘要、原事件、评价值和冻结分析器均未改。

辅助脚本[本轮合成测试](summaries/N09_RP_ONLY__ADD_RUN_00105/A1_JOIN_VALIDATION_TEST_RECEIPT.json)为1个进程、11项PASS：197/197.0匹配，实际不同数值/不同身份/不同来源不匹配，重复数值键拒绝，UNKNOWN/None/NaN/±Inf/布尔时间拒绝。随后两次实际辅助脚本均exit0，各读取缓存而新增原事件读取0。更正回执：[A04](summaries/N09_RP_ONLY__ADD_RUN_00105/A1_JOIN_VALIDATION_RECEIPT.json)、[F04](summaries/N09_RP_ONLY__ADD_RUN_00103/A1_JOIN_VALIDATION_RECEIPT.json)。

## 与原入口阻断、HV资格的关系

[上一阶段A1输入与调度说明](../../v3_mechanism/groups/A1/INPUT_AND_SCHEDULING_NOTES.md)独立记录两对象：原100个已到时GNSS输入三位均false，RP匹配100、事前合格100、整体入口阻断100，实际helper/接受0。本次精确关联把这些原机会与新增100个实际RP接受连接起来；没有把原来不存在的创新虚构成一次拒绝。

同一原机会集合中，HV载入与enable存在100次，但满足原update_flag/容差的候选和资格均0；RD时间候选100、质量资格0。**HV的0只覆盖这100个已到时GNSS输入按原匹配规则的资格**，不表示整个20秒全部Go2行不存在，也不覆盖另设任意异步机会。A1的HV仍继承旧status-heading准备支持；N09未重建HV。原IMU分窗另有3,646次GNSS_ALL_FLAGS_FALSE与32次NOT_DUE，共3,678次；它们不能加进100个GNSS身份，也不是3,646次独立RP拒绝。F03配置关闭对照没有进入本队列。

## 首次新增更新：四种时间保留原值

两对象第一次新增更新均是 GNSS seq651、IMU seq27388、RP原vector row31924，但其状态和P各自不同。

|字段|实际记录（s）|
|---|---:|
|context.measurement_time / stable-key time|196.200000048|
|GNSS事件time|196.200000048|
|RP原行 selected_input.time|196.201063871384|
|RP更新时IMU插值state.time|196.200000048|
|原IMU previous / current|196.195062 / 196.201064|
|RP匹配绝对时差 / 原容差|0.0010638233840154498 / 0.02|
|实际arrival / available time|UNKNOWN|

这里名为measurement_time的context字段取GNSS事件时刻，不能代替RP原行时间。RP行略晚但满足原对称最近匹配，不证明它在GNSS时刻已真实到达。字段精度不同也不直接给出物理时钟偏差。候选RP原row/source_status=active，std_roll/std_pitch均0.027925268031909273 rad；更新有效R的对角A04为0.000779820594653974、F04为0.001169730891980961 rad²，off-diagonal均0。A04 SA off倍率1；F04原SA在自身状态上给combined倍率1.5。不能把两方法同一时刻NIS视为同状态反事实。

A04新增RP_ONLY_ATTEMPT event225792，实际MEASUREMENT_ATTEMPT225793、SELECTED225794、EKF_BEFORE225797、EKF_AFTER225798、DECISION225799；F04依次225836、225837、225838、225841、225842、225843。`DETAILS`保留每个路径/事件/字节入口及21维 `actual_delta=dx_after-dx_before`，两者dx_before均21个0；以下摘录前三个块，不改原值。

|对象|actual_delta局部位置误差（m）|actual_delta速度误差（m/s）|actual_delta姿态误差（rad）|
|---|---|---|---|
|A04|[-3.584511028090243e-05,-2.4419245471362266e-05,-3.953066356423479e-06]|[-0.0007450005924093757,-0.00016894456902722142,5.856202772445952e-05]|[7.713668114295373e-06,-0.0002735047150780064,2.7336042729149927e-06]|
|F04|[-3.549490323028239e-05,-2.4587242623267634e-05,-3.293123874849999e-06]|[-0.0006365298739208964,-0.00015920562698238665,4.981770801200661e-05]|[4.640051500220575e-06,-0.0002258273848395361,3.1495821114312667e-06]|

基线在新增中间更新时刻没有相应状态，不生成插值基线。首个可比IMU末状态为196.201064：两对象候选/基线传播次数2/1、拆分1/0、反馈1/0；RP_ONLY实际res=3，而原GNSS视角的IMU_OPPORTUNITY.res仍为0，这两个字段不可互换。首次共同末状态的候选−基线速度差A04为 `[0.0007483050444934136,0.00016887855611658065,-5.855974012755616e-05]` m/s，F04为 `[0.0006392740159937293,0.00015907780282120587,-4.982285887283888e-05]` m/s。其完整LLH、rpy、bias、scale等差向量与两侧原状态见各自 `DETAILS#/first_common_IMU_end`；LLH前两维单位rad，不与局部误差位置m混用。

各对象首分叉之前27,387个共同IMU末状态精确相同；剩余29,255保留原分类 `DIFFERENT_OR_UNRESOLVED`，不把分类名整体升级为全部已逐字段解决。上述首个分叉已经有两侧具体状态。拆传播与RP更新同在这个候选分支发生，仅此对照不能分离两者各自的贡献。

## 完整P的诊断范围与数值状态

候选每对象56,642个IMU末完整21×21 P诊断全部是 `NONPOSITIVE_DIAGONAL`；基线仅已有EKF前/后完整P快照，A04为14,578个、F04为14,656个，全部同状态，不能称为基线逐IMU连续覆盖。首异常的441项有限，最小对角0，非正对角索引15..20，对应gyro/acc scale六维。诊断按冻结规则在此停止：未归一化、未做对称门或Cholesky，min_pivot与max_normalized_asymmetry不可用；未加jitter/裁剪，未写回P。零对角不单独证明负特征值或严格不定，也不能凭旧checkCov未终止宣称完整P数值正定。流/公式的 `VALIDATED` 不覆盖这个正定性门。

四个流均完成EOF与同流hash记录：A04基线403,330事件/838,624,200 bytes，候选464,372/935,933,624；F04基线403,486/841,547,644，候选464,528/939,006,643。SA同快照数值检查分别为7,289/7,389及7,328/7,428，均VALIDATED。各自source hash、分析器hash、源路径、读取深度和计数原样摘录在 `DETAILS#/scan_receipts`。这不新增真实性、独立参考或完整数学正确性的结论。

已提交的[同口径A1评价](../evaluation/results/N09_RP_ONLY/A1_README.md)给出这两例全窗H下降而Up上升的混合结果；此处只关联实际调度和首分叉，不再评价，不把接受更多等同更准确，也不将两例外推全部种子、时长或无GNSS报文的异步调度。
