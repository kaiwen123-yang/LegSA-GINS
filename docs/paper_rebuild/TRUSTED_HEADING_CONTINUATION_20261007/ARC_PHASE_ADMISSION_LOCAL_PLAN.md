# 相位差局部故障准入与撤销：待审查有限方案

状态：IMPLEMENTED_AWAITING_STATIC_REVIEW_AND_REGISTRATION。已完成新实现与 28 项测试源，
仅作 AST 语法检查，尚未导入、收集或运行测试。根代理已授权实现；执行等待最终冻结 commit。
当前基线 cd81069；已有 arc_phase_difference.py 与 saved-model runner 保持原样。
新增范围仅 src/.../arc_phase_admission.py、tests/.../test_arc_phase_admission.py
和 ARC_PHASE_ADMISSION_*。不读真实模型/raw/reference，不接 native，不搜索整数。

## 1. 目标与资格词义

本轮只证明明确合同下的局部一致性门、不可检测反例及单个 ledger 内的防重用/撤销。
UNKNOWN = 缺 actual availability、误差界/偏差/cross 语义来源等，统计量 NA；
UNRESOLVED = 信息/数值支持不足（例如零 nuisance redundancy 或无法安全白化）；
REJECTED = 声明模型的一致性门失败，或已退休 token/已消费端点的合同冲突；
CONDITIONALLY_USABLE = 在声明局部模型与误差界下两个一致性门均未拒绝。
后者绝不是“无故障”，不生成可信航向、方向点、整数结果或导航更新。
navigation_admitted、phase_fault_proven 均恒为 false；故障漏检概率 NA。

“旧 singleton 无 valid”不代表原始载波信号中断。上一轮 860 块仍要求同物理弧连续，
不作为连续可信航向覆盖或真实物理断载波后恢复证据。

## 2. 明确输入：不暗设零 cross、零 bias 或物理噪声

- 固定 geometry-only contrast，保留每端完整测量身份、真实 available_time。
- 两端 PhaseAttitudeState，显式 body baseline、frame、source 与实际可用时间；
  ECEF 左扰动，误差定义 delta = true − nominal，与现有 core Jacobian 同符号。
- 显式 6x6 两时刻状态 covariance P_cov（含 P01，不能默拼 block diagonal），
  以及状态 mean bias 的外积上界 B_bias >= E[delta] E[delta]ᵀ；
  使用 P = P_cov+B_bias >= E[delta deltaᵀ]，不把任意相关随机 bias 独立相加。
  B_bias=0 也必须由调用方显式声明和给来源，只在零均值假设合格时有意义。
- 相位差误差二阶矩上界 M（m²），非仅 centered covariance；
  必须明确包含未建模 bias 的范围及来源。原 RAWX 工作 Q 不能自动作为 M。
- cross mode 必须显式：
  FULL_DECLARED_CROSS 给 C=E[delta eᵀ|I]（包括均值项，不是模糊的 covariance），
  验证 K=[[P,C],[Cᵀ,M]] PSD。PSD 仅证明声明矩阵代数合法，
  不证明实际 joint error moment 被 K 上界；该物理有效性是调用者声明前提。
  UNKNOWN_CROSS_BOUND 不提供 C，使用任意 cross 的 Young 界；
  不能称 actual cross=0 或 joint covariance 已知。
- 显式原始相位误差界的生效范围、来源 scope、available_time，和状态先验来源。
  输入声明若未 qualified 返回 UNKNOWN；仅 LOCAL_SYNTHETIC 资格不会升级 real。
- 显式 alpha_prior、alpha_projected（均 >0、和 <1），不设默认物理值。
- 显式 deterministic nonlinear/model remainder 欧氏米界 epsilon>=0 及来源。
  epsilon=0 在精确线性合成例可明确使用，不能从“线性化”自动推出真实 remainder=0。
  remainder 有效域必须确定覆盖合同内全部 admissible error；若仅局部有效却缺域内资格，
  返回 UNKNOWN。当前不引入未登记的越域概率预算；精确线性合成可用全域 epsilon=0。
  baseline/安装/geometry/同步等若不在误差界或余项内，不在此门保证范围。

这些矩界须条件于冻结的 geometry、nominal states、支持选择及配置；如果这些量来自
同源数据，不能拿未说明 selection conditioning 的无条件矩冒充对应条件界。
alpha 和来源声明必须在本次 residual 评判前冻结。代码只能校验声明/维度/PSD，
无法认证现实来源或阻止外部先看 residual 后伪造声明。所有界共享同一个显式
conditioning_information_set_id=I，E[wwᵀ|I]<=S(I)；J/S/L/alpha/epsilon 不随当前 r 选取。
两端 nominal state 必须在 freeze 时已实际可用。当前 geometry API 合并 phase arrival、
几何/关系支持可用性，没有独立 geometry-ready 字段，因此保守要求整个 contrast
actual available<=freeze；晚于 freeze 则 UNKNOWN、不消费。这并非要求在 phase 到达前
冻结，而是要求声称条件于 I 的名义状态/几何/支持在 freeze 时已具备。

## 3. 两个门分别推导，避免混用自由拟合与 proper prior

z = F1 y1 − F0 y0，h = G1 R1 b − G0 R0 b，r = z − h；
J = [G0 skew(R0 b), −G1 skew(R1 b)]，r = J delta + e + eta，
其中 ||eta||<=epsilon。没有用当前 r 重新调姿态先验或选择端点。

FULL_DECLARED_CROSS：
S = J P Jᵀ + M + J C + Cᵀ Jᵀ = [J,I] K [J,I]ᵀ。
UNKNOWN_CROSS_BOUND：
S = 2*(J P Jᵀ + M)；
只在 P/M 真正上界对应误差二阶矩时才有效，不需要 cross=0 或跨块独立。

门 A（proper-prior assisted consistency）：
v = ||S^(-1/2) r||，rho = epsilon/sqrt(lambda_min(S))，
T_prior = max(0, v-rho)^2，阈值 m/alpha_prior。
若 E[(J delta+e)(...)ᵀ] <= S，则 E[||S^(-1/2)(J delta+e)||²]<=m，
故 Markov 给 P(T_prior>m/alpha_prior)<=alpha_prior。
这里不减姿态参数个数，不用 chi-square，不宣称错误接纳率。
门失败可能是状态先验、来源界或 phase 的问题，不自动定位为 cycle slip。

门 B（free nuisance residual consistency）：
由 J 的 SVD 得到其左零空间正交基 L，维数 nu=m-rank(J)；
r_perp=Lᵀr，S_perp=Lᵀ S L。用同样形式的统计量和 nu/alpha_projected 阈值。
当 LᵀJ 精确为零时，等价于在 S 度量下自由拟合 nuisance 后检验 residual，而不把 prior 门 m
与 free-fit 门 nu 混用。精确 LᵀJ=0 时 state/cross 项消去；
若数值截断留有小 leakage，仍用完整 LᵀS L 保留 Markov 界，
但不再声称精确 free-nuisance 等价；不把泄漏强行设零。
输出 nu、rank(J)、投影误差 ||LᵀJ|| 和 fault 投影诊断。
alpha 总计用 union bound，两门相关也不假设独立。该保证仅为单次因子在合同内
的无故障模型拒绝上界，不是整段序列风险、故障误接纳率或可信航向概率。

若 S 或 S_perp 在数值上无法可靠正定求解，返回 UNRESOLVED_NUMERICAL_SUPPORT，
不加 floor、不裁掉小方差模式来改善通过率；先求解并核残差，失败不伪造统计。
nu=0 且门 A 未拒绝时返回 UNRESOLVED_NO_RESIDUAL_REDUNDANCY。
有效门拒绝优先返回 REJECTED；其余完整可评估输入才为 CONDITIONALLY_USABLE。
已知零噪声奇异极限本轮保守返回 UNRESOLVED，不强加任意方差使其可用。

## 4. 物理模板与不可检测范围

模板从明确 SD node、端点和波长，经原 F0/F1 形成；target/pivot 共享影响都保留。
模板目录由输入物理节点确定，不读注入 truth、故障时刻或 oracle 标签。
对每个模板 t 输出 ||Lᵀt||、与 col(J) 的相对距离及是否被同一 nuisance 吸收。
数值投影近零仅是局部投影不可检，不说 prior-assisted 门绝对不能发现；
proper prior 若很紧可能拒绝它，但那依赖先验有效性。

必须有精确反例：一个物理 SD 相位阶跃与合法姿态变化产生相同观测，
其模板在 col(J) 内，free-fit residual 为零；宽而合法 prior 门也可不拒绝。
该例强制保留“CONDITIONALLY_USABLE 仍可能含故障”的证据。
弱激励/同几何、两端 baseline 轴 gauge 与共同旋转 gauge 均不消失。
不把 921 块未白化自由-baseline 满秩当作本阶段姿态或检测资格。

## 5. 单 ledger 的端点消费与撤销合同

采用保守 epoch 粒度：canonical key =
(receiver_pair_id,time_scale_id,measurement_time,phase_convention_id)，
不靠可换名的 epoch_id/source_id。同时间不同 pivot/重命名仍视为已用端点。
身份不合法是合同拒绝，不当作物理 fault detection。

在实际检查 r/统计之前做原子 reservation。一次统计尝试之后，无论
CONDITIONALLY_USABLE、REJECTED 或 UNRESOLVED，两个端点都永久消费，
不允许换 alpha/prior、换 factor_id、撤销后复用或再次接受。
尚缺资格/未到 availability 的 UNKNOWN 不计算 r、不消费；不提供中途通过结果。
该边界只能约束此 ledger 内的调用，不能阻止外部绕过入口读数据/另建 ledger。

条件可用记录只在 shadow ledger 中 active，未更新滤波器。
显式晚到来源失效/弧 retirement 事件按物理 token、接收机对和区间绑定：
- break_time 在因子 [t0,t1] 内则撤销相关 active 记录，并发出撤销通知；
- break_time>t1 不自动宣布已完成的旧因子错误，但退休 token 不能参与未来跨断点因子；
- 不确定失效区间按与因子区间相交保守撤销；retire_from_s 是独立的弧终止声明，
  任何使用该 token 且 end>=retire_from_s 的 active 因子均撤销，即便给定证据区间更晚；
- 撤销不释放已消费端点，不在这个模块声称回滚外部滤波器成功；
- 恢复必须是新 token、新端点、新连续性与新误差资格。部分 survivor 可在新因子用；
  同一旧因子的残余部分不自动修改/再接受。
不读取 truth 自动 retire；tests 的注入评估与公开撤销接口分开。
多个不重用端点的 active 因子仍不自动独立，不提供融合权重/后验。

## 6. 有限案例预算：28 个独立合成 case

01 clean/noise-free moving geometry：两个门与独立代数 oracle。
02 有限离散零均值噪声集合：核 E[wwᵀ] 和 Markov 上界，不作 MC 风险估计；
   非零 remainder 用一维 T=9/T=0 手算及有界 eta 的逐点不等式验证。
03 非零 state-source 正 cross：全式与潜变量 oracle。
04 非零负 cross：抵消正确，不能删 cross。
05 完全同源确定性复用/奇异 joint：不伪造额外独立信息。
06 UNKNOWN_CROSS_BOUND：正/负极端均受界，明确不是 actual covariance。
07 非 PSD joint 声明：合同拒绝，无 fault 定位。
08 未界定 bias 或来源不合格：UNKNOWN、统计 NA、不消费。
09 正确包含非零 bias 上界：门仍按二阶矩解释。
10 缺 availability、未来未到达、decision 时虽可用但 nominal/geometry 晚于 freeze：
   UNKNOWN、不消费；不拿 source time 当 actual。
11 零 nuisance redundancy：UNRESOLVED，不能宣告检测成功。
12 弱/奇异 innovation 支持：UNRESOLVED，无 floor。
13 很小但有效噪声方向：不得经尺度截断抹除故障。
14 可检测单 target 整周故障：SD 注入，投影门拒绝。
15 pivot 整周故障：共享多 DD 的实际模板与拒绝。
16 非整周 phase 异常：不依赖整数查找仍可拒绝声明模型。
17 模板在 col(J) 内：姿态吸收，局部 residual 不可检反例。
18 宽 prior 下故障被两门放行：明确条件可用不等于 fault-free。
19 错误/过紧 prior 的 clean 数据被拒：禁止误称检出 phase fault。
20 同几何静止 gauge 与两端 baseline 轴：不生绝对 yaw。
21 坐标/单位一致变换：epsilon=0 时统计不变，cross/J同步变换。
22 合法 pivot reparameterization：epsilon=0 时同一物理判定不变。
   非零 Euclidean remainder 球经非正交变换需运输完整集合；仅乘算子范数会保守，
   不承诺统计完全不变。本轮不实现完整非球余项集合。
23 部分/全失弧与新 token：幸存关系或无支持状态，不继承旧 N。
24 canonical endpoint 防重用：重命名/换 pivot 不逃逸，一次拒绝也消费。
25 active 后晚到 interval fault：撤销且旧端点不释放。
26 retirement 在区间外与之后：历史不乱撤销，未来旧 token 禁用；
   晚证据区间声明更早 retirement 时，已跨该时刻的 active 因子也必须撤销。
27 新 token+新端点恢复及部分 survivor：重新资格，非复活旧统计。
28 decision/event 乱序、重复撤销与幂等 receipt：保持确定生命周期。

不是 28 个实测样本，不承诺每个物理故障可检测。
只运行新 test_arc_phase_admission.py 单次 pytest，最多 30 个收集实例、
单数值线程、最多 120 s、无 raw/saved-real/reference/native/CILS。
若首次失败先保留完整 stdout/JUnit/源SHA和失败数据；只有已定位实现/测试问题
才另登记有限修复，不用修改噪声/prior/alpha/窗口掩盖科学反例。
待根代理审查并登记实现/计划后再执行。实现阶段不修改已封存 arc core/runner。


## 实现中的数值与依赖细节（执行前冻结）

新模块自身用对角 congruence 检查 PSD，避免大方差遮蔽小方差/cross 非PSD块，
并用 half-before-add 对称化避免有限大输入相加溢出。旧 arc core 保持原SHA。
gate 若 lambda_min <= 64*eps*dimension*lambda_max，则整个 gate 为 UNRESOLVED，
不删模态、不加floor；求解残差阈值为 512*eps*dimension。
所有评判中间运算以 finite/浮点异常保护，异常不可能归一化成零后条件放行；
已 reserved 的两个端点仍消费。第13例同时检查有限输入HPHT溢出关闭分支。
J 的数值秩用 max(shape)*eps*smax，leakage 保留到完整投影二阶矩界。

retire/invalidate 的 phase-node 依赖取实际非零物理系数列；已在差分中代数消去的
epoch-only pivot 不阻止新的合法 survivor 因子。epoch 级别消费仍按两端完整 canonical key，
撤销后不会复活旧观测或释放其端点。实现是单个内存 ledger，不声称跨进程持久化。
