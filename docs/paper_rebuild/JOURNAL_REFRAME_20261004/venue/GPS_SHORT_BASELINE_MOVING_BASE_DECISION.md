# GPS Solutions 是否应转向短基线模糊度固定和 moving-base？

日期：2026-10-04。结论是：**该方向具有 GNSS 研究价值，但不能靠改写原 V3 来成立；当前优先保留原 V3 的条件融合论文，新载波/moving-base 方向应另立研究身份。** 正式算法名称正在重新讨论，此处原有 LegSA-GINS 仅作历史/暂用读者名。本文件没有执行新科学矩阵、重跑 V3 或修改科学结果。

## 1. 先拆开三个常被混称的过程

|过程|真正求的量和实际证据|原 V3 的角色|
|---|---|---|
|接收机绝对 RTK fixed|上游接收机用改正/载波求位置；fixed 状态不公开完整正确性证明|V3 消费已生成的位置/速度和状态，不在自身状态中重做该 AR|
|solution-level 双接收机位置差 heading|同一刚体的两端位置在精确共同 iTOW 作差，经安装/坐标转换输出投影方向|这是原 R5/A1 输入合同；两端 carrSoln=2 用作准入，非错固定率验收|
|moving-base 载波差分/整数解|同一移动刚体的基站端/流动端载波观测建立相对基线，估 float ambiguity，再整数搜索/验证，可含已测刚体几何和 INS 约束|本方法不能据已有 solution-level 差分宣称内部具备；后续 raw EXT 是另一个比较身份|

“天线之间的相对向量在移动”是物理描述；“接收机运行 moving-base 模式、交换并处理相对载波改正”是设备/数据链事实；“论文提出新的 constrained integer estimator”又是算法贡献。三者不能用一个词替代。以 u-blox 官方手册为例，moving-base 的观测交换、时匹配和 RELPOS 有其协议/有效性要求；该手册只解释概念，**不证明本项目现场使用该接收机型号、固件或链路**。[制造商官方手册 §3.1.5.6](https://content.u-blox.com/sites/default/files/ZED-F9P_IntegrationManual_UBX-18010802.pdf)

## 2. 该刊并不要求为了投稿强行添加 AR

GPS Solutions scope 包含 GNSS 数学、算法、数据分析、硬件和新应用。因此，一个明确且证据充分的短基线融合问题可以符合 scope。是否足够新是文献/审稿判断，不能把“刊物名称有 GPS”解释成必须发明整数搜索。[官方 scope](https://link.springer.com/journal/10291/aims-and-scope)

现有框架更稳的英文问题是：

> **GPS-RQ1.** Under what projection, receiver-quality and timing conditions does a solution-level lateral-baseline heading observable remain useful for a legged-robot INS?
>
> **GPS-RQ2.** When does robot-reported horizontal velocity add useful information after its heading dependency and shared GNSS lineage are made explicit, and where does that benefit disappear?

这两个问题可以利用原全矩阵、真实三序列、真实失败与已闭合单模块诊断解释。6,468 个任务是条件实验矩阵，不是 6,468 个独立采集；它的注册/可追溯性支持结果可信，不自动证明模型新颖或绝对精度。

现有 GPS 叙事仍要补齐实体输入事实和针对拟推广域的验证，不是“已有审计即投稿 ready”。它不需要为了消除每个工程小问题而改写/重跑原 6,468 个结果。

## 3. 新 AR 方向已经有哪些高度相关先行工作

|primary 文献|已经回答了什么|本项目不能借此声称什么|
|---|---|---|
|Teunissen (2010), GNSS compass constrained ILS|把非线性基线长度约束纳入整数目标与搜索；短基线搜索几何本身可复杂|“加入固定长度/LAMBDA”是新方法；对已固定坐标作差等同实现其载波模型|
|Verhagen & Teunissen (2013), ratio test|固定临界值不足以无条件控制不同模型中的失败率；提出 fixed-failure-rate 模型驱动检验|BOTH_FIXED/ratio=某常数就是已校准成功率；模型内概率自动等于现实多路径风险|
|Farkas, Rózsa & Vanek (2024)|多天线 raw code/carrier/Doppler 与 INS；quaternion-constrained AR；速度+角速度观测同步；车辆实测|仅“把 INS 和模糊度一起做”“用完整动态同步”足以区分；该论文车辆/平台结果保证本机器人同样成立|
|Wu 等 (2024) EGU conference abstract|moving-baseline 长度约束纳入相对定位整数目标，有模拟/实测声明|仅约束长度延伸到相对定位就是未被探索；摘要当成全文实现/完整复现|
|Liu 等 (2026-09-30)|残差特征与 ML 的困难环境 ambiguity validation；不同真实数据域验证|“用 ML 判断固定”自然是空白；其数值复制成我们硬件的风险证明|

来源：[Teunissen](https://doi.org/10.1007/s00190-010-0380-8)、[Verhagen/Teunissen](https://doi.org/10.1007/s10291-012-0299-z)、[Farkas 等](https://doi.org/10.1007/s40328-024-00441-2)、[Wu 等摘要](https://doi.org/10.5194/egusphere-egu24-23)、[Liu 等](https://doi.org/10.1186/s43020-026-00216-w)。本次实际阅读范围在配套 CSV，不声称完整阅读所有文献或证明全球唯一新颖性；付费/失效 PDF 未取得时仅用出版社/作者机构摘要支持有限结论。

2010 的典型载波模型是 y=Aa+Bb+ε、a∈Zᵐ，b 为三维相对基线。固定长度约束进入 mixed integer objective，而不是滤波器已求位置后再改变一个 yaw STD。若宣称新 AR，必须展示 ambiguity 状态、float 联合 covariance、integer candidates、验证/拒绝、cycle slip/重初始化及实际观测模型；代码中一个名称相似的 module 不够。

## 4. 10 个候选问题，以及为什么不全部启动

这里用三种发散思路：现有证据缺口（G）、拆开隐藏假设（A）、将测量问题迁移到 GNSS 准入（T）。这是方向筛选，不是完成实验或给新颖性作量化评分。

|候选|可证伪问题|已有文献/资源限制|建议|
|---|---|---|---|
|G1 条件 heading 可用性|是否能用几何、同步和质量条件解释融合有用/失败域？|原矩阵与失败账本已有；实体条件仍缺|**当前 GPS 主线**；先加强物理输入和作用域，保留原 V3|
|G2 速度的信息增量|heading 有效/失效时，独立 RD 与 SDK 辅助是否真的被调度并改变结果？|已有 135 accepted-domain 与负结果；RV/RD 非独立|当前 GPS 次问题；不能变成全 GNSS outage 桥接主张|
|A1 uncertainty-aware 几何约束 AR|已测基线/安装的不确定度加入准入，是否比把长度当精确常数更可信？|constrained ILS 已成熟；需独立几何、输入 covariance、强 baseline|**新载波研究候选**，新意待更多全文比对和验证|
|A2 动态时差+几何联合可用域|短横向投影下，时差/旋转是否改变固定解的实际可用域？|DBOS 已有；需实际 clock 证据，不能以已有同步复制为创新|可与 A1 合并；不是单独新算法的充分理由|
|A3 INS prior 的重复计数|用于 AR 的姿态/速度 prior 与 GNSS是否共享信息，忽略 cross 是否偏乐观？|已有多传感器 AR；需明确更新顺序和 prior 信息出处|适合 TIM/GPS 交界问题；当前来源不明先登记|
|T1 projected heading 的误差风险准入|整数验证通过，但投影方向 uncertainty 超目标时应如何拒绝？|方向可用域与 AR风险不同；目标须前注册|并入 A1；先声明角度被测量，不追求赢固定率|
|T2 连续协方差+离散错固定层|conditional small noise 能否覆盖大错固定模式？|ratio/integer aperture/新 validator已有；需可信正确/错误标签|新研究的验证层，不可零成本追加保证|
|G3 相同原始信息的构造比较|solution-level、relative-carrier、直接基线因子在公平合同下如何区别？|目前比较输入层次/物理点/初值不同|以后真实构造实验；当前不写 solver 排名|
|A4 纯完整 outage 外推|去掉全部 GNSS 后 SDK-HV 能否独立桥接？|现 HV依赖heading，故域不成立；SDK内部信息未知|不作为当前主张；须新增独立传感器/接口事实才能开展|
|T3 稀少大错的尾部风险保证|有限真实采集能否支撑非常低的 wrong-fix 概率？|单次/密集相关历元不能证明罕见风险；强模型/样本要求|当前不承诺安全完整性；保留为远期研究|

收敛为：**当前完成 G1+G2 的条件融合论文；若作者确实希望 GNSS 载波为中心，则另建 A1+A2+T1 的量测可用性研究。** 两条不能通过混装旧表来互相替代，也不同时开十个方向耗费资源。

## 5. 新方向的一页提案（尚未执行）

候选工作名仅描述问题：**Uncertainty-aware availability of short moving-baseline GNSS heading under geometric and temporal constraints**。它不是已经接受的算法正式命名。

英文问题：

> **GPS-NEW-RQ.** Can uncertainty-aware geometric and temporal admission of short moving-baseline carrier-phase heading improve usable heading availability at a prespecified empirical reliability target across tilt and signal degradation, while retaining all rejected and missing epochs?

待检验假设：在相同载波信息、同初值/物理点/时间支持下，明确考虑基线/安装/时差误差的准入，能减少误导性 heading 被采用；它可能牺牲固定率，却提高可用输出的风险—覆盖折中。若在独立验证域没有改善，或者区间仍明显欠覆盖，就否定该假设，而不是把失败分段删除。

**最低数据准入：**两接收机可识别的 code/carrier/Doppler 观测、星历/信号与 wavelength 身份、共同/异步历元和硬件状态、slip/lock/half-cycle 等有效性；若设备走 moving-base 协议，另锁实际改正流/固件/配置。已存在 raw EXT 证明某个适配链运行过，但不证明新载波模型要求的每个字段/clock/几何已经满足。本研究先做字段/身份可用性登记，缺项明确标识，不能从 status 或上游 fixed 反推。

**最低物理记录：**独立量测三维基线和安装轴及其不确定度；clock 的事件/偏移/漂移/延迟；用于 heading 正确性验证的独立或可识别相关的测量链；不把名义 0.350 m 或从 RTK 记录得到的约 0.356 m 中位数称为 surveyed phase-center length，不按评估成绩改长度/符号。

**基线比较：**至少按实际输入匹配选 unconstrained ILS、已发表 constrained GNSS compass/attitude 方法、原预处理位置差 heading 和候选准入。若复制 Farkas 的联合同步支路，明确其作用条件。比较必须有完整实现/真实执行和参数出处；不能让某个 baseline 只保留模块框架，或者对其中一个额外分段/重初始化后仍称同输入排名。

**预先固定的指标：**全部注册历元的 float/fixed/rejected/missing、usable heading、错误固定/大角偏差事件、复固定时间和每次尝试延迟；own-valid 与 common-valid 分列；用相同目标量及物理点。正确/错误标签的获得方法和参考 U 单列，未知时不能报真 correct-fix rate。故障后新初始化和 prior-only 输出不能当动态桥接成绩。

**统计单位：**独立采集/安装/环境是外推单位；同一轨迹多注入用于条件敏感性。稀有错误概率若要报告统计上界，先规定独立试验和模型假设；“零观测失败”不是零概率，序列相关历元不能直接当独立 n。

**验收标准：**实现与观测合同可审查；物理参数与验证有证据；失败分母不删；按前注册 reliability/availability 目标报告包括负结果；候选在未参与调参的域完成公平比较。上述是研究设计判断，不是 GPS Solutions 规定所有稿件必须实现这些 baseline 或重跑所有旧实验。

## 6. 当前稿件/PPT怎样讲，怎样不讲

可以讲：

> We study the conditions under which a solution-level heading derived from a short lateral antenna baseline can aid low-cost inertial navigation. Velocity aiding is evaluated within its actual heading-dependent admission domain. The retained V3 results quantify agreement with a commercial fusion reference sharing GNSS input lineage.

不能讲：原 V3 提出 quaternion-constrained AR；两接收机 fixed 保证全窗正确；外部 large error 证明该文献方法普遍失败；新分段 Oi 替代严格 H0/O55；SDK-HV 不依赖 GNSS；共享参考 RMSE 是校准绝对 accuracy。

汇报应先展示量与输入，再展示实际结果和失效域，最后展示“下一项可验证的问题”。三张假设敏感性图用于解释数学，不混入实验结果表。若选择新 AR 方向，明确“未来新增研究”页面与原 V3 方法/原矩阵页面分开。

**最终方向判断：现有证据允许继续写条件融合；真正转向内部 AR 需要新增研究。是否值得转向，应看实体数据和验证链是否能获得，而非因为旧 FGO/EXT分数不好就换论文故事。** 当前两条投稿路线都仍有真实材料与制作缺口，不宣布投稿就绪。
