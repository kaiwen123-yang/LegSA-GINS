## 自然工况下与双位置IEKF的比较

Horizontal positioning and heading errors of LegSA-GINS and two-receiver IEKF during nominal walking, large body motion and single-antenna obstruction. The upper and lower rows show horizontal and heading errors, respectively. The two IEKF configurations use literature and calibrated parameters. Gray spans mark the recorded obstruction intervals in the third trial; the insets enlarge the first interval. The dashed black line denotes zero error relative to the reference.

常规行走、大幅机身运动和单侧天线遮挡实验中，LegSA-GINS与双接收机IEKF的水平定位及航向误差。上、下排分别为水平误差和航向误差；两种IEKF配置分别采用文献参数和标定参数。第三组中的灰带表示天线遮挡时段，小窗放大第一个遮挡时段；黑色虚线表示相对于参考值的零误差。

## 保留方向与位置中断中的导航表现

Navigation during GNSS position interruptions. (a,b) Horizontal and heading errors for the first registered 20-s interruption; gray shading marks the interrupted interval, and the inset enlarges its first 8 s. The dual- and single-position IEKFs omit their position updates, while the baseline-retaining IEKF continues relative-baseline updates. LegSA-GINS retains its available heading and robot-motion aids. (c,d) Whole-run RMSE for every registered 10-s and 20-s interruption, with nine placements per duration; thin lines connect the same placement across methods. The baseline-retaining IEKF preserves heading but does not automatically improve positioning. Logarithmic scales retain all finite outcomes.

GNSS位置中断时的导航结果。（a,b）首个登记20秒中断的位置和航向误差，灰带表示中断区间，小窗放大中断后的前8秒；双位置和单位置IEKF停止位置更新，保留基线的IEKF继续进行相对基线更新，LegSA-GINS保留可用航向及机身运动辅助。（c,d）全部10秒和20秒中断的整段RMSE，每个时长九个布置；细线连接同一布置的四种方法。保留基线的IEKF维持了航向，但没有自动改善位置结果。对数坐标保留全部有限结果。

## OiSAM重新初始化后的完整航向比较

Heading errors with OiSAM reinitialized at recorded IMU gaps. Left panels show all matched dynamic-output epochs throughout the three trials. Right panels enlarge a fixed central interval for nominal walking and the first restart inside the other two evaluation windows. Light shading in the left panels identifies the enlarged interval; darker shading in the right panels marks the recorded IMU gap. Initialization-only states are excluded, and curves break across unavailable dynamic outputs. Both methods use the same nominal evaluation seconds and the same heading convention. These heading comparisons do not mix the different position reference points used in the archived evaluations.

OiSAM在实测IMU缺口处重新初始化后的航向误差。左列展示三条记录全部匹配动态输出历元，右列分别放大常规行走的固定中间时段，以及另外两条记录评价窗内的首次恢复过程。左图浅色带表示放大区间，右图深灰带表示实测IMU缺口。仅初始化状态不进入曲线，动态输出缺失处断线。两方法使用相同名义评价秒及一致航向定义；本图不混用原评价中不同的位置参考点。

## 全部外部退化类型的配对比较

Paired RMSE differences across all 18 registered degradation types. Filled markers denote the median external-IEKF minus LegSA-GINS difference over jointly finite cases; open markers denote the 95th percentile, with connecting lines showing the median-to-percentile interval. Each type contains nine registered cases. Negative values favour the IEKF. Both IEKFs diverge in all nine cases for each position-noise type; timestamp-shift cases have no valid common pairs. The symmetric-log axis retains small differences and large excursions. Some velocity, Doppler and heading faults act on channels not read by an external filter; these are input-equivalence controls rather than independent robustness demonstrations. Full type definitions, all 396 logical results and all 744 paired summaries accompany the figure.

全部18种登记退化类型的配对RMSE差。实心点为共同有限样本中“外部IEKF减LegSA-GINS”的中位数，空心点为95百分位，连线表示二者之间的区间；每种退化登记九个案例。负值表示IEKF误差较低。两种位置噪声下，两种IEKF均各9/9发散；时间戳扰动无有效共同配对。对称对数轴同时保留小差值和大偏离。部分速度、多普勒及航向故障作用于外部滤波器未读取的通道，属于输入等价控制。完整类型定义、396条逻辑结果和744条配对汇总随图交付。

## 不同GNSS信息处理路线的定位结果

Horizontal and vertical position errors of OiSAM-FGO, TC-FGO and GNC-FGO during nominal walking, large body motion and single-antenna obstruction, evaluated at the GNSS1 antenna. Curves break across missing outputs and OiSAM-FGO segment boundaries. Horizontal errors use logarithmic axes; vertical errors use a symmetric logarithmic scale with a linear region near zero. OiSAM uses reinitialization at recorded IMU gaps, with initialization-only states excluded. OiSAM uses RTK position and IMU, TC-FGO uses raw code and adapted attitude/velocity inputs, and GNC-FGO uses raw code and Doppler; input information is not identical.

常规行走、大幅机身运动和单侧天线遮挡实验中，OiSAM-FGO、TC-FGO和GNC-FGO在GNSS1天线位置上的水平与高程误差。缺测和OiSAM-FGO分段边界处断线。水平误差用对数尺度，高程误差用零附近保持线性的对称对数尺度。 OiSAM在实测IMU缺口处重新初始化，仅初始化的状态不计入曲线。OiSAM使用RTK位置与IMU，TC-FGO使用原始码及适配姿态/速度输入，GNC-FGO使用原始码和Doppler；三条路线的输入信息不同。
