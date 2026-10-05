# GPS Solutions定位、证据范围及当前投稿要求（2026-10-05）

本文件补充GPS Solutions路线，不改变本轮TIM计量证据工作，也不执行新AR、native、evaluator或绘图。两个正文分支是备选写法，不是同一结果同时投两刊的授权。此前暂用读者名LegSA-GINS；作者正在讨论正式命名，名称不作为贡献证明。

## 1. GPS方向能够成立，但应写真实的输入层与研究问题

GPS Solutions官方scope覆盖GNSS系统设计、数学/算法、数据分析、用户硬件及具有创新或较高要求的应用；并没有要求每篇必须提出新整数模糊度算法。四足机器人短侧向基线、低速/转向时的航向与异源速度条件使用可以落在该范围。Scope符合不等于贡献已足够或保证接收。[官方scope](https://link.springer.com/journal/10291/aims-and-scope)

原V3消费两个接收机已产生的位置/速度解，按有向横向基线形成projected heading，再由质量/残差/来源合同进入GNSS/INS滤波；另有独立开关控制RD派生速度与机器人报告辅助量。它不是在V3内部估载波整周模糊度，也不是新moving-base整数搜索器。两个接收机固定在**同一机器人刚体**上，不是两个独立移动载体。“双固定状态”是输入质量条件，不是本方法证明了整数正确。

可直接写的英文研究问题：

> Under what receiver-status, synchronization, geometric and observation-admission conditions can position-derived heading from a compact lateral baseline support quadruped GNSS/INS navigation, and when do receiver, Doppler-derived and robot-reported velocity inputs add useful information or fail?

贡献主线宜是短基线方向的可用条件、辅助量依赖与完整失败/负结果。将已有KF加几个门限称全新估计理论，会超过证据；把小RMSE称校准absolute accuracy，也超过共享参考设计。本文的审稿判断是：需由具体条件分析和完整结果证明工程组合带来的知识，而不只是列更多实验格。原矩阵可以保留，不为文字层面的修正重新全量跑。

## 2. 与AR、moving-base文献的关系必须按层次说明

|研究层|真实输入/处理|本项目当前可写的关系|
|---|---|---|
|carrier-level ambiguity/moving-base attitude|相位/伪距等原始观测、整数状态、几何约束、质量验证|用相关primary文献解释更上游的技术；V3不冒称实现这一层|
|receiver-solution position-derived heading|两个已解的位置、天线顺序、共同历元、水平投影|原V3主线；接收机已有fix状态是给定输入条件|
|GNSS/INS辅助组织|GNSS位置/速度、IMU、独立RD开关、SDK报告状态及admission|原矩阵与保留诊断检验其条件效果；不是同输入solver排名|
|几何/原始观测/FGO外部工程实现|不同input层、点位、初始化、支持及失败合同|按实现与原文差异给分层参照，不从差RMSE推普遍算法失败|

原文符合性与作者原程序、论文所有实验的完整复现是不同层级。当前横向对比可说“选定论文算法分支的工程实现与真实执行”；作者未知代码或未执行的原数据集实验不能改名为完整作者复现。旧严格Oi单次初始化的缺测/失败与后续固定gap分块诊断保留各自身份；分块支持较多不回填严格结果。几何外部方法的大角误差经名义projected-measurand诊断仍不能凭安装轴未测的条件升格为普遍失效结论。

若未来真正研究新的AR或moving-base方法，应另立问题、phase级输入/时钟/几何与错误fix验证协议，不把已有V3重命名成新AR。当前最值得推进的是已有GPS论文成形、实际接口/安装/时间条件核实及必要范围分析；本轮未执行新科学AR矩阵。

## 3. GPS与TIM的不同主张

|项目|GPS Solutions正文重点|TIM正文重点|
|---|---|---|
|中心问题|GNSS短基线heading何时可用，以及辅助输入的冗余/失效条件|测量量、链路、时间/几何/相关性如何决定条件性能及不确定度|
|贡献证据|原V3完整矩阵、自然录制、成对配置/可用性与失败解释|有依据的joint预算、实际配置、计量验证；当前模型不是已完成校准|
|数学篇幅|投影角、admission、条件aiding及必要cross/时间边界|完整模型、measurand与各输入U/cross、可识别性及验证|
|结果措辞|在已声明点位/模式/支持下相对于共享商业参考的agreement|同样保留agreement；没有校准依据不把RMSE或working R称standard U|
|不能省略|共享GNSS、名义外参、scalar yaw近似、SDK工程frame、历史选择影响|同左，再明确clock/latency及输入U缺口、N08/N17等模型近似|

两个分支不能只换引言、标题和表格名称就分别发表同一核心结果。先选择一个投稿版本；若后续TIM形成实质新的计量方法/验证，须如实引用相关既有工作并说明新增贡献和重用范围。各刊的独占投稿规定仍适用。没有把共享数据另写论文自动视为禁止，也不把换模板视为足够的新论文。

## 4. 现有证据如何组织

主结果仍是作者选择的原V3全矩阵/三自然录制，不以2026-10-04纠错诊断替换；内部F04等代号放补充映射。原主位置/航向数值只从其冻结表引用。本轮稿件可使用以下已完成知识：

- receiver-quality、配对、投影与门控条件；GNSS1/2共享改正/环境误差及两receivercross仍未校准。
- 成对去RD/去机器人速度的结果保留负垂直/航向效果。原basic→gated比较同时改receiver velocity与heading treatment，不归因成RV独立效应。
- SDK辅助在heading仍可用时提供条件信息；完整heading/GNSS失效下不能当独立腿部odometry桥接。开关打开不等于故障内实际发生更新，按accepted source counts界定。
- 当前FGO/EXT等比较按input层、点位、prior、求解/适配耗时、支持及失败对照；不把工程适配后的优劣称同输入solver普遍排名。
- 作者确认事件对齐用receiver P/V与body IMU、CAD同安装、camera朝前；实际每段offset/drift仍未闭合。新八包实际POI/VRTK identity只支持这八包，不回贴旧三序列。

原V3的scalar投影/yaw近似、历史BY2调参与跨序列方法角色/质量选择影响应作为局限保留；没有online GT读取不证明所有开发过程完全盲化。有效高率epoch很多也不等于独立重复数量。旧矩阵完整性与统计独立性是不同事实。

## 5. 当前官方格式与政策（精简核定）

2026-10-05核了期刊-specific remarks：**Word**；约5000–5500词（不是只数body就通过）；150–250词摘要、4–6关键词；author–year与完整书目；可编辑公式/表；双行距；不使用footnote。检查EPS/TIFF或可接受Office图及最终尺寸可读性。需作者/机构/通讯信息、相关声明及Data Availability；实际资金/作者事实不造填。表图/附录与SI须配正文说明。[官方作者指南](https://link.springer.com/journal/10291/submission-guidelines)

同一官方页面的internet-posted manuscript措辞与出版社的统一preprint页面存在冲突：前者写限制，后者说明preprint不视为prior publication。当前仓库已有公开手稿；应在实际投稿前让期刊确认适用解释，并保留答复。此处不判自动拒稿，不把开放代码视为被禁，也不删历史/改变仓库visibility；没有在本轮联系编辑。[期刊指南](https://link.springer.com/journal/10291/submission-guidelines)、[Springer Nature preprint说明](https://support.springernature.com/en/support/solutions/articles/6000258807-preprints)

## 6. 最有价值的后续次序

|优先级|可用现有材料完成|必须新增事实或量测的部分|接受标准|
|---|---|---|---|
|P0稿件成形|正文按真实GNSS层次与研究问题收敛；原V3主结果/分母；旧诊断分列；书目/英文/Word/图表规范|作者、机构、资金与相关声明由作者给事实|所有主张都有准确来源/版本，无把诊断替主版、无同输入/完整作者复现虚称；整体篇幅与Word可编辑性核验|
|P0条件声明|既有config/source、实际支持/accepted counts、原文符合性和选择史|旧三序列配置/marker实际来源、firmware/topic语义未尽|每个时间/frame/POI句标证据层，无新八包回贴旧采集|
|P0测量条件|基线/投影/clock/SDK covariance的已有模型及条件解释|registered真实安装/相位中心、clock/latency、SDK物理frame/点|不把nominal尺寸/厂家规格写成实机校准；不能辨识者明确条件结论|
|P1验证加固|现有数据中可观察时序/质量/依赖/误差支持分析，统计单位和shared-reference解释|适合主张的独立/相关性已知局部检查量、留出验证|事前定义目标、完整missing/failure，输入U与cross有依据；保留negative结果|
|P2更上游GNSS|讨论AR/movingbase相关技术与本方法边界|若另立新AR研究，再补phase级协议与错误fix实验|作为新研究，不靠重命名原V3或为投稿强加全6468重跑|

GPS分支可继续成稿，不需要等所有TIM预算都量测完才写；但未证条件仍须公开，当前不能宣称投稿就绪或校准accuracy。TIM若要主打不确定度，应优先闭合本目录23项台账中最影响主张的事实与量测，不能仅将GPS稿的RMSE改称U。

## 7. 本轮阅读与范围

官方scope只读61–64行核心；指南选读82–109、112–208、212–280、288–353、356–386及620–655相关段落，不声明全文839行逐字审核；preprint说明读9–18。访问日期均2026-10-05。其余项目科学事实继承已封存文稿、原V3与横向交付及本轮来源块；本文件没有重算新结果或读取raw/reference。本轮仅交文档，与正式投稿动作分开。
