# Q2 中英文图注

## RTKLIB原配置下短基线航向的输出与物理一致性

Availability and physical consistency of short-baseline heading from the original RTKLIB moving-base configuration. (a) Cumulative distributions of absolute heading errors at newly available fixed outputs for the three trials; the inset enlarges 0–20° without renormalizing. (b) New-output times; percentages refer to all paired epochs within each trial. (c) Baseline lengths of all 153 fixed outputs in the nominal-walking evaluation window, including 35 with a logged length residual above 4σ. The dashed line is the installed length of 0.35 m, and the gray band is ±4σ with the configured length standard deviation σ = 0.01 m. (d) Enlargement of the shaded 10–22 s interval in (c). All panels use the saved trial windows; the heading quantity is obtained from the horizontal projection of the lateral baseline and compared with the reference yaw.

原始RTKLIB动基线配置下，短基线航向的输出可用性与物理一致性。(a) 三种工况中新固定输出的绝对航向误差累积分布，小窗放大0–20°，保持原累积分布分母。(b) 新固定输出的时刻；百分比以各实验窗内的全部配对历元为分母。(c) 常规行走评价窗内全部153个固定输出的基线长度，其中35个日志长度残差超过4σ。虚线为安装长度0.35 m，灰带为配置长度标准差σ=0.01 m所对应的±4σ范围。(d) 放大(c)中的10–22 s着色区间。所有面板均使用保存的实验窗口；航向由横向基线的水平投影换算，并与参考航向比较。

读图目的：新固定输出的覆盖率与输出后的物理一致性是两个问题：本组数据中固定解稀疏，且固定状态仍可能伴随显著长度残差。

## RTKLIB四配置的航向误差与输出连续性

RTKLIB moving-base heading errors and output times during nominal walking, large body motion and single-antenna obstruction. Original, Alt. eph., Multi-GNSS and Fix-and-hold denote the original configuration, modified ephemeris, extended constellation selection and fix-and-hold processing, respectively. The upper row shows errors of newly available fixed solutions; the middle row shows errors when the latest heading is held between updates; the lower row marks new-output times.

常规行走、大幅机身运动和单侧天线遮挡实验中，RTKLIB动基线航向误差与输出时间。四种配置依次为原始配置、修改星历、扩展星座选择和fix-and-hold处理。上排为新固定解的误差，中排为相邻更新之间保持最近一次航向时的误差，下排标出新解出现的时刻。

读图目的：将“有一个航向值”与“此刻有新的有效航向解”分开，让长时间保持旧值的误差和稀疏新解都能直接看见。

## 三种原始双天线处理路线的误差分布与输出

Heading-error distributions and output availability for three raw dual-antenna processing methods during nominal walking, large body motion and single-antenna obstruction. The upper row shows cumulative distributions of absolute directional error at each method’s recorded valid outputs; the lower row marks their output times. C-LAMBDA and C-WLS denote independent implementations of the constrained objectives, with no integer acceptance test on these candidates. DD-KF uses the saved double-difference filter output. No held heading is added. The plotted direction is derived from the horizontal projection of the lateral baseline and compared with the reference yaw.

三种原始双天线观测处理方法在常规行走、大幅机身运动与单侧天线遮挡下的航向误差分布和可用输出。上排为各方法已记录有效输出时刻的绝对方向误差累积分布，下排标出对应输出时间。C-LAMBDA和C-WLS为对应约束目标的独立实现，这些方向候选未设整数接受检验；DD-KF使用保存的双差滤波输出，不插入保持航向。所画方向由横向基线的水平投影换算，并与参考航向比较。

读图目的：完整使用九组保存结果，把方向误差分布与输出覆盖分开呈现，避免密集正负180度跳转线遮住三种方法的差别。
