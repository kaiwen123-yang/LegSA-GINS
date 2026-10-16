# R6 修改三图的论文图注


## 图3

# 图 3：三场景导航路线、空间近景与航向误差

中列是**时间窗口内的空间近景**，不表示全部 4 s / 5 s 轨迹都落在放大框中；框外点仍保留在原数据及完整路线显示中。

**中文图注。** 三行分别为常规行走、大幅机身运动和单侧天线遮挡记录。左列 (a,d,g) 显示八种主导航配置的完整有效路线，矩形和引线定位中列空间近景。中列 (b,e,h) 为同一 POI 中点的固定空间放大框；坐标原点取参考轨迹在相应时间窗中点的位置，显示 88–92 s、88–92 s 和 228–233 s 轨迹落入该框内的部分，横纵比例相等，框外路线可从左列读取。最后一行近景是登记遮挡结束后的恢复运动。右列 (c,f,i) 为六个实际输出航向的方法在共同动态时刻上的航向误差，时间窗依次为 40–140 s、40–140 s 和 154.945–254.945 s；浅蓝带对应空间近景的时间，灰带为登记遮挡区间 183.94–225.95 s。Truth 表示 Fixposition 参考轨迹。LIT 与 cal. 分别表示文献参数和已登记标定参数。OiSAM 使用与图 9 一致的重新初始化结果，其 POI 转换使用自身姿态和已登记杆臂。TC-FGO/GNC-FGO 保留原生 GNSS1 位置，仅用于左列地理概览；中列同点比较和右列航向不包含这两条方法。输出缺口与 OiSAM 分段边界保留为断线。

**English caption.** Navigation routes, spatial close-ups, and heading errors for nominal walking, large body motion, and single-antenna obstruction (rows). (a,d,g) Complete valid routes from eight principal navigation configurations; rectangles and leaders locate the close-ups. (b,e,h) Fixed spatial viewports at the common POI midpoint, centred on the reference position at the temporal midpoint. The viewports show portions of the 88–92 s, 88–92 s, and 228–233 s trajectories, respectively, using equal east/north scales. The last close-up shows recovery motion after obstruction. (c,f,i) Heading errors from six methods with actual attitude outputs on their common dynamic support, over 40–140 s, 40–140 s, and 154.945–254.945 s. Pale blue marks the close-up time interval; gray marks the registered obstruction at 183.94–225.95 s. Truth denotes the Fixposition reference. LIT and cal. denote literature and registered calibrated parameters. OiSAM uses the same reinitialization protocol as Fig. 9 and is transported to the POI using its own attitude and registered lever arm. TC-FGO/GNC-FGO retain native GNSS1 positions for geographic context in the left column and are excluded from same-point close-ups and heading panels. Breaks retain output gaps and OiSAM segment boundaries.


## 图4

# 图4：同一运动记录在七种初始全局朝向下的估计结果

**中文图注。** 同一接触辅助InEKF在七种初始全局朝向下的运动估计。各次运行使用相同IMU、足位代理与接触输入，初始朝向为−150°、−100°、−50°、0°、50°、100°、150°，世界坐标中的初始状态与协方差按同一旋转变换。(a)各自全局朝向下的轨迹；(b)消除已知初始旋转后的共同相对轨迹；(c)相对0°运行的位置差。最大差约1.89×10⁻⁷m表示数值等变性。0°复用主运行，其余六条来自已有回放。彩色突出三种代表朝向，灰色显示另外四种。

**English caption.** Motion estimates from one contact-aided InEKF under seven initial global orientations. All runs use identical IMU, foot-position-proxy and contact inputs, with initial yaw angles of −150°, −100°, −50°, 0°, 50°, 100° and 150°. World-expressed initial states and covariances are rotated consistently. (a) Trajectories in their respective global frames. (b) Relative trajectories after removing the known initial rotations. (c) Positional differences from the zero-yaw run, with a maximum of approximately 1.89 × 10⁻⁷ m measuring numerical equivariance. The zero-yaw result reuses the primary run; the other six are existing replays. Three orientations are highlighted in color and the remaining four in gray.


## 图8

# Fig. 8

三种已执行退化条件下来源加权的响应。三行分别为位置噪声、方向噪声与乐观不确定度、机身速度噪声，均采用原登记seed00。左列显示受扰输入相对clean输入的变化及自报不确定度；中列为实际更新中的协方差倍率，中位点、粗线、细线分别表示中位数、IQR和范围；右列比较关闭来源加权与完整方法的航向误差。曲线展示同一前120 s，每1 s用全部原样本的中位线与最小—最大范围表示，范围带不是跨回放置信区间。标注指标为完整274 s的原始RMSE。方向条件的倍率来自511条实际记录方向更新，其余所示来源各600条。三例分别体现大幅航向保护、小幅收益及航向近中性、位置改善的不同响应。

Source-weighting responses under three executed degradation conditions: position noise, heading noise with optimistic uncertainty, and body-velocity noise. Each row uses the fixed first registered realization. Columns show input changes relative to the clean input and reported uncertainty, recorded covariance adjustment, and heading response. Covariance points, thick bars and thin bars denote medians, IQRs and ranges. Time plots cover the same first 120 s using one-second medians and min–max bands containing all native samples; the bands are within-time ranges, not replay confidence intervals. Annotated RMSEs are the original complete 274-s metrics. Heading-scaling statistics in the second row use 511 recorded heading updates; the other displayed source summaries each use 600. The examples show a strong heading benefit, a smaller benefit, and nearly neutral heading with improved positioning. Full variant outcomes accompany the figure.
