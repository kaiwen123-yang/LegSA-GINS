# Fixposition 参考自身质量与时间定义：NMB1 只读核查

2026-10-07。当前参考连续输出，但不能据此当作连续绝对高精真值。NMB1 主空窗内，参考状态明确表示 GNSS 未使用、视觉和 IMU 仍在工作，报告的位置不确定度达到米级；恢复后自身位置出现 4.07 m 修正。以上证据来自参考本身，没有读取待测 NAV 或用导航误差定义参考质量，也不证明参考的实际误差等于报告 sigma。

## 输入与读取范围

以 `SUPPORT_SDK_JOINT_NMB1_01/PLAN.json` 的实际 reference 为入口：

- ZIP：`/mnt/g/LegSA-GINS-project/data/raw/XB_PG/2026-01-05/fixpositon数据/vrtk2_a87c6e_2026-01-05-11-16-59_minimal.zip`。
- NMB1 成员前缀：`vrtk2_a87c6e_2026-01-05-11-16-59_minimal/`；trace SHA-256 `5d0c88859d37dabf8f0ede16c0e6177c3c78fe8249409edc071eb559ea001a45` 与冻结 PLAN 一致。
- 当前完整窗 `[40621.403808498384,40972.56780471802]`，原位置空窗 `[40749.60018873215,40912.600195646286]`；时间均为 Unix 减 `1767571200`。
- 仅读取上述前缀的 trace、poi_geodetic、poi_odometry、ODOMSTATUS、两路 GNSS-status；其他七段只读相同四类 CSV 表头，状态分布复用已有 `TIM_EVIDENCE_20261005/data_and_selection/RECORDED_OUTPUT_STATUS_AND_VERSION.json`。没有解压 ZIP、重扫 GNSS raw、接入无时间标准 TXT、读取足部 INS、修改评价或运行 native。

脚本 `scripts/paper_rebuild/unified_legged_heading_20261007/reference_trace_quality_audit.py`；scratch 为 `/home/kaiwen/research/LegSA-GINS-SCRATCH/UNIFIED_LEGGED_HEADING_20261007/REFERENCE_TRACE_QUALITY_NMB1_01/`。PLAN 保存脚本、旧方案、旧状态汇总和每个实际读取 CSV 的 hash。完整逐源历元、状态区间、schema 与 JSON 留在 scratch；三张小汇总表与本文同目录。

## 参考产品有哪些信息

| 当前文件 | 实际记录 | 不能额外推断的含义 |
|---|---|---|
| trace | 到达时刻、原 LLH、processed LLH、yaw/pitch/roll | 无质量或协方差列；processed 字段不是另一独立参考 |
| poi_geodetic | header 测量时刻、GEODETIC 位置、ENU 位置方差、ENU ypr/ypr_var、速度及方差 | legacy `ypr_var` 的生产实现／单位尚未独立定位，不直接开方称 yaw sigma |
| poi_odometry | header、ECEF→POI pose、6×6 pose covariance、twist covariance | 姿态块是角轴协方差，不是 Euler yaw/pitch/roll 方差 |
| ODOMSTATUS | 初始化、IMU／相机／GNSS 是否使用、各内部状态 | 其状态分类是内部融合逻辑，不是每个 pose 的独立真值有效位 |
| GNSS-status | msg_valid、fix_ok、fix_type、position/time 状态、精度及卫星信息 | GNSS status 可与自身时间匹配，但原 GNSS PVA／INSPVAX 并不提供独立于参考融合输入的新真值 |

官方 [日志说明](https://docs.fixposition.com/fd/generating-a-log-of-the-vision-rtk-2) 将 poi_geodetic 标为 PoseTwistWithVarStamped；[ODOMETRY 定义](https://docs.fixposition.com/fd/fp_a-odometry)给出位置 m²、姿态 rad²；[协方差说明](https://docs.fixposition.com/fd/covariance-estimations)明确姿态为 angle-axis、协方差受可用观测影响。本文报告角轴最大主轴标准差，仅表示姿态不确定度量级，不等于航向标准差，也不把厂商模型当作已经独立校准的实际误差分布。

## 到达时间与测量时间：来源定义可追踪，但未改评价

NMB1 trace 共 7,328 行，六个 LLH/RPY 字段逐行复现 poi_geodetic，最大绝对差 `2.84e−14`；trace time 与 geodetic 到达 Time 差最大 `0.477 us`。测量 header 恰有 3,664 个唯一历元，每个出现两次，重复的六个 payload 数值完全相同。原始顺序无倒序，所有 payload 有限。

| 时间证据 | 当前完整窗 | 主空窗 |
|---|---:|---:|
| trace 到达行数 | 7,022 | 3,260 |
| 唯一测量历元 | 3,511 | 1,630 |
| 到达−测量 median | 1.962 ms | 1.847 ms |
| 到达−测量 p95 | 3.562 ms | 3.297 ms |
| 到达−测量 max | 11.705 ms | 11.705 ms |
| 测量间隔 | 0.1 s | 0.1 s |
| trace／测量轴超过原 0.15 s 的间隔 | 0 / 0 | 0 / 0 |

整个文件的最大到达滞后 347.823 ms 出现在当前完整窗之前，不能拿它解释本窗的米级差。旧 R5 评价器 `evaluate_new_sequences_0p15.py:46–54` 实际使用 trace time，按完全相同到达时间去重，并将 ENU yaw 转为 `90°−yaw`；因此没有合并本次这种不同到达时刻的同测量历元。其“20 Hz nominal”注释描述了重复到达行的表象，独立 pose 测量实际为 10 Hz。

可形成独立版本的测量时轴候选：保留完整源行映射，同一 header 且 payload 完全相同者只取首条，直接使用记录的 header，不拟合 offset、不按 NAV 误差选时偏。它能修正参考产品的时间／重复定义，**不能补出绝对精度或安装标定**。本轮不创建新评价结果、不替换冻结 trace，毫秒级延迟也不是已证的米级主因。

## 主空窗的实际模式与不确定度

状态在原到达时轴落窗，共 1,630 条：`init_status=2`、`fusion_imu=1`、`fusion_cam1=1`、`cam1_status=5`、`imu_status=3` 全部成立；`fusion_gnss1=0`、`fusion_gnss2=0`、`gnss1_status=0`、`gnss2_status=0`、`baseline_status=1` 同样全部成立。`imu_noise=3` 为 1,629 条，另 1 条为 2。按官方 [ODOMSTATUS](https://docs.fixposition.com/fd/fp_a-odomstatus) 的对应 enum，这表示全局已初始化、视觉／IMU 继续使用、两路 GNSS 未使用且基线不可用；并非“GNSS 一直有绝对约束”。ODOMSTATUS 与 ODOMETRY 的分类定义不同，不能混用其同名数值。旧记录识别的是 ODOMETRY schema 2，尚未定位安装固件版本；原枚举数字保留，不从当前官网默认值回填设备配置。

ODOMSTATUS header 是内部状态时刻，和 pose header 不同；按它落窗有 1,629 条。本报告同时保留两种窗口计数，未把状态按最近邻包装成精确 pose 真值 mask。GNSS1-status 在 gap 内 `fix_ok=False` 163/163；GNSS2 为 162/163，另 1 条为 True。`pos_valid=True` 并不意味着 fix_ok 或参考高精有效。

定义 `sigma_H=sqrt(var_E+var_N)`，是两个水平边际方差之和的均方根尺度，**不是置信椭圆半径或误差硬界**：

| 来源报告量 | 完整窗 median / p95 / max | 主空窗 median / p95 / max |
|---|---|---|
| sigma_H (m) | 0.893 / 3.301 / 3.643 | 1.568 / 3.455 / 3.643 |
| sigma_Up (m) | 0.484 / 1.144 / 1.308 | 0.862 / 1.064 / 1.077 |
| 姿态角轴最大主轴 sigma (deg) | 1.370 / 4.263 / 4.770 | 1.506 / 4.606 / 4.770 |

按唯一 header 历元取 `sqrt(mean(sigma_H²))`，完整窗为 **1.623395597 m**，gap 为 **2.030940363 m**；Up 对应 0.644974680 / 0.825004880 m。该派生只读已保存 SOURCE_EPOCHS，不重开原数据，见 `REFERENCE_REPORTED_SIGMA_RMS.csv`。可作敏感性假设的量级对照，不能将其自动设为实际参考误差 RMS 上界。

3,664 个完整 pose covariance 均有限；最大不对称 `3.55e−15`，最小特征值 `4.15e−5`，无负对角，四元数模长最大误差 `2.22e−16`。所以没有结构损坏或全段无效证据；但 finite／PSD／连续并不认证绝对准确。

## 恢复后存在参考自身位置修正

测量时刻 `40935.6→40935.7`，0.1 s 内 ECEF 位置改变 **4.070662 m**；同时位置最大主轴 sigma 从 **3.013719 m** 降为 **0.123627 m**。其 ENU 水平合成 sigma 从 3.479578 m 降为 0.147029 m，Up 从 1.308416 m 降为 0.086040 m。gap 内最大 0.1 s 位置步长只有 0.240569 m。

这是参考输出自身的明显全局修正线索，与恢复绝对观测后的融合校正相容；不是待测 NAV 的误差，也不是时间序列缺行。它不告诉我们修正前后哪个位置等于真值，不能据此删除该段、转用 smooth 输出或宣布先前所有排名无效。完整窗/恢复段指标必须保留这层解释边界。

## 其他七段、比较点与当前可宣称范围

八段均有同类 trace、geodetic、odometry、ODOMSTATUS 字段，可继续利用源自身质量；它们不是完全没有不确定度数据。复用的八段全文件状态汇总中，相机均报告使用、初始化均为 2；所有段都有 GNSS 未使用／退化。四段 XB 的 baseline_status 全部为 1；NMB2、NMB4 另有 IMU degraded 状态。详见 `REFERENCE_EIGHT_SEQUENCE_STATUS_OVERVIEW.csv`。这些分母是完整源文件，不能与当前 NMB1 3511 / 1630 窗口混算；本轮没有重扫或评价全部八段。

当前 joint config 明确 `solver_output_reference_point=propagation_imu_reference_point`、`evaluation_reference_point_match_established=false`、`reference_point_compensation_applied=false`，运行 antlever 为 `[0.03,0.03,−0.3] m`。另一方面，冻结评价的 `transform_nav()` 确实施加 `[0.03,0.03−baseline/2,−0.3]`，NMB1 即 `[0.03,−0.14535186047,−0.3] m`。二者意味着存在实际执行的**假定点变换**，不是已实测认证的 POI—机体—天线中点关系；配置里的 false 不能简化为“评价根本没变换”，也不能因执行了变换就写成“比较点匹配已证”。

本次 odometry frame 为 ECEF、child 为 POI。官方 [ROS driver](https://docs.fixposition.com/fd/fixposition-ros-driver)及输出定义区分 POI 与天线；POI 可配置，不能默认本次配置等于设备或机器人原点。既有作者确认相机侧朝前，不等于安装偏角／杆臂精度已认证。[航向提取定义](https://docs.fixposition.com/fd/extract-heading-from-vrtk-2)支持 ENU/NED 的 90° 换算，但不能补出设备到机器人机体的安装标定。此为参考点／姿态定义的不确定度，和参考滤波自身退化是两层问题。

目前准确表述是：**相对共享 GNSS 来源的商业视觉–惯性–GNSS参考的条件一致性，附参考自身退化、安装／点变换未认证及来源相关边界。** 不能称独立绝对 PVA 真值；也不能由这些限制直接宣布“已经证明参考轨迹差，因此算法真实改善”。下一步若用已保存误差系列做条件敏感性代数，必须显式声明参考误差界假设，保留全部原结果，不能将厂商 sigma 等同该界。本轮无质量驱动删点、阈值选优、算法改动或新评价。
