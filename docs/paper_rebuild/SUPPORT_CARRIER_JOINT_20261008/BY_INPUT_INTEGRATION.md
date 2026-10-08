# BY2 真实输入接入说明

日期：2026-10-08。只读定位基于研究分支 `research/support-carrier-joint-20261008` 的 `381db92` 原型接口及既有合法输入。本文件是接入准备；本次未生成新 provider、未运行新导航或评价，不构成真实数据效果证明。下述四项接口缺口描述的是所检查版本，后续实现应记录自己的提交身份。

## 数据分工

- BY/BY2：开发、调参与输入接入验证；本次只查看这一序列的源、配置和模型。
- BYO/BY2O、BYH/BY2H：固定算法后的测试，不用其指标选模型或参数。
- XB、NMB：恶劣条件检验，不用其指标调参；缺失方向或初始化失败保留为结果。

BY2 是本文件实际路径中的序列名。既往已经看过的数据不能宣称全新盲测；本轮分工约束新原型的开发与评价。

## 可直接复用的输入

机器本地绝对路径仅用于本接入说明；实现通过配置传入，不写死到公共算法。

| 输入 | 已核实路径 |
|---|---|
| Go2 原始 body | `/mnt/g/LegSA-GINS-project/data/raw/BY2_BY3/2026-03-06/高层数据/by2.txt` |
| 已校正 IMU | `/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN5_CALIBRATED_SENSOR_MODEL/02_CALIBRATED_PROVIDERS/BY2/CALIBRATED_IMU.imu` |
| GNSS 位置/速度 | `/home/kaiwen/research/LegSA-GINS-SCRATCH/CLEAN8_PROTOCOL_V3/02_PROVIDERS/CASES/BY2__C00_clean_normal__b98b48979d509bce1429b360c6e0d675c028ff42e3158d4c97dd63df61d62663/GNSS18.gnss` |
| 原始码/载波 DD 模型计划 | `/home/kaiwen/research/LegSA-GINS-SCRATCH/TRUSTED_HEADING_20261006/FULL_WINDOW_PREPARE_ATTEMPT02/BY2/MODELS/PLAN.json` |
| 每历元 DD 数组 | 上述 `MODELS` 目录内计划指向的 `GPS_GAL_BDS_DUAL_<index>.npz` |
| 既有导航输入配置 | `/home/kaiwen/research/LegSA-GINS-SCRATCH/TRUSTED_HEADING_20261006/FULL_WINDOW_NAVIGATION_ATTEMPT01/CONFIGS/BY2__CARRIER_FALLBACK.yaml` |
| BY2 加计标定模型 | `/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN5_CALIBRATED_SENSOR_MODEL/00_CALIBRATION/CLEAN5_CALIBRATED_SENSOR_MODEL.yaml` |

输入角色与原有身份还可追到 `docs/paper_rebuild/TRUSTED_HEADING_20261006/FULL_WINDOW_NAV_INPUT_MAP.json` 中的 BY2 条目。该旧映射限定原 V3 输入，不能把新原型称为 V3 原样重放。

## 时间与载波模型

- BY2 基准 Unix 时间为 `1772784000.0`，原窗为 `66–340 s`；本序列不使用 NMB 的 −1.1 s 偏移。
- body 时间由原 `stamp.sec/nanosec` 得到；RAWX 时间沿用保存计划。来源时刻回放不等于已经测量的传输到达延迟。
- 保存计划有 1370 个 RAWX 槽。首槽 `66.19799995422363 s` 无可用因果星历/anchor；首个 `GPS_GAL_BDS_DUAL` BUILT 模型在 `100.19799995422363 s`，为 `GPS_GAL_BDS_DUAL_170.npz`，38 行、19 个 ambiguity。未构建槽保留 `carrier=None`，不向前借用未来模型。
- 模型已包含真实 receiver arc 标签、GNSS2−GNSS1 接收机顺序、SATELLITE_MINUS_PIVOT 双差符号和原报 CPMES 相位语义。保持原 `y/A/Q`、整数列顺序和完整 DD 协方差，不再以旧 `CARRIER.csv` 或 `MOTION.csv` 替代原始模型。

最短复用入口是 `scripts/paper_rebuild/carrier_phase/shadow_replay.py::load_model(models_dir, record, "GPS_GAL_BDS_DUAL")`，随后构造现有 `carrier_phase.temporal.EpochBlock`。原模型 `B` 是 ECEF；当前原型状态是固定局部 NED，因此应转换：

```python
B_ned = model.B @ R_ecef_from_ned
block = EpochBlock(model.time_s, model.y, model.A, B_ned, model.Q,
                   model.ambiguity_labels,
                   {**model.metadata, "baseline_frame": "NED"})
```

`R_ecef_from_ned` 来自明确登记的固定局部原点。只改 frame 标签而不转 `B` 是错误接入。机体为 FRD，物理侧向基线为 `[0, -0.35, 0] m`。保存的 code anchor 是模型几何线性化点，不能直接升级为精确导航位置观测。

如必须重新构建原始模型，现成入口链为 `real_trial.py` 的 `NavigationReplay`、`CausalRawCodeAnchor`、`ArcTracker`、`build_with_pivot_policy`，以及 `carrier_phase.multignss.build_multignss_epoch`；本阶段无需重走该链。

## IMU 和 GNSS 字段映射

`CALIBRATED_IMU.imu` 七列为 `t,dtheta_x,dtheta_y,dtheta_z,dvel_x,dvel_y,dvel_z`。它已做 FLU→FRD、`Rx(-1°)` 安装修正、原始前 1000 样本 gyro 均值扣除，以及加计尺度 `1.0308398903907543`；不要再次应用。

原型 IMU packet 要求 `[dt, ax, ay, az, gx, gy, gz]`，故对应 rate 为 `dvel/dt` 和 `dtheta/dt`，不能直接传入增量再次积分。原七列时间舍入到微秒；精确事件拆分需要同一 raw stamp 的实际 dt，或按原 builder 公式重建 rate。公式在 `src/legsa_gins/input_generation/imu_txt_builder.py:85`，尺度/当前样本积分在 `src/legsa_gins/paper_rebuild/clean5_calibrated/providers.py:47`。拆分区间保持原积分总量与因果样本界，不引入未来样本或重复增量。

GNSS18 的零基列为：

| 列 | 内容 |
|---|---|
| 0 | 相对基准时间 |
| 1–3 | 纬度/经度（度）、高程（m） |
| 4–6 | N/E/D 位置标准差（m） |
| 7–9 | N/E/D 速度（m/s） |
| 10–12 | 速度标准差（m/s） |
| 13–14 | PVT 派生 yaw 及标准差，本研究不作量测消费 |
| 15–17 | position_valid、velocity_valid、yaw_valid |

位置用 WGS84→ECEF→固定局部 NED；速度和协方差也进入同一固定局部坐标。逐历元保留有效性与标准差，不沿用合成的常量位置精度。GNSS1 天线杆臂为 `[0.03,0.03,-0.30] m` FRD：位置因子应预测 `p+R*l`，速度模型应处理相应旋转项；创新、更新和失配判断使用同一物理点。不得先用当前姿态减杆臂，再将结果当独立 IMU 点位置量测。

## 足力/足点到支撑弧

同一 body 流可复用 `horizontal_literature.hartley_h5._parse_allowed_record`，仅解码 timestamp、gyro、accel、foot_force 和 foot_position_body。原足序为 `FR,FL,RR,RL`。足点做 `[1,-1,-1]` 的 FLU→FRD，不再施加 IMU 安装旋转；body 原点到 IMU 原点为零沿用既有工作假设并显式登记。

复用 `carrier_phase.support_arcs.SupportArcTracker` 的真实数据政策：

```text
on  = (34.2, 33.8, 30.6, 32.0)
off = (24.8, 25.2, 23.4, 24.0)
dwell_s = 0.012035608291625977
max_source_gap_s = 0.05
```

每个原 body 样本驱动 tracker。只有实际 `eligible` 的足进入事件，内容为 `foot_id,arc_id,point_body,force`；稳定 token 对应同一支撑弧，低力退出、缺样或 source gap 后不能复活旧 token。不要再用合成 `force>=60` 二次过滤已判定的真实支撑资格。

无需先压成旧 100 ms 足对 START/END。新后端直接维护每条足接触弧；事件由 GNSS/RAWX、支撑身份变化和固定 keyframe 时刻组成，IMU packet 覆盖两事件间完整输入。tracker 按原 body 频率运行，不意味着每个数百 Hz 样本都新增一个 GTSAM pose。连续 SDK 足点的时间相关模型必须保留为明确工作模型，不能当 IID，也不能将 SDK 代理宣称为原始关节运动学真值。

## 必改的四个真实接入接口

1. **初始化与异步事件。** 所查 `_initial_pose` 要求同 event 同时有 carrier、GNSS position 和 velocity；真实 RAWX 约 `.198 s`、PVT 约 `.0/.2 s`，不能最近邻伪造成同历元。应明确采用有来源的初值并传播，或保留等待初始化状态；不得用 100 s 的模型回填 66 s。
2. **逐事件 GNSS covariance 和天线杆臂。** 所查因子把位置/速度直接当状态点，并使用 metadata 常量精度；真实接口需让更新和独立预测共享正确测量模型。
3. **真实支撑资格。** 使用 provider 的因果支撑 token/资格，替代合成的统一 60 阈值。
4. **真实 partial 定义。** 所查 `full_phase_relations=5` 是合成场景计数。BY2 丢失部分真实关系后仍可能有超过 5 个整数，不能靠固定数量划分完整/部分；需按实际载波弧及保留整数关系区分 U0/U1 与 U2/U3。

## 统一来源政策

各研究臂保留相同合法 PVT position/velocity 供给；GNSS18 的 yaw/yaw_std/yaw_valid 不作航向因子，旧 dual-yaw、CARRIER/MOTION、SDK yaw/quaternion 和已被历史 heading 旋转的 SDK 水平速度 provider 不输入新主链。主体输入为原始 EpochBlock、IMU、直接足点和明确使用的 GNSS p/v。

PVT p/v 与 raw DD 来自相关 GNSS 来源，不能沿用合成“独立 stream”结论；SDK 足点也不是已认证独立于 IMU 的传感器。初版若使用未标定交叉项的工作模型，应明确登记并在全部臂一致应用，不能以来源名称不同宣称独立性。以上配置只避免 PVT 派生航向和原始载波方向被重复消费，不等于已经消除所有来源相关性。

本说明到此结束：真实接入、BY 开发结果及后续固定参数测试尚需另行实际执行和记录。
