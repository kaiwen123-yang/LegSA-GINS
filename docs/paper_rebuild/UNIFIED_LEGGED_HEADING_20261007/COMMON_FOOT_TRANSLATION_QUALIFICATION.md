# 两足共同位移的资格与差分方向下一步

2026-10-07。本轮为测量层只读审查：不增加 native/evaluator，不修改 XYZ、SDK 模型、噪声、接触规则或源输入。常量 SDK discrepancy 的实现与失败结果已分别保存于 `54200fd` / `9752fd6`；本文件不把其失败改写为已识别真实滑移。

## 1. 当前证据能判定什么

- 同一冻结足对 provider 有 481 个 END，主 163 s 空窗有 242 个 END；现有源内读出没有更换足、修改时间映射或接触资格。
- 空窗原 242 个约 100 ms 区间，foot 与 SDK velocity 的共同前向差为 −7.260 mm，即区间覆盖上的 −0.07101 m/s。完整连续支撑弧仍有约 5.96% 的前向差；只改变固定机会／取样阶段不足以解释它。
- 同区间 foot 与 SDK position 位移更接近（前向均值差 −0.406 mm），SDK velocity 积分与 SDK position 相差 +7.234 mm。但三者都是 SDK 输出，position 不能成为独立真值；此关系不能认证 foot 无滑移，也不能授权 velocity 缩放。
- 记录 foot_speed 与足点导数全窗符号、尺度总体一致，但 stance / swing 的前向差反向。它不是严格的 `−SDK velocity−omega×r` 复制恒等式，也不能据此认证独立关节运动学来源。
- 现有 XYZ 相比 XY 的垂向导航作用是真实已观测到的算法效应；这一评价结果本身不能证明“共同 Z 物理正确、共同 XY 物理错误”。共同水平失配无法仅凭现有源差、足力或导航误差定位到某一传感器。

证据：`NMB1_SUPPORT_SDK_CONSISTENCY.md`、`NMB1_FULL_SUPPORT_ARC_CONSISTENCY.md`、`NMB1_FOOT_SPEED_SOURCE_DIAGNOSIS.md`、`NMB1_SOURCE_POINT_TIME_AUDIT.md`。本文件使用已封存的摘要，不重新读参考或求解。

## 2. 两足观测的条件信息

在共同 body0 坐标中，令 `D=R0^T R1`，零杆臂为当前工作假设。两足原始位姿约束为

```
e_i = R0^T(p1−p0) + D r_i1 − r_i0
e_j = R0^T(p1−p0) + D r_j1 − r_j0
c   = (e_i+e_j)/2
d   = e_i−e_j = D(r_i1−r_j1) − (r_i0−r_j0).
```

`c` 含直接共同平移信息；`d` 消掉共同平移、共同杆臂和两足完全相同的接触位移。支撑 token 只提供因果生命周期与足身份，不保证两足没有相对滑移或 SDK 足点没有相对误差。

对非零足对基线 `b1=r_i1−r_j1`，在 `D'=Exp([delta_theta]x)D` 约定下，差分方向 Jacobian 为 `−[D b1]x`，秩为 2，弱轴为 `D b1`。单条基线不能提供完整三维相对旋转、绝对航向或平移。NMB 对角足对近水平，完整 XYZ 差分仍含 yaw 与一个倾斜组合；不能因为足高接近就丢掉 `d_z`。该结论以足对方向在区间内确实保持为条件，不是无滑移认证。

当前独立、各向同性端点工作模型为四个点各 `sigma_p=0.01 m`：`Cov(e_i)=Cov(e_j)=2 sigma_p^2 I`，`Cov(c)=sigma_p^2 I`，`Cov(d)=4 sigma_p^2 I`，`Cov(c,d)=0`。最后一个等式只在此工作独立模型成立；完整协方差或不等端点噪声下须保留交叉块。可逆的共同／差分变换本身不丢信息，也不是删除某轴的依据。

## 3. 按弧共同接触位移 nuisance 的限制

若每弧引入完全自由的三维共同接触位移 `s`，`e=[e_i;e_j]−B s`、`B=[I;I]`，其无信息先验消元精度为

```
W_eff = W − W B (B^T W B)^−1 B^T W.
```

它精确消掉全部共同 XYZ。所有直接 `p0/p1` 平移列落在被消掉的空间，留下两足差分相对方向；原共同 Z 平移约束也一并消失。差分姿态经联合状态仍可能间接影响垂向，但不能称为保留了原 XYZ 的垂向测量。

若只设置二维 nuisance，则必须指定一个法向 `n` 并硬设 `n^T s=0`。body0 XY 不是 NED 水平；重力竖直也不等于已知接触平面法向或无穿透证明。两接触点只定义一条线，标量足力未标定，不能推出摩擦锥或滑移边界。不能因 Up 结果好而悄悄固定 normal nuisance 为零。

给 `s` 有限先验等价于增加 `B Sigma_s B^T` 的共同相关噪声。没有独立物理依据时，这只是新的未标定模型自由度。一个所有足共享的位移也假设了相同接触移动或相同 SDK 误差；差异滑移不受它解释。当前记录不足以决定 nuisance 维数、法向或先验，因此本轮不实施它、不扫描噪声。

正常 RETIRE 仍只结束未来作用，不否定历史；两足差分长度／方向矛盾可以成为特定依赖的证伪证据，但 foot−SDK 共同差不能直接标成滑移 REVOKE，更不能撤销独立载波信息。

## 4. 已有字段与支撑几何的上限

现有完整缓存：

`<SCRATCH>/NMB1_SDK_INTERNAL_FRAME_01/NMB1_FULL_SOURCE_MOTION.npz`

字段为 `native_ns, times, source_rows, gyro_frd, velocity_frd, rpy_flu, position_sdk, foot_position_body_frd, foot_speed_body_frd, foot_force, metadata`。原始源 `/mnt/g/LegSA-GINS-project/data/raw/XB_PG/2026-01-05/高层数据/nmb1.txt` 的已读文件头为 `ros2 topic echo /sportmodestate`；顶层包含 `stamp, error_code, imu_state, mode, progress, gait_type, foot_raise_height, position, body_height, velocity, yaw_speed, range_obstacle, foot_force, foot_position_body, foot_speed_body`，没有原关节 `q/dq` 或关节采样时刻。

2026-01-05 原目录的六个子目录为 `fixpositon数据 / 双天线RTK数据 / 数据审计 / 高层数据 / 标准轨迹 / 足部惯导数据`。仅盘点文件名，排除 `.venv/__pycache__/.git` 后共 322 个文件，`lowstate/low_state/encoder/motor/joint/rosbag/关节/底层` 文件名命中 0；高层目录只有 nmb1–4、xb1–4 的 txt/xlsx、nmb1.7z、处理脚本和已有导航派生文件。本次没有解压全部归档或重扫原始内容，目录名称本身不是任意压缩包内容的认证。更直接的既有事实是 `../TRUSTED_HEADING_CONTINUATION_20261007/ANKLE_INS_EVIDENCE_ASSESSMENT.md:11,15` 已记录用户确认“没有采集底层日志”。因此现有输入不能重建独立 encoder FK；不再寻找不存在的旧 q/dq，不引入已被用户排除的足部 INS 或新采低层支线。

从已保存 `NMB1_FOOT_INTERNAL_KINEMATICS_01/SUPPORT_EPISODES.csv` 的冻结 token 寿命，与完整缓存精确 `native_ns` 取交集：每个固定三 token 最大交集从首合格源点到失效前最后合格源点，单点零时长仍计数，不改原成熟／迟滞规则。

| 连续共同合格支撑 | 全 native 窗 | 主 163 s 空窗 |
|---|---:|---:|
| 至少三足的源行数 | 197 | 66 |
| 三 token 共同弧数（所有三足组合） | 155 | 52 |
| 其中正时长弧 | 50 | 17 |
| 最长三足弧 | 10.491 ms | 7.953 ms |
| 三足弧时长之和（可重叠，非独立覆盖） | 246.577 ms | 83.954 ms |
| 至少 100 ms 三足弧 | 0 | 0 |
| 四 token 共同弧／正时长弧 | 4 / 1 | 1 / 1 |
| 最长四足弧 | 7.953 ms | 7.953 ms |

这些瞬时多足点不能给现有约 100 ms 因子提供持续三接触平面。即使三个点成平面，其来源仍是同一高层 SDK，也不能自动证明该平面是固定地面。此统计用于否定“已有持续三足法向资格”，不用于新增拒收门。

`<SCRATCH>` 指 `/home/kaiwen/research/LegSA-GINS-SCRATCH/UNIFIED_LEGGED_HEADING_20261007`。原两足端点在 `SUPPORT_POSE_PROVIDER_NMB1_01/SUPPORT_POSE_EVENTS.csv`，现有模型实现见 `cpp/legsa_v23_port_core/src/factors/pose_clone.cpp:128` 与 `cpp/legsa_v23_port_core/src/kf_gins/gi_engine_support_pose.cpp`。

## 5. 下一唯一动作：差分方向的数学／源内可辨识性读出

本轮仅冻结设计，不执行下一读出，也不把 XYZ 换成差分再跑 NAV。问题是：**在原 481 / gap 242 个同 token 区间，足对差分究竟提供哪些相对方向，这些方向是否与短侧向天线基线的弱方向互补？**

1. 保持足序、原端点、−1.1 s 映射、历史 IMU 安装工作假设及现有噪声数值。使用 `d=D b1−b0` 的原始三维似然；不先用 gyro 旋转后把它当一条独立足姿态测量反馈。在线定义中的 D 来自共同两时刻状态；源内检查可在同区间因果 IMU 增量处线性化，但须明确这是 gyro 条件读出。
2. 全端点噪声顺序取 `[r_i0,r_j0,r_i1,r_j1]`，映射 `A=[−I,I,D,−D]`，`Sigma_d=A Sigma_12 A^T`。保留一般交叉块表达，并单列当前 `sigma_p=0.01 m`、独立端点只是未标定工作假设。重用端点或重叠弧的互协方差不能消失。
3. 将基线长度失配与两维切向方向分开报告：归一化向量需用 `(I−u u^T)/||b||` 传播端点噪声，选择正交切向基而不制造沿基线的第三个旋转信息。原长度失配和原资格结果全量保留；切向／径向噪声若相关须保留联合似然，不能先条件接受又将同一径向证据独立乘第二次。无 NAV/reference 选择轴或门限。
4. 列出相对旋转方向信息矩阵的秩、特征值和三维弱轴；与实际天线短侧向基线的物理旋转弱轴在同一 frame 比较。几何夹角只能说明潜在互补。载波部分候选域可能具有不同于单一物理基线的弱方向／多模态，必须使用其现有方向似然而非把它简化为一个任意 yaw 方差。
5. 把相对 `R0→R1` 与载波对绝对／历元方向的信息映射到同一两时刻变量，并保留全局旋转规范自由度。足对差分单独没有绝对 yaw；若不消去未锚定的 R0 就直接叠加两个 3×3 信息矩阵，会夸大互补。应分别报告“R0 无绝对锚”“已有独立载波锚”两个条件，不用参考姿态充当锚。
6. 若 IMU 增量进入条件似然，传播其噪声及与共同状态、已有 gyro 候选传播的依赖，不能再把 shared gyro 当独立证据计入。高层足点本身是否用过同一 IMU 未被证实，未知交叉来源必须标注。为每条实际足差分建立所消费 token／端点依赖；长度或方向被证伪只能撤销受其影响的候选，纯 gyro 与独立 carrier 不虚构足依赖。

可反驳的终点是：若保留这些规范与噪声后，足差分在实际载波弱方向没有增量秩／足够信息，或源内残差已否定其条件模型，则不进入融合；即使显示互补，也只得到下一步统一状态接入的物理候选，不认证无滑移、不宣称导航收益。共同 XYZ 的既有结果与失败完整保留，本阶段没有按评价结果删除共同水平分量。
