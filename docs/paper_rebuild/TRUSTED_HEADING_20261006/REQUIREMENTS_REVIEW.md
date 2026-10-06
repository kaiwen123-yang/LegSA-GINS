# 可信航向完整版本：需求、接口与证据审查

日期：2026-10-06。只读审查基点：`856923d6bce83ffb69e1f339606879410d0e6230`。本文件是新目标的实现与验收建议，不是算法完成声明。

本次读取现有载波库、native 接口和已封存开发小表；没有读原始观测或参考，没有执行搜索、导航、评价或测试，没有改算法。旧两历元无向夹角支线的停止结论保留，其有限负结果不限制本次完整可信航向目标。全部处理在 Ubuntu 22.04 WSL；V3/main 及历史结果不变。

## 1. 结论与最小实现路线

现有库已经闭合“原始载波→整数候选→未来验证→连续跟踪→当前时刻基线→LegSA-GINS 更新”的实验接口。应复用它，优先补上 **物理 SD 弧身份下的局部支持续接与重新获取资格**，而不是继续放宽门限或重建 EKF。

最小实施顺序：

1. 独立实现整数图的精确坐标输运内核。先证明同一冻结假设在合法换 pivot、失去部分物理弧后的代数关系；暂不改变旧 tracker 的准入。
2. 在明确的条件跟踪身份下接入局部支持状态。完整可逆换基与不可逆支持缩减必须分开；后者不能继承旧 top-two 证书。必要时用当前可用的过去窗口重新搜索/验收，不能复活失效旧弧。
3. 将选择目标从现有三维位置型 log-det 指标扩展为预先规定的航向方向信息与过去可用性指标。只读取选择时刻已到达的几何、Q、弧历史，不读取未来存活或误差。该改变需要独立消融，不能和图续接混成一个不可归因改动。
4. 实现真正接触/足端运动学速度 provider，先通过原有二维 body-FRD 输入接入。与 GNSS 独立是信息来源声明，不是统计独立声明；不能把现 SDK 最终速度改名为腿里程计。
5. 完成实际整链运行时序、失效/恢复、相关性声明和原 V3 三全窗对比，再判断完整版本的效果与三项贡献。不能用图单元测试、候选数增加或一小段 RMSE 作为目标完成证据。

三项贡献建议按层分开：①短侧向基线的方向量测与退化定义；②足式平台的本体速度/弱约束互补及支撑切换；③原始载波整数假设的物理弧生命周期、局部支持续接和可信航向输出。现有长度约束、PAR、换参考星、残差门和接触速度本身都是已有思想；第三项是否有方法创新，要由完整规则与同信息对照的增量证据确定，不能凭组合无人使用来判定。

## 2. 当前代码能证明什么

| 部件 | 当前入口 | 已实现 | 还不能推出 |
|---|---|---|---|
| 物理信号与逐接收机弧 | `carrier_phase/observations.py`、`arcs.py::ArcTracker` | exact time-tag、CP/half/lock/clock、TDCP-Doppler、两端 SD token；新弧另编号 | 元数据合法等于无物理周跳；exact tag 等于实际硬件同步标定 |
| 多系统多频 DD | `multignss.py::build_multignss_epoch` | 分组 pivot、信号波长、完整组内 shared-pivot Q、ECEF 动基线 | 跨时 Q 或接收机系统偏差已经校准 |
| 数值候选搜索 | `temporal.py`、`solver.py`、`native_sphere.py` | 每期独立动态基线、共享整数、球面约束、明确 selected-class 证书；可选 native 精确球面核 | 目标最优整数是真整数，或全部模型失配已处理 |
| 两种 partial 问题 | `partial.py`、`selected_likelihood.py` | full likelihood 的整数 nuisance profiling；另一个预选观测似然只留全部 code 与 selected-only phase | 两者是相同似然；缩维后的旧证书可直接沿用 |
| 初次准入 | `admission.py::CausalAdmissionSession` | primary/competitor 冻结；固定未来五槽；残差、长度和不同 active class；不按未来重选 N | 只比较两候选就有 false-fix 概率；α=0.01 是错误固定概率 |
| 跨时相关分支 | `joint_admission.py` | 显式 full future Q，缺 Q 拒绝；selection independence 为假时不接纳 | 只换正确未来边际 Q 就处理了选择条件依赖；该分支已接入当前 tracking/native 主线 |
| 单信号故障诊断 | `faults.py`、`sensitivity.py` | 物理 SD target/pivot fault map、完整 Q、Holm、别名、可检测性 | top GLRT 故障一定可唯一定位；MDB 是球面误差界/航向保护级 |
| 持续跟踪 | `tracking.py::FixedCandidateTrack` | origin 重验、N 与 selected_at 不变、滚动五槽、首失败永久释放、receipt/model 绑定 | 局部弧失效后可保留其他支持；重叠 PASS 是独立重复验证 |
| 当前量测 | `measurement.py` | 当前期 fixed-N GLS、固定长度投影、全 3×3 ECEF Cb 加工程角度 floor、无回填 | Cb 包含整数错误、选择效应或时相关；valid 是可信 FIX |
| native 入口 | `GnssFileLoader::loadExternalCarrier`、`buildExternalCarrierBaseline3dModel` | 15 列 CSV；商业 yaw 被替换；GNSS2−GNSS1；FRD 左侧杆臂；全 R 旋转；当前事件一次消费 | 保留的 P/V 与新载波统计独立；native 接纳等于前端整数正确 |
| body HV | `buildBodyVelocity2dModel`、`applyBodyVelocityPriorForTime` | 2D body residual 和姿态 Jacobian；past-only、过期拒绝、一次 attempt、独立 timer | 已有完整接触腿里程计；没有垂向观测就绝不会影响垂向状态 |

代码相对路径均在 `src/legsa_gins/paper_rebuild/` 或 `cpp/legsa_v23_port_core/` 下。证书、准入、量测可用和 native 更新是四层不同状态，应继续分别计数。

## 3. 已封存结果对新目标的约束

当前最密集开发前端为同一 BY2 100–340 s 的 1,191 个重叠窗口：

- 所有窗口取得所登记似然的候选搜索证书；116 个初次合格。
- 初次结果中 535 个 `UNRESOLVED_ACTIVE_ARC_CHANGED`；55 个跟踪 owner 中 28 个因 phase diagnostic、14 个因 arc 变化释放。
- 157 条有效当前测量、145 次 native 接纳；这些都不是独立正确固定次数。
- 含记录搜索耗时的载波版本 yaw/H/V RMSE 为 1.937270° / 0.098965 m / 0.048794 m；同开发条件的双 PVT 向量对照为 1.620834° / 0.098646 m / 0.048823 m。载波没有胜过该航向对照，更不能据此声称胜过原 V3。
- CILS 中位数 34.6 ms、P95 154.5 ms；当前串行回放将准备、验证、GLRT、catch-up、IO、融合等开销设为零，不是实际整链实时性。

来源：`CARRIER_INTEGRATION_20261006/DENSE_SELECTED_FRONTEND_READOUT.md`、`DENSE_NAVIGATION_READOUT.md`。旧 120 窗 V2 的 arc 审查将 partial 的 60 个首次失弧分为 metadata-only 44、TDCP-only 14、mixed 2；不能把这组比例直接赋给新 535 个窗口。它足以否定“arc_changed 全是随意换 pivot”的解释，也不证明元数据异常的物理原因。

另有实质安全反例：`CARRIER_ROBUSTNESS_20261006/README.md` 记录有限合成中错误整数及漏检 slip 模型被 shadow 接纳；21 个带 pivot 四分之一周偏差的 heldout 条件中，整数正确但接纳基线三维角 RMSE 平均达 13.562°。因此仅修整数图或增加支持不能独自解决航向可信性。

## 4. 整数图最小 API 与证书边界

### 4.1 模型和重要次序

组 g 内定义顶点 v=(signal identity, RX1 arc token, RX2 arc token)，对应一个物理 SD 整数 n_v。组应保留当前已资格的 constellation/signal/frequency 身份；不同频率、信号类型和未资格组不能因波长接近而合并。边值为 d_sp=n_s−n_p，单位 cycles。每个原连通分量只有整数 gauge 不可识别，差分可识别。

**必须先解旧分量的整数势，再投影存活顶点。** 若旧图是以 p 为中心的星形，p 当前失效但 i、j 原 SD 弧都持续，则 d_ij=d_ip−d_jp 仍是原假设蕴含的差分。先删 p 再按显式边判连通会错误丢掉这个信息。相反，原来不同连通分量之间没有已知 gauge offset，不能事后拼接。

这只是以原冻结整数假设成立为条件的代数输运；不修正错误原固定，也不消除旧 pivot 的非整周偏差。失效顶点是“其旧弧不再供当前测量”，不是重写过去整数历史。

### 4.2 建议接口

- `PhysicalSdArc(group_key, signal_id, receiver1_arc, receiver2_arc)`：不可变物理身份，不含当前 pivot。
- `FrozenIntegerGraph.from_dd(labels, integer_values, origin_fingerprint, selected_at)`：核验完整标签、同组、整值范围、边方向、重复边及所有 cycle-sum=0；求各原分量整数势。
- `project_survivors(qualified_nodes, available_at)`：仅投影原节点，返回旧分量内的存活节点、canonical gauge signature、可识别差分、lost/new nodes、原假设来源。new nodes 只能列为未知，不能赋旧势。
- `query_dd(target, pivot)`：仅双方属于同一旧连通分量且原物理弧持续时返回差分；其他为明确 UNIDENTIFIABLE。
- `full_rebase_matrix(...)`：完整未减维节点集的可逆整数换基，供观测、设计、Q 及整数一致变换。现有 `multignss.py::pivot_transform` 可作为组内代数基础，但它不证明弧连续。
- `project_hypothesis_family(...)`：按投影 class 分组，保留每个 class 的全部 origin membership；记录输入是否只是候选子集，不能把两条候选当全假设集。

共同输出至少包括 `scope=CONDITIONAL_ON_FROZEN_HYPOTHESIS`、`false_fix_probability=None`、`origin_selected_at`、`observed_at`、`certificate_transfer`、`support_rank`、`origin_memberships`。

完整可逆换基且似然/可行域完全一致，才可保留原排序证书的意义。丢观测要取 Q 的边际主子矩阵；换坐标要用 TQTᵀ。二者不可混用。删节点、删观测或 active class 投影均可能使原 top-two 合并、改变排名或遗漏新的第二类；`certificate_transfer=False` 应是默认值。最小版本允许继续输出有明确身份的“条件跟踪”，但若证据不足必须重新获取或无效，不能把旧 SHADOW_ACCEPTED 原样升级成新子集全局可信。

### 4.3 最小独立数学测试

1. 三节点 star 的 pivot 消失后，两持续 target 的差分等于原两边相减。
2. pivot、输入边顺序与整数 gauge 改变，不改变 canonical 差分身份；完整可逆换基的原始白化成本相同。
3. 任一接收机 arc 改变，即使同卫星同频率回归，也不能继承整数。
4. 原分离分量不可建立新差分；单节点只保留 gauge，无可融合 DD。
5. 非零 cycle-sum、冲突重复边、跨组边、整值溢出均拒绝；合法负整数保留。
6. 两个原假设投影合并，必须保留两个来源，并输出竞争未分离；不能制造第二候选。
7. 删除 target、删除 pivot 和整组失效分别核对物理支持；恢复旧数值不复活旧失效节点。
8. Q 的相关项、T 的方向和波长单位由独立小矩阵检查，不只比较同一实现两次输出。

这些只证明内核代数正确，不证明信号仍有效、N 正确或导航变好。下一集成测试仍须覆盖动态基线、单/多信号偏差、half/lock/clock 失效、隐藏 slip、支持恢复及错误初始整数。

## 5. 必须闭合的运行状态与信息边界

建议在前端明确状态：NO_SUPPORT → ACQUIRING → VALIDATING → CONDITIONALLY_TRACKING；随后可进入 SUPPORT_REQUALIFYING、FAULT_QUARANTINED 或 RELEASED。状态名不是可信概率。

- ACQUIRING 只用已到达的过去窗口；VALIDATING 的未来槽固定，不以迟到样本补缺。
- 合法完整 pivot 变换不等于新一次固定；记录 coordinate change。
- 部分支持丢失：硬元数据失效弧必须移除；剩余支持 rank/冗余/故障可检测性重新检查。GLRT 的 alias 不唯一时不能任选一个最大值当真故障删掉。
- 不可逆投影后，若继续条件跟踪须明确剩余整数的假设来源、未枚举替代类和新工作协方差；要恢复完整新子集准入，必须有适配证书/新的证据程序。
- 新弧重获始终新 N；冻结失败 origin 不复活。旧数据可以是历史证据，不能伪造新 selected_at 或重复计成独立验收。
- 每历元一个 measurement owner。当前最早 active owner 占优、当步释放不抢用同刻新 origin 的规则可保留。
- 前端失效只使载波输入无效，不伪造 PVT FIX、不自动回退为“可信商业 yaw”。若设计 fallback，应显式命名来源、互斥同刻融合并单列其效果。
- `measurement_time=decision_available_time` 接口要求当前基线。算法迟到时只能因果追赶到当前并重新检查，或拒绝；不将历史基线改时间戳冒充当前测量。

## 6. 相关性与垂向风险

### 6.1 现有接口并未解决的重复信息

新载波模式会关闭 GNSS18 的商业 yaw，但仍保留同接收机的 P/V、RD；因此“没有重复 yaw 更新”不等于“没有重复 GNSS 信息”。最简单的例子是 b=p₂−p₁，Cov(p₁,b)=C₁₂−C₁₁，一般不为零。真实 RAWX 基线与 PVT 不恰好服从这个简式，但共享原始源足以要求明确相关性边界。

SDK 速度/RP 与本体 IMU 可能共享内部估计；足端 vᵦ=−ṙ−ω×r 也使用传播中的 gyro。去掉 GNSS yaw 旋转只消除了该构造依赖，未消除与 EKF 状态的统计相关。若再把 EKF 后验姿态用来选择整数、构造载波协方差，然后将该载波作为独立观测回灌，会形成额外数据重用。首版前端应继续不读取导航后验。

连续 tracking 输出共享 N，重叠五槽重复使用观测，错误固定会形成跨时间共同偏差。1.5° floor 是工程工作权重，不是这类相关误差的统计处理。full future Q 也不能自动修复 selection conditioning。

最小研究版本应：给每条 measurement 保存数据依赖/owner/arc 身份；保证同历元来源互斥和一次消费；设计保留 P/V、选择性去除同源辅助等分层消融；将未建模相关性写为限制。不能通过放大 R、降低更新频率或去掉一路观测后宣称已经严格解决。若最终目标要求严格校准的状态—观测相关更新，需要另行给出交叉协方差或可证明的保守融合模型；现 15 列 CSV 只传 R，没有传状态—量测交叉项。

### 6.2 不能承诺航向改善必然改善 H/V

baseline3d 的 H 直接作用姿态，但 EKF 交叉协方差会更新其他状态。body HV 的 H 同时作用速度和姿态，虽然只测两维，也可能改变垂向速度、位置、零偏。侧向单基线绕其自身轴不可观；不能把三维向量量测称完整三自由度姿态测量。

应同时保留 yaw/H/V 的整体、尾部、故障窗、恢复窗指标及协方差健康；不能只列接纳片段或只列平均航向。新 covariance 若有不可检测偏差，正确 N 仍可能产生坏基线。条件 GLS/MDB 和投影后的实际角误差需要分列，不把自由 GLS 的 MDB 米数称刚性基线误差上界。

## 7. 独立足端速度的最小实现边界

已有三序列 4,539 条稀疏检查证实 foot_position/foot_speed/foot_force 非空；“力最大的两脚”只是旧可行性代理，没有接触真值。详见 `RESEARCH_AUDIT_20261006/04_LEG_INPUT_FEASIBILITY.md`。当前 body provider 使用 SDK velocity，固定 scale=1、σxy=0.20 m/s；它不是足端重建。

新 provider 至少需要：

- 明确 foot_speed 是机体系相对导数还是已运动补偿量；本体/IMU/足端点、FLU→FRD、gyro 单位和时间对齐。
- 从原消息因果计算 −ṙ−ω×r，并按刚体杆臂换到 native 速度状态对应点。未经核验不能默认零杆臂。
- 接触进入/退出的固定规则及迟滞；脚间残差、滑移/腾空/切换期间的降权或禁用；源不够就 invalid，不补零、不保持上次速度。
- 工作协方差体现 gyro、足速、接触不确定性及多脚共用 gyro 的相关；当前二维 native 只收 stdx/stdy。若必须表达非对角 R，需小型显式接口扩展，或声明并验证保守替代，不能悄悄当独立脚平均。
- 先保持二维接口，避免用未资格的 z 约束“补好”垂向。SDK z 非零及与足端代理一致性不足以证明垂向真值。
- GNSS 不可用时仍由 IMU 时间推进；past-only、每样本最多一次、过期停止。无绝对 yaw 观测的速度约束不能创造绝对航向可观性。

## 8. 完整目标的要求—证据表

| 要求 | 已有可复用 | 必须实现/补齐 | 完成证据，不能用什么代替 |
|---|---|---|---|
| T1 原 V3 身份 | AR_V3_RESEARCH 的 lock/metrics | 新分支与正式 V3 分列，输入只用同三序列 | 三全窗、初始化、物理点、冻结评价身份；研究 C1/PVT 不能替 V3 |
| T2 原始完整支持 | RAWX/SFRBX、因果 NAV schedule、anchor helper | 三序列完整历史与各自可用开始；未知星历保留无效 | 原窗全时键和不可用原因；100–340 BY2 子窗不能替三全窗 |
| T3 精确整数图 | pivot_transform、SD arc tokens | 上述 graph API、失弧投影、gauge/组边界 | 独立代数 oracle 和状态测试；只证明输运正确 |
| T4 方向/持续性选择 | 过去五槽 rank/log-det 预选 | 预登记方向信息度量与过去 availability 特征 | selection-only 无 y/未来泄漏；与现选择同信息对照，非看 future 后挑最稳集合 |
| T5 候选与竞争 | native exact search、selected-class certificate | 改子集后的正确证书或明确条件身份 | 不同投影类及完整未知范围；top2 merge 不是假竞争 |
| T6 故障和可信输出 | residual/length/GLRT、sensitivity | 局部故障可识别性、不可检测方向的输出政策 | 已知 N 的错接受/漏检/偏基线压力证据；实测无整数标签仍 NA |
| T7 持续与恢复 | frozen owner/rolling receipt/permanent release | 支持重资格、新弧重新获取、失败不可复活 | 完整失效/重获时间轴和空窗；候选数增加不能替恢复效果 |
| T8 本体速度 | causal body 2D native | 接触/足端 provider、支撑切换和点位/噪声合同 | 三序列原始输入资格及独立速度消融；SDK 列改名不算完成 |
| T9 信息相关性 | 同刻商业 yaw 替换、单 owner | 来源依赖账、共享 IMU/PVT/phase 的处理或明确限制 | 同源互斥/消融与不确定度适用范围；floor/alpha 不等于风险校准 |
| T10 真正执行时延 | CILS 记录成本/理想串行 replay | 采集到模型、搜索、验证、tracking、IO/native 全链计时 | 实际 wall-clock 延迟/超时/忙丢弃/队列及当前可用时间，非只报 CILS P95 |
| T11 native 兼容 | external 15 列、全 R、事件拆分、body timer | 最小新增字段按需 opt-in，默认行为保留 | 关闭身份、invalid/missing 一致、时间/坐标/Jacobian；不重写历史结果 |
| T12 三全窗效果 | 原 V3 冻结 yaw/H/V/尾部 | 完整新方法、AR-only、velocity-only、full 的匹配消融 | 全窗与共同支持并报，NA/失败不删；无只选接纳区间排名 |
| T13 退化/恢复 | 原 V3 PVT 层注入定义 | 新 RAW carrier fault 与 PVT fault 分层登记 | 相位/周跳/失弧与 PVT outage 不混名；不放宽资格追改善 |
| T14 独立性/泛化 | 同源三段与商业派生参考 | 诚实定义开发/锁定评价；需要泛化时才资格新采集 | 三序列不冒称跨日留出；共有 GNSS reference 不冒称独立真值 |
| T15 方法贡献与交付 | 可复现库、历史负结果 | 各贡献对应机制/公平对照/真实效果与限制 | 代码可运行≠三创新成立；graph 通过≠完整目标完成 |

建议最小正式消融为同共同配置的 existing-carrier、new-AR、independent-velocity、full 四臂×原 V3 三全窗，原 V3 正式结果独立复用；必要的研究 PVT 向量对照单列。所有改共同配置的量都注明，不能冒称与冻结 V3 的方程、来源和初始化完全相同。航向改善及 H/V 可接受退化范围应在正式运行前由物理/应用要求固定，不从已见差值反推容忍线。

完整版本最终需要三个独立判断：实现链路是否闭合；可信性声明是否被对应证据支持；相比原 V3 与公平对照是否有实质效果。某一局部机制失败后可以调整研发路线，但不能仅以审查文件或单元 PASS 标记完整目标完成，也不能为了得到成功结论把不利全窗、延迟、故障或相关性边界删掉。
