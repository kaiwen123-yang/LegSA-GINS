# R5 修改三图的论文图注


## 图3

# F03_integrated_routes_and_heading

**建议图名：完整导航路线与同点空间细节。**

**中文图注。** 三次记录的完整导航路线及分组空间细节。(a,c,e) 分别为常规行走、大幅机身运动和单侧天线遮挡记录，展示八种主导航配置的全部有效路线；粗黑虚线标出固定 100 s 的参考轨迹背景段，空心圆和方形分别标记该段的首、末有效参考点，矩形与引线定位右侧空间细节。(b,d,f) 将双位置 IEKF、单位置 IEKF 和重新初始化的 OiSAM 分为三个宽幅局部，每组重复 Truth 和 LegSA-GINS 作为共同参照；LIT 与 cal. 分别表示文献参数和已登记标定参数。局部时间为前两条记录的 88–92 s、遮挡记录的 228–233 s，分别位于 40–140 s 和 154.945–254.945 s 的背景段内。遮挡局部属于登记遮挡区间 183.94–225.95 s 结束后的恢复运动。局部以参考轨迹在时间窗中点的位置为共同坐标原点，完整显示所选 4 s 或 5 s 内各方法的有效输出；同场景三组范围相同，东西、南北比例相等。所有局部均位于 POI 中点；OiSAM 使用自身姿态和已登记杆臂转换。完整路线中的 TC-FGO 和 GNC-FGO 保留其原生 GNSS1 点，因此左列用于地理概览，不作同点精度排名。Truth 表示项目使用的 Fixposition 参考轨迹。断线保留真实输出缺口和 OiSAM 分段边界。航向精度及连续性在图 9 中统一比较。

**English caption.** Full navigation routes and grouped spatial details from three recordings. (a,c,e) Nominal walking, large body motion, and single-antenna obstruction, respectively, showing all valid trajectories from eight principal navigation configurations. The heavy black dashed reference segment marks a fixed 100-s context; open circles and squares denote its first and last supported reference samples. Rectangles and leaders locate the details. (b,d,f) Wide details separately compare dual-position IEKF, single-position IEKF, and reinitialized OiSAM, with Truth and LegSA-GINS repeated as common anchors. LIT and cal. denote literature and registered calibrated parameters. Details cover 88–92 s in the first two recordings and 228–233 s in the obstruction recording, within contexts of 40–140 s and 154.945–254.945 s, respectively. The latter detail shows recovery motion after the registered obstruction interval of 183.94–225.95 s. Local coordinates share the reference position at the temporal midpoint as their origin. Every valid output within each complete 4-s or 5-s detail is retained, with identical limits across the three groups and equal east/north scales. Details use the POI midpoint; OiSAM is transported using its own attitude and registered lever arm. TC-FGO and GNC-FGO retain native GNSS1 positions in the full routes, which provide geographic context rather than a same-point accuracy ranking. Truth denotes the project's Fixposition reference trajectory. Breaks preserve output gaps and OiSAM segment boundaries. Heading accuracy and continuity are compared in Fig. 9.

**与上一版的区别。** R4 的源文件保留了完整局部时段，但显示窗口会裁掉部分轨迹；R5 的视窗由该时段内所有方法点共同决定，外侧保留适量留白，没有裁掉任何局部有效点。正文不再重复右列航向曲线，把宽度交给空间细节。文件 stem 为兼容总图册索引仍保留 `F03_integrated_routes_and_heading`。


## 图4

# F04：机器人自身观测的航向自由度与相对运动估计

**中文图注。** 机器人自身观测的航向自由度与相对运动估计。(a)相同IMU与接触输入在七种初始航向下的估计路径；(b)消除各自已知初始旋转后的路径，最大位置差1.89×10⁻⁷m衡量数值等变性。(c,d)常规行走中接触辅助InEKF与足端运动学航位推算的相对水平位置、航向误差。每条路线沿用最初10秒内一次yaw与三维平移对齐，灰带标记对齐区间，全部2741个评分历元保留。InEKF由机体IMU和接触/足位代理估计姿态；航位推算结合接触运动学速度与SDK机载姿态完成坐标转换。(a,b)采用项目的reported-IJRR实现；(c,d)采用官方InEKF库与已保存的航位推算结果。其余场景及InEKF参数敏感性见配套结果。

**English caption.** Proprioceptive heading freedom and relative-motion estimation. (a) Estimated paths for seven initial yaw settings using identical IMU and contact inputs. (b) The same paths after removing each known initial rotation; the maximum positional discrepancy of 1.89 × 10⁻⁷ m measures numerical equivariance. (c,d) Relative horizontal-position and heading errors for contact-aided InEKF and kinematic dead reckoning during nominal walking. Each route uses the previously computed single yaw and three-dimensional translation alignment over the first 10 s, shown by gray shading; all 2,741 scored epochs are retained. The InEKF estimates attitude from body IMU and contact/foot-position proxies, whereas dead reckoning uses contact-kinematic velocity together with onboard SDK attitude for frame rotation. Panels (a,b) use the project’s reported-IJRR implementation; panels (c,d) use the official InEKF library and the saved kinematic route. The remaining recordings and InEKF parameter sensitivity are provided in the supplementary results.

# S04：三场景的两路线相对运动估计

**中文图注。** 三条实测记录中的接触辅助InEKF与机载姿态辅助的足端运动学航位推算。上、下排分别为相对水平位置和航向误差，沿用每个分支最初10秒内的一次对齐。三个场景每条路线分别保留2741、2700、3771个评分历元；大幅机身运动的一个无支持网格保持缺失。官方示例参数作为同一InEKF的敏感性结果列于完整配表。

**English caption.** Relative-motion estimates from contact-aided InEKF and onboard-attitude-assisted kinematic dead reckoning on all three recordings. Top and bottom rows show relative horizontal-position and heading errors, respectively, using each branch’s saved single alignment over the first 10 s. The three recordings retain 2,741, 2,700 and 3,771 scored epochs per route. One unsupported grid epoch remains missing in the large-body-motion recording. The official-example parameter setting is retained as InEKF sensitivity data in the complete table.


## 图8

# Fig. 8

三种已执行退化条件下来源加权的响应。三行分别为位置噪声、方向噪声与乐观不确定度、机身速度噪声，均采用原登记seed00。左列显示受扰输入相对clean输入的变化及自报不确定度；中列为实际更新中的协方差倍率，中位点、粗线、细线分别表示中位数、IQR和范围；右列比较关闭来源加权与完整方法的航向误差。曲线展示同一前120 s，每1 s用全部原样本的中位线与最小—最大范围表示，范围带不是跨回放置信区间。标注指标为完整274 s的原始RMSE。方向条件的倍率来自511条实际记录方向更新，其余所示来源各600条。三例分别体现大幅航向保护、小幅收益及航向近中性、位置改善的不同响应。

Source-weighting responses under three executed degradation conditions: position noise, heading noise with optimistic uncertainty, and body-velocity noise. Each row uses the fixed first registered realization. Columns show input changes relative to the clean input and reported uncertainty, recorded covariance adjustment, and heading response. Covariance points, thick bars and thin bars denote medians, IQRs and ranges. Time plots cover the same first 120 s using one-second medians and min–max bands containing all native samples; the bands are within-time ranges, not replay confidence intervals. Annotated RMSEs are the original complete 274-s metrics. Heading-scaling statistics in the second row use 511 recorded heading updates; the other displayed source summaries each use 600. The examples show a strong heading benefit, a smaller benefit, and nearly neutral heading with improved positioning. Full variant outcomes accompany the figure.
