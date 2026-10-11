# 原 15 组图：按当前科学问题阅读

**最新修改：** [S9/S8 正文姿态合图及逐面板说明](revisions/attitude_main_20261011/README.md)。以下保留原图作为来源版本。

旧 M/S 编号仅用于文件定位。S9/S8 当前为核心姿态结果。PDF 是原导出，预览为已有彩色 PNG；数据与图注不重算。

## M1 · 机器人自身观测与绝对航向

![M1](figures/robot/preview/Q1_proprioception_absolute_heading.png)

[原始 PDF](figures/robot/Q1_proprioception_absolute_heading.pdf) · [来源与图件元数据](figures/robot/Q1_proprioception_absolute_heading.json)

读图顺序：左图说明同样自身观测可以对应多个全局方向；右上说明初始方向差异在时间中保留，而局部航向变化相同；右下给出这一现象的结构来源。它支持论文对外部绝对方向约束的需求。

**中文图注：** 机器人自身观测下的绝对航向自由度。（a）同一组 IMU 与足端接触数据的七次已保存运行，初始航向覆盖 −150° 至 +150°，在任意局部坐标系中形成相互旋转的轨迹。彩色突出 0° 与 ±100°，圆点表示共同起点与各轨迹终点。（b）展开后的航向演化保留初始方向差异；插图为预先根据输入选定的 0.216 s 双接触窗口内航向增量，七条曲线重合。（c）含偏置模型在五个预选接触窗口的已保存可观测性奇异值，分别除以各自最大奇异值，并按从小到大排序。两段四接触与三段双接触窗口分别对应 27 维和 21 维状态；前四个方向均低于相对秩阈值（虚线，10⁻⁹），对应三维全局平移与一维全局航向自由度。不同标记表示不同窗口。仅消除各运行初始旋转后，最大位置差为 1.90 × 10⁻⁷ m。该组实验验证同一自身观测下全局方向的等价性。

**English caption:** Absolute heading freedom under proprioceptive sensing. (a) Seven stored runs of the same IMU and foot-contact data, initialized at yaw angles from −150° to +150°, give rotated trajectories in an arbitrary local frame. The 0° and ±100° runs are highlighted; dots denote the common start and individual endpoints. (b) Their unwrapped yaw histories retain the initial offsets. The inset shows yaw increments over an input-selected 0.216 s two-contact interval; all seven curves overlap. (c) The saved observability spectra of the bias-augmented model for five preselected contact intervals, each divided by its own largest singular value and ordered from smallest to largest. Two four-contact and three two-contact windows contain 27 and 21 state dimensions, respectively. The first four singular directions fall below the relative rank threshold (dashed line, 10⁻⁹), consistently with three global translations and one global yaw degree of freedom. Different markers denote different windows. Removing only each run’s initial rotation gives a maximum position discrepancy of 1.90 × 10⁻⁷ m. The experiment demonstrates equivalent global orientations under the same proprioceptive observations.

## S1 · 接触辅助估计与机载姿态参与积分的相对运动表现

![S1](figures/robot/preview/S01_robot_relative_motion.png)

[原始 PDF](figures/robot/S01_robot_relative_motion.pdf) · [来源与图件元数据](figures/robot/S01_robot_relative_motion.json)

结构图解释绝对方向自由度；这张补充图展示同一平台输入下相对状态估计的实际误差演化，以及机载姿态参与的运动学积分参照。

**中文图注：** 接触辅助状态估计的相对运动误差。各列分别对应一种工况；在评价窗开始的10 s内进行一次平移与航向对齐后，上、下排分别为水平和航向误差。官方接触辅助InEKF分别采用文献与示例噪声设置；接触运动学积分使用接触足速度和机载姿态。小窗放大常规行走的前40 s。曲线采用已完成评价的原时刻。

**English caption:** Relative-motion errors from contact-aided state estimation. Each column corresponds to one trial; the upper and lower rows show horizontal and heading errors after a single translation and yaw alignment over the first 10 s of the evaluation window. The official contact-aided InEKF is shown with literature and example noise settings. Kinematic integration uses contact-foot velocity and onboard attitude. The inset enlarges the first 40 s of nominal walking. All curves retain the completed evaluation times.

## M2 · RTKLIB原配置下短基线航向的输出与物理一致性

![M2](figures/heading/preview/Q2_heading_availability_and_consistency.png)

[原始 PDF](figures/heading/Q2_heading_availability_and_consistency.pdf) · [来源与图件元数据](figures/heading/Q2_heading_availability_and_consistency.json)

新固定输出的覆盖率与输出后的物理一致性是两个问题：本组数据中固定解稀疏，且固定状态仍可能伴随显著长度残差。

**中文图注：** 原始RTKLIB动基线配置下，短基线航向的输出可用性与物理一致性。(a) 三种工况中新固定输出的绝对航向误差累积分布，小窗放大0–20°，保持原累积分布分母。(b) 新固定输出的时刻；百分比以各实验窗内的全部配对历元为分母。(c) 常规行走评价窗内全部153个固定输出的基线长度，其中35个日志长度残差超过4σ。虚线为安装长度0.35 m，灰带为配置长度标准差σ=0.01 m所对应的±4σ范围。(d) 放大(c)中的10–22 s着色区间。所有面板均使用保存的实验窗口；航向由横向基线的水平投影换算，并与参考航向比较。

**English caption:** Availability and physical consistency of short-baseline heading from the original RTKLIB moving-base configuration. (a) Cumulative distributions of absolute heading errors at newly available fixed outputs for the three trials; the inset enlarges 0–20° without renormalizing. (b) New-output times; percentages refer to all paired epochs within each trial. (c) Baseline lengths of all 153 fixed outputs in the nominal-walking evaluation window, including 35 with a logged length residual above 4σ. The dashed line is the installed length of 0.35 m, and the gray band is ±4σ with the configured length standard deviation σ = 0.01 m. (d) Enlargement of the shaded 10–22 s interval in (c). All panels use the saved trial windows; the heading quantity is obtained from the horizontal projection of the lateral baseline and compared with the reference yaw.

## S2 · RTKLIB四配置的航向误差与输出连续性

![S2](figures/heading/preview/SQ2_RTKLIB_all_configurations.png)

[原始 PDF](figures/heading/SQ2_RTKLIB_all_configurations.pdf) · [来源与图件元数据](figures/heading/SQ2_RTKLIB_all_configurations.json)

将“有一个航向值”与“此刻有新的有效航向解”分开，让长时间保持旧值的误差和稀疏新解都能直接看见。

**中文图注：** 常规行走、大幅机身运动和单侧天线遮挡实验中，RTKLIB动基线航向误差与输出时间。四种配置依次为原始配置、修改星历、扩展星座选择和fix-and-hold处理。上排为新固定解的误差，中排为相邻更新之间保持最近一次航向时的误差，下排标出新解出现的时刻。

**English caption:** RTKLIB moving-base heading errors and output times during nominal walking, large body motion and single-antenna obstruction. Original, Alt. eph., Multi-GNSS and Fix-and-hold denote the original configuration, modified ephemeris, extended constellation selection and fix-and-hold processing, respectively. The upper row shows errors of newly available fixed solutions; the middle row shows errors when the latest heading is held between updates; the lower row marks new-output times.

## S3 · 三种原始双天线处理路线的误差分布与输出

![S3](figures/heading/preview/SQ2_raw_dual_antenna_methods.png)

[原始 PDF](figures/heading/SQ2_raw_dual_antenna_methods.pdf) · [来源与图件元数据](figures/heading/SQ2_raw_dual_antenna_methods.json)

完整使用九组保存结果，把方向误差分布与输出覆盖分开呈现，避免密集正负180度跳转线遮住三种方法的差别。

**中文图注：** 三种原始双天线观测处理方法在常规行走、大幅机身运动与单侧天线遮挡下的航向误差分布和可用输出。上排为各方法已记录有效输出时刻的绝对方向误差累积分布，下排标出对应输出时间。C-LAMBDA和C-WLS为对应约束目标的独立实现，这些方向候选未设整数接受检验；DD-KF使用保存的双差滤波输出，不插入保持航向。所画方向由横向基线的水平投影换算，并与参考航向比较。

**English caption:** Heading-error distributions and output availability for three raw dual-antenna processing methods during nominal walking, large body motion and single-antenna obstruction. The upper row shows cumulative distributions of absolute directional error at each method’s recorded valid outputs; the lower row marks their output times. C-LAMBDA and C-WLS denote independent implementations of the constrained objectives, with no integer acceptance test on these candidates. DD-KF uses the saved double-difference filter output. No held heading is added. The plotted direction is derived from the horizontal projection of the lateral baseline and compared with the reference yaw.

## S9 · 基础GNSS/INS加入双天线航向的作用

![S9](figures/aiding/figures/preview/S_Q4_heading_information.png)

[原始 PDF](figures/aiding/figures/S_Q4_heading_information.pdf) · [来源与图件元数据](figures/aiding/figures/S_Q4_heading_information.json)

基础配置加入航向链后持续航向误差明显降低，完整方法与该配置的航向曲线接近；二者微小差值不是本文全部收益。

**中文图注：** 基础GNSS/INS、基础配置加入双天线航向更新以及完整LegSA-GINS的航向误差。三列依次为常规行走、大幅机身运动与单侧天线遮挡。（a–c）完整误差时序，灰色区间在（d–f）放大。三种配置共享初始方向；前两种配置用于解释加入双天线航向链的作用，完整方法还包含其他辅助。

**English caption:** Heading errors for basic GNSS/INS, the same basic configuration with dual-antenna heading updates, and LegSA-GINS. Columns correspond to nominal walking, large body motion and single-antenna obstruction. (a–c) Full error histories; shaded intervals are enlarged in (d–f). All three configurations share an initial direction. The first two configurations isolate the addition of the dual-antenna heading chain; LegSA-GINS also includes the other enabled aids.

## S8 · 机载倾角辅助与姿态误差

![S8](figures/aiding/figures/preview/S_Q4_tilt_aiding.png)

[原始 PDF](figures/aiding/figures/S_Q4_tilt_aiding.pdf) · [来源与图件元数据](figures/aiding/figures/S_Q4_tilt_aiding.json)

蓝线相对零线更近的区段，就是倾角辅助直接改善机身姿态的时段。

**中文图注：** 三条实测序列中机身倾角辅助对横滚、俯仰误差的影响。蓝线为完整方法，橙色虚线为关闭倾角辅助；每列对应一个序列，上下分别为横滚和俯仰。

**English caption:** Roll and pitch errors with and without robot tilt aiding during nominal walking, large body motion and single-antenna obstruction. Each column shows one recording, with roll above and pitch below. The zero-error line represents the reference attitude. All curves use the same fixed parameters and their recorded timestamps.

## M5 · 保留航向时的机身速度辅助

![M5](figures/aiding/figures/preview/Q4_body_velocity.png)

[原始 PDF](figures/aiding/figures/Q4_body_velocity.pdf) · [来源与图件元数据](figures/aiding/figures/Q4_body_velocity.json)

先看上排两条误差曲线何时分开，再看下排这种变化是否在九个布置中都出现。

**中文图注：** 机身速度辅助在GNSS中断中的条件作用。（a,b）一处20 s中断及恢复过程的水平误差，灰色为中断区间；（b）插图放大中断期间0–2.5 m误差范围。（c,d）同一实测路线中，每种时长九个中断布置的全窗水平RMSE，细线连接相同布置。两列分别为全部GNSS观测中断与保留航向的平移观测中断。所评价实现中，全部GNSS观测中断同时暂停辅助更新。

**English caption:** Conditional effect of body-velocity aiding during GNSS interruptions. (a,b) Horizontal error around one 20-s interruption; grey shading marks the interruption. The inset in (b) enlarges the 0–2.5 m range during the interruption. (c,d) Whole-run horizontal RMSE for nine interruption placements per duration on the same recorded route. Lines connect identical placements. Columns show complete GNSS loss and interruption of translational observations with heading retained. Complete GNSS loss also pauses auxiliary updates in the evaluated implementation.

## S4 · 保留方向与位置中断中的导航表现

![S4](figures/navigation/preview/Q3_02_heading_retention.png)

[原始 PDF](figures/navigation/Q3_02_heading_retention.pdf) · [来源与图件元数据](figures/navigation/Q3_02_heading_retention.json)

上排显示位置中断中误差如何增长，下排说明这一现象在全部18个登记条件中的分布。

**中文图注：** GNSS位置中断时的导航结果。（a,b）首个登记20秒中断的位置和航向误差，灰带表示中断区间，小窗放大中断后的前8秒；双位置和单位置IEKF停止位置更新，保留基线的IEKF继续进行相对基线更新，LegSA-GINS保留可用航向及机身运动辅助。（c,d）全部10秒和20秒中断的整段RMSE，每个时长九个布置；细线连接同一布置的四种方法。保留基线的IEKF维持了航向，但没有自动改善位置结果。对数坐标保留全部有限结果。

**English caption:** Navigation during GNSS position interruptions. (a,b) Horizontal and heading errors for the first registered 20-s interruption; gray shading marks the interrupted interval, and the inset enlarges its first 8 s. The dual- and single-position IEKFs omit their position updates, while the baseline-retaining IEKF continues relative-baseline updates. LegSA-GINS retains its available heading and robot-motion aids. (c,d) Whole-run RMSE for every registered 10-s and 20-s interruption, with nine placements per duration; thin lines connect the same placement across methods. The baseline-retaining IEKF preserves heading but does not automatically improve positioning. Logarithmic scales retain all finite outcomes.

## M6 · 来源加权的收益与精度代价

![M6](figures/aiding/figures/preview/Q5_source_weighting.png)

[原始 PDF](figures/aiding/figures/Q5_source_weighting.pdf) · [来源与图件元数据](figures/aiding/figures/Q5_source_weighting.json)

权重轨迹说明各来源受到不同程度的降权；误差轨迹与完整案例集合共同显示，发散和大航向偏离减少，同时保留位置精度代价。

**中文图注：** 来源加权的收益与位置精度代价。（a,b）已保存的GNSS位置加噪案例中的水平和航向误差，水平标准差3 m、竖直5 m。（c）同次运行三个观测来源的实际协方差放大倍数。（d）541个案例的发散次数；两种配置各另有九例缺少有效初始航向。（e）双方均完成的513例的全窗水平RMSE。等值线下方表示完整方法误差更小，插图放大正常误差量级。案例来自同一实测路线的受控观测扰动。

**English caption:** Benefits and costs of source-dependent weighting. (a,b) Horizontal and heading errors in a saved GNSS position-noise case (horizontal standard deviation 3 m, vertical 5 m). (c) Recorded covariance multipliers for three observation sources in the same run. (d) Divergent runs across 541 cases; both configurations additionally have nine cases without valid initial heading. (e) Whole-run horizontal RMSE for the 513 cases completed by both configurations. Points below the identity line favour LegSA-GINS; the inset enlarges the nominal error range. The cases reuse one recorded route with controlled observation perturbations.

## S6 · 全部外部退化类型的配对比较

![S6](figures/navigation/preview/Q3_04_all_degradation_pairs.png)

[原始 PDF](figures/navigation/Q3_04_all_degradation_pairs.pdf) · [来源与图件元数据](figures/navigation/Q3_04_all_degradation_pairs.json)

这张补充图保留所有故障类别和反例；它逐类比较，不把异质故障混成一个总排名。

**中文图注：** 全部18种登记退化类型的配对RMSE差。实心点为共同有限样本中“外部IEKF减LegSA-GINS”的中位数，空心点为95百分位，连线表示二者之间的区间；每种退化登记九个案例。负值表示IEKF误差较低。两种位置噪声下，两种IEKF均各9/9发散；时间戳扰动无有效共同配对。对称对数轴同时保留小差值和大偏离。部分速度、多普勒及航向故障作用于外部滤波器未读取的通道，属于输入等价控制。完整类型定义、396条逻辑结果和744条配对汇总随图交付。

**English caption:** Paired RMSE differences across all 18 registered degradation types. Filled markers denote the median external-IEKF minus LegSA-GINS difference over jointly finite cases; open markers denote the 95th percentile, with connecting lines showing the median-to-percentile interval. Each type contains nine registered cases. Negative values favour the IEKF. Both IEKFs diverge in all nine cases for each position-noise type; timestamp-shift cases have no valid common pairs. The symmetric-log axis retains small differences and large excursions. Some velocity, Doppler and heading faults act on channels not read by an external filter; these are input-equivalence controls rather than independent robustness demonstrations. Full type definitions, all 396 logical results and all 744 paired summaries accompany the figure.

## M3 · 自然工况下与双位置IEKF的比较

![M3](figures/navigation/preview/Q3_01_IEKF_natural.png)

[原始 PDF](figures/navigation/Q3_01_IEKF_natural.pdf) · [来源与图件元数据](figures/navigation/Q3_01_IEKF_natural.json)

这张图把整体误差大小还原为随机器人运动变化的过程，同时让遮挡期间的细微差别可见。

**中文图注：** 常规行走、大幅机身运动和单侧天线遮挡实验中，LegSA-GINS与双接收机IEKF的水平定位及航向误差。上、下排分别为水平误差和航向误差；两种IEKF配置分别采用文献参数和标定参数。第三组中的灰带表示天线遮挡时段，小窗放大第一个遮挡时段；黑色虚线表示相对于参考值的零误差。

**English caption:** Horizontal positioning and heading errors of LegSA-GINS and two-receiver IEKF during nominal walking, large body motion and single-antenna obstruction. The upper and lower rows show horizontal and heading errors, respectively. The two IEKF configurations use literature and calibrated parameters. Gray spans mark the recorded obstruction intervals in the third trial; the insets enlarge the first interval. The dashed black line denotes zero error relative to the reference.

## M4 · LegSA-GINS与OiSAM的精度及输出连续性

![M4](figures/navigation/preview/Q3_oisam_precision_continuity.png)

[原始 PDF](figures/navigation/Q3_oisam_precision_continuity.pdf) · [来源与图件元数据](figures/navigation/Q3_oisam_precision_continuity.json)

上部比较相同时刻的精度，下部交代这些时刻覆盖了多少实际运行时间；右下放大首次输入缺口后的输出变化。

**中文图注：** LegSA-GINS与OiSAM-FGO的精度及输出连续性。（a–d）在同一评价点与匹配时刻比较水平定位和航向误差：常规行走为274个历元，单侧天线遮挡记录起始阶段为54个历元；精度曲线采用仅初始化一次的OiSAM。（e）三条完整记录中，LegSA-GINS、仅初始化一次的OiSAM，以及在实测IMU缺口处分段重新初始化的OiSAM的输出时段。重新初始化的OiSAM行中，空心圆表示仅初始化的状态，线段表示有效动态输出；每个场景内三行按图例顺序排列。（f）放大单侧天线遮挡记录中方框标出的时段，灰带表示首次IMU输入缺口。时间均相对于各评价窗口起点。

**English caption:** Accuracy and output continuity of LegSA-GINS and OiSAM-FGO. (a–d) Horizontal positioning and heading errors at the same evaluation point and matched times: 274 epochs during nominal walking and 54 epochs at the beginning of the antenna-obstruction trial. The error curves use OiSAM with a single initialization. (e) Available output over each complete trial for LegSA-GINS, OiSAM with a single initialization, and OiSAM reinitialized at recorded IMU gaps. Open circles on the reinitialized OiSAM row mark initialization-only states; line segments mark available dynamic output. Within each trial the rows follow the legend order. (f) Enlargement of the boxed interval in the antenna-obstruction trial; gray shading marks the first IMU input gap. Elapsed time is measured from the start of each evaluation window.

## S5 · OiSAM重新初始化后的完整航向比较

![S5](figures/navigation/preview/Q3_03_OiSAM_reinitialized_heading.png)

[原始 PDF](figures/navigation/Q3_03_OiSAM_reinitialized_heading.pdf) · [来源与图件元数据](figures/navigation/Q3_03_OiSAM_reinitialized_heading.json)

在允许按真实输入缺口重新初始化后，比较两方法整段航向，而非只用OiSAM一次初始化后的早停描述它。

**中文图注：** OiSAM在实测IMU缺口处重新初始化后的航向误差。左列展示三条记录全部匹配动态输出历元，右列分别放大常规行走的固定中间时段，以及另外两条记录评价窗内的首次恢复过程。左图浅色带表示放大区间，右图深灰带表示实测IMU缺口。仅初始化状态不进入曲线，动态输出缺失处断线。两方法使用相同名义评价秒及一致航向定义；本图不混用原评价中不同的位置参考点。

**English caption:** Heading errors with OiSAM reinitialized at recorded IMU gaps. Left panels show all matched dynamic-output epochs throughout the three trials. Right panels enlarge a fixed central interval for nominal walking and the first restart inside the other two evaluation windows. Light shading in the left panels identifies the enlarged interval; darker shading in the right panels marks the recorded IMU gap. Initialization-only states are excluded, and curves break across unavailable dynamic outputs. Both methods use the same nominal evaluation seconds and the same heading convention. These heading comparisons do not mix the different position reference points used in the archived evaluations.

## S7 · 不同GNSS信息处理路线的定位结果

![S7](figures/navigation/preview/Q3_05_FGO_position.png)

[原始 PDF](figures/navigation/Q3_05_FGO_position.pdf) · [来源与图件元数据](figures/navigation/Q3_05_FGO_position.json)

把三种GNSS信息处理路线的误差变化放到同一场景时钟中，呈现持续误差和局部异常，而不是只给一个整段RMSE。

**中文图注：** 常规行走、大幅机身运动和单侧天线遮挡实验中，OiSAM-FGO、TC-FGO和GNC-FGO在GNSS1天线位置上的水平与高程误差。缺测和OiSAM-FGO分段边界处断线。水平误差用对数尺度，高程误差用零附近保持线性的对称对数尺度。 OiSAM在实测IMU缺口处重新初始化，仅初始化的状态不计入曲线。OiSAM使用RTK位置与IMU，TC-FGO使用原始码及适配姿态/速度输入，GNC-FGO使用原始码和Doppler；三条路线的输入信息不同。

**English caption:** Horizontal and vertical position errors of OiSAM-FGO, TC-FGO and GNC-FGO during nominal walking, large body motion and single-antenna obstruction, evaluated at the GNSS1 antenna. Curves break across missing outputs and OiSAM-FGO segment boundaries. Horizontal errors use logarithmic axes; vertical errors use a symmetric logarithmic scale with a linear region near zero. OiSAM uses reinitialization at recorded IMU gaps, with initialization-only states excluded. OiSAM uses RTK position and IMU, TC-FGO uses raw code and adapted attitude/velocity inputs, and GNC-FGO uses raw code and Doppler; input information is not identical.
