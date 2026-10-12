# 图 9(h) 与原图 9(i)：直白解释与本轮调整

## (h) 到底在比较什么

它比较同一常规行走记录上 **18 个位置观测中断条件**：10 秒中断和 20 秒中断各九个布置。它不是 18 条不同实地路线，也不是一个时刻的 18 个传感器。

每个点表示一个完整条件运行的**全窗航向 RMSE**，横轴越靠左，航向误差越小。四行分别是 LegSA-GINS、双位置 IEKF、单位置 IEKF，以及位置中断时仍保留相对基线观测的 IEKF。黑色短竖线给出各方法 18 个条件的中位数。

原版的 Dual-pos. / Single-pos. / Baseline kept 过短，读者需要来回查图例；很多条件的 RMSE 又非常接近，点会聚在一起，看上去像只画了一个点。新版将完整方法名直接写在各行上方，并明确写出每个方法 18 个条件、点和中位线的含义。所有 72 个指标均保留；横轴仍是全窗 RMSE，没有改成中断末端或中断区间 RMSE。

这张面板回答：改变位置中断时刻与时长后，几个方法的航向表现是否仍一致。它与(g)的一个具体 20 秒中断过程相互配合。与原图相比，指标与坐标方向都不变。

四个方法的全窗航向 RMSE 中位数依次为 **1.885°、2.998°、12.431°、2.995°**。本文和保留基线的 IEKF 等方法的18个结果非常接近，所以点簇看起来较窄；图内现在注明了每种方法都有18个条件。这里比较的是整个运行窗口的航向精度，不能读成机器人在中断末端恰好偏了这些角度。

## 原 (i) 为什么移出主航向图

原(i)显示的是 **OiSAM、TC-FGO、GNC-FGO 在 GNSS1 天线点的水平位置 RMSE**。三种标记代表三个场景，并且横轴使用对数尺度。它不是航向结果，与(h)相比同时更换了物理量、评价点、支持范围和符号含义，所以放在主航向图末尾很难读。

本轮主图 9 保留(a–h)，把原(i)的全部九个指标移到 `METHOD_POSITION_TABLE.md` / `.csv`，由新增全方法轨迹组配套引用。读者可以一边看三个场景的 GNSS1 定位轨迹，一边查同点、共同历元下的 RMSE。

配表同时列出观测输入、共同动态历元数及各自全窗有限输出数。原来 36 行完整结果保留在 `data/FGO_GNSS1_ALL36_RESULTS.csv`。TC-FGO / GNC-FGO 当前输出没有自行估计的航向，本轮没有给它们补造 yaw；这些已完成的定位比较仍完整使用。

## 图注

中文：滤波与因子图方法的航向精度。(a–f)三条自然记录中六种配置的共同动态历元航向误差及绝对误差累计分布；(g)首个登记20秒位置中断过程；(h)全部18个位置中断条件的全窗航向RMSE，每个点为一个条件，黑色短线为18个条件的中位数。旧定位面板的数据由同点定位配表与新增轨迹组呈现。

English: Heading accuracy across filtering and factor-graph methods. (a–f) Signed heading errors and absolute-error ECDFs at the saved common dynamic epochs for six configurations. (g) The first registered 20-s position interruption. (h) Whole-run heading RMSE for all 18 registered interruption conditions: nine placements each at 10 and 20 s. Each dot denotes one condition and the black mark is the median. The previous position panel is retained in a companion table with the trajectory comparison.
