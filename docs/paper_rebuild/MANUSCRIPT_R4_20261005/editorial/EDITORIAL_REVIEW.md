# Reader-first 独立稿件审查：从抽象标签回到观测机制与可解释效果

## 结论与推荐主线

r3 并非没有技术内容；其主要问题是最能证明价值的结果没有进入主要论证。正文反复使用“conditional”“complete”“declared”等组织性词汇，却用方向计数代替效果量、用完整矩阵规模代替科学问题、用限制说明代替对观测机制的解释。读者能知道作者很谨慎，却很难马上知道哪条观测实际改变了什么、改变有多大，以及为何只在某些信息条件下有效。

**推荐的唯一主线：在约 0.35 m 横向双接收机基线提供可用航向的条件下，机身倾斜与 SDK 水平速度如何分别改善姿态和导航，以及这些辅助在何种信息损失下失效。** 这是一篇解算层 GNSS/INS 观测组织和具体场景评价论文；传统误差状态滤波器是实现载体。标题可暂作 *Conditional Robot-State Aiding with Short-Baseline Heading for Quadruped GNSS/INS*，最终方法名仍由作者讨论。

最清楚的三条证据是：

- 三个自然记录中，无在线航向更新配置与完整配置的航向 RMSE 分别为 8.090→1.886°、7.137→1.934°、5.739→2.434°。这是完整配置之间的描述性差异，包含多项变化；所有配置都有双接收机航向初始化，不能表述为完全不使用双接收机信息的对照，也不能把全部差异归因于某一项辅助。
- 原 V3 的 519 个共同完成 CORE 配对中，加入 SDK 倾斜先验后，roll 和 pitch RMSE 均在全部配对中降低，中位配对差分别为 −1.072003° 和 −0.663803°。这比“more consistent attitude effects”更直接说明哪项辅助最有稳定效果。
- 原 45 案例 ADDENDUM 中，20 s 平移观测失效而航向保留时，完整配置与禁用 SDK 水平速度配置的**全 274 s 窗口**水平 RMSE 中位数为 0.240759 与 7.960869 m，中位配对差为 −7.749902 m；9 个位置均改善。20 s 同时失去位置、接收机速度、Doppler 和航向时，两配置中位数却为 10.292008 与 10.300694 m。这组正、负证据把“条件式辅助”变成可解释的结果，不需要声称新的模糊度求解器。

这些数据来自原 V3，不是后来 135 次 IMU 诊断子集；完整原 V3 身份为 source `7d43b9af26120ed5dde21f53e515386361072ba6`、binary `96ae436d82ba8922c68382bd73fc42c8bf4bcb22d72a43a8bd05f506043a9c1c`、evaluator `aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da`。全部原始值、配对与失败表见本目录已封存的 `EFFECT_SIZE_READY.json` 和相邻 CSV。

## GPS Solutions 与 TIM 的实质判断

GPS Solutions 的公开范围包含 GNSS 模型、算法、数据分析和有挑战的应用，不要求每篇论文提出新的整数模糊度算法。因此，当前证据可以支持一篇有明确观测机制、适用条件和负结果的紧凑机器人 GNSS/INS 应用与评价稿。**但是创新幅度必须说实：**EKF、解算位置差航向、残差门控、协方差膨胀均不是单独的新理论；本稿应以小基线、低速机器人上可复现的观测组织和受控失效对照为贡献，不能凭 6468 次运行宣称基础滤波理论创新。[GPS Solutions scope](https://link.springer.com/journal/10291/aims-and-scope)

TIM 的当前作者要求强调仪器与测量的主要贡献，并明确 RMSE 不等同于仪器测量不确定度。r3 增加了正确的一阶传播和交叉协方差结构，但接收机误差相关性、安装、SDK 速度测量点、时钟偏差/漂移/延迟及参考交叉项仍缺乏实际辨识。这些公式可以构成讨论和下一步实验设计，不能单独把现有应用结果升级为“已校准测量不确定度”论文。若仍选 TIM，应先回答具体测量问题：哪一项测量链特征被实际识别，提出的处理如何改进其可靠性，如何用独立或已量化的验证链验证该改进。[TIM author information](https://ieee-ims.org/publication/ieee-tim/information-authors)

**当前不宜作为主线的两项：**

1. **新的约束模糊度求解/高可靠整数固定方法。** 原 V3 直接使用接收机输出的位置和状态，未执行新的整数候选搜索、联合基线约束或错误固定概率控制。C-LAMBDA、C-WLS、DD-KF 和 RTKLIB 是另行比较的路线，不是原方法内部新贡献。固定状态也不能代替已知真实方向下的整数正确性验证。
2. **完成物理标定的不确定度、完整性或独立厘米级准确度。** 工作 R、滤波 P 与共享参考差异 RMSE 具有不同含义。未辨识的相关性和时间/安装项不能被“完整预算公式”替代。可以准确报告 reference agreement、经验误差和失败支持，不能据此声称 calibrated uncertainty 或已保证完整性。

## 十二处最影响稿件质量的问题及具体改法

以下定位针对冻结 r3：GPS 201 行，TIM 223 行。引文均为原句片段；建议句是可用于改写的原创草案。先修论证，再润色语言。

### 1. 摘要和贡献以组织词替代科学结果

**原句：**GPS/TIM L5 “We investigate conditional heading and velocity aiding”；GPS L19/TIM L19 “Its contribution lies in the specified observation admission, the conditional organization of auxiliary observations and an evaluation retaining the full registered outcome set.”

**问题：**“specified/conditional/complete”描述稿件组织和执行纪律，不告诉读者哪个估计量改变、效果有多大。摘要中“negative vertical and heading effects”没有量级，容易把微米级垂向中位差与米级故障收益放在同一重要性上。

**具体改法：**摘要保留一条输入/方法句，接自然结果、倾斜配对结果和 D62/D61 对照。贡献按“观测依赖建模→配对姿态效果→信息损失下的成功与失败”组织，矩阵规模放实验设计一句。

> Robot-reported tilt lowered roll and pitch RMSE in all 519 common-completed pairs, with median reductions of 1.072° and 0.664°. When a 20 s loss removed translation observations but retained heading, horizontal-velocity aiding reduced the median whole-recording horizontal RMSE from 7.961 to 0.241 m across nine placements; it provided little benefit when heading was also removed.

**证据：**`ORIGINAL_V3_COMPONENT_EFFECTS_EXACT_28.csv`、`ORIGINAL_V3_ADD_HV_WHOLE_WINDOW_BY_DURATION.csv`。这里“whole-recording”必须说明原案例固定 274 s 窗口，不是故障内部 RMSE。

### 2. 引言提出困难，却没有把困难连到本文真正处理的环节

**原句：**GPS/TIM L11 “The small antenna separation, however, makes the direction sensitive to errors in the difference of the two antenna positions.”

**问题：**这句话正确，但下一步立即进入泛泛的同步、状态、物理含义。应明确：本文处理的是接收机解算输出进入滤波器的资格和作用，并不是解决所有小基线模糊度问题。

**具体改法：**引言第二段画清短基线方向→航向更新→SDK 速度旋转→导航约束的链条，把可检验的两种失效置于段末：方向不可用时不应依赖由其旋转得到的速度；仅平移 GNSS 观测失效时，已有航向可能维持速度辅助资格。若用小误差公式解释短基线敏感性，明确它是几何灵敏度，不是实际不确定度预算。

> A short baseline increases the sensitivity of its projected direction to differential position error. The issue studied here is how this receiver-output direction is admitted to the navigation filter and how its availability conditions the conversion of robot-reported velocity, rather than how carrier ambiguities are newly resolved.

**证据：**r3 Method 2.3–2.4 与原 ADD 的两种信息损失。新颖性不能仅建立在已知长度或同步本身上。

### 3. 最近的双接收机比较方法没有形成可辨认的文献与机制对照

**原句：**GPS L113/TIM L137 “The two-receiver IEKF is the closest receiver-output comparator, while its project-parameter variant is retained separately.”

**问题：**正文没有在参考文献中给出这条最近路线的 Pavlasek–Walsh–Forbes 论文，读者不知道它利用相对位置和交叉协方差约束姿态的具体方式。相反，较远的 AR 和多条适配路线占据较长说明。

**具体改法：**在 Related work 或 Methods 的比较表用一段说明：两接收机 IEKF 联合绝对位置与相对位置约束姿态；绝对/相对误差有共享接收机交叉项。与本文的“两个位置生成标量方向，再进入常规 ESKF”相比，这是状态和观测组织的区别。报告全窗 yaw 与支持，不宣称数值差直接证明某种滤波理论优越。

**引用：**Pavlasek N, Walsh A, Forbes JR (2021), *Invariant Extended Kalman Filtering Using Two Position Receivers for Extended Pose Estimation*, DOI [10.1109/ICRA48506.2021.9561150](https://doi.org/10.1109/ICRA48506.2021.9561150)。本轮自行核验作者原始记录的标题/作者/摘要；具体原文方程与项目合同映射继承同组既有审查，不冒称本轮重新阅读全文。[Author preprint](https://arxiv.org/abs/2104.14711)

### 4. 门控和权重给了形式，却没有给可复现的实际规则

**原句：**GPS L55/TIM L55 “Boundary comparisons and covariance factors follow the frozen rules.” GPS L75/TIM L75 “The complete factors, cap and branch identities are supplied in the supplementary configuration table.”

**问题：**r3 中 Supplementary 表只有条目安排，无法由正文或实际附表复现边界相等时的分支、软区 2.5 倍 R，以及创新评分的自由度归一化和各源 α/cap。读者不应去软件收据中猜测方法公式。

**具体改法：**正文给紧凑分段：marker σ 下限 0.5°；normal 为 σ<3° 且 |rψ|<6°；hard 为 σ≥6° 或 |rψ|≥15°；其余 admissible soft 区将航向 R 乘 2.5。另给正式创新评分 `z=sqrt(rᵀS⁻¹r/d)` 和六源 α/cap 小表：P .00003/5、RV .04/8、yaw .03/10、RD .35/15、RP .02/10、HV .03/10。deadband 1.5，二次增长及 2.5/4 的追加因子 1.2/1.6，最终采用有界 max 倍率，不减小基准 R。全文不用把历史 QA11E robust 形状当成正式新算法。

**证据：**原 V3 方法故事与冻结源码映射；这是原有规则的说明，不修改源码。正常区“within”不可含混包括阈值本身。工作 marker/R 不能称为校准标准不确定度。

### 5. SDK 辅助最重要的依赖藏在密集变换公式后面

**原句：**GPS L63/TIM L63 式(5)的 `Ĉ=Rz(ψA)Ry(-θSDK)Rx(φSDK)M`；GPS L67/TIM L67 “Robot tilt and horizontal velocity also enter through the GNSS update scheduling entrance.”

**问题：**读者容易把 SDK 水平速度理解成独立腿里程计，并误以为完整 GNSS 中断时仍单独执行 RP/HV 更新。旧 provider 使用准备阶段 A1 航向和 SDK roll/pitch 的工程旋转，A1 投影角也不能在非零倾斜下直接解释成真实 Euler yaw。

**具体改法：**给一张信息依赖图：接收机配对方向和有效性→HV 准备；SDK roll/pitch→RP 和 HV 旋转；有效的启用 P/RV/yaw 之一→原 GNSS 调度入口→RP/HV 可执行。图中把准备资格与运行时调度分开，并在 D61/D62 结果旁重新标注存活的观测。注明不是关节/足端运动学或接触观测；SDK frame/实际 POI 未由公开接口完整确认。

> The horizontal aid is a transformed robot-state estimate, not independent leg odometry. Its prepared value requires heading support, and its runtime update remains subject to the archived GNSS scheduling entrance.

**证据：**原 Method 2.4、选择故事与 ADD 条件。不得把 provider 时间域的有效行计数直接叫成实际 dispatch 次数；此处也不借后来 IMU 修复改变旧行为。

### 6. 自然结果只列完整方法，不能回答“比什么改善了多少”

**原句：**GPS L121/TIM L145 “The proposed configuration yields heading RMSE between 1.886 and 2.434 degrees”；GPS L123/TIM L147 “The backbone and unweighted configurations yield nominal yaw agreement close to the full configuration.”

**问题：**全文只见完整配置三组值，参照意义不足。与此同时，“close”没有显示完整配置相对 gated+RV 骨架的航向增益非常小，BY2O 甚至略差。应把主法和有解释力的基线放在同一实际表中。

**具体改法：**主表至少列无在线航向、gated+RV 骨架、完整方法的三序列 H/yaw/support。F01 的 yaw 为 8.089647/7.137488/5.739038°，F03 为 1.915591/1.940801/2.432184°，完整为 1.886272/1.933770/2.433815°。说明完整方法自然窗口的主要航向改善来自完整配置对无在线航向结构的区别，额外辅助价值要由单变量配对和故障条件检验。F02→F03 同时改变 RV、heading 处理和算法分支，不可作为纯 RV 因果效应。

**证据：**全 33 行自然原 token 表。完整方法 H 在 BY2/BY2H 不低于 F01；不得把自然表写成各指标普遍占优。两者都有双接收机初始化。

### 7. HV 的方向计数掩盖量级，还夸大了微小的垂向代价

**原句：**GPS L135/TIM L159 “Enabling robot horizontal velocity lowers horizontal RMSE in 472 of 519 pairs. In that same cohort, vertical RMSE is higher in 365 pairs.”

**问题：**472/519 是方向，不是效应大小；365 个“更差”也不表示重要的实际误差损失。HV 的 H 中位/均值改善是 1.119/10.651 mm；Up 中位差只有 +0.004215 mm，而均值反而为 −0.603775 mm。不能据方向计数在摘要强调笼统的 negative vertical effects。

**具体改法：**正文以 H 配对中位与均值、Up 量级和全分布说明其常规影响较小且异质。米级价值放到 D62。mean/median 都基于共同完成的 519 对；另外单列两侧完成差，避免以失败缺值构造均值。

> Under the CORE conditions, horizontal-velocity aiding produced a median horizontal-RMSE reduction of 1.119 mm and a mean reduction of 10.651 mm. Although vertical RMSE increased in 365 pairs, its median change was only +0.004 mm; the mean change was −0.604 mm.

**证据：**`ORIGINAL_V3_COMPONENT_EFFECTS_EXACT_28.csv`。这里不是新计算 in-fault 指标，也不增加显著性检验。

### 8. RP 是最稳定的单模块姿态证据，却被一句泛语带过

**原句：**GPS L137/TIM L161 “The robot tilt prior yields more consistent attitude effects in the registered cases.”

**问题：**这句话隐藏了全 519 配对 roll/pitch 都改善，以及量级明显大于若干其他模块的结果。也没有说明两个轴的单独观测，不是新的腿运动学滤波器。

**具体改法：**独立短段介绍 roll/pitch 两轴先验的作用，并给两面板配对效果图。正文写 519/519、median −1.072003°/−0.663803°，必要提供 mean −1.789550°/−1.026838°，不要拿同一录制上的受控 placement 当作 519 次独立采集。

> Robot-reported tilt provided the most consistent attitude improvement among the one-switch comparisons: both roll and pitch RMSE decreased in every common-completed pair.

**证据：**28 行原配对汇总中 RP 的两个轴；初始化和参考关系与其他原案例一致。这是相对当前融合参考的配对结果，不把 SDK 倾斜输出宣称为校准真值。

### 9. “substantial benefit”没有列出最能支撑主线的 D62/D61 对照

**原句：**GPS L141/TIM L165 “When heading survives position-related loss, ... [the aid] can provide a substantial horizontal benefit.”

**问题：**正文缺少时间长度、9 placements、实际误差和负对照。读者无法判断“substantial”是 1 mm 还是 8 m。D62 不是 heading outage；D61 的失败不是证明 SDK 没有速度，而是原资格/调度设计在此条件下不提供独立更新。

**具体改法：**给全部 5 个预定组，不选好的窗口：D61 10/20/30 s 和 D62 10/20 s，各 9 对。主文重点解释 D62 20 s 的 noHV 7.960869→full 0.240759 m，以及 D61 20 s 的 10.300694→10.292008 m。配对中位差 D62 为 −7.749902 m，**不是两边中位数相减**；统计覆盖全固定 274 s 案例，不可命名为 outage RMSE、终点误差或 recovery error。

**证据：**全部 45 原 ADD pair ledger 与 5 行 duration 表。原 495 行均完成；不以新 135 诊断结果替代原版本。

### 10. SA、RD 的角色需要用完成差和幅度解释，而不是“一致/混合”标签

**原句：**GPS L137/TIM L161 “Doppler and covariance inflation have more mixed patterns.”

**问题：**这个标签错过两种不同角色：RD 的普通 H 中位效果约 0.145 mm；SA 使原 CORE 多 6 个案例完成，却在共同完成案例 H 中位上变差约 0.981 mm、均值变差 24.245 mm。只报多数方向会掩盖 SA 的完成/尾部与精度权衡。

**具体改法：**RD 保持独立观测身份和来源相关性，简短报告小幅常规增益，不把它写为主要突破。SA 的结果段先写 complete：full 519/541、SAoff 513/541、6 个 full-only completion；再写 common-completed 513 对的 H 分布与 yaw 异质性。NA 失败不能改成有限罚分混入 RMSE。

**证据：**`ORIGINAL_V3_CORE_OUTCOMES.csv` 与 28 行配对表。该六源工作 R 政策不构成已识别真实异常原因或标定 fault probability。

### 11. 外部比较主段以身份解释为主，缺少“同路线怎样比较”的读者表

**原句：**GPS L147/TIM L171 “The selected raw-observation compass adapters produce large angular discrepancies and varying valid support”；GPS L151/TIM L175 最后一句 “not a same-input solver ranking”。

**问题：**这些边界必要，但占比过高；“large/varying”没有直接量化。应先给读者一个分层比较表和最接近的 IEKF 结果，再解释不同输入的限制。输入差异尚未关闭时，差结果只支持本工程条件下效果不足，不支持作者算法一般不适用。

**具体改法：**主文表列方法读者名、主要输入、是否自行估计姿态、比较物理量/点、fresh support/expected、误差合同；IEKF 是接收机解算层最接近路线。RTKLIB 四个冻结条件必须把 fresh 与 held 分开；C-LAMBDA/C-WLS/DD-KF 为作者核心的独立适配，保留原全池拒绝等工程策略说明；严格连续 OiSAM 和后来 segmented OiSAM 分栏，Wen/GNC 无自行估计 yaw 不填姿态名次。Hartley/contact 与 QM robust 模块类不混成完整同输入算法。

**证据：**原全比较 inventory 及最新 FGO 包，具体表的数值由各冻结 provenance 引用。本轮未重新跑所有外部算法。名义 projection–Euler 检查的 RMS 0.031–0.044°、外部 RMSE 最大变化约 0.0043°可作为量级排除证据；它不等于已完成轴、安装和方向独立校准。

### 12. 图、讨论、结论需要承担论证任务，不应让审查说明成为正文结构

**原句：**GPS L121/L131/L135/L141/L147 引用 Fig.3/5/6/7/8；GPS L155 “The main result is the usefulness and limitation of explicitly conditional observation aiding”；GPS L169 大段泛化结论。

**问题：**本轮读取 r3 的两个 DOCX 结构，`word/document.xml` drawing=0、`word/media/`=0；MD 也没有实际图文件与图例。因此 Fig.1–8 尚未给读者真实证据。这个结论只是文档结构检查，**没有声称逐页视觉审查 r3 Word**。讨论再重复 abstract 标签，而技术效果和一组清晰的反例不足。

**具体改法：**使用下方 6 幅主图分工，实际正文顺序是 setup→observation mechanism→natural role→RP paired effect→D61/D62 eligibility+outcomes→SA completion/paired trade-off。安装/共享参考/时轴/跨场景边界放 Discussion 与 SI，不在每段重复同一否定句。结论只用一段给三条量化发现及一种失效机制；资料路径、Git 和逐文件身份收据放可复现附录。

> The heading-supported configuration achieved 1.886–2.434° agreement over the three natural recordings. Robot-reported tilt consistently improved roll and pitch in the paired evaluation, whereas the main velocity benefit appeared when heading survived translation-observation loss. The complete-loss comparison shows that the archived robot aid does not operate as independent outage odometry.

**证据：**r3 DOCX 结构与已封原 V3 数值；不凭尚未展示的图宣称支持某项结论。

## 从三篇用户原论文学习的论证方式

本轮由同组 `venue_readiness_audit` 实读用户提供的三篇全文共 37 页，并实际查看 16 个图页；我完整读取其 `paper_models/THREE_PAPER_WRITING_MODELS.md`。以下继承的是其具体阅读结果，不称为我本轮重新读过这些 PDF。

- **Chang et al. (2021), DOI 10.1007/s10291-021-01148-5：**先把动态跟踪和稳态精度的不同问题对应到因子机制，再用指定时段误差和因子变化解释效果。可借用“失效→作用接口→指定结果”的结构，不能把本文 R 膨胀写成他们的新 fuzzy strong tracking filter。
- **Jiang et al. (2021), DOI 10.1007/s10291-021-01165-4：**不是新 AR；同一 CKF 骨架下讨论 adaptive/fading 作用位置，并比较位置/速度/姿态和 innovation 行为。它说明具体模型作用与公平对照可以形成论文主线。本文应突出真正单变量的 RP/HV/RD/SA 配对，不能把 F02→F03 联合变化装成纯 RV。
- **Wang et al. (2020), DOI 10.1109/TIM.2019.2955798：**将噪声失配、outlier 和 GNSS outage 三个问题分别对应到 TC、robust 和 NHC，再给实际实验和负面现象。可借用此种闭合机制链，不能把车轮 no-slip NHC 当成 Go2 SDK 速度的物理前提，也不能把其旧刊发表视为当前 TIM 不确定度要求的豁免。

详细出处、阅读范围和原图角色以相邻 `paper_models` 报告为准。这里不搬用他文的性能数值作为本项目证据。

## 六幅主图的证据分工

| 图 | 图的唯一问题 | 面板与实际来源 | 可以支持的结论 |
|---|---|---|---|
| 1 | 测到什么、在哪个点、如何进入估计器？ | 同一实际安装照片/尺寸与 frame；六观测输入和输出点图；SDK 与 receiver/reference 不同角色 | 具体测量与处理链；名义 CAD 尺寸不能冒称独立外参标定 |
| 2 | 什么条件决定航向和 SDK 辅助可以更新？ | 原规则 piecewise 门控；准备资格/dispatch 分层；已有记录的状态/残差示例 | 算法机制与可复现资格规则；不由 REJECT 单独识别物理故障 |
| 3 | 在线航向在三个自然记录中起什么作用？ | 原 F01/F03/full 的 H/yaw 表与 signed trace；每序列全窗、支持条带 | 自然记录上配置角色与接近程度；不是单模块因果或独立绝对真值 |
| 4 | 哪项 SDK 姿态辅助效果稳定？ | 原 RP common519，roll/pitch 配对差分布；mean/median/完成数 | 姿态作用的量级与异质性；placements 非独立现场试验 |
| 5 | SDK 速度为何在一种故障有用、另一种无用？ | D61/D62 存活观测矩阵；全部5duration×9placements的 H-RMSE points；whole274s固定合同 | 本稿最强机制结果；不将全窗 RMSE 叫成 in-fault/endpoint |
| 6 | 有界协方差政策改变精度还是完成？ | 全11方法 completion/divergence/noheading；SA common513/H与yaw差；RD/HV附带量级 | 完成/精度权衡与所有结果保留；不是全部模块普遍增益 |

外部输入层、fresh/held 和 FGO strict/segmented 的完整比较表优先放正文一张紧凑表及 SI，避免抢占以上科学主线。地图若用于路线展示，必须沿既有冻结轨迹解释空间环境和故障 placement；未给出实际遮挡/反射/城市环境证据时，不能仅凭地图把序列冠以 “urban canyon” 或独立复杂环境。不要为图好看重新选择轨迹范围或对齐偏移。

## r4 快速审查与本次边界

在本审查收口前，我完整读了 root 新写的 `manuscript_gps_solutions_r4.md`（当时 252 行）。它已把 RP 的姿态幅度、D62/D61 的全窗中位对照、SA 6 个额外完成案例、自然结构基线和实际方法参数写入真实表格，删除空置 Fig.1–8 引用，并正确区分方向计数与量级。**未发现原 V3 数值或 D62 航向保留条件的阻断错误。**已向 root 发送三条精确措辞建议：normal 区用严格 σ<3° 且 |rψ|<6°；评分明确 `sqrt(rᵀS⁻¹r/d)`；自然结果用 “recorded-window agreement with the reference”。r4 由 root 继续修改，我不改该文件或给它签最终冻结身份。

### r3→r4 已修复与仍需闭合的区分

| 问题组 | 本轮读到的 r4 状态 | 后续是否还需要科学新证据 |
|---|---|---|
| 摘要/贡献没有量化发现；自然结构基线未展示 | 已把三类具体结果及自然结构基线写入正文；贡献不再只围绕运行规模 | 现有数字可支撑描述性结论；方法新颖性仍需按具体接口与最接近方法论证 |
| RP/HV/RD/SA 只有方向计数 | 已给中位/均值量级、SA完成差和微小负效应说明 | 当前配对数值闭合；跨记录/平台泛化需新采集，不能由placements数量代替 |
| D62/D61 “substantial”无数值 | 已给全部5组实际表，正确区分保留heading与complete-loss，并用原whole-window合同 | 现有原V3足以解释该资格链；无需把135或新in-fault指标替进原表 |
| 正式门控/创新倍率缺实际参数 | 已新增规则、α/cap表和评分；精确边界/归一化三条建议已交root | 参数说明修正即可，不需重新估计或改变原V3 |
| 最近的双receiver IEKF缺引用 | r4已补实际作者参考，F02→F03联合结构差仍保留 | 对照机制/输入表还应清楚；数值差不是IEKF理论优劣证明 |
| Fig.1–8引用未对应实际图 | r4已去掉空图引用，用5张真实数值表；root另完成Word版面QA | 最终科学图件/正文图例仍应逐一绑定证据；本报告不代替root的版面验收 |
| 外部差结果和名义量检查 | r4给出了fresh-support及路线差异，保留约0.0043°量级检查 | 轴/安装/独立truth等实际未闭合项仍不能用措辞宣称解决 |
| TIM的U传播公式尚无实际输入辨识 | GPS r4不再依靠这套公式充当已完成新方法 | 若转TIM，测量链特征辨识及实际验证是实质新增工作；语言润色不足以替代 |

因此，r4在本轮提出的主要内容缺口上已作实质改进。剩余重点不应再演变成原V3重跑或微小参数纠错：一是把观测机制和上述效果配成读者能看懂的真实图表，二是把尚无证据的测量与泛化主张限定到现有事实范围，三是决定GPS应用研究与TIM测量研究的优先路线。

本轮全部工作均为文本阅读和留存 CSV 的描述性汇总：0 estimator、0 evaluator、0 provider 调用，0 原科学结果写入，0 offset 优化。逐行人工阅读范围与逐条机器数值检查范围在 `EDITORIAL_READ_COVERAGE.csv` 分开记载；矩阵遍历不是全仓每字语义审查。单模块与 ADD 的取值只使用本目录已封存原 V3 数值块。
