# 同一 GNSS1 天线点的 FGO 定位比较

这张配表保留原图 9(i) 的全部九个水平 RMSE，现与新增轨迹组一起阅读。
每个场景的三个方法使用同一 GNSS1 天线点和共同动态历元；最后一列另列各自全窗有限动态输出支持，不与共同支持数量混用。CSV同时保留登记行数和参考匹配数。

|场景|方法|观测输入|共同动态历元|水平 RMSE（m）|各自全窗有限输出数|
|---|---|---|---:|---:|---:|
|常规行走|OiSAM (recorded-gap reinitialization)|RTK positions + body IMU|274|0.098025|275/275|
|常规行走|TC-FGO|Raw pseudoranges + AHRS / inertial input|274|7.692119|274/275|
|常规行走|GNC-FGO|Raw pseudoranges + Doppler|274|2.173504|274/275|
|大幅机身运动|OiSAM (recorded-gap reinitialization)|RTK positions + body IMU|267|0.064957|267/271|
|大幅机身运动|TC-FGO|Raw pseudoranges + AHRS / inertial input|267|7.699611|270/271|
|大幅机身运动|GNC-FGO|Raw pseudoranges + Doppler|267|2.131602|270/271|
|单侧天线遮挡|OiSAM (recorded-gap reinitialization)|RTK positions + body IMU|369|0.052061|370/378|
|单侧天线遮挡|TC-FGO|Raw pseudoranges + AHRS / inertial input|369|9.442500|377/378|
|单侧天线遮挡|GNC-FGO|Raw pseudoranges + Doppler|369|2.732494|377/378|

OiSAM 在这些记录中估计姿态；当前 TC-FGO / GNC-FGO 输出不包含自行估计的航向，因此本表仅报告其已完成的定位结果。
本文主结果原登记评价点为 POI_MIDPOINT。新轨迹组分面展示相应物理点，不给不同评价点补造同口径误差。
原始36行不同支持/角色结果完整保留在 data/FGO_GNSS1_ALL36_RESULTS.csv。所有数值直接复用原指标，无新增求解或评价。

Table caption: Horizontal position RMSE at the common GNSS1 antenna point. The three methods use the saved common dynamic epochs for each recording. Full-window native output counts are listed separately. RTK-position and raw-observation inputs are identified explicitly.
