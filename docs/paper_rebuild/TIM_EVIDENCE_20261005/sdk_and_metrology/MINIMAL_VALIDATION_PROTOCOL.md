# 最小验证协议与接受标准（拟议，2026-10-05）

本协议没有在本轮执行。它不要求为写TIM重新跑原V3全6468矩阵，不把新增材料回贴成旧采集已校准。下面的数量、阶段和阈值选择是项目设计建议，官方TIM没有逐项规定这些实验。原V3结果继续报告其实际输入、支持和经验agreement；后续计量验证另建身份。

## P0-A：先锁定接口、配置和记录归属

最小资料：每次采集的日期、机器人/接收机/FP设备身份与firmware、SDK/collector commit、topic、消息版本、配置、天线顺序、对齐规则及body/GNSS文件配对。每段还须说明outer stamp是在采样、估计还是发布时形成、clock epoch、tick单位与reset规则。当前公开IDL只证明字段，不能补写这些实机事实。

接受标准：每一条Methods设备/frame/时间句都能对应作者事实或具体记录；不明项逐项标unknown；不同年份/序列的默认配置不混用。新的八份body日志与八包接收机记录须按采集身份配对，不能因时间相近自动代换BY2/H/O。先核新包实际FP_A-TF/status，再讨论输出点和参考模式；POI/VRTK相等也不等于机器人IMU与两天线点位已闭合。

现有代码/数据可做：完整字段/时间连续性机器profile、topic/版本痕迹、实际消息中配置与status、已采用base_time/offset及其来源。输出包含完整选择/缺失记录和hash。本块阅读profile，没有重做科学数据处理。

## P0-B：事件对齐与clock offset/drift分离

每段保存接收机P/V和机身IMU的原始marker时标、所选区间、操作记录及变化定义。加速度尖峰、速度起动、位置移动应各自定义规则；不要任意将不同量的最大峰当同一采样时刻。人工判断保留允许区间，并做独立重复标记以量化选点重复性。

一个起点只接受“有效相对起点差”结论，不能接受drift估计或纯clock offset结论。若旧段只有一个事件：报告实际配键方案、δτ未识别项及动态敏感度；不将其拟成已同步。新验证优先采用同时可记录的硬件timing/clock比较。若只能用运动事件，建议至少三个分布于记录起、中、末的重复事件，加独立留出事件；这是让拟合与诊断分开的设计选择，不是仅凭三个事件就证明clock模型。

接受标准：设计矩阵对拟估的clock量满列秩；拟合使用已说明的延迟/响应模型；留出marker残差及其区间与事前声明的应用时间预算相容，且无未建模的时间趋势/reset。先登记应用的uτ,target与实际motion敏感度目标，再看留出结果。常数延迟未独立测得则报告b_eff；延迟变化未分离则报告effective slope而非纯晶振drift。拟合不得最小化同一测试段的商业融合轨迹误差。

不可接受：用epochlike数值日期吻合证明同步；用ros echo采样间隔当latency；把所有marker视为IID；把marker方差同时计入U_bd和另加的误差项。

## P0-C：最小几何及实际输出点注册

按同一明确坐标系注册robot IMU敏感中心、SDK velocity点、FP外壳X标记/IMU、output POI、GNSS1/2相位中心。保存装配版本、坐标轴定义、天线编号/顺序、使用仪器和不确定度来源、原始尺寸读数、重复装配/读数及环境。CAD对应同一结构可作构型来源，模型部件原点不能代替相位中心；照片不作毫米尺寸拟合。

接受标准：每个用于转换的刚体edge及inverse方向均明确；变换链闭合仅在同一对象/版本下检验。量测precision须满足事前列出的被测量目标，经Jacobian/非线性传播后预算不超过目标；厂商“3cm外参要求”不能作为未做量测的误差分布。若无法量测，明确nominal geometry并给条件/假设bound，不称traceable calibration。

近垂直基线应在预算可信后按水平投影、目标uψ及错误fixed风险判定可用性。单纯r²数值门通过只能说明程序可算；不可当实用精度接受标准。

## P0-D：SDK速度frame、点位与相关性

先取得与本固件相符的接口定义或设备支持文档。利用可重复的已知静态朝向及独立可观察的前向/侧向/转动运动检验轴、符号、单位与报告物理点；记录接触/gait/status，不能以调一个yaw offset抵消frame错误。项目quat→rpy自洽只验证同一报告内的数学一致性。

接受标准：事前候选frame和点位的观测预测可区分，留出方向/转动数据与选定解释一致；报告不能判别的候选。若SDK是世界/odom速度，必须按实际定义改测量模型的描述，不能继续宣称独立body FK量测。未取得内部算法时，诚实报告opaque robot-reported estimate。

相关性验证：对有独立速度和姿态检查值的同步记录共同估误差样本、cross及时间dependence；若只用共享GNSS检查，则只得到该检查条件下的差，不独立分离SDK与GNSS误差。cross无法辨识时用有依据的bounds/情景敏感性并保持条件结论；不要零填或从两个边际cov猜出完整joint。measurement与filter prior的cross亦应进入滤波性能解释。

比例k、IMU bias/noise/安装补偿的拟合数据与验证数据分开，保留既有BY2调参声明和历史inspection/selection限制。原F02→F03同时改变receiver velocity和heading gate，不能称RV单开关因果。若后续论文确要独立RV效应，再设计只改该开关的事前对照；本轮不执行，原矩阵不重构。

## P0-E：参考模式、同量定义与预算验证

先锁实际参考message/version、POI、time、frame及camera/IMU/GNSS参与状态。新八包的实际POI/VRTK identity若有效，只对该八包成立；旧三序列单独核。建立方法与reference的共享source表，同点运输及投影角/Euler量定义不能省略。

最小验证可用一个与研究输入不共用主要误差来源、并有自身测量不确定度的局部检查量：例如已注册的基线方向/长度、受控位移/速度或适合场景的外部量测；不规定必须哪一种设备，也不捏造其precision。不需要先覆盖完整任意大场地，需覆盖当前主张的代表工况，并说明未覆盖动态/环境。

接受标准：报告被检查量的定义、标准/参考值、其U及与本链的共享来源；依联合传播计算差值cov。对留出数据事前规定coverage/误差界限和分组规则。时序相关采用session/block单位或经证据支持的dependence模型；连续epoch不能直接作为独立重复次数。报告valid输出分母、拒绝/缺测/failure、wrong-fixed事件及原始支持；没有输出的样本不以成功子集替代全分母。

只能以共享商业reference验证时，可接受的结论是“在指定支持、模式、点位及相关性假设下的agreement”，不能接受校准absolute accuracy。依据U_d的normalized difference也必须有可信joint/independence或明确bounds；从同一数据拟U_d再以同一数据coverage通过不是独立验收。

## P1：模型、统计与结论加固

1. 将N08 reset近似、N17 Earth耦合截断、RV/RD Earth-relative角速近似等模型边界列为model-discrepancy来源；先作量纲/解析bound及独立验证，不因PSD矩阵就宣称协方差校准。
2. 在预算输入有依据后检查一阶线性化有效域；短投影、wrong-fixed mixture及角wrap可能需要分布传播。Monte Carlo必须输入可信joint分布，否则只能称assumed sensitivity。
3. 实际accepted source counts与availability按工况报告。D61故障期没有accepted HV；D62的HV依赖有效heading；RD开关不能证明故障期RD有实际更新。已有完整记录可补写，不用新成绩调参。
4. 用未用于选择的session/installation作为统计验证单元。现有三序列的相关性/调参史如实报告；不是据实验格数宣称独立泛化样本量。

## 交付形式及停止规则

每阶段产生source/config身份、原始记录列表、derived表、拟合/留出划分、完整不确定度输入及cross、计算软件版本、接受/不接受结论。若缺少一种量，仅停止依赖它的校准主张；现有经验agreement与范围受限的方法说明仍可写。

本协议的目标是补齐最有价值的计量证据，而不是为TIM重新包装所有历史实验。现阶段submission_ready=false；论文应准确说明已完成研究与尚未验证预算的区别。
