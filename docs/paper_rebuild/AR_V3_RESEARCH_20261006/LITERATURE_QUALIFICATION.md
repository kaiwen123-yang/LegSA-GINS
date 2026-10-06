# AR 对照文献资格与两历元最小研究边界

日期：2026-10-06。状态：**文献局部核查与算法设计；新对照尚未完成实现资格**。

## 1. 本次范围与决策

用户附件 `<PROJECT_ROOT>/论文/10.2478_v10018-007-0009-1.zip` 内有 **34 个 PDF 条目，含重复文件**。本次只核查下列指定 8 篇的题名页与相关方法页，不声称通读全部附件，也不声称完成逐式审稿。使用 Ubuntu 22.04 WSL 中的 `ZipFile.read(member)` 与 `fitz.open(stream=..., filetype='pdf')` 从内存解析；没有解压或保存 PDF/提取文本。补充 PD-PAR 的作者机构 PDF 同样在 WSL 从内存解析。网页文献只用出版方或作者机构来源。

**最多新增两项候选对照：方向可观子空间适配的 PD-PAR，以及有适用条件的 2013 gyro-integral 机制。** 两者均未成为“已运行作者算法”。先关闭数学、观测与接受检验资格，再决定实际实现。常规 C-LAMBDA/C-WLS、RTKLIB 类长度伪观测，以及整套多天线紧耦合 INS，不再各增一条重复或过宽的对照。

正式实测比较只使用用户指定的 **V3 数据与来源链**。算法正确性合成检查与正式比较分开；不增加新采集、不用合成提升代替 V3 收益、不把之前研究分支结果倒写成原 V3 实现。原 V3 结果和方法身份保留。此前设计中提及其他日期留出数据的建议，不属于本阶段执行范围。

本交付只新增本文档：无算法源代码修改、无测试/CILS/导航/评估执行、无参考轨迹读取、无 Git 提交、无 main 修改。下面“需检查”“计划”均为未执行要求。

## 2. 八篇附件：核实身份、实际阅读范围与当前关系

页码均为 **PDF 文件自第 1 页起的页码**；不是阅读完全部页数。方法页的读取不等同于验证论文的全部证明或复现实验。

### 2.1 The LAMBDA Method for the GNSS Compass

- 文件：`10.2478_v10018-007-0009-1.pdf`，15 页。
- 作者：P. J. G. Teunissen。Artificial Satellites 41(3), 89–103。PDF p1 卷标为 2006；出版方记载实际发布日期 **2007-05-10**，DOI `10.2478/v10018-007-0009-1`。应同时保留卷期年与发布日期，不从 DOI 字符串推断年份。[出版方书目](https://reference-global.com/article/10.2478/v10018-007-0009-1?tab=metrics)
- 实际核查：p1 题名/范围；p6 非线性基线长度约束；p9 椭球包络搜索与初始化；p11 目标上下界及搜索缩减。
- 已覆盖内容：长度约束加入整数目标、球面条件基线求解及安全搜索界，是当前 CILS 与已有 EXT01 适配的理论来源。本文核查不能认证 EXT01 与作者程序等价；“短基线 + 已知长度 + LAMBDA”不构成新增方法。

### 2.2 Testing of a new single-frequency GNSS carrier phase attitude determination method: land, ship and aircraft experiments

- 文件：`s10291-010-0164-x.pdf`，14 页。
- 作者：P. J. G. Teunissen、G. Giorgi、P. J. Buist。GPS Solutions **15:15–28, 2011**；2010-03-13 在线。DOI `10.1007/s10291-010-0164-x`。
- 实际核查：p1 题名、摘要及平台范围；p3–4 完整码/相位 DD 模型、长度约束、非二次整数目标、搜索包络与 search-and-shrink。
- 已覆盖内容：无惯导辅助的单频单历元 C-LAMBDA，已有陆地、船舶、飞机实验。原文指出单历元不依赖跨时整数恒定；当前多历元共享弧具有不同资格要求。动态平台验证不是我们的独有方法内容；本次没有逐表核对其所有实验。

### 2.3 Integer least-squares theory for the GNSS compass

- 文件：`s00190-010-0380-8.pdf`，15 页。
- 作者：P. J. G. Teunissen。Journal of Geodesy **84:433–447, 2010**。DOI `10.1007/s00190-010-0380-8`。
- 实际核查：p1 书目与目标；p3 精确/近似非椭球搜索；p7 长度信息处理与加权；p9 浮点/条件基线协方差、弱模型和局部近似。
- 已覆盖内容：正确 CILS 目标不同于先求普通 ILS、再任意加一个长度否决门。标准硬/软长度约束、局部线性化、目标界均已有来源。已有内核是否正确实现这些条件要用独立算法检查确认，不能以文献标题或历史输出误差代替资格证明。

### 2.4 The affine constrained GNSS attitude model and its multivariate integer least-squares solution

- 文件：`s00190-011-0538-z.pdf`，17 页。
- 作者：P. J. G. Teunissen。Journal of Geodesy **86:547–563, 2012**；2011-12-28 在线。DOI `10.1007/s00190-011-0538-z`。
- 实际核查：p1 书目；p3–5 阵列几何与多变量随机模型；p11–12 ADOP 及退化情形。
- 不适合作为新单基线对照的原因：p11 给出 `r=q` 时仿射 ADOP 与无约束者相同；p12 指出 `r=q=1` 退化为无约束多频单基线模型。两天线不能获得不存在的额外阵列仿射信息。把不同时刻当“虚拟多天线”还需处理几何、公共旋转和噪声相关，不能直接引用原阵列证明。

### 2.5 GPS/BDS Dual-Antenna Attitude Determination With Baseline-Length Constrained Ambiguity Resolution: Method and Performance Evaluation

- 文件：`GPS_BDS_Dual-Antenna_Attitude_Determination_With_Baseline-Length_Constrained_Ambiguity_Resolution_Method_and_Performance_Evaluation.pdf`，14 页。
- 作者：Hongli Yang、Yuanming Shu、Rongxin Fang、Lulu Qiao、Dong Ding、Guangxue Li。IEEE TIM **73, 1003414, 2024**。DOI `10.1109/TIM.2024.3374423`。
- 实际核查：p1 书目与范围；p2–4 算法来源、DD/KF 模型、长度线性化伪观测、MLAMBDA、实验参数及固定判据。
- 原法与已有覆盖：KF 中加入长度伪观测，随后 MLAMBDA 与固定 ratio 阈值 3；它与精确非线性 CILS 不是完全相同方法，但与已有 RTKLIB/线性化长度约束机制重叠。p4 给出静态基线 7.99 m、动态基线 1.23 m；摘要将静态长度简写为 7.9 m。与本项目紧凑侧向基线的安装条件不同。
- 固定标签比例不是已知真整数正确率。本文可以支持相关工作与模型比较，不作为本轮两项新增对照之一。

### 2.6 Robust Dual-Antenna GNSS/INS Attitude Determination via Constrained Ambiguity Resolution and Misalignment Compensation

- 文件：`Robust_Dual-Antenna_GNSS_INS_Attitude_Determination_via_Constrained_Ambiguity_Resolution_and_Misalignment_Compensation.pdf`，14 页。
- 作者：Jiaji Wu、Jinguang Jiang、Yuying Li、Tianci Tang、Jianghua Liu、Jingnan Liu。IEEE TIM **74, 9539914, 2025**。DOI `10.1109/TIM.2025.3626898`。
- 实际核查：p1 书目/平台；p3 C-LAMBDA、PAR 与质量控制描述；p4 加速度补偿、误差四元数融合和失准角模型入口；另检索 PAR 相关文字位置，未逐式审完整滤波器。
- 关键限制：p3 已包含按 SNR、仰角、最优/次优一致性及浮点协方差选择 PAR，再用长度、后验残差和 ADOP 质控。**所核方法页没有给出足以直接复现的完整排序、联合规则与阈值**；不能自行补齐后称作者法复现。
- p4 动态补偿使用 GNSS 速度时间差分，不能当作 GNSS 无关本体运动先验。其 C-LAMBDA + PAR + INS 融合 + 失准补偿已直接限制宽泛创新表述，但整套系统不在本轮新增对照范围。

### 2.7 Constrained Wrapped Least Squares: A Tool for High-Accuracy GNSS Attitude Determination

- 文件：`Constrained_Wrapped_Least_Squares_A_Tool_for_High-Accuracy_GNSS_Attitude_Determination.pdf`，15 页。
- 作者：Xing Liu、Tarig Ballal、Hui Chen、Tareq Y. Al-Naffouri。IEEE TIM **71, 8005315, 2022**。DOI `10.1109/TIM.2022.3193412`。
- 实际核查：p1 书目；p3 DD 随机模型；p4–6 半周残差约束、wrapped 目标、与 CILS/oracle 的条件关系。
- 原法与已有覆盖：已有 EXT02 是适配实现，不是本文作者代码复现。p4 的半周观测误差假设与接收机报告的 half-cycle-valid 位不同；后者不能证明前者。p5 Lemma 3 给出对角相位 Q 下与 CILS 同最优的充分条件；完整相关 DD Q 不能直接沿用该特殊条件。wrapped 候选、完成搜索或 ratio 通过均不等于真实整数已正确固定。
- 本轮不增加一个改名的 C-WLS 对照；已有大角误差也不能直接归因于原论文方法不适合短基线。

### 2.8 Low-Cost Inertial Aiding for Deep-Urban Tightly-Coupled Multi-Antenna Precise GNSS

- 文件：`2201.11776v1.pdf`，16 页。
- 作者：James E. Yoder、Todd E. Humphreys。附件是 **2022-01-27 arXiv v1**，不是后来正式期刊版本。[作者预印本身份](https://arxiv.org/abs/2201.11776v1)
- 实际核查：p1 书目/范围；p6 unscented 基线先验传播；p7–8 分离整数/状态代价、integer aperture、float fallback 与 IMU 状态；p12 实验配置；p16 所引接受检验文献。
- 已有内容：惯性先验与多基线相关性、整数接受、错误固定检测/恢复均已有完整系统前作。p7 模拟固定失败率 0.01 与 p12 系统 FF-difference 配置 0.001 是不同上下文，不能混用。
- 本轮只将其用于风险与相关性边界，不新增完整 UKF/多天线紧耦合实现。它引用的 Wang/Verhagen 接受阈值方法不是随意给当前非线性 CILS ratio 安装“固定风险”标签的许可。

## 3. 仅保留的两个新增候选

### 3.1 PD-PAR：方向精度适配，资格尚未闭合

补充来源：J. Manuel Castro-Arvizu、Daniel Medina、Jordi Vilà-Valls，**Precision-Aided Partial Ambiguity Resolution Scheme for GNSS Attitude Determination**, ION ITM 2022。[作者机构 6 页全文](https://elib.dlr.de/193961/1/ArvizuMedinaVila_ITM_2022.pdf)。核查 p1–4 的模型/方法和 p6 参考；p3 式(17) 未选整数为实值，式(19)–(22) 用条件姿态协方差选集，p4 Algorithm 1 按子集精度和 FF-RT 迭代。未重新验证作者全部仿真。它有明确新对照价值，但不是本项目创新来源的空白区。

**单基线适配问题（以下是本项目数学分析，不是原文已有结论）：** 一条已知机体系基线 `r` 的方向观测 `b=Rr` 不识别绕 `r` 的旋转。不能直接以完整四元数协方差的 `trace(Pq)` 作为双天线质量指标，也不能把奇异信息矩阵伪逆中不可观方向的零特征值解释成零不确定度。四元数还须区分四分量协方差与三维局部扰动协方差。

可实施的适配落点是基线方向的二维切平面。令 `u=b/L`，`E` 为任一满足 `E^T E=I2, E^T u=0` 的正交基；由可辨识局部模型获得同源条件基线协方差 `P_b|I`，定义

```text
C_dir,I = L^(-2) E^T P_b|I E .
```

该式是单位球方向的一阶小误差传播，`trace(C_dir,I)` 的单位为 rad²，且不依赖二维正交基的任意旋转。也可选预先声明的航向方差，但水平投影趋零时应不可用，不能靠任意正则化消除退化。这里的精度是**给定整数正确及局部工作噪声模型**的条件精度，不是包含错整数概率的完整误差。

通过资格至少需要：同一 float 模型的 `P_b, P_N, P_bN`；与长度/方向参数化一致的可观局部空间；未固定变量的明确域；子集选择与接受检验的完整规则。原 FF-RT 基于其指定随机模型和整数检验统计量，不能直接套当前含球面/运动罚项的非二次 top-two 代价；递归多子集检验的整体选择效应也不能被单次名义阈值掩盖。若先采用共同研究准入门，须命名为 **PD-PAR-inspired directional-subspace adaptation + shared admission**，不可称作者原 FF-RT 的风险保证。

### 3.2 2013 gyro-integral：有条件的运动机制对照

补充来源：Jiancheng Zhu、Tao Li、Jinling Wang、Xiaoping Hu、Meiping Wu，**Rate-Gyro-Integral Constraint for Ambiguity Resolution in GNSS Attitude Determination Applications**, Sensors 13(6):7979–7999, 2013，DOI `10.3390/s130607979`。[出版方原文](https://www.mdpi.com/1424-8220/13/6/7979)。本轮通过出版方网页核查摘要、§1–4 与结论中相关部分；网页读取范围不冒充附加 PDF 全文逐页阅读。

它已经使用无需初始航向的短时陀螺积分转角来筛除整数候选，并讨论陀螺误差、相位误差和转轴偏移。原应用依赖陆地车辆转弯时基线近水平的条件；足式平台一般三维转动不自动满足。未来对照应先按原模型资格报告适用/不适用支持，不能用参考误差挑选“近水平好区间”。改成任意三维 SO(3) 关系时必须标为本项目适配，不能继续声称原文忠实复现。

这项对照的目的，是分清新增方法的收益来自“任何合理的相对转角先验”，还是确实来自三维模型、误差集合或求解机制。**无初始 yaw、陀螺积分、跨时候选筛选及误差分析均不能再作为首创新意。**

## 4. 三种“部分固定”必须分开

令共同观测为 `y=A_I N_I+A_U N_U+B b+e`，`Q=Cov(e)` 包括共享 pivot 的相关性。下表是当前源码/原文的域区别，不是性能排名。

| 方法身份 | 被固定子集外的处理 | 不能混称的内容 |
|---|---|---|
| 当前完整似然的 selected-class 搜索 | `N_U` 仍在整数域中 profile；各选中整数类需要在完整整数空间找最小代价 | 不是文献 PD-PAR 的实值 nuisance；旧完整 top-two 截取也不是新的子集 top-two |
| 文献 PD-PAR 的问题式(17) | `N_U` 放松为实值，观测仍在目标中 | 需要正确消元，不能设零或沿用整数 nuisance 证书 |
| 当前 selected-observation likelihood | 只保留所有未选 `A_U` 列均为零的行；用 `Q_RR` 主子矩阵 | 是新的观测边缘似然；不能普遍声称等价完整观测 profile |

当前语义入口：[partial.py](../../../src/legsa_gins/paper_rebuild/carrier_phase/partial.py) 的模块说明与 `prepare_partial_search`；[selected_likelihood.py](../../../src/legsa_gins/paper_rebuild/carrier_phase/selected_likelihood.py) 的模块说明与 `restrict_selected_observations`。本次仅阅读这些接口，没有调用它们。

对实值 nuisance，在满列秩条件下，固定其余变量后的正确剖面精度矩阵为

```text
W_prof = Q^-1 - Q^-1 A_U (A_U^T Q^-1 A_U)^-1 A_U^T Q^-1.
```

秩亏时需要白化后的可观空间消元与明确秩判定。只有额外结构条件满足时，实值 nuisance 消元才可能等价于删除某些观测并保留主协方差；例如被删行拥有足够独立、无限制的实值 nuisance 能吸收这些行全部残差。跨历元共享一个弧整数的结构通常不满足“每行一个任意实值”的条件，必须推导，不能因名字都叫 PAR 就假定等价。

## 5. 两历元最小验证：理论条件与安全搜索界

这是将来实现前应满足的限定问题，不是新算法已通过的证据。首先冻结同一观测、Q、合法共同弧和整数域；已选 cap、支持、时段不能按未来误差重选。比较两种方法时必须保留同样的未选变量处理。

### 5.1 几何与误差集合

若刚性机体系基线为 `r`，`||r||=L`，相对转动定义为将当前 body 向量表达在初始 body 坐标中的 `DeltaR_k`，则

```text
b_k^e = R0^e DeltaR_k r,  R0 ∈ SO(3),
b_1^T b_2 = r^T DeltaR_1^T DeltaR_2 r.
```

`R0` 必须未知，不可填入已融合 GNSS 的 yaw。IMU 与基线外参、相位参考点、同步、转动方向、地球/参考系转动及偏置必须解释；机体系 gyro 积分不能直接当 ECEF 相对旋转左乘 `b1`。不满足刚性条件的形变也属于误差来源。

设相对旋转误差满足 SO(3) 测地界

```text
||Log(DeltaRhat_12^T DeltaRtrue_12)|| ≤ epsilon, 0 ≤ epsilon ≤ pi,
beta_hat = acos(clip(r^T DeltaRhat_12 r / L², -1, 1)).
```

则必要的基线夹角区间为

```text
beta ∈ [beta_lo,beta_hi]
beta_lo=max(0,beta_hat-epsilon), beta_hi=min(pi,beta_hat+epsilon),
b1^T b2 ∈ [L² cos(beta_hi), L² cos(beta_lo)].
```

这是标准旋转几何推论，不是新定理。误差界若来自概率区间，则只具有相应模型内覆盖；遗漏偏置、时延或外参后不能叫硬安全界。两向量的 Gram 信息不恢复完整初始姿态；静止或绕基线轴转动尤其不能凭运动幅度推断方向激励。扩到多历元还需处理共享陀螺积分相关性及 SO(3) 手性/整体可实现性，不能将各 pair 当独立信息相乘。

### 5.2 可复用的界与不能复用的证书

将两历元堆叠，记 `Jraw=||y-AN-Bb||²_Q`。在 **观测行、整数/nuisance 域、Q 和 Jraw 完全相同** 时，令

```text
J0(N)    = min Jraw,                         ||b1||=||b2||=L;
Jshape(N)= min Jraw over the tighter motion-feasible set;
```

或者在相同球面域上加入非负运动罚项，则 `J0(N)≤Jshape(N)`。因此有证明的独立球面/更宽连续松弛下界可用于新分支剪枝；旧整数候选可作初始化。若改了 Q、加入与原噪声的交叉项、变更观测支持或将整数 nuisance 改为实值，该不等式不能直接跨方法沿用。即使 Q 不变，存在跨时非零相关项时，原始目标也未必按历元可分，不能机械相加旧单历元内核值。

新方法的最优整数可能来自原第 3 名或更后；只筛旧 top-two 不能得到新全局 top-two。新可行解才提供上界；局部内层优化值一般只是上界，不能拿来剪除可能更优的分支。整数分支下界需对该分支所有合法完成都成立，第二名须按声明的选中整数类区分。给定 N 的耦合球面内层也需有合法下界/上界或完整证书；未完成时报告有界候选/未决，不能继承旧独立球面 global certificate。超时、无可行点和资格失败原样保留。

### 5.3 最少但有判别力的正确性场景（未执行）

| 场景 | 要暴露的缺陷/检查 | 不能据此宣称 |
|---|---|---|
| 已知 N、移动基线、非固定轴三维旋转；独立正向观测 | 外参、旋转方向、DD 符号/波长与真实整数仍在可行域；小问题穷举校验新最优/次优 | 合成成功等于 V3 实测正确固定 |
| 静止、绕基线轴、近零转角 | 应正确报告弱激励、别名或竞争未决，不能凭“转过角”伪造辨识增益 | 一条基线能提供三轴绝对姿态 |
| 错误陀螺偏置/时延/外参，且 epsilon 故意过紧 | 真夹角 60°、先验 0°、epsilon=5° 这样的真解排除必须可见；不能只统计剩余候选变少 | 搜索更快或通过率变高就是更安全/新颖 |
| 完整相关 Q、合法 pivot 变换、弧 reset/半周未决 | 正确坐标变换下物理结论不变；新弧不得继承旧 N；同 Q 的松弛界逐候选成立 | 放宽资格门带来的覆盖改善是 AR 贡献 |
| 正确/错误 N 均解释观测与运动的别名；原 top-two 之外的新最优 | 必须允许未决、保留竞争；检查新全类搜索而非旧候选重排 | global optimum 证明 true integer，或共识证明没有共同模型误差 |

测试设计应独立生成几何和观测，不只重算被测实现中的同一公式。全体场景只承担算法正确性和反例证据，不参与 V3 效果表、不用于参考驱动的阈值调优。若先验坏时只加 veto、却无可解释的恢复/接受分支，最多说明风险/可用性取舍，不支持“同风险更高可用率”的泛化结论。

## 6. 资格完成前后的声明边界

- **已有覆盖**：标准长度 CILS、C-WLS、长度伪观测、动态平台应用、惯性辅助和错误固定恢复均有前作。当前资格审查不削弱这些工作的地位，也不以未经资格核实的历史大误差证明本方法优越。
- **待实现的适配对照**：PD-PAR 的方向可观子空间/正确实值 nuisance，以及 2013 gyro-integral 的明确适用条件；不是两个新首创算法。若任一项无法闭合观测或统计条件，就留作相关工作/机制反例，不强凑两行正式排名。
- **真正待验证的问题**：在 V3 的实际三维运动、弧支持和误差范围内，新增运动约束能否可靠分开原本竞争的整数，且收益足以承担耦合求解与延迟；已知的标准角度界或改权重本身不构成答案。
- **融合边界**：同一 gyro 用于运动先验和 EKF 预测会产生相关性；固定 N 后重新求载波基线也不能消除离散选择依赖。仅放大 R 不等于解决重复信息。先前的 [有界 EKF 设计](../CONTACT_CARRIER_DESIGN_20261006/BOUNDED_EKF_SCOPE.md) 是推导入口，不是已通过的风险校准。
- **本交付终点**：文献关系与最小设计已明确；PD-PAR/gyro 的正式实现资格仍未闭合。下一步应先解决声明的模型差异与最小独立正确性检查，再进入用户授权的 V3 对照。本文不是论文正文、测试结果或执行登记。
