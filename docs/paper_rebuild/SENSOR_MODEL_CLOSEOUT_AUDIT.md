# P-12：传感器模型收尾审计

2026-09-13。人类已将执行顺序改为“先完成审计，再进行 v2.1”；本审计不以 v2.1 已完成为前提。只读三序列观测，零 trace、零求解器、零评估器；不修改合约、provider、参数或既有决定。

## 计算前登记的定义与行动阈值

以下定义在本次 P-12 数值计算前写入。没有依结果调整选择规则。

- 冻结窗：BY2 [66,340]、BY2H [413,683]、BY2O [3186,3563] s；静止噪声另用各原始日志前 1000 个完整 IMU 帧，保留其真实时间。
- 转弯段：从各冻结窗起点划分连续、不重叠的完整 5 s 区间；A1 unwrap 后线性插值端点，整段须有 A1 支持且不跨 >1.2 s 缺测，保留 |Δψ_A1|>20° 的全部区间。不按残差或质量指标删除区间。过原点模型 Δψ_A1=k·Δψ_gyro；主列使用冻结安装变换、首 1000 帧均值去偏后的 z 轴角增量；同时列 Euler yaw-rate 投影的敏感性对照。95% CI 按完整 5 s 区间有放回 bootstrap 10000 次，固定随机种子 20260913（各序列依次加 0/1/2）；少于 2 段则 CI 不可用。x/y 标度 NOT_OBSERVABLE。
- A1 噪声：所有精确 iTOW 相隔 1000 ms 的 A1 端点对，整段有 IMU 和 A1 支持。r=Δψ_A1−∫yaw_rate_gyro dt；σ_A1=sqrt(var(r,ddof=1)/2)。冻结 z 积分另列。此量包括陀螺、时序及运动误差，不宣称独立识别 A1 白噪声。ACF 用真实端点起始时间的 0.02 s 时差箱，至少 20 对；不跨 A1 长缺测；首次非正箱作为首次过零的观测界限。
- 陀螺积分沿用 FLU→FRD、Rz(0)Ry(0)Rx(−1°)、首 1000 帧均值去偏及右端当前样本规则；实际 dt 积分，端点在样本区间内时按覆盖时长积分。Euler 对照使用相应安装后的姿态与 (ω_y sin roll+ω_z cos roll)/cos pitch。未拟合时延、标度或新零偏。
- 静止 Allan：三序列前 1000 帧不重新选择。BY2O 另取冻结窗内 PVT 水平速度 <0.3 m/s、相邻 PVT 间隔 ≤0.21 s 的最长连续段（至少 5 s）；列 Go2 速度和角速率验证静止条件，不能满足时保留候选并标非可靠静止。按实际时间积分的角度序列 θ，用重叠二阶差分 sqrt(mean((θ(t+2τ)−2θ(t+τ)+θ(t))²)/(2τ²)) 求角速率 Allan 偏差，τ 包括精确 1 s。ARW 代理值=σ_Allan(1s)·60，单位 °/√h。短窗、振动、非白噪声限制必须注明。gbstd 用固定静止窗均值角速率的跨窗样本标准差，单位 °/h，标 APPROXIMATE；单窗序列不虚构跨窗标准差。
- 安装横滚：固定 GNSS2−GNSS1 左向基线的 D 分量结合重力俯仰得基线 roll，再与未安装修正的 FRD 加速度计 gravity roll 比较，报告 sensor roll−baseline roll。使用同步静止/慢速（PVT<0.8 m/s）样本；加速度计 1 s 均值仅作重力近似。无匹配时标 UNAVAILABLE，不换为动态“真值”。
- 安装俯仰：静止加速度计给出相对重力的表观俯仰及跨序列离散；未有独立机身水平/俯仰基准时，安装俯仰本身 NOT_OBSERVABLE，不能把平台倾斜判为安装偏差。
- 安装偏航：方法一用 PVT 及 H-A 水平速度均 ≥0.3 m/s 的样本，求修正框 H-A 转向 PVT 的有符号方向差（Σ叉积/Σ点积的 atan2；另列逐样本均值/σ）；方法二用直线段（PVT≥0.8 m/s，中心 1 s A1 转角绝对值≤5°，H-A 水平模长≥0.3 m/s）的 PVT course−A1 与 Go2 经 roll/pitch 倾斜补偿后的体系速度方向比较。列每种角差及分散，保留侧滑/腿速横向偏差/A1 偏差不可分的限制；不把 Go2 position 或 velocity 当真值。这两种方法使用同批速度观测，不能称为独立交叉验证。
- RP 约定：分别列前 1000 帧静止及窗内慢速 PVT<0.8 m/s 下原始 Go2 rpy、FLU→FRD 对应 [roll,−pitch] 与 FRD 加速度计重力姿态的差；同时给原始 rpy 被直接作为 FRD 的冻结操作对照。列 roll/pitch 均值与样本 σ，检验符号/轴序但不拟合新变换。
- 行动阈值（严格 >，等号不触发）：可观测系统误差超过对应标定噪声 3 倍，或可观测安装角相对冻结 [−1,0,0]° 偏差 >1°，或 σ_A1 相对冻结 1.5° 的差异 >50%，才登记 HUMAN_DECISION_REQUIRED。角增量系统误差用固定转弯段拟合偏离 k=1 的 RMS 与同段去拟合均值后的残差 σ 比较；RP/速度均值用对应残差 σ 比较；静止均值角速率用跨窗 gbstd 代理比较。不可观测项列限制，绝不填成 PASS/0；噪声大小对比本身不等于系统偏差。即使触发也不自动更改链。

## 执行结果

状态：`HUMAN_DECISION_REQUIRED`。未改变任何链；v2.1 尚未执行。

### 1. 陀螺 z 标度（Δψ_A1 = k·Δψ_gyro）

| 指标 | BY2 | BY2H | BY2O |
|---|---:|---:|---:|
| 转弯 5 s 段 n | 14 | 12 | 12 |
| z 积分：斜率 k [95% CI] | 0.991971 [0.953341 / 1.043298] | 0.944907 [0.804485 / 1.049073] | 1.036122 [0.986089 / 1.095230] |
| Euler yaw-rate：斜率 k [95% CI] | 0.989862 [0.951257 / 1.041031] | 0.942915 [0.803830 / 1.047101] | 1.034428 [0.985501 / 1.091746] |
| z 拟合残差均值 ± σ / ° | -2.516175 ± 6.866067 | 28.649803 ± 82.341156 | 3.134658 ± 9.217835 |
| x / y 标度 | NOT_OBSERVABLE / NOT_OBSERVABLE | NOT_OBSERVABLE / NOT_OBSERVABLE | NOT_OBSERVABLE / NOT_OBSERVABLE |

CI 为预定 5 s 区间 bootstrap 的描述性区间，转弯段数有限；A1 异常、安装与运动耦合均进入结果，不是高精度独立陀螺标度标定。全部转弯区间及增量见 JSON，未因异常残差删段。

### 2. A1 航向增量噪声

| 指标 | BY2 | BY2H | BY2O |
|---|---:|---:|---:|
| 1 s 端点对 n | 274 | 267 | 370 |
| σ_A1：Euler yaw-rate / ° | 2.933193 | 8.406459 | 2.936449 |
| σ_A1：直接 z 积分对照 / ° | 2.925596 | 8.406847 | 2.932391 |
| 冻结 σ_A1 / ° | 1.500000 | 1.500000 | 1.500000 |
| 1 s 增量残差均值 ± σ / ° | -0.071491 ± 4.148161 | 1.336022 ± 11.888529 | -0.028592 ± 4.152766 |
| ρ[1,1.02)s | -0.288133 | 0.366013 | -0.357875 |
| 首个非正 ACF 箱 / s | 1.000000 / 1.020000 | 6.000000 / 6.020000 | 1.000000 / 1.020000 |

σ_A1 是依题定义的增量残差代理值。A1 自身时间相关、陀螺误差和重叠增量破坏独立白噪声前提；首次过零及 1 s 的负相关不能被自动解读为原始 A1 白噪声。

### 3. 静止窗 Allan 与 gbstd

| 指标 | BY2 | BY2H | BY2O |
|---|---:|---:|---:|
| 前 1000 帧时间窗 / s | 44.887078 / 49.753051 | 394.943074 / 399.529064 | 3101.557068 / 3106.395053 |
| 前 1000 帧时长 / s | 4.865973 | 4.585990 | 4.837984 |
| τ=1 s Allan / (°/s)，x/y/z | 0.054305 / 0.016950 / 0.019876 | 0.017217 / 0.018267 / 0.036493 | 0.035878 / 0.017307 / 0.020287 |
| τ=1 s ARW 代理 / (°/√h)，x/y/z | 3.258305 / 1.017005 / 1.192574 | 1.033009 / 1.095999 / 2.189563 | 2.152673 / 1.038402 / 1.217219 |
| 冻结 arw / (°/√h)，x/y/z | 0.985000 / 0.985000 / 0.985000 | 0.985000 / 0.985000 / 0.985000 | 0.985000 / 0.985000 / 0.985000 |
| 静止均值角速率 / (°/h)，x/y/z | -1577.416805 / -559.843905 / -245.808775 | -1665.966598 / -539.098498 / -265.949289 | -1631.249801 / -578.046027 / -306.584338 |
| 静止检查 | SUPPORTED_BY_LOW_MEAN_MOTION | SUPPORTED_BY_LOW_MEAN_MOTION | SUPPORTED_BY_LOW_MEAN_MOTION |

BY2O 站立窗（最长连续 PVT<0.3 m/s 区间）及全部 τ 读值：

区间 3324.200000 / 3416.000000 s，n=17636，状态 SUPPORTED_BY_LOW_MEAN_MOTION。

| τ / s | 配对 n | Allan x / y / z（°/s） |
|---:|---:|---|
| 0.010000 | 17619 | 0.907167 / 0.542356 / 0.371827 |
| 0.020000 | 17606 | 0.915684 / 0.571678 / 0.533347 |
| 0.050000 | 17569 | 1.067138 / 0.406360 / 0.689734 |
| 0.100000 | 17508 | 1.043366 / 0.350623 / 0.602057 |
| 0.200000 | 17390 | 0.811635 / 0.233195 / 0.444035 |
| 0.500000 | 17042 | 0.420798 / 0.082845 / 0.159184 |
| 1.000000 | 16461 | 0.258864 / 0.054762 / 0.098907 |
| 2.000000 | 15299 | 0.158287 / 0.033016 / 0.061086 |
| 5.000000 | 11945 | 0.065013 / 0.016301 / 0.026706 |
| 10.000000 | 6480 | 0.044139 / 0.013169 / 0.016295 |

站立窗 τ=1 s ARW 代理 x/y/z = 15.531849 / 3.285690 / 5.934390 °/√h。

| 指标 | BY2 | BY2H | BY2O |
|---|---:|---:|---:|
| 各序列静止窗数 | 1 | 1 | 2 |
| 本序列跨窗 gbstd / (°/h)，x/y/z | UNAVAILABLE | UNAVAILABLE | 16.806190 / 13.260326 / 33.638799 |
| 状态 | UNAVAILABLE_SINGLE_WINDOW | UNAVAILABLE_SINGLE_WINDOW | APPROXIMATE |

跨三序列共 4 窗合并 gbstd = 37.453926 / 24.707103 / 26.198129 °/h；冻结为 9.38 / 9.38 / 9.38 °/h，`APPROXIMATE`。BY2/BY2H 各只有一个指定静止窗，不能各自估计跨窗 σ。跨窗差也含温漂、实际姿态运动与地球自转投影，不是纯零偏不稳定性。

原始静止角速率均值不等于当前链的剩余系统误差：冻结 provider 已减去每序列前 1000 帧均值。阈值表在同一现有操作后比较，首窗剩余均值为 0；BY2O 站立窗剩余 x/y/z = 23.767541 / -18.752932 / 47.572445 °/h，均未超过 3 倍合并跨窗 σ。原始均值及其阈值标志保留在 JSON 中，不登记为尚未处理的新陀螺偏置。

Allan 公式来源：[NIST SP 1065 §5.2.4](https://tf.nist.gov/general/pdf/2220.pdf)。本实现对实际时间积分角作二阶差分；短窗及真实机器人站立微动限制 ARW 辨识。τ=1 s 读值不是对 −1/2 斜率区间的拟合。冻结单位由 `port_config_loader.cpp` 的 D2R/60、D2R/3600 换算核对。

### 4. 安装角与可观测性

| 指标 | BY2 | BY2H | BY2O |
|---|---:|---:|---:|
| roll 慢速同步样本 n | 3 | 0 | 97 |
| roll：sensor−baseline 均值 ± σ / ° | -3.422178 ± 2.574785 | UNAVAILABLE ± UNAVAILABLE | -4.150564 ± 14.207494 |
| roll 对冻结 −1° 的均值偏差 / ° | -2.422178 | UNAVAILABLE | -3.150564 |
| pitch：首窗表观 gravity 均值 ± σ / ° | -0.792355 ± 0.273615 | -0.895742 ± 0.274569 | 2.354111 ± 0.274849 |
| pitch 安装角 | NOT_OBSERVABLE | NOT_OBSERVABLE | NOT_OBSERVABLE |
| yaw 方法一有效修正角 / ° | 4.544357 | 3.905588 | 1.617459 |
| yaw 方法一逐样本均值 ± σ / ° | 4.477473 ± 6.561201 | 3.951466 ± 16.236087 | 1.728273 ± 6.848059 |
| yaw 方法二直线样本 n | 13320 | 13681 | 13688 |
| yaw 方法二中位有效修正角 / ° | 3.952922 | 3.908300 | 1.162595 |
| yaw 方法二逐样本均值 ± σ / ° | 4.171174 ± 5.962823 | 3.973292 ± 6.034888 | 1.414546 ± 6.469843 |
| 冻结安装角 roll/pitch/yaw / ° | −1 / 0 / 0 | −1 / 0 / 0 | −1 / 0 / 0 |

roll 是低动态基线/重力代理，样本少时不构成精确安装校准；天线自身垂直错位也进入结果。pitch 的三序列表观重力倾角均值跨序列 σ=1.847181°，缺少独立机身水平基准，无法分离安装俯仰。yaw 是把 H-A 速度转向 PVT 的有效角差，不能单独归因于 IMU 安装、A1 安装或侧滑。两种 yaw 诊断在相同样本上代数等价，只是取样/汇总不同。

### 5. RP 先验符号与轴序

各格 roll / pitch；差定义为指定 RP 减未安装修正的 FRD 加速度计 gravity 姿态。

| 指标 | BY2 | BY2H | BY2O |
|---|---:|---:|---:|
| 首窗：FLU→FRD RP 残差均值 / ° | 0.688255 / -0.444112 | 0.666042 / -0.420844 | 0.677666 / -0.412029 |
| 首窗：FLU→FRD RP 残差 σ / ° | 0.212923 / 0.272702 | 0.217379 / 0.273699 | 0.208591 / 0.273803 |
| 首窗：冻结原始 RP 残差均值 / ° | 0.688255 / 2.028821 | 0.666042 / 2.212328 | 0.677666 / -4.296193 |
| 首窗：冻结原始 RP 残差 σ / ° | 0.212923 / 0.274704 | 0.217379 / 0.275599 | 0.208591 / 0.275975 |
| 慢速样本 n | 82 | 26 | 5605 |
| 慢速：FLU→FRD 均值 / ° | 3.175570 / 1.760538 | 3.405132 / -0.769777 | 0.827840 / -0.521081 |
| 慢速：FLU→FRD σ / ° | 11.099307 / 7.277832 | 8.332473 / 5.759462 | 3.514357 / 2.043686 |
| 慢速：冻结原始 RP 均值 / ° | 3.175570 / 0.217957 | 3.405132 / -2.201637 | 0.827840 / -0.913150 |
| 慢速：冻结原始 RP σ / ° | 11.099307 / 7.488247 | 8.332473 / 6.907200 | 3.514357 / 2.198220 |

rpy 的源轴序由日志 quaternion 重建逐样本核对，见 JSON。物理 FLU→FRD 的对应是 [roll,−pitch]；冻结 RP 操作直接使用 [roll,pitch]，属于不同操作约定。比较用的是同一 Go2 IMU 的融合 rpy 与加速度计，并非独立姿态真值。动态加速度、低速样本少和姿态幅度不足会限制符号辨别。

### 6. 预注册阈值判定

| 项目 | 序列 | 绝对量 | 严格阈值 | 判定 |
|---|---|---:|---:|---|
| gyro_z_scale_systematic_angle | BY2 | 0.335037 | 20.598202 | 未触发 |
| sigma_A1_relative_difference | BY2 | 0.955462 | 0.500000 | HUMAN_DECISION_REQUIRED |
| installation_roll_offset_proxy | BY2 | 2.422178 | 1.000000 | HUMAN_DECISION_REQUIRED |
| installation_pitch | BY2 | UNAVAILABLE | 1.000000 | NOT_OBSERVABLE / UNAVAILABLE |
| installation_yaw_effective_method1 | BY2 | 4.544357 | 1.000000 | HUMAN_DECISION_REQUIRED |
| installation_yaw_effective_method2 | BY2 | 3.952922 | 1.000000 | HUMAN_DECISION_REQUIRED |
| HV_N_mean | BY2 | 0.006790 | 0.435760 | 未触发 |
| HV_E_mean | BY2 | 0.006721 | 0.357405 | 未触发 |
| RP_slow_converted_roll_mean | BY2 | 3.175570 | 33.297922 | 未触发 |
| RP_slow_converted_pitch_mean | BY2 | 1.760538 | 21.833495 | 未触发 |
| RP_slow_frozen_roll_mean | BY2 | 3.175570 | 33.297922 | 未触发 |
| RP_slow_frozen_pitch_mean | BY2 | 0.217957 | 22.464740 | 未触发 |
| RP_first_1000_frozen_roll_mean | BY2 | 0.688255 | 0.638769 | HUMAN_DECISION_REQUIRED |
| RP_first_1000_frozen_pitch_mean | BY2 | 2.028821 | 0.824113 | HUMAN_DECISION_REQUIRED |
| gyro_z_scale_systematic_angle | BY2H | 2.475751 | 247.023468 | 未触发 |
| sigma_A1_relative_difference | BY2H | 4.604306 | 0.500000 | HUMAN_DECISION_REQUIRED |
| installation_roll_offset_proxy | BY2H | UNAVAILABLE | 1.000000 | NOT_OBSERVABLE / UNAVAILABLE |
| installation_pitch | BY2H | UNAVAILABLE | 1.000000 | NOT_OBSERVABLE / UNAVAILABLE |
| installation_yaw_effective_method1 | BY2H | 3.905588 | 1.000000 | HUMAN_DECISION_REQUIRED |
| installation_yaw_effective_method2 | BY2H | 3.908300 | 1.000000 | HUMAN_DECISION_REQUIRED |
| HV_N_mean | BY2H | 0.001561 | 0.482413 | 未触发 |
| HV_E_mean | BY2H | 0.023632 | 0.749660 | 未触发 |
| RP_slow_converted_roll_mean | BY2H | 3.405132 | 24.997420 | 未触发 |
| RP_slow_converted_pitch_mean | BY2H | 0.769777 | 17.278386 | 未触发 |
| RP_slow_frozen_roll_mean | BY2H | 3.405132 | 24.997420 | 未触发 |
| RP_slow_frozen_pitch_mean | BY2H | 2.201637 | 20.721599 | 未触发 |
| RP_first_1000_frozen_roll_mean | BY2H | 0.666042 | 0.652137 | HUMAN_DECISION_REQUIRED |
| RP_first_1000_frozen_pitch_mean | BY2H | 2.212328 | 0.826796 | HUMAN_DECISION_REQUIRED |
| gyro_z_scale_systematic_angle | BY2O | 1.609843 | 27.653504 | 未触发 |
| sigma_A1_relative_difference | BY2O | 0.957633 | 0.500000 | HUMAN_DECISION_REQUIRED |
| installation_roll_offset_proxy | BY2O | 3.150564 | 1.000000 | HUMAN_DECISION_REQUIRED |
| installation_pitch | BY2O | UNAVAILABLE | 1.000000 | NOT_OBSERVABLE / UNAVAILABLE |
| installation_yaw_effective_method1 | BY2O | 1.617459 | 1.000000 | HUMAN_DECISION_REQUIRED |
| installation_yaw_effective_method2 | BY2O | 1.162595 | 1.000000 | HUMAN_DECISION_REQUIRED |
| HV_N_mean | BY2O | 0.006313 | 0.320654 | 未触发 |
| HV_E_mean | BY2O | 0.007913 | 0.317730 | 未触发 |
| RP_slow_converted_roll_mean | BY2O | 0.827840 | 10.543070 | 未触发 |
| RP_slow_converted_pitch_mean | BY2O | 0.521081 | 6.131057 | 未触发 |
| RP_slow_frozen_roll_mean | BY2O | 0.827840 | 10.543070 | 未触发 |
| RP_slow_frozen_pitch_mean | BY2O | 0.913150 | 6.594659 | 未触发 |
| RP_first_1000_frozen_roll_mean | BY2O | 0.677666 | 0.625772 | HUMAN_DECISION_REQUIRED |
| RP_first_1000_frozen_pitch_mean | BY2O | 4.296193 | 0.827924 | HUMAN_DECISION_REQUIRED |
| RP_BY2O_standing_frozen_roll_mean | BY2O | 0.730233 | 3.139593 | 未触发 |
| RP_BY2O_standing_frozen_pitch_mean | BY2O | 0.953407 | 3.728521 | 未触发 |
| static_first_1000_gyro_x_mean_after_frozen_debias | BY2 | 0.000000 | 112.361778 | 未触发 |
| static_first_1000_gyro_y_mean_after_frozen_debias | BY2 | 0.000000 | 74.121308 | 未触发 |
| static_first_1000_gyro_z_mean_after_frozen_debias | BY2 | 0.000000 | 78.594388 | 未触发 |
| static_first_1000_gyro_x_mean_after_frozen_debias | BY2H | 0.000000 | 112.361778 | 未触发 |
| static_first_1000_gyro_y_mean_after_frozen_debias | BY2H | 0.000000 | 74.121308 | 未触发 |
| static_first_1000_gyro_z_mean_after_frozen_debias | BY2H | 0.000000 | 78.594388 | 未触发 |
| static_first_1000_gyro_x_mean_after_frozen_debias | BY2O | 0.000000 | 112.361778 | 未触发 |
| static_first_1000_gyro_y_mean_after_frozen_debias | BY2O | 0.000000 | 74.121308 | 未触发 |
| static_first_1000_gyro_z_mean_after_frozen_debias | BY2O | 0.000000 | 78.594388 | 未触发 |
| static_BY2O_standing_gyro_x_mean_after_frozen_debias | BY2O | 23.767541 | 112.361778 | 未触发 |
| static_BY2O_standing_gyro_y_mean_after_frozen_debias | BY2O | 18.752932 | 74.121308 | 未触发 |
| static_BY2O_standing_gyro_z_mean_after_frozen_debias | BY2O | 47.572445 | 78.594388 | 未触发 |

总判定：`HUMAN_DECISION_REQUIRED`。触发仅登记供人类决定；没有据此改变 provider、标准差、安装角或求解链。不可观测量和条件性代理均保留限制，不冒充通过或标定完成。

### 7. 输入、复核与封存

观测来自哈希锁定的 raw Go2 日志、GNSS status 与冻结 CAL/V2s GNSS18/HV/IMU；PVT 和 A1 的 iTOW 身份沿用并固定 P-11a 已验证记录。此次重新检查输入哈希、完整冻结 HV/gyro 增量重建及 A1 基线航向同历元一致性。

计算基底：`958f5778040a5371274e54e282f5bdf7f9eff690`。计算前登记全文 SHA-256：`bc74d5e96ed176e383edb87519c7a453c1fff7f95b6a70fed92774e88572016f`；完整输入及运行脚本哈希见 JSON。

实施复核记录：首轮在未舍入 gyro 增量与 8 位小数冻结 token 的比较处停止，尚未计算 P-12 指标；修正为原 .12g→.8f 写出格式后全量 token 一致。第一份完整计算及过程脚本另存 FIRST_CALCULATION；随后仅以相同静止窗均值减去冻结首窗均值，修正行动表的既有去偏适用范围，科学统计值和预注册阈值未改。

外部文件：`<CLEAN_ROOT>/stages/CLEAN6_HV_PRIOR_CALIBRATION/SENSOR_MODEL_CLOSEOUT_AUDIT.json`、`.md`；计算前登记副本 `SENSOR_MODEL_CLOSEOUT_PREREGISTRATION.md`。零 trace/求解器/评估器/provider 生成；所有数组仅作诊断，不作为求解器输入。
