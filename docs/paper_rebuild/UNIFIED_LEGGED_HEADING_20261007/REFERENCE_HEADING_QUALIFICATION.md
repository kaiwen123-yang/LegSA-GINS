# NMB1 参考航向：角轴协方差传播与历史语义边界

2026-10-07，起点 HEAD `72af566`。本次补齐“参考自身报告的航向不确定度是多少”，不重新评价算法。**角轴最大主轴 sigma 不能当作 yaw sigma。按公开 ROS／Fixposition 固定参考轴约定作主解释时，NMB1 gap 航向 sigma RMS 为 0.9365°；历史导出器协方差语义尚未锁定，另列 POI 局部轴解释的 1.7729°。两者均不是独立实测航向误差或硬界。**

## 1. 已确认的记录及公开约定

上一审计缓存 `REFERENCE_TRACE_QUALITY_NMB1_01/SOURCE_EPOCHS.csv` 有唯一测量历元、LLH、ENU yaw 与 legacy ypr_var，但没有 quaternion／完整 orientation covariance。因此本轮仅补读一次 NMB1 ZIP 的 `user_io-out-poi_odometry.csv`（6,658,436 bytes），SHA 与旧审计 member pin 一致；没有复扫八段或重新读取 trace、GNSS raw、标准 TXT。

3,664 条记录均为 `header.frame_id=ECEF`、`child_frame_id=POI`。整数 header sec/nsec 本次完整保存；与旧缓存浮点时间的最大差 95.37 ns，属于其浮点表达。实际 quaternion 按 `R_ECEF_POI` 转入各历元当地 ENU，所得 yaw 与旧缓存全部记录的最大差仅 `7.63e−14°`，因此旋转方向、四元数顺序及 ENU yaw 数值链已由同源 payload 核对。

公开依据如下：

- [Fixposition ODOMETRY](https://docs.fixposition.com/fd/fp_a-odometry)给出 ECEF quaternion 和 rad² 姿态协方差；[协方差说明](https://docs.fixposition.com/fd/covariance-estimations)明确 orientation 为 angle-axis，ODOMENU covariance 相对 ENU0。不能直接取 orientation_cov_zz 或最大特征值作为 Euler yaw 方差。
- ROS 官方 [Odometry.msg](https://github.com/ros/common_msgs/blob/noetic-devel/nav_msgs/msg/Odometry.msg)规定 pose 在 header.frame_id，twist 在 child_frame_id；[PoseWithCovariance.msg](https://github.com/ros/common_msgs/blob/noetic-devel/geometry_msgs/msg/PoseWithCovariance.msg)规定姿态协方差按固定轴旋转排列。这支持将本次 ECEF header 的姿态块解释为 ECEF 固定参考轴角扰动。
- [官方航向提取说明](https://docs.fixposition.com/fd/extract-heading-from-vrtk-2)将 ECEF 姿态先转 local ENU，再以 `heading=90°−ENU yaw` 得到北起顺时针航向。

这些是公开消息／坐标约定，不是本次 legacy FPL→ROS→CSV 导出程序版本的认证。日志属于内部 `poi_odometry / PoseTwistWithVarStamped` 链；现有证据没有锁定当时 exporter/firmware commit，不能将当前公开 driver 自动视为当时 producer。旧识别的 FP_A-ODOMETRY schema 2 也不是固件版本。因此以下 A 是有公开依据的主解释，B 是历史序列化语义未闭合时的明确敏感性假设，不将二者说成同样已获证。

## 2. 从完整角轴块到航向的 Jacobian

记 `R=R_ECEF_POI`、`A=R_ENU_ECEF(lat,lon)`，`U=AR`，`f=U e_x=[x,y,z]^T`，`q=x²+y²`。固定当前记录的 local frame：

```
psi = atan2(y,x)                  # ENU yaw
h   = pi/2 − psi                  # NED heading
G   = [-y/q, x/q, 0]
J_psi_ENU = G (−[f]x) = [−xz/q, −yz/q, 1]
```

解释 A：序列化 `C` 是 ECEF 固定轴角扰动的协方差，`R_true=Exp([delta_E]x)R`：

```
J_h_E = −G (−[f]x) A
Var_A(h) = J_h_E C J_h_E^T.
```

解释 B：**同一组序列化数字另被假设为 POI 局部轴协方差**，`R_true=R Exp([delta_P]x)`：

```
J_h_P = −G (−U[e_x]x) = J_h_E R
Var_B(h) = J_h_P C J_h_P^T.
```

B 不是把 A 换坐标后再算一次。若确实是同一个物理协方差，必须用 `C_P=R^T C_E R`，则 `J_h_E C_E J_h_E^T = J_h_P C_P J_h_P^T`；实际全部历元两式最大差 `1.08e−18 rad²`。两解释结果不同，完全来自历史序列化矩阵究竟代表哪组轴的假设差异，不能按结果大小选择。

完整 3×3 非对角项均参与传播；没有将角轴块变成对角矩阵。局部 ENU 的经纬度在此条件传播中固定，未加上参考位置不确定度引起的 local-frame 变化，也未纳入 POI→机器人 body 的安装误差；因此这是条件性的姿态到航向传播，不是完整参考误差预算。

一次集中公式检查使用非零 RPY `[13°,−17°,47°]`、各向异性协方差及中心差分 `1e−6 rad`。左右 Jacobian 最大差分别 `7.63e−11`、`1.21e−10`，同物理 covariance 换轴的方差差 `1.63e−19`，PASS。没有增加阈值扫描或算法测试。真实数据的 `q` 最小为 0.984974，未接近前向轴竖直导致的航向奇异；所有历元保留。

## 3. 固定窗口结果

使用唯一 source header 历元，不按待测误差选择片段：FULL 与 GAP 沿用旧界；RECOVERY 固定为 `[40912.600195646286,40972.56780471802]`。表内单位全部为 degree，RMS 是 `sqrt(mean(sigma_h²))`，不是实际航向误差 RMSE。

| 窗口 | 历元 | A：median / p95 / max / RMS | B：median / p95 / max / RMS |
|---|---:|---|---|
| FULL | 3511 | 0.8169 / 1.1160 / 1.9298 / **0.8518** | 1.0568 / 2.7280 / 3.2251 / **1.4192** |
| GAP | 1630 | 0.8799 / 1.1893 / 1.9298 / **0.9365** | 1.1531 / 2.8878 / 3.2251 / **1.7729** |
| RECOVERY | 599 | 0.7174 / 0.9485 / 1.0435 / **0.7466** | 0.8672 / 1.3262 / 1.7089 / **0.9423** |

A 在 gap 起末为 1.0327°→0.9404°，峰值出现在 40898.8 s；恢复窗起末为 0.8995°→0.4702°。这些值没有单调增长要求，不能将下降本身解释为获得独立绝对航向信息。按上一源内状态审计，gap 全部到达状态均报告 GNSS1/2 未使用、相机和 IMU 继续使用；RMS 不确定度有限不等于有持续绝对 GNSS 航向锚。

B/A 的 gap sigma 比 median 1.5011、p95 2.6346、max 3.2817，说明历史 covariance frame 不能随意忽略。旧报告 gap 的 4.606° 是角轴最大主轴 sigma 的 p95，**并非本次 A 的 yaw p95 1.1893°，也不是 B 的 2.8878°**。

此前已识别的 40935.6→40935.7 s、4.0707 m 位置修正附近，记录 NED heading 改变约 +1.3996°；A sigma 为 0.9780°→0.8782°，B 为 1.0440°→0.9688°。没有把这段 heading 变化从真实机体转动中分离，因此不能命名为“真实 yaw 跳误差”，也不能按它删除恢复段。

## 4. Legacy ypr_var 不能替代本次推导

保留 `ypr_var.vector3.x` 原值，分别与 A/B 的 degree 标准差、degree² 方差作不拟合比例／偏移的数值一致性检查；四种关系均不恒等。例如 gap 原字段与 A degree² 方差最大差 4.6059，与 A degree 标准差最大差 5.3399。当前没有该字段的历史生成实现，不能通过寻找更贴近的曲线替它指定单位或反过来选择 covariance frame。本次没有用它认证 A/B，也没有调整原字段。

## 5. 航向资格结论与产物

目前能确认：记录的 quaternion、坐标换算和 trace yaw 相互一致；完整 covariance 可在明示轴假设下传播为航向不确定度；参考输出在原长空窗中依赖视觉／IMU继续维持，不能称独立无误差航向真值。不能确认：厂商内部 sigma 已独立校准、历史 exporter 完全遵从当前消息约定、POI 相对机器人 body 的安装旋转已实测，因此不能将表中 sigma 直接加到算法误差上或当其误差硬界。

下一解释应使用“相对于商业参考的条件航向一致性”，同时保留 A 主解释及 B 敏感性边界；历史安装／来源语义如得到原配置或 producer 版本可再缩小边界，而不是按 NAV 误差拟合一个参考 yaw 偏置。没有修改原参考、旧评价、时间偏置、质量 mask 或任何导航状态。

新增脚本：`scripts/paper_rebuild/unified_legged_heading_20261007/reference_heading_qualification.py`。同目录小表 `REFERENCE_HEADING_SIGMA_SUMMARY.csv`、公式核对 `REFERENCE_HEADING_FORMULA_CHECK.json`。完整 PLAN、SUMMARY、逐历元 HEADING_EPOCHS 以及今后无需重读 ZIP 的 `ORIENTATION_SOURCE_CACHE.npz` 位于 `/home/kaiwen/research/LegSA-GINS-SCRATCH/UNIFIED_LEGGED_HEADING_20261007/REFERENCE_HEADING_QUALIFICATION_NMB1_01/`；原 ZIP relevant entry 新读取次数 1，NAV / native / evaluator / 八段重扫均为 0。
