# F04：机器人自身观测的航向自由度与相对运动估计

**中文图注。** 机器人自身观测的航向自由度与相对运动估计。(a)相同IMU与接触输入在七种初始航向下的估计路径；(b)消除各自已知初始旋转后的路径，最大位置差1.89×10⁻⁷m衡量数值等变性。(c,d)常规行走中接触辅助InEKF与足端运动学航位推算的相对水平位置、航向误差。每条路线沿用最初10秒内一次yaw与三维平移对齐，灰带标记对齐区间，全部2741个评分历元保留。InEKF由机体IMU和接触/足位代理估计姿态；航位推算结合接触运动学速度与SDK机载姿态完成坐标转换。(a,b)采用项目的reported-IJRR实现；(c,d)采用官方InEKF库与已保存的航位推算结果。其余场景及InEKF参数敏感性见配套结果。

**English caption.** Proprioceptive heading freedom and relative-motion estimation. (a) Estimated paths for seven initial yaw settings using identical IMU and contact inputs. (b) The same paths after removing each known initial rotation; the maximum positional discrepancy of 1.89 × 10⁻⁷ m measures numerical equivariance. (c,d) Relative horizontal-position and heading errors for contact-aided InEKF and kinematic dead reckoning during nominal walking. Each route uses the previously computed single yaw and three-dimensional translation alignment over the first 10 s, shown by gray shading; all 2,741 scored epochs are retained. The InEKF estimates attitude from body IMU and contact/foot-position proxies, whereas dead reckoning uses contact-kinematic velocity together with onboard SDK attitude for frame rotation. Panels (a,b) use the project’s reported-IJRR implementation; panels (c,d) use the official InEKF library and the saved kinematic route. The remaining recordings and InEKF parameter sensitivity are provided in the supplementary results.

# S04：三场景的两路线相对运动估计

**中文图注。** 三条实测记录中的接触辅助InEKF与机载姿态辅助的足端运动学航位推算。上、下排分别为相对水平位置和航向误差，沿用每个分支最初10秒内的一次对齐。三个场景每条路线分别保留2741、2700、3771个评分历元；大幅机身运动的一个无支持网格保持缺失。官方示例参数作为同一InEKF的敏感性结果列于完整配表。

**English caption.** Relative-motion estimates from contact-aided InEKF and onboard-attitude-assisted kinematic dead reckoning on all three recordings. Top and bottom rows show relative horizontal-position and heading errors, respectively, using each branch’s saved single alignment over the first 10 s. The three recordings retain 2,741, 2,700 and 3,771 scored epochs per route. One unsupported grid epoch remains missing in the large-body-motion recording. The official-example parameter setting is retained as InEKF sensitivity data in the complete table.
