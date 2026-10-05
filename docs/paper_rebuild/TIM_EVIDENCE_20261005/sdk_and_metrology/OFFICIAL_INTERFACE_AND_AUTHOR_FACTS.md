# 官方接口、作者新增事实与尚未完成的计量确认

日期：2026-10-05；起点仓库 6559d083。此块只阅读文档/源码与网页，不读取科学 raw/reference 载荷，不执行 provider、native、evaluator 或新绘图。原 V3 主结果及此前诊断版本不变。这里的官方公开版本不是采集时固件的替身。

## 1. 三层事实必须分开

|层级|本次可以记录的事实|不能由此推出|
|---|---|---|
|作者于2026-10-05确认|Fixposition 相机侧朝机器人前方；机身 IMU 使用狗的时钟，GNSS 使用 GNSS 时钟；用踢动造成 IMU 突变，再观察接收机位置/速度及机身 IMU 的启动变化定起点；观察的不是 Fixposition 融合轨迹；CAD 对应当时同一安装，后来的日期是补存/整理|精确安装旋转、杆臂、天线相位中心、每段选点、数值 offset/drift、输出延迟及其不确定度均尚未因此获证|
|已读文件的软件合同|项目 body parser 从 sport-state 外层 stamp.sec/nanosec 取时间；IMU builder 构造 sec+nanosec×10⁻⁹ 后减 base_time 加配置 offset；HV provider 按已冻结工程旋转处理 SDK velocity|外层 stamp 就是 IMU 芯片采样时刻；时间戳具有 GNSS/UTC 同一时基；单位、点位和旋转已实体校准|
|需要采集/配置/标定记录|实机 firmware/build、采集 topic/collector、timestamp 事件与时基、每序列对齐点及判断区间、POI/安装/相位中心量测、SDK 输出速度 frame/点、同步链和参考模式|未提供的量不能零填；不能把官方默认值写成实际采集值|

作者确认采用接收机 P/V 而非融合 trace，消除了这项陈述中的“以评价轨迹选起点”混淆；它不独立证明历史每次执行均完全按此操作，也不证明其他历史标定或方法选择对参考盲化。文件时间配键与物理同步仍是两件事。

## 2. Unitree SDK2：公开 C++ IDL 能确认什么

本次锁定 [unitree_sdk2@63096d0](https://github.com/unitreerobotics/unitree_sdk2/tree/63096d0ac0c5d2dec9d6e0c22cd5233410ca2f36)（提交日期2026-09-21）。另查截至2026-01-05T23:59:59Z公开可见的提交 f29ee9f234851e9e79f75102c0f9e83008d8fdd1：以下四文件 Git blob 完全相同。这只证明这两次公开仓库接口相同，不能证明实际 Go2 firmware、SDK 构建和采集客户端相同。

|接口|确切字段/类型（字段声明已读）|边界|
|---|---|---|
|[IMUState_](https://github.com/unitreerobotics/unitree_sdk2/blob/63096d0ac0c5d2dec9d6e0c22cd5233410ca2f36/include/unitree/idl/go2/IMUState_.hpp#L24)|quaternion float[4]；gyroscope、accelerometer、rpy 各 float[3]；temperature uint8|这个类没有 timestamp/frame_id/POI/covariance 字段；成员名不编码单位、四元数映射方向、内部滤波或传感器延迟|
|[SportModeState_](https://github.com/unitreerobotics/unitree_sdk2/blob/63096d0ac0c5d2dec9d6e0c22cd5233410ca2f36/include/unitree/idl/go2/SportModeState_.hpp#L31)|stamp TimeSpec；imu_state；position、velocity 各 float[3]；yaw_speed；foot_position_body、foot_speed_body 各 float[12]|velocity 不附 frame/测量点/协方差字段；不能因 foot 字段写有 body 就推定 velocity 同样为 body；它是报告状态，不是已取得纯腿部 FK 量测|
|[LowState_](https://github.com/unitreerobotics/unitree_sdk2/blob/63096d0ac0c5d2dec9d6e0c22cd5233410ca2f36/include/unitree/idl/go2/LowState_.hpp#L31)|tick uint32；sn/version 各 uint32[2]；imu_state 等|tick 名字和位宽不证明秒/ms单位、采样事件、rollover/reset规则或跨设备同步；本项目所读 body parser 使用 stamp，未用 tick 给原 IMU 改时间|
|[TimeSpec_](https://github.com/unitreerobotics/unitree_sdk2/blob/63096d0ac0c5d2dec9d6e0c22cd5233410ca2f36/include/unitree/idl/go2/TimeSpec_.hpp#L22)|sec int32；nanosec uint32|类型不证明 Unix/GPS/UTC/boot-time epoch 或 timestamp 在 acquire/estimate/publish 中哪一刻形成|

官方 [Go2 sport client example](https://github.com/unitreerobotics/unitree_sdk2/blob/63096d0ac0c5d2dec9d6e0c22cd5233410ca2f36/example/go2/go2_sport_client.cpp) 确认 rt/sportmodestate 的订阅类型及 rpy[2] 用作初始 yaw；它没有公开 velocity 内部估计方程、接触权重、滤波带宽或延迟。官方 ROS2 的 [TimeSpec.msg](https://github.com/unitreerobotics/unitree_ros2/blob/668d1ec5a05d1c38d3306bdca7d59f2ba3581a88/cyclonedds_ws/src/unitree/unitree_go/msg/TimeSpec.msg) 也将时间描述为相对某个 clock 的零点，未指定该 clock 与 GNSS 的映射；其中 nanosec 范围注释原文含 `10e9`，本块不把这个注释归一成实机时标保证。

项目 `go2_body_state_parser.py` 的 wxyz/rad/rad_per_sec/m_per_s2/FLU 是项目采用的解析合同，字段本身没有把这些单位打包传输。该文件还将 sport velocity 标为 `go2_odom_or_body_evidence_missing`（第262行）；与后续 HV provider 按 FLU 旋转的处理之间，实机 frame 证据仍需补齐。应称 robot-reported velocity aiding；不得称已独立校准的腿部运动学速度。

## 3. 官方 Go2 几何不能代替实机量测

锁定 [unitree_ros@5994d4fa](https://github.com/unitreerobotics/unitree_ros/tree/5994d4faef0a9cadd3287f8de0199a67eeb2a259)。同一提交的 [go2_description.urdf 735–739](https://github.com/unitreerobotics/unitree_ros/blob/5994d4faef0a9cadd3287f8de0199a67eeb2a259/robots/go2_description/urdf/go2_description.urdf#L735) 声明 base→imu 的 origin 为 [−0.02557,0,0.04232]、rpy=[0,0,0]；[xacro/robot.xacro 68–71](https://github.com/unitreerobotics/unitree_ros/blob/5994d4faef0a9cadd3287f8de0199a67eeb2a259/robots/go2_description/xacro/robot.xacro#L68) 则声明 trunk→imu_link 位于原点。它们是不同命名/建模表示，不能任选一个替换实际安装、SDK 速度点或观测杆臂。作者确认 CAD 同安装值得作为装置证据，但必须对接明确原点、轴、尺寸定义和尺寸不确定度；本块不从公开模型/照片拟合真实尺寸。

## 4. Fixposition 公开文档与本装置的区别

官方 [FP_A-TF](https://docs.fixposition.com/fd/fp_a-tf) 定义 VRTK 原点位于外壳 X 标记，轴为前/左/上；CAM 有其自身轴定义；POI 是可配置输出点，默认等于 VRTK。相机侧朝前不等于 CAM、VRTK、POI 或机器人 IMU 四个 frame 自动相同，也不提供旋转和平移的标定精度。

[FP_A-ODOMETRY](https://docs.fixposition.com/fd/fp_a-odometry) 公布 GPS week/TOW、ECEF位置、四元数、输出 frame 的速度，以及位置/姿态/速度各自协方差块和软件版本字段。该接口不包含方法与参考的交叉协方差，所列各块也不是所有变量间的完整 joint covariance。厂商输出 covariance 是报告模型，不能未经验证当作真实误差分布。[FP_A-ODOMSTATUS](https://docs.fixposition.com/fd/fp_a-odomstatus) 提供各输入融合状态，可用于核对实际 camera/IMU/GNSS 的参与；网页字段存在不证明旧采集保留了这些字段。

[官方 ROS driver 文档](https://docs.fixposition.com/fd/fixposition-ros-driver) 将 GNSS1/2 天线位置、融合 odometry、原始/补偿 IMU、输出 POI 分开；本次作者说用接收机 P/V 对齐，不能把它写成使用融合轨迹。具体当时消息版本、输出模式和 POI 配置需要采集记录，不从当前文档默认值回填。

[Fixposition PTP 指南](https://docs.fixposition.com/fd/enabling-precision-time-protocol-ptp) 与正式 integration-manual 的时间章节说明 NTP/PTP/PPS 是可用机制。支持某种协议不证明当时 Go2 参加同步，更不证明正文可填写厂商实验的同步精度。须有配置、链路、clock-status 与量测记录。

即使参考融合实际包含前向相机和内部 IMU，参考仍可与本方法共享 GNSS1/2 和改正/环境误差。新增传感器不是将参考改名为 independent truth 的依据。

## 5. 本块交付范围

`OFFICIAL_SOURCE_PINS.csv` 保存实际公开 commit、Git blob 与完整文件 SHA-256；完整 byte 读取/hash 不等于逐行语义读完生成序列化代码。`READ_COVERAGE_BLOCK01.csv` 逐文件标明真正阅读区间。网页为2026-10-05访问的活文档，不伪装有不可变 commit。`AUTHOR_FACTS_AND_OPEN_RECORDS.csv` 区分作者陈述、代码事实和待量测记录。

本块足以支撑诚实的接口与装置描述；还不足以完成 TIM 的实体预算、相关性辨识、时间同步或独立参考验收。下一块给出新时钟模型、输入预算与最小验证协议，不改变原 V3。
