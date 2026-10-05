# 影响结论的实现与接口核查

本文件记录2026-10-05新增定向阅读与继承证据的区别。既有源码数学审查及作者核心绑定可以复用，但不能因此声称本日逐行读完所有源码/PDF。

## 1. LC01：初始化能力与真实运行不是同一个事实

`src/legsa_gins/paper_rebuild/hext/ext05_sequence_runner.py:802–819`可从起始GNSS1历元向后寻找有效双接收机基线，并把该基线的yaw放在起始时间的初态中。这里存在需要到达时刻/等待合同约束的能力边界。但本次对14个实际CLEAN7 native summary的两个时间字段逐一比较，`initial_time_unix_seconds == initial_yaw_source_time_unix_seconds`全相等。**未观察到这14个身份实际跨后续历元预载yaw**；不能把接口能力写成这些运行已经发生未来信息使用。两个早期BY2 LIT身份引用原批次收据，本结论不扩大为全部历史运行。

`parameters.py:100–120`把四个H02条件统一设为`DROP_DT_GT_0P1_AND_CONTINUE`；`ext05_sequence_runner.py:943–1005`对无效IMU源间隔不传播惯性，但推进state_time，仍尝试间隔内GNSS更新并记录次数。因此LC01输出连续性不是跨缺口具有完整惯性物理输入的证明。它与OiSAM严格不跨输入缺口、以及预登记分块重新A1初始化的策略不同。不能仅凭LC01和OiSAM支持差异确定solver更稳，也不应给不使用IMU的GNC人为套同样停机规则。

`ext05_pavlasek.py:248–259`确实实现`[p1,p2−p1]`必须保留的共享p1相关块`[R1,−R1;−R1,R1+R2]`，不是把6个测量误差都当独立。但`PHASE5_EXT05_PAVLASEK_CONTRACT_V1.yaml:80–88`同时明确R1/R2采用pAcc²I，跨接收机solution error independence并非exact。程序包含stacked correlation不能等同真实GNSS误差联合协方差已校准。

`parameters.py:49–78`的S分支读取本项目冻结sensor model：ARW单位转PSD、q与(vrw/60)²检查、全轴acc scalar s；103–120只统一H02 gap政策。S不是另一篇方法论文，其BY2开发重叠与LIT后验选择的披露必须保留。EXT05C/EXT05C-S是p1-only在线更新，但初始yaw仍来自双接收机基线，不得标为从初始化开始纯单天线信息。

## 2. 接触InEKF：官方核心已执行，观测接口未证明同作者

新读`hx02e_official_driver.cpp`全166行。90–103行先从缓存前一秒收集加速度重力方向，136–153行再从第一条缓存时间写输出。它是带一秒启动数据的离线驱动，不宜宣称首条输出在零启动等待时即可在线得到；不代表读了参考。139–140行调用作者`Propagate`与接触观测更新，不能把当前差成绩直接定性为作者程序仅有占位模块。

已继承官方core `ef16e8a1...`未改数学实现、58/58源与22/22 build对应证据；六个真实LIT/DEF身份均保留。输入却是Go2 `foot_position_body`高层FK proxy和force hysteresis，并非作者原关节编码器/噪声/接触接口。已有报告`HX02E_RESULTS.md:69–73`明确−1°仅作用IMU，FK是否本就在目标body frame未知；那里5.24mm/8.56m只是带条件的量级例子，不能当实际损害测量。

误差经过first10s的一次xyz+yaw四自由度gauge对齐，因此可评价相对漂移和输入适配，不能与绝对GNSS/INS定位排名。SDK速度+姿态积分另有三序列输入诊断，SDK成绩更小不证明InEKF数学错误。

## 3. RTKLIB与EXT：程序完整执行、整数正确性和角定义分开

新读V0/V1/V2配置各54行；四条件都用固定官方RTKLIB2.4.3_b34/180043ee。V0E只改变广播星历；V1再改变navsys33→57；V2再改变AR continuous→fix-and-hold。它们是同软件的四条件，不能计算成四篇独立算法。12个native与原13个离线评价身份区分（包含一项历史转换诊断评价）。

Q=1、固定率、ratio门或10°错误代理都不等于真实integer正确率。本日只从原保存误差重算Q1有效和因果保持，float无独立保存误差列，未声称重算float。各条件采用原1370/1350/1885配对分母。

EXT V2真实9身份仍绑定各自13项旧SOURCE_SNAPSHOT+config与输出，使用物理修正后的`iterated_geometric`卫星旋转/SPP合同。后置dimensionless近垂直guard与heading失败valid=false只改变三当前源，旧9个结果未重新运行；其19/75测试与15669/9100保存baseline无触发检查是后置修补证据，不能把新source hash写回旧9或135身份。

侧向baseline投影+90°不是任意roll/pitch下的Euler yaw。继承独立nominal-tilt诊断只有约0.031–0.044° RMS、最大0.4544°、RMSE差不超过0.004278°，因此不能用它解释64–104°量级的大误差；更不能把这一几何解释诊断称实物姿态/时延标定。

## 4. 三篇FGO：完整选定链与作者实验分层

原文身份/关键式/源码/合成oracle/真实事件已登记为上级45条[逐链表](../../FGO_COMPLETE_AUDIT_20261004/COMPLIANCE_MATRIX.csv)，本日逐条复读关键链/符号/源码范围/差异字段，而非重新读完全部PDF与每个源码文件。

OiSAM实际拥有Earth预积分/15状态联合残差/结构Givens缓存/边缘化/Ceres与选定A-JSWR工程解释；不只是给另一个滤波器套模块。严格一次A1身份B/H/O为275/0/55正式输出。H/O缺失IMU不能伪积分或补造：另身份分段只由事前真实input gaps分1/3/7块，每块都尝试，块内不得按数值失败重启。11次真实初始化源时间/信息量保留，主域排除prior-only；同点GNSS1运输使用Oi自己的估计姿态。作者完整Oi实现未取得，缓存前缀与触发解释仍不能承诺exact。

3286秒`NO_CONVERGENCE`在20次上限后仍usable，已保留真实状态/事件/加权因子及normal矩阵。均衡normal满rank与condition只能说明该诊断定义下数值维度，没有证明全算法正确或已经解决收敛问题。分段新图与历史旧图不是同一优化问题，不能拿新cost下降当旧错误修复收益。

Wen实现选定完整TC batch：码、motion、bias、右端AHRS/INS速度联系和LM求解；输出p/v/ba/clock，**不自行估姿态**。外部Go2 quaternion/acceleration设备不等价于已验证Xsens Ti10安装/噪声/动态延迟。GNC是完整码+原Doppler联系与GM state/weight交替，选定Eq21平方驻点，theta按1.4缩减、减后<1停止、末次solve权重与随后Step3新权重分存；原文Eq22不平方与作者Doppler接口仍待裁定。

这三法都存在真实完整选定估计链及真实机器人运行，但“所有作者实验完全复现”仍不能宣称。实际取得材料和未知材料详见[AUTHOR_MATERIALS](../../FGO_COMPLETE_AUDIT_20261004/AUTHOR_MATERIALS.md)。
