# NMB1 足点、SDK位置和速度：原点及时间只读核对

**关键新证据：同一481/242个END区间里，足点经SDK RPY推得的位移贴近SDK position端点差，SDK velocity积分则系统偏大约8%。** 已发现的END/source错配、固定区间长度使用错误和共同−1.1 s平移不能解释该差额。下一模型问题应优先定位到SDK速度与同源位姿/足点的内部估计及时间语义，不能把7.48%直接当作足点尺度误差。SDK position仍不是独立真值。

本轮只读已有完整源cache、足点provider及事件日志，不读raw/NAV/reference；native/evaluator调用0。没有拟合尺度、时移、杆臂或修改C++。原foot/SDK对比保持原结果，新读出不是替换原测量。

## 三者在同一源坐标和同一区间比较

用SDK raw RPY组成FLU→SDK world旋转，再显式乘diag(1,−1,−1)得到FRD→SDK world的Q。原始START/END整数ns完全复用。三种位移最后都投到START的body FRD：

- position：`Q0ᵀ(position_sdk1−position_sdk0)`。
- foot：两足平均 `r0−Q0ᵀQ1 r1`。
- velocity：`Q0ᵀ integral Q(t) v_frd(t) dt`，在同源全部时间节点上因果左ZOH积分。

这不引入导航姿态，也不把SDK world当NED真值。481个END完整保留，其中gap242个；包括原native后来拒绝的END机会，不按结果删条。cache中的所有足端点与provider逐点最大差0。

| 前向量，mm | 全窗481 | gap242 |
|---|---:|---:|
| foot位移均值 | 79.946578 | 89.416283 |
| SDK position位移均值 | 80.064639 | 89.821795 |
| SDK velocity积分均值 | 86.856152 | 97.055504 |
| foot−position均值 | −.118060 | −.405512 |
| foot−position RMS | 2.012569 | 2.172331 |
| velocity−position均值 | +6.791513 | +7.233709 |
| velocity−position RMS | 7.818024 | 8.125388 |
| 累计foot/position | .998525 | .995485 |
| 累计velocity/position | 1.084825 | 1.080534 |

改用RPY后gap foot−velocity前向仍为−7.639221 mm，97.93%为负；原gyro版为−7.260 mm。RPY和gyro两时刻相对旋转的角差median/p95=.127031°/.238771°，不足以消去该主差额。gap三维foot−position均值为(−.406,+.229,−.180) mm，velocity−position为(+7.234,+.755,+4.061) mm。不是仅前向一个轴的现象。

SDK position可能与foot共享内部运动学/滤波状态，所以二者贴合不证明哪一支物理正确；但它把“应优先检查哪条通道”收窄到velocity这一支。它仍不能单独区分SDK速度尺度、内部滤波延迟、接触相位处理或position/foot的共同偏差，更不能据1.080534立即缩放velocity。

## 时间和区间：未发现当前执行错配

| 核对 | 实际结果 |
|---|---|
| START/END source/event/available | 1645端点三者完全相等 |
| 原始整数ns到provider身份 | 0错配 |
| XY/XYZ event_time与native state_time | 各2328事件差均为0 |
| gap END真实dt | min .100000218、median .101997532、max .109282053 s |
| 全窗END真实dt | mean .102305533 s；没有用.2 s机会周期当测量长度 |

`PairSchedule`使用当前raw行建立START，首个满足真实起点+100 ms的有效raw行建立END，事件与源时间同值：`foot_pair_provider.py:45–61,86–110`。NMB适配在同一parse回调取当前两足坐标并记录raw整数ns：`support_pose_nmb1_provider.py:64–70,99–115,130–135`。native parser要求source=event=available：`support_pose_events.cpp:37–45`；engine逐事件拆分原IMU增量，保存其dt而非重造固定dt：`gi_engine.cpp:773–796`，END还要求event/state完全同刻：`gi_engine_support_pose.cpp:77–78`。

pose因子直接使用p0/p1、R0/R1与足点位置，不把位移除以固定.1/.2 s：`pose_clone.cpp:125–157`。源内SDK积分也使用每个节点真实ns差：`nmb1_support_sdk_consistency.py:109–128`。原body offset=−1.1 s对foot、velocity、gyro共同平移，只改变绝对时间标签，不改变这些同源相对dt；它无法解释已出现的源内冲突。未测到的SDK各字段内部不同延迟仍可能存在，但本轮没有估计延迟或更改offset。

## 原点与lever：真实缺项及其当前边界

令l为body原点到IMU的向量，r为body原点到foot的向量，则固定足点应满足 `p_IMU0+R0(r0−l)=p_IMU1+R1(r1−l)`。现foot模型确实采用这个减号：`pose_clone.cpp:140–143`，没有把foot误加到IMU两次。

现body速度模型却直接预测 `Rᵀ v_IMU`，没有原点转动项：`body_velocity_model.cpp:5–18`。如果SDK velocity定义在body原点而l确为非零，同一物理观测应为 `Rᵀv_IMU−ω_(body/world)^body×l`，并与foot使用同一l和旋转外参。不能只在foot侧加lever而让SDK仍测另一个点。当前l=0是明确工作假设，不是机械标定；共享文件没有提供已核实的非零原点外参。

发现一项**当前休眠的确定实现问题**：engine先将foot乘 `foot_frd_to_engine_body`（`gi_engine_support_pose.cpp:98,112`），却把命名为body-FRD的lever未经同一旋转直接送入footModel（同文件124行）；loader只是原样读入（`port_config_loader.cpp:555–562`）。非identity旋转且非零lever时，两者将不在同坐标。当前全部identity＋zero，因此该问题对已完成结果没有作用，按本轮约束只登记、不改C++。

如果foot和SDK velocity已经指向同一body原点，IMU零lever不能解释本轮不含IMU状态的源内冲突；若二者参考点不同，则共同项可含 `(I−D)l`。对原gyro版gap冲突作非拟合必要条件计算：仅解释前向差所需lever范数的逐区间下界median/p95=.291/.581 m；这是允许各区间自由选最有利方向后的下界，**不是估计出的真实lever**。纯lever项还必须垂直于旋转轴，而原冲突沿旋转轴分量RMS3.553 mm。此量级与约束都反对把全部误差草率归到“小的IMU偏心”，但机械量未确认，不能宣称已标定或彻底排除物理原点差。

## 下一统一模型动作的约束

当前最有证据的优先级是：先厘清SDK velocity与同源position/foot的时间及状态定义，并与真实body→IMU外参共同建模；不能继续把foot端点与SDK速度交替当成彼此独立、同参考点、同有效时刻的白噪声测量。若采用非零lever，必须同步进入foot和body速度观测，保持共同R/v/p及gyro bias依赖；没有已确认机械值时，不为本次结果拟合一个lever。源码原−1° IMU映射与当前identity足点/SDK映射仍属既有约定，本轮源证据不能把其物理含义唯一反推出来。

本轮已经足够区分下一候选：不是简单axis翻转、dt长度除错、END配错或先给foot乘尺度。三者的同源一致性证据支持优先修正信息使用关系及SDK速度语义；它没有授权把SDK position加入导航或当作真值，也没有给出可直接采用的数值校正参数。到此停止，没有新增参数搜索。

脚本 `scripts/paper_rebuild/unified_legged_heading_20261007/nmb1_source_point_time_audit.py`。完整输出 `.../UNIFIED_LEGGED_HEADING_20261007/NMB1_SOURCE_POINT_TIME_AUDIT_01/`：`SUMMARY.json`保存时间身份及必要lever条件，`INTERVALS.csv`保存481条三者比较。仓库精炼表 `NMB1_THREE_SOURCE_METRICS.csv`。


## 补充：实际运行的 −1° frame 链（同轮只读核对）

IMU8 活路径是 R5 `ATTEMPT_03/INPUTS/NMB1/IMU8.imu`，实际SHA256与NMB三臂PLAN一致：`112add1085b03ae14896241d46fe5d613715b09fea07bd382390ff0658a2f22b`。不是旧死代码。`new_data/run_new_sequences.py:96–100`将原始FLU gyro/acc先乘 F=diag(1,−1,−1)，再乘 C=Rx(−1°)，gyro扣C之后首1000帧均值，acc保持scalar 1.0308398903907543，按实际dt形成增量。`align_and_run_new_sequences.py:31–42`直接调用同一函数，仅统一平移−1.1s，并逐项断言增量与上一attempt不变。

C的数值是 `[[1,0,0],[0,0.9998476951563913,0.01745240643728351],[0,-0.01745240643728351,0.9998476951563913]]`。以缓存80295条真实raw-FRD gyro核对 `IMU_dtheta/dt + saved_bias = C gyro_rawFRD`，三轴最大误差均2.22e−16 rad/s，最大时间舍入差1.1921e−7s。同80295条GO2_RP严格等于原SDK `[roll,−pitch]`，没有对应1°补偿。

|实际通道|当前body轴操作|代码证据|
|---|---|---|
|IMU gyro/acc|F后C|R5 run_new_sequences.py:96–98|
|SDK RP|[roll,−pitch]，无C|同文件100；go2_weak_prior_factor.cpp:20–23直接与state Euler作差|
|SDK body速度|仅F；二维只保留x/y|body_velocity.py:71–72；body_velocity_model.cpp:10–18直接预测Cbnᵀv|
|足点|仅F；配置再乘identity|support_pose_nmb1_provider.py:115；nmb1_support_pose_navigation.py:95–96|
|PVT短基线方向|engine body −y，没有C|gi_engine.cpp:1298、1309|
|carrier body基线|[0,−.35,0]，没有C|当前NMB配置182；gi_engine.cpp:1422–1425|
|GNSS杆臂/init|[.03,.03,−.3]；[roll,pitch]=[0,0]，没有C|当前NMB配置29、44|

IMU loader第59–60行直接赋值dtheta/dvel，没有隐藏逆旋转。上述不对称是确定的软件事实；是否物理错误取决于C是不是确有依据的sensor→body安装变换。可查来源只有`final_v23_parity_contract.yaml:180–193`的归档固定安装常数及R5继承；没有找到实际−1°量测/机械校准证明，也不能推断它一定是场景调参。`CLEAN5_PARITY_CONTRACT.yaml:424–429`的“Input-side static calibration”说的是acc scalar，不是−1°。`FOOT_PAIR_PROVIDER_PLAN.md:7`先前把C解释为IMU安装，因而feet不重复旋转，并明确不是本轮独立实机标定。最近安装证据`TIM_EVIDENCE_20261005/installation/INSTALLATION_EVIDENCE_REVIEW.md:14–15`的两种URDF名义旋转均0；它们本身也不是实际IMU外参测量。

这把下一步优先级进一步具体化：先建立所有通道可解释的同一body frame，再研究SDK内部速度语义。若在研究链选择rawbody FRD，最少输入改动是对现有IMU gyro/acc增量左乘Cᵀ，同时一致旋转原bias表示并保留scalar/dt；这是撤销未证实历史安装假设的模型诊断，不能先称确定bug修复。另一种表示是保留C而把所有body量一致转入C轴：需要SDK原Z、RP旋转右乘Cᵀ、baseline C[0,−.35,0]=[0,−.3499466933,.0061083423]，还包括杆臂/init/bias/相应噪声协方差的坐标变换。两种完整表示是坐标等价的，不能把它们当两个可择优参数臂；仅改foot旋转则不完整。本轮未实施其中任何一种。

统一Rx绕forward轴，故统一变换不会改变三源比较的forward分量，不能消除前面约7.6mm的源内前进冲突；混合frame却可能通过roll/重力投影影响NAV右/下速度与bias。g sin1°约0.171m/s²只说明理论敏感量级，不是已测得的本序列误差。新增读出身份与数字保存在同scratch的`ACTIVE_FRAME_CHAIN_AUDIT.json`；没有新native、参考调用或raw扫描。
