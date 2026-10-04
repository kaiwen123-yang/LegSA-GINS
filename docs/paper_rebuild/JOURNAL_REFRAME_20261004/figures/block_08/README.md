# READY 08：FGO轨迹与唯一自行估计的姿态

R17三序列保存GNSS1点的全部primary dynamic轨迹，并显式区分RTK＋IMU、code＋AHRS/IMU、code＋Doppler输入。黑虚线仅由原评价已保存matched reference XYZ显示，未再打开原reference。采用原EVALUATION保存LLH anchor，固定WGS84 ECEF→East/North显示、equal-metre坐标；没有轨迹拟合或新插值。真实缺测/初始化block reset均断线。方块标参考窗首尾。

这些是后续FGO工程分段诊断，不替代原V3 midpoint轨迹；尤其原V3 H/O完整matched trajectory未保存，不能借这些新图冒充。Oi使用自己的估计姿态将结果运到GNSS1。同物理点不能消除输入层/信息窗/估计分支差别，也不是同输入求解器排名。

R18只画Oi自行估计yaw的全窗保存误差。Wen TC/GNC没有可报的自行估计姿态，不能造yaw成绩或将AHRS/参考姿态当算法结果。三个primary原分母275/271/378，实际yaw支持275/267/370；仅先验seed全部排除。Oi固定1/3/7块共11初始化，不能称H/O连续一次init。O3286未收敛但usable保留。

所有原EVALUATION、METRICS、trajectory、Oi ERROR CSV均核ALL_OFFLINE_COMPLETE输出pin；data/保存全部原decimal字段，including invalid/prior状态。只做科学绘图，没有solver/evaluator调用、原reference访问或改旧结果。4张300dpi PNG/PDF/SVG；最终4PNG实际打开，完整轨迹范围、图例、各yaw支持及未收敛标记可读。PDF/SVG同Figure导出，未独立渲染PDF。
