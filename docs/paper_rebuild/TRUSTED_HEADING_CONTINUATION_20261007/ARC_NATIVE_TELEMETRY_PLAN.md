# ARC 联合姿态日志：六运行精确提案

状态：REVIEWABLE_PROPOSAL_NOT_REGISTERED。本轮仅只读源码/合同/已封存元数据并新增本文件；没有修改 C++、构建、运行 native 或读取新 P。冻结的 ARC_PHASE_INFORMATION 四文件不变；其12项合成资格已由根代理在0cd9772登记后首次12/12通过，回执提交2dc63ae。此PASS只支持局部数学/数值，不自动授权本提案。以下构建、测试、loader、native 和输出验证均须根代理另行冻结源与登记后才能执行。

## 1. 问题、对照与完整分母

目标仅是获得原 921 个五历元块在精确两端时点的、同一条件信息集下的联合姿态工作 prior。相位 z/G/Q/整数不进 native，无相位更新、无 AR、无性能评估。860 个模型合法块与 61 个端模型缺失块全保留；不能按模型是否可用、残差或预计收益改变 clone 时间表。

|序列|原窗口 / s|块数|START+END 行数|已有合法模型|端模型缺失|
|---|---|---:|---:|---:|---:|
|BY2|66–340|274|548|240|34|
|BY2H|413–683|270|540|243|27|
|BY2O|3186–3563|377|754|377|0|
|全部|原三完整窗|921|1842|860|61|

提案基准为旧 FULL_WINDOW_NAVIGATION_ATTEMPT01 的 `BY2/BY2H/BY2O__PVT_CONTROL` 科学配置：`pvt_priority_control`、`euler_yaw`、`external_carrier`，原 IMU/PVT/RD/RP/HV/噪声/初始化/窗口不改。最新Go2接口文档的运动状态码与控制函数返回码属不同域；本提案不把新语义追溯用于旧collector/firmware，不改变旧error_code==0质量门或重建SDK provider，不推定state.velocity反馈坐标或足端FK独立性。对应旧 config SHA 分别为 `f7d70b96dc15770824dfe9507960b658ba68b9f8e6931c7730f20cf41a81e6b2`、`df7079b666bf6c3918848491209183d01c9b8419e0d08baf530e9f37679d1fd7`、`e43ed53dc6e0e55e3ae442bb081401ef4492a364df65a2c4a47fdb582a3f49d4`。这里只读核过配置身份及模式，不重新评价旧结果。根代理如需换基准，必须在执行前修改登记，不能在看到 P 后选择。

每序列两臂：`ARC_NULL` 与 `ARC_TELEMETRY`。二者使用**同一 config 字节、同一新 binary、同一 ARC 时间表、同一普通观测及全部 clone/reset 算术**。NULL 表示空相位模型；两臂都没有相位测量，不是 off-vs-on clone。建议每序列共用新的内部科学 run_id `<sid>__ARC_EMPTY_MODEL`，外部 diagnostic_id/CLI 输出目录分别标两臂。

只允许追加独立 ARC 配置与运行元数据。`dual_yaw_prediction_model` 等科学设置不改；不能把侧向投影、HV 修改、足端更新或新相位准入混入。旧 PVT_CONTROL 是历史身份，不能当作同时间表 NULL。新 split/24 维更新/full reset 可能改变旧 NAV/STD；不要求也不预称与旧轨迹相同。

## 2. 独立配置与事件格式

新增 `ArcCloneConfig`，默认 off；计算模式只设 `off` / `NULL_ARC_DIAGNOSTIC`。新增来源事件路径/指纹、manifest 指纹、source time scale/mapping 身份和 `source_time_replay_assumption`。原生新增config键固定为 `arc_clone_mode`、`arc_source_events_path`、`arc_source_events_sha256`、`arc_schedule_manifest_sha256`、`arc_source_time_scale_id`、`arc_source_time_mapping_id`、`arc_availability_policy`。manifest由prepare/runner核查后把身份写入冻结config；原生只解析严格CSV，不新增C++ JSON解析依赖。另以环境开关 `LEGSA_ARC_NATIVE_TELEMETRY=0/1` 仅控制矩阵文件写出。两臂数学模式完全相同，不以开关选择 gain、reset、事件、边缘化或 logging 数据的计算顺序。

约束：research_experiment only；原 foot `attitude_clone_mode=off` 且 foot input 路径为空；ARC 与 foot 互斥，不能借 foot_i、episode 或 direction 字段。启用 full reset 的 QA/QM/clipped-feedback 限制与旧 clone 一致，要求完整反馈，禁止部分裁剪。旧 legacy 配置没有新字段时路径完全保持原样。

使用无新 JSON 依赖的严格 CSV `ARC_SOURCE_EVENTS.csv`，头固定为：

    schema_version,sequence_id,block_id,endpoint_id,role,source_time_s,source_time_bits_hex,replay_execution_time_s,actual_available_time_s,availability_mode,epoch_index,endpoint_model_fingerprint

schema_version=1；role 仅 START/END；actual_available_time_s 必须空，availability_mode 必须 SOURCE_TIME_REPLAY_ASSUMPTION。ID 采用固定安全字符集合且不含逗号/换行。source/replay 两个 double 精确相等；source 的 17 位 round-trip 文本及 IEEE754 64 位 hex 必须匹配封存块端点，不能容差吸附或四舍五入为 0.8 s。实际区间例如 0.7999999523162842 s，沿用原端点，不凭 nominal 0.8 重新造时刻。

`ARC_SOURCE_EVENTS_MANIFEST.json` 保存三序列、921 行块身份/状态、1842 端点、源时标与本地映射 provenance、schema、上游 COMPLETE/SUMMARY/OPPORTUNITIES hash 和 schedule hash。端模型缺失时 fingerprint 可空，原 status 留在外部 manifest。native 不得按 fingerprint/status 决定是否建 clone；控制只由已注册时刻/角色/身份决定。

事件准备只允许一次读取已封存 OPPORTUNITIES 的身份和时间列、SUMMARY/COMPLETE。若这些列不足以证明精确时间身份，停止并报告缺项，不能读 raw 或从 NAV/最近 IMU 补造。所有 sequence/block/epoch/time 均与原全分母一一绑定；重复、重叠、乱序、END 配错、未知 schema 均拒绝。non-overlap 使单个 clone slot 足够，但不证明块间噪声独立。

## 3. 精确时间表与 ordinary-update 优先次序

现有 loader 将 carrier/PVT 按精确 double 时间并表，但 gi_engine.cpp:678–690 对无 PVT 且不用 carrier 的行直接跳过；invalid carrier 行不是既有传播边界。ARC 必须作为独立 `JointTimedEvent.arcs` 加入队列；不能伪装成有效 carrier，也不能给它 auxiliary update 权限。

新队列合并 GNSS/ARC 的相同精确时刻，排序保持旧 GNSS 之间顺序。原 continue 条件只在该时刻没有实际 GNSS、foot、ARC 动作时成立。ARC 新时点严格切分当前 IMU：用现有比例分配 dtheta/dvel/measured dt，守恒剩余增量；传播后 state.time、timestamp、source/replay time 必须精确相等。不能以最近姿态、插值后的 Euler 或手工 P 插值代替 native 传播。

冻结 dispatch 规则：

1. 非 IMU 末端的 ARC 时点：完成该时点原 GNSS 及其原辅助更新、完整 feedback，再 START/END；没有原观测时只传播，不注入辅助更新。
2. ARC 时点恰等 IMU 末端：先完成队列中的原 GNSS/aux 与原 IMU-end body-HV scheduler 及其 feedback，再处理该时点 ARC。仅 ARC 动作延后；foot 旧顺序在 ARC off 时不动。否则现 gi_engine.cpp:741–749 的 body-HV 在队列之后，会导致 END 日志误标为已包含全部同刻信息。
3. 记录 dispatch_phase=`POST_ALL_EXISTING_UPDATES_AT_TIMESTAMP`，并保存已消费 ordinary-update ordinal 与 reset ordinal。START 要求 dx21=0；END 的 dx24 应为完整 feedback 后零。已到时间仍有未反馈误差即停止，不偷加一次改变语义的反馈。
4. START 创建确定性 ECEF clone，区间内由原普通观测更新并 reset；END 记录同条件状态后直接删除 clone 取当前边缘，绝不 Schur 条件化。不存在 pairModel/safeInnovation/Young/相位 likelihood 调用。

初始 IMU 之前或已初始化首时刻无法构造的 START、运行末尾无 END 等，须记录 `UNCOVERED_INITIAL_STATE` / `UNCOVERED_TERMINAL`，不传播过去、不重用下一 clone。每个原块最终有一个状态，日志仍共921行块回执。终止清理不输出新 NAV 样本、不伪造 END。

## 4. 具体源码改动点（此轮不实施）

|文件/位置|拟改动及边界|
|---|---|
|新 factors/arc_source_events.hpp/.cpp|ArcCloneConfig、ArcSourceEvent、严格 parser/验证；完全独立于 FootPairEvent，不读相位值。|
|options.hpp:54 附近|新增 ARC config/counts；foot config/counts原字段与含义保留。|
|config/port_config_loader.cpp:549–570、1365–1369|新增 ARC 字段解析和互斥检查；完整反馈限制覆盖任一 joint-clone mode；没有新字段时行为不变。|
|kf_gins/gi_engine.hpp:120–135、171–199|JointTimedEvent增加 arcs；独立 ARC lifecycle/来源/diag状态；共用21+3矩阵存储和低层 clone 代数。活动所有者显式区分 FOOT/ARC，避免旧foot语义混入。|
|新 kf_gins/gi_engine_arc_clone.cpp|set/process/finalize/write ARC；确定性增广、END快照、边缘退休、独立source/update ledger。只读记录在两臂使用相同计算路径。|
|gi_engine.cpp:129–175、514–598|共用 joint-clone enabled 检查覆盖 ARC；active时24维ordinaryUpdate，full reset在整个两臂同模式内一致启用（包括两块之间无active clone时），冻结零scale/cross检查一致。ordinary_joint_updates/full_resets按owner记ARC或foot，不能让ARC计入足更新。|
|gi_engine.cpp:638–751|精确队列合并与上述IMU-end延后规则；原GNSS arbitration、更新次序、IMU dt拆分公式不改；source事件自身不能启用RD/RP/HV/SA。|
|gi_engine.cpp:2065–2068|current-only covariance replacement禁止条件覆盖任何joint-clone mode。|
|runtime/port_runtime.cpp:1442–1445、1604–1664|独立ARC输入loader在initialize之前；结束时独立finalize与writer；foot off不能打开足文件。|
|writers/port_writers.cpp|新ARC模式/计数/来源hash和telemetry输出开关单列manifest；同算术字段两臂相等，允许诊断ID/输出路径/写出标志不同。|
|cpp/CMakeLists.txt:54–60|已有GLOB_RECURSE会包含新增.cpp，重新configure一次即可；无需修改旧clone数学源码。|

`factors/attitude_clone.cpp` 的 augment、ordinaryUpdate、reset、NED connection 等数学函数原样复用；不改 foot pair 的 H/R、区间、epsilon 或更新选择。已有 full reset 与普通观察联合更新是新空模型两臂共同组成，不是可隐瞒的日志副作用。最小实现不另外引入旁路 covariance observer 或新滤波器。

## 5. 日志与同一条件信息集

两臂都输出同一 `ARC_LIFECYCLE.csv` 与 `ARC_CONDITIONING_EVENTS.jsonl`，并都执行快照所需的同样矩阵计算/计数。仅 TELEMETRY 将完整快照序列化为 `ARC_JOINT_PRIORS.jsonl`；NULL 丢弃该序列化输出。写出均在运行结束，不能按日志内容反馈算法。

每块回执必须含原 block/端点/epoch ID、模型 fingerprint、source/replay time、actual_available_time_s=null、state time、事件处理顺序、最终状态、clone owner 和当前状态样本数。实际 arrival/model-ready 不知，任何 replay、软件处理耗时或最近消息时刻都不是实测 availability。

每个覆盖的 END 快照保存：

- 完整 P24 和 dx24、21+3 state ordering/单位/符号；START P21、原精确 J0、START C0、START信息集ordinal。零方差/冻结块保留，禁止jitter、删cross或把对角STD拼成P。
- END时**经普通更新修正及reset后的**clone C0_given_end、current cbn、BLH、C1=cne(BLH)cbn；旧START nominal另列仅审计，不与END P混配。
- END fullfeedback后的 BLH 重算 `J1=[−nedFrameConnection at position, cne at PHI]`。记录 B6x24=[[0_3x21,I3],[J1,0_3x3]] 和 P6=B P24 Bᵀ，后续独立全P复核；不能直接截取PHI/clone两块忽略position-frame项。
- run/config/binary/schedule/provider hash、坐标frame/误差约定和 `conditioning_information_id`。该ID绑定当前运行输入身份及已消费普通更新ledger前缀，不把两端各自原始时刻的不同信息集拼成一个joint prior。
- 完整已执行ordinary update与full reset次序ledger：monotone ordinal、exact state time、callsite/source tag、provider row/measurement身份（可确定时）、reset/dispatch阶段。建议由EKFUpdate统一记录实际执行、各现有调用处传递只读source tag；无法解析的内部来源保留UNKNOWN，不假称已建立原始误差共享图。额外source tags不改H/R/dz或执行门控。

输入provider/config hashes与ledger能说明哪些PVT、carrier、IMU、SDK/anchor相关来源可能已用；它们不能自动给出 C_en。默认 C_en=UNKNOWN，不从state-state cross推定state/phase独立。两臂原足因子更新/尝试数必须为0；RAW/reference open=0。

物理基线向量、body-to-engine安装和时标来源需由后续离线信息登记单独冻结；native不读相位z/G/Q或选定基线方向。缺乏已资格安装/工作基线定义时，P快照仍可交付，但不能自动触发860块姿态信息数值读出。不能把合成测试的0.28 m当实机标定。

## 6. 身份门、封存与停止条件

单次执行次序固定为 BY2 NULL→TELEMETRY、BY2H NULL→TELEMETRY、BY2O NULL→TELEMETRY，3×2=6 native，0 retry。新唯一stage根：`<SCRATCH_ROOT>/TRUSTED_HEADING_CONTINUATION_20261007/ARC_NATIVE_TELEMETRY_ATTEMPT01`；已存在即拒绝，不换目录复跑。

prepare只建立3个共用科学config和3个时间表，运行3次loader-only；每对config/输入完全同hash，唯一差别为CLI输出目录、external diagnostic_id与纯写出flag。前后核全部原输入/源pin和先前封存物；进程使用strace核raw/reference=0、无保护区写入、仅对应run输出。原旧输出不读入算法。

每序列完成两臂后，先核 native return、有限状态健康，再核以下字节身份：`KF_GINS_Navresult.nav`、`KF_GINS_STD.txt`、`ARC_LIFECYCLE.csv`、`ARC_CONDITIONING_EVENTS.jsonl`，以及原 `HEADING_SOURCE_EVENTS.csv` 和存在的原更新trace；manifest仅比较排除明确元数据差别后的科学字段。两臂覆盖计数/未覆盖原因与source/update/reset/IMU split次序全部同一。任何不等硬停，保存首次日志，不解释P、不评价新轨迹，不以容差代替身份门。

在每对门通过后只封存输出；三对全通过、六native全seal后才做一次纯字段验证：每序列所有原块有且只有一回执，合法860和缺失61分列；覆盖END与source/姿态/P维度完整匹配、actualavailability全NA、C未知、没有新增相位消费。矩阵PSD/信息分析另属之后的数学读出预算，不在本次字段核查偷偷执行。

如有未覆盖块，仍报告921全分母与实际covered/legal-covered数量；不得直接宣布获得860组prior。缺页/不完整/时间身份不符拒绝该记录并保留原因，必要门失败停止；不得采最近姿态修补。

## 7. 最小构建与局部测试预算提案

先实现并冻结源码，根代理登记后才执行。一个新ext4局部stage，单数值线程，无raw/reference/真实文件；一次configure、一次build（只demo/library目标）、两次harness compile（旧16项harness源不改、另一个新ARC harness）。configure≤60 s，build≤300 s，两个compile各≤60 s；上限是独立进程timeout，调用之间回报状态，不用长blocking等待。

一个pytest进程，24项=原16项native clone回归+新增8项ARC集成资格，≤120 s；原16项从源码静态计得28次harness子进程，新8项最多32次，合计≤60次**合成harness调用**（与6次真实native分账）。每次命令/输入/退出码/stdout/stderr保留。第一次失败停止进入真实阶段，修复重跑需根代理另登记受影响项，不自动消耗原预算再来一轮。冻结的12项phase数学测试源码不改，本次不重复跑。

新增8项固定覆盖：

1. ARC CSV/manifest与精确double/hex时刻验证，actualavailable空；off不打开事件源，错schema/未知时标/伪known availability拒绝。
2. 两个不重叠0.8s块完整START/END/边缘退休，clone owner与ID不复用；含一块端模型缺失，时间表仍完全相同。
3. 新ARC时点切分IMU，所有segment dtheta/dvel/measured dt守恒；无最近时刻吸附，source/state精确相同。
4. 同刻GNSS/aux先反馈，再START/END；IMU-end body-HV同刻碰撞按登记次序，END P/C0/J1取最后反馈后值。
5. 原普通观测产生非零clone修正与current-clone cross，验证joint update/reset以及P24→P6位置frame映射；对照既有Python clone代数/有限差分。
6. NULL/TELEMETRY的合成NAV/STD/旧事件/ARC lifecycle/conditioning bytes完全一致；flag只能影响矩阵序列化；phase/foot更新均0。
7. 初始支持不足、out-of-IMU末端、缺END、重复/乱序/错配/重叠事件失败或明确未覆盖；不得补历史pose/多追加NAV样本。
8. ARC/foot互斥、QA/QM/clipped feedback拒绝、零scale冻结、current-onlyCov替换禁止；ARC off旧默认行为与原脚更新16回归保持。

## 8. 分阶段最大计数

|阶段|预算|本文件执行数|
|---|---|---:|
|实现/局部资格|configure1、build1、harness compile2、pytest1/24items、synthetic harness≤60|0|
|时间表/config prepare|一次921块元数据遍历、3个事件CSV、3个共用config、loader-only3|0|
|真实联合状态日志|native6，0retry，三原完整窗×两空相位臂|0|
|六输出seal后纯字段/身份汇总|一次聚合，921全分母；phase数学函数调用0|0|
|phase信息/故障/导航评价|本提案均0；后续需独立冻结输入/相关性/基线/权重与调用预算|0|

当前还没有实装独立ARC生命周期，没有证明这921块都会覆盖，更没有可信相位或导航增益结果。下一步只在根代理完成源/接口/时间表与预算登记后执行上述局部资格，再决定是否启动6native；不能跳过NULL身份门直接消费已有phase模型。
