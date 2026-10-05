# 三篇原论文的实际写法与 r3→r4 改写依据

核查日期：2026-10-05。以下不是原文翻译或算法复现实验，是对作者提供的三篇论文逐页阅读全文、目视关键图表后，给出的结构与证据写法分析。页码均指 PDF 物理页；TIM 同时给印刷页码。完整版权文本和页面图仅存外部私有工作目录，不进入仓库。

## 1 选择和判断

选取两篇 GPS Solutions 滤波论文和一篇 TIM 实测系统论文，分别代表“新方法”“理论比较与性能评价”“测量系统与条件约束”。这样比只选载波模糊度论文更贴近原 V3 的实际定位：它使用接收机已输出的位置和速度，再构造基线投影航向、辅助观测与来源相关权重；它并没有内部求解一个新的载波整数问题。

| 编号 | 原论文和正式来源 | 已实际全文阅读 | 实际目视页面 |
|---|---|---|---|
| P1 | Chang Y, Wang Y, Shen Y, Ji C (2021), *A new fuzzy strong tracking cubature Kalman filter for INS/GNSS*, GPS Solutions 25:120. [DOI](https://doi.org/10.1007/s10291-021-01148-5) | 1–15，共15页 | 4、7、9、12、14 |
| P2 | Jiang C, Zhang S, Li H, Li Z (2021), *Performance evaluation of the filters with adaptive factor and fading factor for GNSS/INS integrated systems*, GPS Solutions 25:130. [DOI](https://doi.org/10.1007/s10291-021-01165-4) | 1–11，共11页 | 4、6、7、8、9 |
| P3 | Wang D, Dong Y, Li Z, Li Q, Wu J (2020), *Constrained MEMS-Based GNSS/INS Tightly Coupled System With Robust Kalman Filter for Accurate Land Vehicular Navigation*, IEEE TIM 69(7):5138–5148. [DOI](https://doi.org/10.1109/TIM.2019.2955798) | 1–11，共11页 | 3、4、6、7、8、9 |

全文阅读含附录、参考文献和作者简介；37页文字全部读到，16页关键图片实际查看。其余提供的 GINav、Wen 和 OiSAM 本轮只核首页/元数据以选样，没有新增“已阅读全文”的声明；既有原文符合性审查另有记录。

这三篇最值得借鉴的共同点是：先说清一个具体失效，再指出原算法中产生该失效的数学或信息位置，接着让实验小节逐项回答该问题，并用同一比较对象、量、窗口和图表给数值。原文的强势措辞、局部数字不一致和未充分描述的参考相关性不构成本项目升级主张的许可。

## 2 P1：新方法如何写到可识别、可验证

### 问题不是“精度不够”，而是两种不同的失败

第1–2页介绍动态跟踪与稳态精度的矛盾。第4页单设 Problem formulation，把缺口具体落在既有强跟踪滤波的两个设置上：统一的 fading factor 难以区分状态变化；固定 smoothing factor 又可能在稳态让较嘈杂的 GNSS 获得过大影响。这个段落的作用是告诉读者，下一节到底要改哪个数学位置，而非重述 GNSS/INS 有用。

第4–7页的 Proposed algorithm 随后逐项对应：位置和速度 innovation 分别检验，再进入两个模糊推理分支，生成随时间改变的 smoothing factor，最后调整 multiple fading factors。第4页 Fig.2 与第7页 Fig.5 实际能看出输入、分支、输出及它们进入预测协方差的位置。传统 CKF 部分作为已有框架介绍，创新集中在控制分支，不把整个惯导和滤波重新包装为原创。

### 实验同时给最终误差和内部响应

第7页明确四个算法、3D误差和局部窗口 RMSE 的定义。第8–11页依次测试运动状态改变、过程噪声失配、加速度计偏置失配；这些是三个不同问题，不是一条轨迹换三种图名。第9页 Fig.7 给误差，Table 4 按固定运动区间给数字，Fig.8 再给检验量和 smoothing factor 的时间变化，用来解释为何动态和稳态出现不同响应。

一个可借鉴的结果句结构是：**在什么工况和窗口，哪两个算法，哪个量从多少变到多少，图中的什么内部量同步发生了什么变化，说明了哪一级结论。**例如第9页左转区间1568–1664 s，Table 4 的位置 RMSE 从 STCKF-FB 的2.0821 m到新方法1.2472 m，约下降40.1%。这里的强处不是“40.1%”本身，而是读者可以立即找到比较对象、窗口、误差定义和证据图。

第12–14页加入真实飞行数据，给出不同动态窗口和误差曲线；复杂度小节给阶数量级，并没有用一个离线总运行时冒充在线最坏时延。

### 本项目应学什么，不能照搬什么

应学：将 heading 配对/状态准入、conditional SDK aid、来源相关 inflation 画成真正的数学接口；选一两个已有代表时段展示准入或更新计数，而不是仅说“quality was controlled”。若没有预先固定时段，应明确是回顾性展示。

不能照搬：该方法调整预测协方差的 fading/smoothing 机制，不等于本项目改变观测 R 的来源相关 inflation。其模糊参数含经验设置，本项目不能据此把有效工程参数称独立标定。

原论文也不能作为数字审查的替代：第12页 Table 7 目视确认，稳态总速度 RMSE 新方法0.0100 m/s，而 STCKF-IFF 为0.0089 m/s；其“所有列最低”说明与这一列不一致。正文的某些百分比也不能由该表给出的总列直接复得。这是本次读图发现的出版文本一致性问题，不是重跑原数据后的纠错结论。r4应借鉴论证结构，并坚持自己的数值台账，不能继承这种“所有方面均优”的强度。

## 3 P2：不发明一个新滤波器，也能写出明确科学问题

### 贡献是区分，而非堆模块

第1–2页指出 adaptive factor 和 fading factor 广泛使用，但它们在 GNSS/INS 中的理论作用位置和实际表现缺少清楚对照。第3–4页分别给公式，再集中比较：因子作用在完整预测 P、历史 P 或 Q 的位置不同；从 innovation 不能简单精确识别模型偏差和上一时刻估计误差；多通道矩阵与单因子的行为不同。第5–6页再把这些差异放进共同的15状态、loosely coupled CKF，实现和比较对象因此一致。

这为本项目提供了一条真实可写的 GPS 路线：**接收机位置解算层 heading 的准入与其下游速度依赖，怎样区别于原始载波约束/整数搜索，以及不同来源的观测在同一滤波骨架中如何影响各输出量。**贡献必须具体到信息位置、规则和被回答的问题，不能仅写“a complete framework”或“conditional utility”。

### 六方案不是六个名字，是六种可以解释的改变

第6–7页列明六方案：CKF、两种不同作用位置的 fading、fading matrix、adaptive factor、adaptive factor加robust observation scaling。第6页给装置照片、技术指标、IMU/GNSS频率和参考解由商业IE双差载波处理产生的事实。第7页 Fig.4 把六方案以同轴范围排成小多图，圈出出现差异的时段；第8页 Tables 2–3给位置、速度、姿态数值；随后 Fig.5和第9页 Table 4给innovation自相关、偏度和峰度。

可以直接借鉴的定量层级：第8页Table 2的X位置RMSE由Scheme 1的0.0347 m到Scheme 6的0.0288 m；第8页Table 3的heading由0.582°到0.387°。相比只给“更稳定”，它告诉读者改进发生在哪个量。第8–9页的统计诊断又回答“滤波残差有什么变化”，但接近高斯/白噪声的样本诊断本身不能证明真实系统全部误差已校准。

### 对本项目的直接约束

必须把“同骨架、一个明确改变”和“两个及以上设置同时改变”分开。原V3 basic position+heading到heading-gated position/velocity，同时改变receiver velocity、heading marker/残差处理及更新分支，不能照P2的单因子比较来称RV独立效果。对 SDK-HV、raw-Doppler aid、tilt prior、inflation 的真实一开关配对，才可在保持原版本和support的前提下讨论各量的条件效果。

参考解仍须写实。P2说明商业IE参考来源，但并未给本项目所需的共享GNSS交叉协方差测量。它可示范报告数据来源，不可借它把我们的共同GNSS lineage reference改称独立truth。

## 4 P3：TIM系统文章如何让设备、方程和验证连成一条链

### 三个明确问题，三个对应设计

第1–2页（5138–5139）说明低成本MEMS惯导、城市GNSS和约束条件，并明确NHC只在特定车辆/运动条件下成立。第4页（5141）Problem Statement给三类问题：解算层噪声模型失配、GNSS异常导致发散、中断时惯导增长。随后TC原始观测、innovation-based robust KF、NHC分别对应这些问题。

第3页（5140）的Fig.2明确IMU中心→GNSS天线相位中心杆臂；状态、坐标系、动力学与观测残差紧随其后。第5–6页（5142–5143）写原始伪距/Doppler及接收机钟差状态；第6页Eq.21–25定位robust修改innovation covariance/gain的具体位置；Eq.26–29明确NHC两个横向/竖向速度近零条件与选择矩阵。第4页Fig.4将新模块着色，使“改了什么”可见。

本项目不能继承其TC名称或NHC假设：原V3在navigation filter入口使用receiver solution和Doppler-derived velocity，并非这里的逐卫星17状态TC；SDK高层velocity没有已证joint/contact测量模型，四足侧滑、腾空和机身运动也不自动满足汽车NHC。

### 装置和参考不是一句“采用高精度设备”

第7页（5144）给路线、装置照片、STIM-300参数表和MP-POS830参考性能表，并说明临时基站RTK与参考系统的平滑融合；给IMU125 Hz/GNSS1 Hz、初始化和工作噪声。读者先知道数据怎样来，再看分层实验。

这篇表II还可见position一栏印为m/s；应识别为文内单位疑点，不能抄成设备标定结果。论文中列出的仪器specification并不自动等于本项目该次安装的校准证书，也不是共享参考相关性为零的证明。

### 实验标题直接对应设计目的，也保留坏结果

第7–9页（5144–5146）依次为：LC→TC、standard→robust、60 s模拟GNSS outage下NHC。第8页Fig.9把卫星数、PDOP与GNSS位置/速度误差放在同时间轴，再看Fig.10 robust结果；它没有用“大量成功运行”替代观测状态证据。

第7页Table III支持连续GNSS下robust TC位置RMSE4.3349 m，相比standard LC5.1850 m约下降16.4%；第8页相应正文说清比较对象。第9页Table IV同时给outage RMSE和maximum，不把两者混用。尤其第9页讨论承认NHC相对robust TC改善位置/速度最大误差，却让姿态最大误差变差，并把可能杆臂原因写为解释性假设。这种**先报负结果，再谨慎解释**，比把模块累积写成全面改善更值得借鉴。

不能照抄其“对几何免疫”等概括。原始观测使用也仍受几何可观性与噪声约束；少于四星可继续aiding不等于所有状态准确可观。本项目同样不得因raw-Doppler开关开启就称故障中存在独立Doppler更新。

### 旧TIM论文不是当前投稿要求的豁免

P3主要是系统误差和RMSE实测验证，全文未提供一个已经闭合的GUM测量不确定度预算。当前TIM作者指南明确区分algorithmic RMSE与instrument uncertainty，并要求测量链及I&M贡献足够具体。因此r4可以学习P3的“设备→方程→问题分层→结果”结构，不能以旧论文未做数值U为理由，宣称本项目未估预算已经验证了测量不确定度。

## 5 对 r3 的具体诊断：有科学结果，但主线仍被审查叙述分散

本次实际全文读了GPS r3的201行与TIM r3的223行（身份见覆盖收据）。r3已经有三自然数据、完整矩阵结果、single-component方向计数和负面结果，不应称“没有内容”。问题是多段以版本、身份和不能推出的结论结束，而问题的效果量、算法分支和观测行为留在SI；读者可能知道边界，却仍不能从主文独立理解核心设计和验证。

| r3位置 | 当前具体不足 | 原论文给的可借鉴做法 | r4应做什么 |
|---|---|---|---|
| Introduction末段 | 两个问题很合理，但贡献多用specified/conditional/complete等抽象形容 | P1第4页指向两个参数失败；P2第4页区分P/Q作用位置 | 用三句可检验目标：heading准入、aiding依赖、按输出量的增益/代价；每句指定方法接口及Results小节 |
| Methods 2.3 |阈值已有，但为何marker与residual共同判断、何时影响K不够直观 | P1第4/7页核心分支与滤波接口图 | 给精简准入分段表/算法框：pair/status→soft/hard规则→variance或reject；marker不是已标定u |
| Methods 2.4 | SDK依赖写实，但M、scale、heading来源和dispatch被长段文字遮住 | P3第6页约束方程+物理有效条件 | 一个转换式+输入条件表+dependency图；公开未知frame/POI不删除；接收机和raw-Doppler aid分列 |
| Methods 2.5 | 只给max/min形式，把cap/各source因子都交SI，难独立实现主贡献 | P1第5–7/P3第6页给参数生成及进入滤波的位置 | 在主文定义metadata与innovation输入、共同作用位置及固定cap；全部数值只能取已封配置，不另调优 |
| Experimental design | 6468/588/版本细节与核心问题交织 | P3第7页先装置和参考，再分别验证三问题 | 先3自然/完整controlled/一开关三类问题，再用小表列cohort、support、比较对象与量；历史identity放SI不抹除 |
| Results 4.3 | 472/519等方向数已在，但未给多数收益多大；RP/Doppler/inflation仍概括 | P2 Tables 2–3不止称优劣 | 配对表主文至少给median和mean(单位mm/deg)、方向数、共完成N和completion差；不能以mean替median或选择较好者 |
| Results 4.4 | ‘substantial horizontal benefit’缺主文量化，whole-window与in-fault含义不同 | P3 continuous/outage分开、RMSE/max分开 | 原V3 whole-window只报原量；135另用明确diagnostic小节报其accepted source/domain和已验收效果量，不能拼成同版本单因果 |
| Results 4.5 | raw compass/movingbase/FGO大量身份文字，核心support及效果难对照 | P2先明确方案，再表+图报告差异 | 精简native-layer/support/quantity表；保留strict Oi0/55与segmented协议，Wen/GNC无自产姿态；不做同输入solver排名 |
| TIM 2.6 | 方程正确但数值U输入未估；不能由加方程自动形成TIM已验证贡献 | P3装置表与实际实验验证，以及当前TIM明确要求 | 将现有model称measurement interpretation；逐项明确实测已知/模型声明/未估；若主攻uncertainty必须填物理、时钟、参考/SDK cross terms验证 |
| Discussion | 各节多次重复limit，挤压机制解释 | P3负面结果直接连接具体measurement约束 | 每条发现先解释信息路径，再一个集中限制段；共享参考边界Methods定义+Discussion一次，结果保持agreement用词即可 |

## 6 可直接给 r4 的结构和英文句型（本报告新写，不是原文翻译）

### GPS主线

1. **Problem and objective**：短基线方向对双位置误差敏感，低速course不等于body yaw；为什么直接把所有velocity报告加进滤波不等于独立信息。
2. **Conditional observation design**：相同receiver epoch基线→projected heading→fixed-status/marker/residual准入；robot aid转换与heading/dispatch依赖；R inflation进入测量更新的位置。
3. **Experimental questions**：自然agreement；同backbone single-component effects；heading retained vs complete-loss的可用性；外部route比较作为范围检查。
4. **Results**：三自然表现→效应量/负方向→失败/可用性→outage条件→external support，不按代码修订历史叙述。
5. **Discussion**：哪些结论来自真实一开关，哪些只是版本/结构复合比较；共享reference、实际frame/time/POI未闭合；与AR/movingbase是不同测量路由。

可替换抽象贡献句：

> We specify a receiver-solution heading update for a nominal 0.35 m lateral baseline and couple auxiliary velocity observations to their actual admission and dispatch conditions. The evaluation asks whether these conditions improve horizontal agreement, which other state quantities incur a cost, and when aiding becomes unavailable.

可替换“HV improves performance”结果句（已有r3方向数，效果量从封表填，不能虚构）：

> On the 519 commonly completed controlled cases, adding robot-reported horizontal velocity reduced horizontal RMSE in 472 pairs, while vertical RMSE increased in 365 pairs. The median and mean paired differences are reported alongside these counts, because improvement frequency does not identify the magnitude or its distribution.

可替换强AR比较句：

> The receiver-solution route and the constrained carrier-phase routes differ in observations, ambiguity handling, and fresh-solution support. Their retained outcomes describe the tested adapters and installation rather than a universal ordering of ambiguity-resolution methods.

### TIM主线

TIM应重新围绕“什么物理量、由哪些传感输入、在哪个点/时刻、何种相关性下可报告”组织。保留同一算法证据，但不把原GPS稿只加一个GUM段就称全新论文。未闭合校准时可用working manuscript定位，不能宣称经过验证的measurement uncertainty instrument。

建议Methods顺序为：measurand/frames/points→原始消息和timestamp来源→baseline与SDK变换→admission与融合→error/uncertainty传播及未估项→实验验证。结果至少分别回答量的定义一致性、可用性和误差/uncertainty解释；没有实测U时不填一个假预算数字。

可用英文：

> We distinguish the working covariance used for navigation weighting from the uncertainty of the reported heading and velocity. Baseline differencing, attitude-dependent velocity conversion, event timing, and comparison with a shared-GNSS reference introduce joint covariance terms. The available recordings validate the executed observation conditions and empirical agreement; they do not identify every input required for a calibrated uncertainty statement.

此句的价值是准确界定现有证据；TIM创新及实验完备性仍须真正补足，不能把限制本身当成已完成的计量创新。

## 7 本轮不需要新增估计器试验即可完成的写作动作

- 从已封原V3配对表取RP/HV/RD/SA的mean、median、量纲及完整support，放入主文精简表；方向数与误差大小同时呈现。
- 用已有源码合同画准入/依赖图，并说明进入K/measurement R的位置；不是重新设计原V3或调参。
- 用旧结果的明确版本和现有33/135诊断的小节区别主角色；严禁用新诊断填旧失败或选择后替换主方法。
- 为外部方法给fresh valid/support、quantity、物理点及输入层次，减少重复身份段；原作者完整实验未知不能变成已等价复现。
- 把完整历史/哈希/ledger移SI或evidence companion，把主文空间留给可检验问题和效果量；不能把支持核心结论的规则与关键结果全移出正文。
- TIM的物理安装、clock、reference correlation和SDK velocity/attitude covariance仍需要真实测量/记录；公开IDL、CAD和事件观察各能证明什么应分层，不能补造校准值。

## 8 当前官方要求与本报告判断分开

2026-10-05再次浏览：[GPS Solutions作者指南](https://link.springer.com/journal/10291/submission-guidelines)具体要求Word、约5000–5500词、double spacing、150–250词摘要、4–6关键词、author–year引用。期刊排版要求不等于科学贡献已经通过；5000词正文也不能替整篇文章计数。

[TIM当前作者指南](https://ieee-ims.org/publication/ieee-tim/information-authors)要求主创新落在I&M、区分algorithmic metric与measurement performance/uncertainty、给足可复核的装置和测量链、论证实验验证，并要求IEEE双栏自包含正文。上述具体写法建议是本报告的评审判断，不是官方规定必须新增某算法或重跑6468。

两分支是候选研究叙事，不能把同一研究和数值仅改标题后同时或重复发表。GPS公开稿件条款与出版社preprint政策存在既有已记录冲突，实际投稿前按既有路标核定；本次不改变仓库公开性或历史提交。

## 9 阅读和证据范围

- 所选三论文全文37页；16关键页实际图像检查。图像和版权全文只在 G:/LegSA-GINS-project/论文重写_20261005/.work/paper_models/。
- r3两稿全文201/223行；报告基于这些具体身份，不主张已读全仓每字。
- 原PDF读取前后SHA一致；本次无科学源码/原结果修改、无native/generator/evaluator执行，无新科学矩阵。
- 原论文数量和曲线均描述作者所报结果，不冒充本项目复现实验。版权页面没有复制进项目，报告没有连续摘录原段落。
