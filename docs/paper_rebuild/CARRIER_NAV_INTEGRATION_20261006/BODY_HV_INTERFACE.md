# 因果 body-FRD 二维速度接口

本接口恢复完整模块实验中的 HV 信息，但不把 SDK 速度假设升级为已校准足式里程计。默认 `go2_horizontal_velocity_frame: ned` 完全保留旧 NED 路径；只有显式 `body_frd` 才启用新观测与独立时钟。新模式要求 `runtime_contract: research_experiment`。

## 配置、数据和坐标边界

```text
enable_go2_horizontal_velocity_prior: true
go2_horizontal_velocity_frame: body_frd
go2_body_velocity_prior_path: <BODY_CSV>
go2_horizontal_velocity_prior_mode: horizontal_2d
go2_horizontal_velocity_prior_vertical_disabled: true
go2_body_velocity_update_period_s: 0.2
```

保持方法 catalog 的 HV 开关；完整 AB1111 的 loader 会在内部启用对应 velocity prior 模块。两个历史 std-scale 配置键若同时存在，后读取的 horizontal 别名覆盖通用键；本轮 runner 将两者明确设为 1，CSV 标准差即实际基础权重。

专用 CSV，禁止把 body 值藏在旧 vn/ve 列中：

```text
time,v_forward_mps,v_right_mps,std_forward_mps,std_right_mps,valid,source_status
```

时间严格递增、数值有限、有效行两项标准差严格正且 `source_status=active`。无效行可空置速度和标准差。表为空或全部无效是允许的无更新结果。原始 SDK 解析、坐标证据与 provider 责任在接口上游；C++ 不读取 SDK 姿态，不用 GNSS yaw 旋转观测，不内置旧标度 `1/0.962142` 或旧 0.132838 m/s 标准差。

官方示例的 odometry-frame 描述与本批日志的内部表现存在冲突，不能将 raw SDK velocity 天然视为 body。此次上游使用的证据是 [HV_FRAME_AUDIT.md 第2节](../HV_FRAME_AUDIT.md)：仅 body 日志内，BY2 56,624 个运动样本 raw velocity 对 position 差分中位夹角 99.124518°，经 SDK rpy 旋转后 1.104701°；BY2H/BY2O 有同方向证据。这一子检验不使用 PVT/A1，支持**本批记录**的体系表达，不能推广到全部 SDK 版本，也不是独立精度证明。报告其他节的 PVT/A1 残差和标度不作为此新接口参数。

输入被声明为导航 IMU 点处的 FRD 前向/右向速度；零点位差与机体系轴对齐仍是物理假设。没有经过标定的 SDK 点到 IMU 杆臂时，不凭空添加角速修正。若后续得到非零杆臂，应使用 `Cnb v_I + omega_b × lever_I_to_sensor` 并补相应 gyro-bias/scale 项；目前接口不支持这一扩展。

## 观测及误差模型

令 `S` 选择 body x/y 两行，`Cbn` 为滤波 body→NED 姿态，`v_n` 为滤波 IMU 点速度：

```text
h = S Cbn^T v_n
residual = h - z_body_xy
H_v = S Cbn^T
H_phi = -S Cbn^T [v_n]x
R = diag(sigma_forward^2, sigma_right^2) * configured_scale^2
```

符号对应现有反馈 `v <- v-dv`、`Cbn <- Exp(phi) Cbn`。有限差分检查六个 velocity/attitude 列；其余列为零。只增加两项 body 观测，无 body-z 测量。倾斜姿态和实际 KF 交叉协方差可以改变 NED Down 速度/位置，不能把 `vertical_disabled=true` 解读成强行冻结垂向状态。

共同旋转导航 yaw 和水平速度不改变 `Cnb v_n`；静止时姿态 Jacobian 为零，因此这一观测不凭空提供绝对 yaw。SDK 内部估计与导航 IMU、RP 的相关性及速度时序相关性仍未校准。接触滑移、SDK 点位和标度误差未由数学 Jacobian 检查解决。

## 时序、拒绝与计数

定时器锚定 `starttime + n*period`，在达到该时刻的 IMU 处理末执行。它不依赖 GNSS 是否有记录；GNSS 事件不再重复触发 body-HV。只选 `sample_time <= state_time`、年龄不超过配置容差的最近未消费样本，不插值、不外推。被判无效或被 source-aware 拒绝的样本也只尝试一次；最新样本无效时不回退到较早有效样本。跳过多个 tick 时仅检查一个当前的新鲜样本，不补播过期测量。

`BODY_VELOCITY_EVENTS.csv` 记录每个实际 timer 检查的 state_time、source_time、age、有效/接受位和拒绝原因。原 source-aware 模块继续使用正常 availability 状态 `available`，坐标身份单独记录，避免非标准状态词使所有观测被无条件拒绝。模块更新计数仍是 `go2_horizontal_velocity_update_count`，新增 manifest 明示 body frame、forward/right 两轴、无 z 观测以及允许状态交叉修正。

## 验证和交付

新增 `body_velocity_model.hpp/.cpp`、专用 loader 和 timer；默认 NED 路径保持。新 binary 位于独立 `BUILD_BODY_HV`，未覆盖第一版外部载波接口 binary。

WSL 内新增 15 项 C++ 检查通过，另有外部载波/旧 B3 39 项回归通过。覆盖有限差分、旋转不变性和静止 yaw 不可观、仅二维误差模型、无 GNSS 独立更新、未来/陈旧/重复/invalid 源、禁用逐值恒等、严格 frame/参数/CSV 门，以及启用 source-aware 后有效 body 观测确实被接受。一次新增测试函数与 C++ namespace 同名导致测试 harness 编译失败，改名后 15 项通过；算法库本身编译正常，没有科学运行或结果替换。
