# 横向比较全景、证据等级与论文组织（2026-10-06）

审查输入起点：工作树 `audit-code-xbpg-20261001`，分支 `fix/fgo-v3-reproduction-20261004`，起点提交 `5441621`。本文是现有证据的分层复核与组织，不是重新执行实验，也不声称本轮逐行重审全部算法或原论文。所有读取与派生 CSV 均在 Ubuntu 22.04 WSL 中完成；本子任务新增 solver/provider/evaluator/参考原始流读取均为 0。旧结果、旧代码和失败不改。

**你已完成的横向比较确实很丰富，主要问题是版本、输入层次和证据用途交叉堆积。当前应整理成四类外部比较加一类内部因果对照，不能写成“30篇方法全部复现且统一胜出”。** 核心外部账本是30个读者身份：原23项登记＋RTKLIB新增3条件＋3条FGO路线＋SDK积分诊断1项。18项有可引用的执行链/条件/输入诊断，12项未准入。此前验收对选定链给出15 PASS、3 PARTIAL、12 BLOCKED；更强的“所有作者程序/原实验与传感器完全等价”口径为18 PARTIAL、12 BLOCKED。PASS包含如实保留失败的完整执行，绝不是精度保证。

## 1. 当前引用入口与版本优先关系

|要回答的问题|优先入口|科学版本边界|
|---|---|---|
|30项到底完成哪些|[总验收](../TIM_EVIDENCE_20261005/comparisons/COMPARISON_ACCEPTANCE_REPORT.md)、[完整链与公平性](../TIM_EVIDENCE_20261005/comparisons/ESTIMATION_CHAIN_AND_FAIRNESS_MATRIX.csv)|2026-10-05汇合各版本；不能把表行数加成新运行数|
|当前三个raw双天线方法|[EXT V2精确63行](../V3_STORY_20261004/COMPARISON_SOURCES/EXT_V2_COMPARISON_TABLE.csv)、[450行共同支持](../V3_STORY_20261004/COMPARISON_SOURCES/EXT_V2_COMMON_SUPPORT_ALL.csv)|`EXT_REPRO_V2_TECH_RETRY_2`；早期EXT_REPRODUCTION正文是较早代，不能混取数字|
|RTKLIB四条件|[HX07R报告](../hext/HX07R/HX07R_REPORT.md)、[主行](../hext/HX07R/HX07R_MANUSCRIPT_ROWS.csv)、[补充](../hext/HX07R/HX07R_SUPPLEMENT_ROWS.csv)|V0/V0E/V1/V2各自保留；不按最小RMSE选成一个“RTKLIB”|
|IEKF/GINav/官方接触InEKF|[HX05主表](../hext/HX05/EXTERNAL_THREE_SEQUENCE_MANUSCRIPT.csv)、[补表](../hext/HX05/EXTERNAL_THREE_SEQUENCE_SUPPLEMENT.csv)、[Hartley官方96行](../hext/HX02E/HARTLEY_OFFICIAL_TABLE.csv)|LC01 H几何失败另读原审计；Hartley旧移植退补充|
|外部方法退化|[HX03R2结果](../hext/HX03R2/HX03R2_RESULTS.md)、[逐例396行](../hext/HX03R2/DEGRADATION_EXTERNAL_TABLE_R2.csv)|R2只修观察器处置，复用原native；旧146审计不可用已转有限，36原生发散保留|
|严格FGO|[严格9身份](../hext/FGO_REPRODUCTION_FIX_20261004/RUNS.csv)、[指标](../hext/FGO_REPRODUCTION_FIX_20261004/METRICS.csv)、[实现差异](../hext/FGO_REPRODUCTION_FIX_20261004/REPRODUCTION_NOTES.md)|一次A1初始化、不跨IMU缺口重启；旧FGO_COMPARISON不是最新严格链|
|FGO分段恢复诊断|[最终结果](../FGO_COMPLETE_AUDIT_20261004/SEGMENTED_RESULTS/RESULTS_AND_LIMITATIONS.md)、[36行指标](../FGO_COMPLETE_AUDIT_20261004/SEGMENTED_RESULTS/publication/ALL_36_METRIC_ROWS.csv)|3新Oi native＋6复用Wen/GNC，11块；不能填回严格H0/O55|
|内部方法与全矩阵|[全矩阵故事](../V3_STORY_20261004/03_SELECTION_HISTORY_AND_FULL_MATRIX_RESULTS.md)、[自然66行](../V3_STORY_20261004/NATURAL_METHOD_RESULTS.csv)|原V3 6468 native；v2/v3是同native的两份评价合同|
|新八段迁移结果|[R5最终结果](../EXISTING_DATA_R5_20261005/new_data/RESULTS_AND_USE.md)、[16组合](../EXISTING_DATA_R5_20261005/new_data/RESULTS.csv)|T03实际dt修正版＋输入派生−1.1s移时＋0.15s参考插值；不回贴原V3|

本轮提供：[30行身份表](02_COMPARISON_REGISTRY.csv)、[241行精确值/原单元格证据表](02_COMPARISON_EVIDENCE.csv)、[11配置映射](02_INTERNAL_CONFIGS.csv)。241行是多个支持域、条件和历史角色的索引，不是241个独立实验。CSV保留源文件、从1开始的数据行号和行键；空值保持空值。源路径都相对于仓库，运行大载荷沿原来源索引定位。

`AGENTS.md`优先于早期ACTIVE_CONTEXT中的“未运行”描述，但AGENTS自身较老的v2/v2.1数值与CLEAN4登记也不能覆盖后续有终态证据的V3、EXT V2、HX和FGO。本文按明确终态的各版本原证据引用，未删除或改写历史。原V3 scientific native源 `ca73cb1...`、runner/协议冻结 `7d43b9a...`、二进制 `96ae436d...`的角色须分开；当前Git HEAD不是所有历史运行的科学版本。详见[正式身份](../audit_xbpg_20261001/METHOD_IDENTITY.csv)。

## 2. 30个外部身份的完整清单

下面的状态继承2026-10-05选定链验收。更强的作者全部实验等价均尚未成立，具体输入/状态/点位/初始化/剩余动作逐行见本轮CSV及原验收矩阵。

|序号|登记身份|方法层级|选定链|当前用途|
|---|---|---|---|---|
|1|`EXT01`|核心独立实现|PASS|raw整数/长度约束核心；输出候选不等于正确固定|
|2|`EXT02`|核心独立实现|PASS|raw wrapped最小二乘；单基线，不是多天线三轴|
|3|`EXT03`|核心独立实现|PARTIAL|raw DD-KF/MLAMBDA；F/Q/R与重置仍有工程假设|
|4|`EXT04`|模块诊断|PARTIAL|FAR/PAR模块零接受；非整篇GNSS/INS/misalignment|
|5|`RTKLIB_UNMODIFIED_MOVING_BASE`|完整已命名官方求解路线|PASS|官方V0，低有效率与保持误差同报|
|6|`D01_DIRECT_GEOMETRIC_BASELINE`|无合法性能比较资格|BLOCKED|无可准入独立性能；具体缺口见第8节|
|7|`LC01`|完整已命名主IEKF算法的独立实现|PASS|两位置IEKF；H几何FAIL与起点条件保留|
|8|`LC01-S`|项目参数变体|PASS|同IEKF的项目标定条件，补充|
|9|`EXT05B`|无合法性能比较资格|BLOCKED|无可准入独立性能；具体缺口见第8节|
|10|`LC01-M`|无合法性能比较资格|BLOCKED|无可准入独立性能；具体缺口见第8节|
|11|`LC01-S-M`|无合法性能比较资格|BLOCKED|无可准入独立性能；具体缺口见第8节|
|12|`LC01-2D`|无合法性能比较资格|BLOCKED|无可准入独立性能；具体缺口见第8节|
|13|`LC02_GINAV`|完整已命名官方求解路线|PASS|官方SPP/INS路线，失败和H低支持|
|14|`LC02_YIN2023_RAEKF`|无合法性能比较资格|BLOCKED|无可准入独立性能；具体缺口见第8节|
|15|`LC02_CHANG2021_FSTCKF`|无合法性能比较资格|BLOCKED|无可准入独立性能；具体缺口见第8节|
|16|`LC02A_JIANG2021_ADAPTIVE_FADING_CKF`|无合法性能比较资格|BLOCKED|无可准入独立性能；具体缺口见第8节|
|17|`LC02B_TAGHIZADEH2023_AHINF_CKF`|无合法性能比较资格|BLOCKED|无可准入独立性能；具体缺口见第8节|
|18|`EXT06_HAO2018_TWO_ANTENNA_LC_EKF`|无合法性能比较资格|BLOCKED|无可准入独立性能；具体缺口见第8节|
|19|`EXT05C`|模块诊断|PASS|单接收机在线更新诊断；初始化仍双天线|
|20|`EXT05C-S`|模块诊断|PASS|同诊断的项目参数条件，H早起点发散|
|21|`D02_SINGLE_RECEIVER_IEKF`|无合法性能比较资格|BLOCKED|无可准入独立性能；具体缺口见第8节|
|22|`EXT06`|无合法性能比较资格|BLOCKED|无可准入独立性能；具体缺口见第8节|
|23|`Hartley`|完整官方滤波核心+项目观测适配|PASS|官方接触InEKF两参数条件；相对/gauge对齐|
|24|`RTKLIB_V0E`|完整已命名官方求解路线|PASS|同官方程序换星历条件|
|25|`RTKLIB_V1`|完整已命名官方求解路线|PASS|同程序扩展星座条件|
|26|`RTKLIB_V2`|完整已命名官方求解路线|PASS|同程序fix-and-hold条件|
|27|`OISAM`|selected complete estimation chain independent implementation with declared engineering instantiation|PARTIAL|严格与真实gap分段两协议分别报告|
|28|`WEN_TC`|selected complete estimation chain independent implementation with declared engineering instantiation|PASS|原始码＋AHRS运动图；不自行估计姿态|
|29|`GNC`|selected complete estimation chain independent implementation with declared engineering instantiation|PASS|码＋Doppler GM图；不自行估计姿态|
|30|`LEG_DR`|conditional input diagnostic|PASS|SDK供应姿态/速度积分，输入诊断|

不能另计：LC01的EXT05A别名、Hartley OFF-LIT/OFF-DEF参数条件、EXT04 FAR/PAR模块行、RTKLIB三序列、内部F03/A02与F04/A01别名、同轨迹的v2/v3评估。LEG-DR不是第31篇文献方法。七种Huber/Cauchy/Tukey/IGG3/Barron/DCS/switchable内部类比只实现标量R倍率，不包含各原法完整状态/因子/优化器；见[七模块范围](../TIM_EVIDENCE_20261005/comparisons/ROBUST_MODULE_ACCEPTANCE_MATRIX.csv)。

## 3. 机器人状态估计：用途是检查本体输入与相对漂移

已完成官方RossHartley/invariant-ekf `ef16e8a...`的OFF-LIT/OFF-DEF×三序列6次原生及相对评估。数学核心来自官方库，Go2足端位置代理、力阈值接触、噪声、轴向和初始化是项目适配。没有GNSS时全局xyz与重力轴yaw四个自由度不可观，评价各自先10s做一次xyz/yaw对齐；下列H是对齐后相对轨迹误差，不是绝对GNSS定位精度。

|配置/量|BY2|BY2H|BY2O|
|---|---:|---:|---:|
|OFF-LIT H RMSE / m|50.187304|68.544623|77.504150|
|OFF-DEF H RMSE / m|35.463605|51.281549|30.683277|
|OFF-LIT位置漂移 / m每100m|33.633600|47.525517|28.558852|
|OFF-DEF位置漂移 / m每100m|21.889076|34.015027|11.652023|
|LEG-DR供应姿态积分 H RMSE / m|6.209111|9.178417|6.322412|

来源：[官方结果](../hext/HX02E/HX02E_RESULTS.md)及[HX05主表](../hext/HX05/EXTERNAL_THREE_SEQUENCE_MANUSCRIPT.csv)。1/5/10s RPE、评分点数、路程、航向漂移全部有记录；漂移定义是带截距OLS斜率，负值不能写成负误差。旧移植Hartley在H静止初始化异常，HX02D仅支持接触/零偏反馈适配值得查，未唯一定位公式错误。新官方执行没有抹掉旧失败。

论文应把这一组用来说明“本体运动学信息能提供怎样的相对约束、输入适配为何重要”。不能用有GNSS锚的LegSA厘米级误差与无GNSS相对估计的大漂移，证明EKF形式胜过InEKF；也不能用带供应姿态的LEG-DR证明官方InEKF数学错误。

## 4. 双天线/动基线/AR：必须分候选、接受、有效、保持和正确整数

LegSA原V3的5Hz A1来自两个接收机已解算HP位置及质量门，raw一词在这里指从原始消息解析位置，不代表滤波器内执行载波整周求解。EXT01–03和RTKLIB moving-base则从两接收机码/载波求相对基线/整数。当前没有真整数标签，因此**不能把有效率、ratio通过或RTKLIB Q1写成正确固定率，也不能称现有LegSA提出了新AR算法。**

最新EXT V2、各自native-valid支持的投影航向相对商业融合Euler yaw诊断如下；三序列原分母为1370/1350/1885。

|方法|BY2有效数；RMSE°|BY2H有效数；RMSE°|BY2O有效数；RMSE°|
|---|---:|---:|---:|
|C-LAMBDA|980；85.015472|1059；89.127388|1173；81.273465|
|C-WLS|961；85.179795|1029；89.192923|1210；81.486071|
|长度约束DD-KF/MLAMBDA|541；79.931845|467；63.994556|269；103.754200|

[精确源表](../V3_STORY_20261004/COMPARISON_SOURCES/EXT_V2_COMPARISON_TABLE.csv)以sequence_id/method_id/support=native_valid定位。EXT01/02没有原生接受检验，fixed比例NA；EXT03窗内ratio-fixed是78/70/5，与完整历史78/73/7不同。硬约束0.350m的输出长度不能反过来作为独立精度验证。

三法确实实现了对应核心：C-LAMBDA完整约束混合目标及各向异性球面搜索，CWLS候选与wrapped目标/细化，DD-KF中长度伪观测＋MLAMBDA。独立核心实现不是原作者全部程序/数据复现；预算、整池拒绝、未披露F/Q/R、每历元SPP先验重设等要随表交代。共同键三法为506/451/227；加RTKLIB四条件后七法共同仅6/39/55，不能把这小交集当全窗总成绩。

|RTKLIB条件|BY2有效/1370；RMSE°|BY2H有效/1350；RMSE°|BY2O有效/1885；RMSE°|
|---|---:|---:|---:|
|V0 原条件|153；14.566166|179；27.011169|112；23.138950|
|V0E 换星历|194；20.646991|217；31.263814|231；20.402911|
|V1 扩展星座|154；14.611254|186；12.732971|117；21.781901|
|V2 fix-and-hold|60；4.511761|149；10.622992|93；19.205502|

V2较低误差伴随不同且稀疏支持，不作最好条件拼表。V0全窗因果保持RMSE58.241/55.118/129.988°；O最大保持年龄301.4s。保持值不表示新解。原HX07窗截断转换157/1370不满足完整历史153/1370控制门，保留硬停；HX07R才是重现完整历史的当前对照。

EXT04 FAR/PAR三序列均0接受；INS/misalignment和精确PAR规则不完整，且没有升级EXT V2后端。它只进模块/失败附表。大误差来源已修过不同接收机发射时刻/地球旋转几何项，但修后仍大，不能唯一归因硬件相位偏差或宣称所有raw法普遍不适用。后续名义倾斜物理量检查最大RMSE变化仅0.004278°；这不能解释64–104°误差，也不能代替实物安装与独立参考核准。见[物理量诊断](../EXT_MEASURAND_20261004/README.md)。

## 5. EKF/IEKF松耦合：区分系统路线比较与同骨架因果对照

LC01是Pavlasek两位置接收机SE₂(3) IEKF主文算法独立实现，9维R/v/p且不估IMU bias；并非标准21状态KF-GINS的同输入替换。它用两个位置及相关协方差，没有LegSA的RV/RD/SDK RP/HV。EXT05C是同滤波器的单位置在线更新诊断，但初始yaw仍用了GNSS2。LC01-S/EXT05C-S是项目有效标定条件，不是新增文献方法。

|方法；v3点位合同|BY2 H / yaw|BY2H H / yaw|BY2O H / yaw|
|---|---:|---:|---:|
|LC01 LIT|0.097548m / 2.994827°|0.074606m / 2.208612°|0.054304m / 2.453697°|
|EXT05C LIT|0.087751m / 12.048642°|0.069190m / 20.108223°|0.051954m / 5.845502°|
|原V3 F04|0.097906m / 1.886272°|0.068362m / 1.933770°|0.054543m / 2.433815°|

来源：[HX05主表](../hext/HX05/EXTERNAL_THREE_SEQUENCE_MANUSCRIPT.csv)及[自然V3表](../V3_STORY_20261004/NATURAL_METHOD_RESULTS.csv)。这里展示不是公平排名：支持、参数、初态、状态与辅助信息不等；LC01 H的LIT/S×FILE/CONTRACT四行有基线几何审计FAIL，表中数值可描述该运行但不能隐去资格问题。LIT主条件选择记录 `amended_after_results_seen=true`；S用BY2标定且有开发重叠。H FILE_START与CONTRACT_START均保留；EXT05C-S H FILE_START速度发散，不能以另一好起点替代。

GINav官方SPP/INS路线真实执行；HX02 BY2/O触发速度发散，H只2/271正式键，自身2/2匹配不是全窗覆盖。较早BY2为另一身份：113.002s对准后77/275窗键，H RMSE130.818726m；不能与后来失败拼成同一运行。官方路线的真实负结果可报，不能从高层RTK与raw-SPP差距推导IEKF/EKF公式优劣。

外部provider层退化是已完成证据：Classic-18=162条件，A2=18条件；HX03R2 396逻辑行包含A1/A2的18别名、LC01-BR的18修改条件；360有限、36原生发散、0审计不可用。36失败全部是LC01/EXT05C的D14/D21位置噪声，各9。九族主展示153 Classic条件之外，D43速度噪声9另列，不可漏掉；A1等价行不新增native。

|代表族；有限case中位数|LC01|F04或解释|
|---|---:|---|
|位置中断 H / Up|1.407350 / 4.978736m|F04 H / Up=0.106991 / 0.050229m；条件性provider故障比较|
|航向中断 H / Up|3.136051 / 9.186026m|LC01跳整次双天线更新；EXT05C不读p2，信息暴露不同|
|A2 H，LC01-BR vs LC01|2.785782 vs 1.407350m|修改过的BR未显示H改善，18/18有限；不替换LC01|

来源：[HX03R2](../hext/HX03R2/DEGRADATION_EXTERNAL_SUMMARY_R2.csv)、[HX05九族](../hext/HX05/DEGRADATION_MANUSCRIPT.csv)。对应原始码/载波同层故障未构造：九族RAW_LEVEL_COMPATIBLE=0、PROVIDER_LAYER_ONLY=9。D57甚至不同方法暴露到position time或无heading，不能仅同D编号说相同故障。见[逐族输入层证明](../hext/EXT_REPRODUCTION/CONTROL_AND_DEGRADATION_SCOPE.md)。

## 6. FGO：三条选定链已执行，严格和分段必须分表

OiSAM实际包含15维INS/GNSS、作者OB_GINS Earth预积分桥、结构Givens/增量缓存、30/40 A-JSWR、边缘化与Ceres；Wen实际包含raw码、clock、运动与AHRS/加速度联系的联合LM；GNC实际包含码/Doppler、平方GM目标与θ连续化。它们超过仅模块替换，但不是取得全部作者程序、原设备/场地/参数并复现所有原文实验。[45项符合性矩阵](../FGO_COMPLETE_AUDIT_20261004/COMPLIANCE_MATRIX.csv)保留每条公式/实现/验证/开放项。

严格一次A1初始化：OiSAM B275/275、H0/271、O55/378。H408s缺IMU时尚只有6节点，正式窗无输出；O3241s后不能继续。BY2 3D RMSE0.114439m、O前缀0.056376m只描述各自支持，H误差NA。Wen/GNC均为完整batch，正式匹配274/270/377，起点前约2ms一项保留缺失。严格Oi在声明中点评价，Wen/GNC在GNSS1评价，不把这版位置直接混排。

后续分段诊断另3新Oi native，按真实gap固定B1/H3/O7块，各块一次A1初始化；6旧Wen/GNC明确复用。统一GNSS1点，Oi用自身估计姿态运输；主动态表排除prior-only：

|序列|方法|H / 3D RMSE m|自行估计yaw °|匹配/原分母|
|---|---|---:|---:|---:|
|BY2|OiSAM|0.097867 / 0.107594|4.652921|275/275|
|BY2|Wen TC|7.692119 / 13.654694|NA|274/275|
|BY2|GNC|2.173504 / 5.037039|NA|274/275|
|BY2H|OiSAM|0.064957 / 0.077222|2.534907|267/271|
|BY2H|Wen TC|7.672239 / 14.360929|NA|270/271|
|BY2H|GNC|2.134280 / 4.722683|NA|270/271|
|BY2O|OiSAM|0.052046 / 0.064826|3.971789|370/378|
|BY2O|Wen TC|9.583724 / 19.016172|NA|377/378|
|BY2O|GNC|2.724164 / 4.012433|NA|377/378|

[36行源表](../FGO_COMPLETE_AUDIT_20261004/SEGMENTED_RESULTS/publication/ALL_36_METRIC_ROWS.csv)用support_role=PRIMARY_DYNAMIC_ONLY、support=OWN_VALID定位。共同主动态键为274/267/369；次全部有效位置Oi275/269/376仅作补充，不能混入主动态。额外A1、物理点和状态历史改变，新的H/O良好数值不能写成严格算法修复收益；3286s仍usable NO_CONVERGENCE，20次迭代，不掩盖。

三法信息不同：Oi用RTK+IMU；Wen用raw码+外部AHRS/线加速度；GNC用raw码+Doppler。后两者是离线batch，允许窗内未来观测；Oi当前节点增量。共同支持仅控制评分时刻，不能控制信息。计时包含读取/适配/求解/写出且并发环境不同，不作同后端在线延迟优劣结论。未取得作者Oi精确缓存/触发，Wen Go2与原Xsens动态等价、GNC Eq21平方/Eq22歧义及Doppler接口仍开放。没有自行估计姿态的Wen/GNC永远不能补造yaw成绩。

## 7. 内部同骨架对照是因果论证主力，新数据是边界证据

原V3共588物理条件×11唯一配置=6468 native：CORE541×11=5951、ADD45×11=495、H/O额外22。33次未注入自然配置运行与6435半合成任务分表；588不是588次独立采集。6185完成、193发散、90无有效航向。12936双合同槽中12370有评价，566因失败无评价；不是12936次独立求解。

|ID|读者含义|可检验的对照|
|---|---|---|
|F01|无在线双航向更新GNSS/INS|初始化仍用了双天线，不能称全流程纯单天线|
|F02|位置＋双航向，关闭receiver velocity|与F03还变receiver velocity/heading treatment，不能单归因一个模块|
|F03=A02=AB0000|位置/速度＋双航向基础骨架|与F04是多模块总增益，非单开关|
|F04=A01=AB1111|完整LegSA-GINS|主方法|
|A03=AB0111|F04关RD|同分支RD效应|
|A04=AB1011|F04关SA|同分支权重保护及代价|
|A05=AB1101|F04关RP|弱姿态先验效应|
|A06=AB1110|F04关HV|弱水平速度效应|
|A07=AB1100|关RP/HV|组合诊断|
|A08=AB1000|仅RD附加|组合诊断|
|A09=AB0100|仅SA附加|组合诊断|

精确开关与共同初态见[11配置](02_INTERNAL_CONFIGS.csv)及[30个配置差分](../V3_STORY_20261004/CONFIG_COMPARISON_DIFFS.csv)。单变量消融比跨输入方法排名更适合解释机制。原F04 CORE519完成、13发散、9无航向；F03为512/20/9，A04为513/19/9。有限case分布不能把失败填0；均值提升也不能盖住尾部和其他量的恶化。

原消融显示RP在519共同case的roll/pitch全下降；HV在519共同case水平472下降/47上升，但Up154下降/365上升。SA尾部航向保护伴随平均水平代价，RD也非姿态全面改善。这些是在同一BY2及受控暴露下的条件证据，不是跨平台普遍定律。参考仍共享GNSS，不能称绝对精度认证。

已完成另身份的135失锁诊断：45条件×F04/RD-off/HV-off，实际IMU间隔修正版本，不能替换原495 ADD。故障域10/20s保留航向时，H RMSE九位置均值F04 0.430548/0.859800m、无HV 7.870438/30.474212m，9/9均改善；全源丢失10/20/30s时F04 8.981919/39.642001/94.441738m，几乎等于无HV，因为故障内本体辅助实际更新为0。故障域均值、终点误差、恢复域是不同量；见[135证据](../EXISTING_DATA_R5_20261005/existing_results/DIAGNOSTIC135_PAPER_RESULTS.md)。

H/O另22成员、7内部IMU中断、77重启记录的比较是复合版本/支持敏感性，含实际dt、heading预测、Jacobian/协方差与重启改变，不是纯“修dt”的独立因果证明。支持H58556/58580、O72810/76548，同时间和自身支持均保留；[完整说明](../EXISTING_DATA_R5_20261005/existing_results/GAP22_PAPER_RESULTS.md)。

新八段是更强的反例：NMB四段F03/F04最终8真实运行，F04 H RMSE1647.668/897.338/10265.359/955.324m；NMB1/2比F03更差。相邻有效GNSS位置间隔约163–173s，中间公里漂移并非厘米级迁移成功。XB四段无双fixed，8组合NO_INIT；空误差不等于0。T03采用输入事件派生−1.1s对齐，非参考拟合；最终16行与24次总native尝试须分开。当前辅助更新仍受GNSS事件调度，HV还有A1依赖，故“完全独立腿里程计长期抗GNSS失锁”不受现有证据支持。该边界正是后续解耦小试验的动机，不能直接预先宣布升级有效。

## 8. 未完成组与无需恢复的历史候选

|身份|真正缺什么|建议|
|---|---|---|
|D01直接几何、D02单receiver IEKF|历史归属/源码身份不闭合|停用旧排序，必要时才另立可追踪诊断|
|EXT05B Pavlasek附录MEKF|左右误差、reset、交叉协方差/符号未闭合|不以通用MEKF冒名，不为方法数补跑|
|LC01-M、LC01-S-M、LC01-2D|修改草案执行已取消|保留取消史；只有新科学问题才登记|
|Yin RAEKF|部分融合式有，完整R统计/feedback-reset缺口|先闭合数学链再谈性能|
|Chang FSTCKF|15状态、inverse/lift、beta、启动窗、TS、参数、点位共七门失败|不能用CKF加fading替原法|
|Jiang adaptive/fading CKF|全文VoR及唯一分支缺失|先核全文|
|Taghizadeh adaptive H∞ CKF|全文及H∞/adaptive/sqrt耦合缺失|先核材料/生命周期|
|HAO2018|只有token，无唯一论文身份|不得与Yin/Luo混名|
|Luo EXT06腿里程计GNSS/INS|中置信文献登记，未核全文/实现|最相关潜在对照；先确认方法定义与可实现输入，不承诺补齐|

原[27项具体缺口](../TIM_EVIDENCE_20261005/comparisons/UNRESOLVED_BLOCKERS_AND_MINIMUM_ACTIONS.csv)包含12未准入身份＋15已运行方法的较强主张边界；不是27个未实现算法。优先级应是独立/更独立参考、实物杆臂/安装、SDK速度物理点与坐标、时间/延迟、真实足端/接触来源，以及同输入公平对照。当前比较数量充分，恢复全部被取消CKF候选并不是最有价值的下一步。

## 9. 建议的论文论证顺序与最小表图集合

先回答“短侧向基线的高层位置差航向，在何种质量和倾斜/时间条件下可作为弱观测”，用A1定义、可用率/支持、EXT/RTKLIB原始观测路线及误差物理量边界。raw AR比较作为输入路线与适用条件，不把对方负结果转成自己的新AR创新。

再回答“机器人本体弱姿态/速度在松耦合骨架中实际贡献什么，代价是什么”，用原11配置中的四个单开关配对、故障期间真实更新计数、相同时间支持，外部LC01和接触InEKF作为信息结构背景。保留共同初态双天线、RP/HV并非独立足端里程计的事实。

最后回答“不同来源何时退化、何时辅助链一起消失”，用CORE失败和尾部、A1/A2的可用信息区别、135时域诊断、八段长缺测/NO_INIT；FGO严格/分段补充说明缺测策略和初始化信息为何决定支持。这个故事可以包含显著失败，不需要把每个表写成胜出。

建议正文四个比较面板，各面板有自己的度量：①raw航向native/fixed/held与支持；②LC导航H/Up/yaw及资格；③官方接触InEKF相对RPE/漂移；④严格FGO支持＋分段同GNSS1点性能。另列内部单开关因果表。不要做一张跨米/度/相对漂移、不同点位、不同输入的总排行榜。

附录保留30身份总表、12缺口、方法实现/作者差异、原协议与后来诊断时间线、所有失败/NO_INIT、共同支持、七内部类比范围。推荐表述是“本记录、输入和适配合同下的应用表现与边界”，证据最强的是同骨架单开关的条件作用；“优于所有现有算法”“完整复现30篇”“正确固定率”“独立真值验证”“无GNSS持续腿里程计”均超出当前证据。

## 10. 本轮复核范围与可复查方式

本轮人工读取AGENTS相关规则、旧ACTIVE_CONTEXT/data/claim边界、HX官方/退化结果、EXT早晚版本、严格/分段FGO、V3方法/矩阵故事、2026-10-05总验收和R5八段/时域诊断；用Python标准CSV解析30身份、126外部支持域、66自然双合同、16新数据及HX05主/补表，生成本文的241行证据和11配置映射。没有重新打开逐历元raw/reference、运行原科学包或把历史69/313/3316次验证算成本轮新增算法测试。

原验收的3316身份/支持检查与313项保存RMSE复算通过，是2026-10-05继承证据，见[原独立复核](../TIM_EVIDENCE_20261005/comparisons/BLOCK02_EXISTING_ARTIFACT_REVIEW.md)。本轮只对派生CSV行数/唯一身份/原token对应/源路径与Markdown链接进行必要核对；没有重复全部科学验证，也没有宣称已经核定真实整数或参考独立性。
