# 输入与场景证据：转动、支撑变化和载波中断

日期：2026-10-06；入口版本为任务指定研究 HEAD 856923d。此次复用已封存小表、接口源码和少量 PLAN/MANIFEST 元数据；不全扫 raw、不读取评价参考、不运行解算器、不调参。原 V3 与后续载波/body-HV 研究身份分开。

## 1. 当前可执行的数据范围

| 正式 V3 序列 | body 与接收机目录对应 | Unix 基准 | 完整相对窗 s | 已审 RAWX 成对历元 |
|---|---|---:|---|---:|
| BY2 | by2.txt / by2 | 1772784000 | 66–340 | 1370 |
| BY2H | by3.txt / by3 | 1772784000 | 413–683 | 1350 |
| BY2O | by1.txt / by1 | 1772780400 | 3186–3563 | 1885 |

路径前缀：<RAW_ROOT>/BY2_BY3/2026-03-06/，body 在 高层数据/，接收机在 fixption数据/2026.3.6/。具体目录、hash、原 15 个 provider 与配置见 [V3_BASELINE_LOCK.json](../AR_V3_RESEARCH_20261006/V3_BASELINE_LOCK.json)及[说明](../AR_V3_RESEARCH_20261006/V3_BASELINE_LOCK.md)。本次不重新 hash raw。DG01_INTER_RECEIVER.csv 的三条 paired_epochs 行均为 RAWX rcvTow 差 0、两端未配对 0；这证明记录键配对，不证明接收机物理时钟完全相同。

原 V3 的 IMU、RP、RD、HV 可按锁复用，但原 HV 使用 status-A1 航向工程旋转，不是 GNSS 独立 body 速度。新模型若更换此信息、初始化或时间政策，必须登记为研究方法，不能继承原 V3 名字与成绩。

当前最完整的载波建模输入是 <CARRIER_INTEGRATION_SCRATCH>/REAL_100_340_V2/PLAN.json：BY2 100–340 s，1200 个唯一双端 RAWX 配对，无重复/未配对；ARC_EVENTS.json 和逐历元模型全部保存。这不是原 V3 的完整 66–340 s 支持；66–100 s 无该载波输入必须保留。三 V3 文件的原始历史均存在并已重建一致，但不能将 BY2 当前六信号族的因果建模资格自动复制给 BY2H/O。

别名：<CARRIER_INTEGRATION_SCRATCH> 为既有 CARRIER_INTEGRATION_20261006 scratch；机器路径由本机配置/PLAN 解析，本文不另建 raw 副本。

## 2. 机体可读字段：观测与代理分层

| 字段 | 现有可执行入口/合同 | 可以直接记录 | 不能直接断言 |
|---|---|---|---|
| 外层 stamp.sec/nanosec | body parser；sec+ns×10⁻⁹−base_time+已登记 offset | 消息时间、顺序、间隔、缺字段 | 芯片采样时刻、硬件同步、延迟已校准 |
| imu_state.gyroscope[3] | 项目采用 rad/s、body FLU；导航另做安装/坐标变换 | 报告角速率与有限区间转动输入 | 原始 ADC、无偏真角速率、与 SDK 派生量独立 |
| accelerometer[3] | 项目采用 m/s²、含重力/比力语义；FLU | 比力报告、振动/动态代理 | 仅重力或真实线加速度；动态时不能直接当倾角真值 |
| quaternion[4]、rpy[3] | wxyz、roll/pitch/yaw rad；项目有内部一致性检查 | SDK 姿态报告与 RP 辅助 | 与 gyro/foot/velocity 误差独立；磁/内部融合过程已知 |
| foot_force[4] | 消息 int16[4]，原足序 FR/FL/RR/RL | 每足 SDK 力指示及变化 | 已校准 N 单位、独立真实接触、无滑移、真实承载力 |
| foot_position_body[12] | 四足各 xyz，SDK body-relative；FLU 几何有输入检查 | 足相对位置报告及时间变化 | 原始编码器+URDF FK、无 IMU/滤波参与、足端静止 |
| foot_speed_body[12] | 四足各 xyz；官方示例称 body-frame / relative-to-body | SDK 足速报告及内部一致性诊断 | 必然等于机体系坐标的时间导数；必然是独立 J(q)qdot |
| position/velocity[3] | body/odom 语义需按数据集区别；BY2 body-HV 有专项证据 | SDK 状态报告 | 通用 SDK 版本皆为 body；独立纯腿里程计 |
| mode、gait_type、error_code | body 原字段 | 模式/步态/错误码标签 | 每足接触真值；gait_type 不等于实际支撑相 |

字段来源：[go2_body_state_parser.py](../../../src/legsa_gins/datasets/by2/go2_body_state_parser.py) 第 206–274 行；[unitree_imu_semantics.py](../../../src/legsa_gins/datasets/by2/unitree_imu_semantics.py) 第 109–143 行。旧 parser 顶部把 velocity 写作 odom，其字段后来为 go2_odom_or_body_evidence_missing；新 [body_velocity.py](../../../src/legsa_gins/paper_rebuild/body_velocity.py) 明确要求 dataset_supported_body_flu。这属于后续本批记录证据，不是所有 SDK 的统一官方定义。

[足输入可行性](../RESEARCH_AUDIT_20261006/04_LEG_INPUT_FEASIBILITY.md)已按三全窗每隔至少 0.2 s 选择消息：BY2/H/O 分别 1352/1333/1854 条，4539 条所需字段全部有限且脚位置/速度非零。它只证明稀疏采样输入可用；最大间隔 0.218/0.212/0.526 s 是诊断采样间隔，不是原始 IMU 最大缺口。top-2 足力的接触假设未经验证，不能作为新模块真值标签。

### 足速语义仍未闭合

已读的官方 pinned unitree_ros2 示例 read_motion_state.cpp 第 50–59 行只打印“foot position and velocity in body frame / relative to body”；SportModeState.msg 第 13–15 行只定义字段。SDK2 IDL 同样是传输类，不公开生成方程。来源及版本在[官方接口资料](../TIM_EVIDENCE_20261005/sdk_and_metrology/OFFICIAL_INTERFACE_AND_AUTHOR_FACTS.md)第 15–28 行。

当前资料无法确认 foot_speed_body 是 J(q)qdot、坐标差分、世界速度旋转，还是包含 IMU 补偿的融合输出；foot_position_body 的内部估计依赖也未披露。本仓库 parser 原样取值，不会提供缺失的物理语义。历史常用名称 footSpeed2Body/footPosition2Body 不足以证明本批消息的生成机制。未知保留，不能靠和 gyro 相合就证明独立。

### 新 body-HV 的现成输入

<CARRIER_INTEGRATION_SCRATCH>/BODY_VELOCITY/MANIFEST.json 记录 BY2 66–340 s 的 56643 行，实际首末 66.001034907 / 339.997055685 s；仅 FLU→FRD 的 x、−y，不读 GNSS、不使用姿态旋转、不插值。基础 std=0.2 m/s、scale=1 是既有工程工作值，不是校准值。接口为 time,v_forward_mps,v_right_mps,std_forward_mps,std_right_mps,valid,source_status；[body-HV 合同](../CARRIER_NAV_INTEGRATION_20261006/BODY_HV_INTERFACE.md)规定 past-only、每源一次和独立 timer。BY2H/O 的新 body provider 尚不能从本 BY2 manifest 推定已生成。

## 3. 支撑变化：能复用的接口与不能升级的声明

旧 [hartley_h0_h2.py](../../../src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h0_h2.py) 提供 force_hysteresis_contacts（1486–1545 行），输入 N×4 力和严格递增时间，使用滞回及实际经过时间确认切换。原阈值 off=(24.8,25.2,23.4,24.0)、on=(34.2,33.8,30.6,32.0)，原足序 FR/FL/RR/RL，dwell=0.0120356083 s。它们是旧输入统计来源规则，不是当前新任务应重新拟合的参数，也不是计量接触阈值。

旧 propose_contact_detector 先看完整输入分布再产生阈值；该拟合入口不能冒充在线因果检测。复用时只使用事前锁定阈值的逐时状态机；切换可用时刻是 dwell 确认时刻，不能回填 crossing 起点。应保留未知/初始左删失状态、缺帧、源错误、切换和足身份。

[HX02D 的 B3 足力小表](../hext/HX02D/HX02D_HARTLEY_DIAGNOSTIC.md)第 173–193 行是已有输入侧证据：BY2 两足 proxy 支撑样本约 92.545%，BY2O 两足约 71.370%、四足约 22.901%；每足切换约 4.11–4.16/s 与 3.12–3.17/s。这是固定分类器的输出分布，不是现场接触真值，不用它重选方法/门限。该表没有覆盖 BY2H，不能补写 BY2H 同类比例。

[H5 parser](../../../src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h5.py)第 1–6、225–280 行只解码 timestamp、gyro、acc、foot_force、foot_position，明确跳过 SDK rpy/velocity/foot_speed。其 [run_h5.cpp](../../../src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/tools/run_h5.cpp)第 429–441 行复用存活足、删除离地足、增加新触地足的生命周期。可复用输入隔离与生命周期思路，但它是接触点相对位置的滤波更新，不是现成的独立足对角速度因子；不应把旧后端移植表现等同于输入不可用。

## 4. 足对差分转动：可实施但条件明确的新代理

以下是运动学分析，不是新实测结果。若两足 i、j 在区间内为同两个世界静止接触点，body 相对导航框架角速度为 ω、机体系原点速度为 v，则 p_dot_i=−v−ω×p_i。令 d=p_i−p_j：

p_dot_i−p_dot_j = [d]×ω。

共同平移被消去。单足对的叉乘矩阵秩为 2，沿 d 的转动分量不可观；至少两个不平行足对才可能恢复三个局部转动分量。不可把最小范数解的零分量当高置信观测。即使 rank=3，也只是接触条件下的相对转动信息，不产生绝对 yaw。

优先用同足位置的 past-only 区间差分，以避开 foot_speed_body 未明确的导数语义；但仍叫“SDK position-derived contact-rotation proxy”。位置可能包含 IMU/估计器依赖，因此“数据读取不依赖 GNSS”不等于“误差独立于 IMU”。

有限区间使用中点 p_mid 时，(p1−p0)/dt=u+[p_mid]×w 的刚性关系对应 Cayley 转动率 w=2 tan(θ/2)axis/dt；只在小角时接近普通平均角速度 θ axis/dt。必须明确该参数化、近 π 奇异/跨周限制和时间标签，不能直接将其当瞬时 gyro 测量。

最小内核合同（尚不接 EKF）：

- 使用两端均已确认 stance 的同一足 ID；未知、单足、切换、缺帧与已知滑移不生成完整旋转观测。SDK 代理不能检出所有未标记滑移，需有反例。
- time_end 是决策最早可用时刻；两端严格递增，dt 有限且正；不使用未来中心差分或回填历史测量。
- 显式 FLU/FRD 变换位置、速度和协方差，IMU 安装修正只作用于其定义的传感器轴，不能二次旋转本来已在 body 的足点。
- 保留 endpoint/足间相关协方差；多个足对共享同一只足时，差分噪声相关。可白化每足方程再投影共同平移 nuisance，避免误当独立多对约束。
- 输出 rank、可观 basis、nullspace、可观坐标/协方差与线性化点；endpoint covariance 只是已声明工作模型，不称已校准。
- 不以足力、参考误差或本次结果调 threshold；不把 gyro 检验自身与足代理的差作为独立真值。

## 5. 时间、坐标、物理点的已知与未知

作者已确认 body 使用狗时钟、GNSS 使用接收机时钟，以踢动/接收机 P/V 启动变化和机体 IMU 对齐，并非使用融合 trace；但这不提供每段采样事件、offset/drift、发布延迟或不确定度。外层 stamp 同时承载 foot/IMU 字段只证明同消息时间，不能证明内部传感器零延迟。沿用[23 项输入预算](../TIM_EVIDENCE_20261005/sdk_and_metrology/INPUT_UNCERTAINTY_BUDGET.csv) U01–U06、U11–U20，不另编造标定结论。

原物理合同：GNSS1 右、GNSS2 左，差为 GNSS2−GNSS1，FLU +y / FRD −y，名义 L=0.35 m；IMU 安装 −1° roll、既有杆臂 [.03,.03,−.30] m 是模型声明。SDK 速度点到导航 IMU 点仍假设零位差，足点和天线相位中心均无本次新增实体标定。名义向量不能替代逐轴测量及安装不确定度。

RP 是 SDK 报告姿态的弱辅助，与机体 IMU/SDK速度/足点可能相关。研究三维运动先验不能把已经 GNSS 融合的 yaw 作为未知初始姿态的免费锚点。将原始 gyro 从 body rate 转成相对导航系的转动还需说明偏置、地球/运输项和参考系定义。

## 6. 自然载波场景证据与三窗口缺口

[DG01_OVERVIEW.csv](../hext/DG01/DG01_OVERVIEW.csv)报告三全窗每接收机 RAWX 1370/1350/1885 点；全部信号的 lock-regression 计数分别为 BY2 2380/2334、BY2H 2278/2285、BY2O 2240/2749。它们跨不同信号、可重复、含语义限制；不是独立物理周跳次数。BY2O 接收机2 PVT carrier FIX 为 1595/1886，而接收机1为1886/1886；产品状态变化与原始载波可用性另列。

[同历史转换核查](../AR_V3_RESEARCH_20261006/INPUT_AUDIT_RESULTS.md)已证明六份完整 UBX 与旧完整输入逐字节一致，旧 OBS 299516 相位/LLI 字段一致；28 条异常 OTHER/0A06 cell 的排除/重同步历史已保留。这保证重建身份，不证明载波真实整数或噪声正确。RTKLIB 已有 time/P/c 时钟处理不能重复扣；subHalfCyc 也不能盲加半周。

BY2 100–340 的 [V2 弧审计](../CARRIER_INTEGRATION_20261006/ARC_REVIEW_V2/REPORT.md)复用 1200 模型历元、174787 事件记录，未改 0.5 周 TDCP 门。RX1/RX2 的 repeated MISSING=14195/15897、HALF_CYCLE_UNRESOLVED=25492/22823、LOCKTIME_REGRESSION=2024/1953；没有 TIME_GAP 或 RECEIVER_CLOCK_RESET 记录。MISSING 是已知单信号在消息中缺失，不能写成几万个整接收机消息缺口。TDCP>0.5 周为174/203条（所有原始信号），只在 metadata-continuous 端点检查，原因可能是噪声、时序、时钟或相位异常；不能自动宣告物理 slip。

本轮可以直接用完整时间母体研究这些自然状态下的断弧、释放和重获。不能因为旧候选 first-break 分析取自 selected 集合，就把其比例推广为全信号自然故障率。BY2H/O 尚缺当前六信号族同口径的逐时弧/因果星历完整审计；先做输入元数据资格，不先承诺同样持续载波输出。

[ArcTracker](../../../src/legsa_gins/paper_rebuild/carrier_phase/arcs.py)已提供 per-receiver/full-signal identity、missing/reset/lock退/half变化与 TDCP 分离、arc token 和 temporal_link_qualified。默认不修 half，不继承新弧整数；metadata 连续不等于接受 N。回放必须用完整接收机 epoch 才能识别“缺席信号”，只喂筛选后子集会人为制造 MISSING。

因果星历入口为 [real_trial.py](../../../scripts/paper_rebuild/carrier_phase/real_trial.py)的 checked_navigation_manifest / NavigationReplay。必须显式给 prefix 或 schedule，cutoff≤当前及首次实际 RAWX 时刻；TOE 合适不等于当时已收到。现有 BY2 CAUSAL_NAV_SCHEDULE_V2 共有12个100、120…320 s prefix；每历元按当时可用者加载，旧全历史 NAV 禁用。Galileo 的八字 SFRBX overlay与 E1B 导航/E1C、E5bQ观测区别见[修复资格](../CARRIER_PHASE_DEVELOPMENT_20261006/GALILEO_NAVIGATION_REPAIR.md)。BY2H/O 不可加载 BY2 prefix，须自己源内的历史可用性合同。

## 7. 真实与注入故障必须分别报告

| 场景层 | 已有证据 | 允许用途与边界 |
|---|---|---|
| 自然机体转动/支撑变化 | gyro、足力/足点、步态报告 | 输入定义的连续场景分层；无独立 slip/contact 真值 |
| 自然信号失效/断弧 | RAWX validity、half、lock、缺席、原时间戳、TDCP诊断 | 保存拒绝/释放/重获；不把标志全归因为物理整周跳 |
| PVT/provider 人工航向故障 | 原 V3 yaw/valid 覆写，旧 D61/D62、heading outage | 仅产品层鲁棒性；RAWX未受扰不能叫载波故障对照 |
| 载波 signal-level 注入 | 既有合成 fractional-cycle / integer-slip / pivot fault 等机制试验 | 有已知注入真值，但合成/半合成单列；不能当自然发生率 |
| 新原始窗口时间/数据丢失注入 | 当前未由本文执行 | 必须另登记干预层、真值、固定时窗、传播到弧/候选/导航的链，不能按结果挑故障 |

以转动或接触变化与载波失效时间重合，最多得到关联；机身遮挡、多路径、时钟行为和真实滑移的因果仍未分离。

## 8. January 数据能否作额外留出

[Jan5 完整审计](../HEADING_REASSESSMENT_20261006/02_DATA_AND_FIX_AUDIT.md)已确认原 ZIP 与8个 body 和 R5 字节相同，不是新数据。Jan5 与 March6 是两个日期，8段非重叠 session 不是8个独立采集日；NMB/XB 原 PVT 包围盒不同不证明8条独立路线。

全部8段包含 IMU/RPY/velocity/force/foot-position/foot-speed；除 NMB2 外各有1个末尾不完整帧，不可填零。旧 full-file profile显示存在多条连续重复SDK向量，外层约4ms时间间隔不能当每字段独立有效带宽。

- NMB1–4 有双 FIX 航向与 FLOAT 转换；相邻有效位置最大间隔163–173 s、双 FIX 航向202.6–216.8 s，主要是有消息但 invalid，不是同长度原始文件空洞。适于定义输入层恢复场景，不能未经 RAWX 审计叫载波全失锁。
- XB1–4 两端 FIX 均0，双 FLOAT 位置差中位10.02/17.73/15.10/44.57 m；删 FIX 门不能制造0.35m航向。旧8个 NO_INIT=4session×2方法，不是8次发散。
- RAWX 精确 week/tow 键交集0，近邻偏差约−8ms（XB4约−7ms）；现 exact-pair frontend 不能直接用于这8段。需先解决钟差/物理时标和异步运动模型，不能硬贴时间。
- 共同有效相位且 half-valid 的 GPS≥4星机会 NMB=796/735/849/690，XB=0/12/39/30；多星座总数不能代替组内 pivot、几何和星历资格。RELPOSNED 约2.5–2.94km且 isMoving=0，不能当双天线短基线。
- R5 已用−1.1s input-event对齐并运行/检查过这些数据；这不是硬件标定，也不能无说明迁移到新carrier输入。BY2的速度frame和足力阈值不自动适用于 January。

因此 January 可用作“已看过数据上的冻结参数转用/失败边界”，不再称纯未见 heldout。新的真正未见采集并非开始本地内核工作的必需条件；但当前材料不能制造独立泛化/正确整数真值。若在此8段内预先冻结某些session仅后测，也须保留此前审阅与开发使用史。

## 9. 最短执行接口与本次读取清单

可立即复用：原V3三全窗锁和15provider；BY2 body-FRD CSV；Hartley allowed-field parser/force生命周期；carrier observations/ArcTracker；BY2 1200 saved models/ARC_EVENTS 和12 prefix schedule。新接触内核优先用位置端点而非未经确认的 SDK 足速，先做数学/反例资格，不接 EKF、不扫描实绩参数。

必要后续输入审计：三窗 body 的完整源时序/重复值/共同stance支持小表；三窗同口径 carrier arc/meta 与 causal NAV支持；无原始编码器时明确 SDK依赖；所有失败/缺席母体保留。本文不生成这些新表，也不调整门限。

本次读取范围：上述 repo MD/CSV/JSON 与源码；小型 scratch BODY_VELOCITY/MANIFEST、REAL_100_340_V2/PLAN、CAUSAL_NAV_SCHEDULE_V2/NAVIGATION_SCHEDULE；外部已保存官方 ROS2 两文件。仅解析既有表/元数据选择字段，没有重算旧观测矩阵、扫描raw、打开NAV卫星载荷或评价reference。新raw读取0、solver/CILS/native/evaluator0、Git操作0。仅写本文；随后单独授权的 contact_rotation 数学内核与测试不属于本次只读数据审计的计数。
