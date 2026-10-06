# 外部载波基线接入合同

这是实验导航接口；`valid=1` 表示上游允许尝试该观测，不表示可信 FIX，也不提供错误固定概率。默认 `runtime_contract: legacy`、`baseline3d_source: dual_pvt` 保持旧运行行为和旧 scalar/baseline3d 配置。

## 配置与输入

新实验使用 `runtime_contract: research_experiment`，显式填写 stage/protocol/case/run/data_mode；运行角色为 `experimental_navigation_solver`。方法模块开关仍逐项核对，trace/输出回灌/逐例调参等禁止项仍检查。某个已启用模块零次更新允许作为真实实验结果，不伪造成功计数。新 scalar 对照指定 `dual_yaw_prediction_model: lateral_projection`，不借用旧阶段名称选择公式。

外部观测另指定：

```text
dual_antenna_measurement_model: baseline3d
baseline3d_source: external_carrier
external_carrier_baseline_path: <CSV>
baseline3d_body_vector_m: [0, -L, 0]
```

`L` 必须来自该平台几何；程序没有论文长度默认值。任意已知安装向量可通过三维 FRD 向量输入。传统 dual-PVT 模式继续使用 `baseline3d_path`、`baseline3d_length_m`、`baseline3d_k_b`，其原始协方差为 `k_b²(pAcc1²+pAcc2²) I`（没有除以 3）。

外部 CSV 头严格为：

```text
measurement_time,decision_available_time,b_ecef_x,b_ecef_y,b_ecef_z,cov_xx,cov_xy,cov_xz,cov_yx,cov_yy,cov_yz,cov_zx,cov_zy,cov_zz,valid
```

时间和导航 IMU/GNSS 使用同一秒制。每行时间严格递增，且当前版本要求 `measurement_time == decision_available_time`：上游只能提供该决策时刻的基线，不可把通过未来验证的整数回填到较早选择时刻。没有实现延迟状态/OOSM。向量单位米、完整对称正定协方差单位平方米；不从 pAcc 构造替代 R，不在 C++ 内加对角噪声或修复坏协方差。`valid=0` 可空置所有向量/协方差字段；只记录诊断，不引入 IMU 拆分、不更新滤波。

GNSS18 只保留原位置/接收机速度的显式可用位，外部模式不解析商业 yaw 数值/方差/有效位，也不把缺失 carrier 恢复成商业 yaw。载波时刻与 GNSS 时刻精确合并；独立 carrier 时刻以额外事件进入队列，不伪造位置、速度或 PVT FIX。

## 坐标与观测方程

载波向量定义为 `r_GNSS2 - r_GNSS1`，先处于 ECEF。若 GNSS2 位于 GNSS1 的机器人左侧，FLU 安装向量为 `(0,+L,0)`；FLU→FRD 的 `diag(1,-1,-1)` 给出 `(0,-L,0)`。改变接收机顺序必须同时改变机体系和观测向量符号，协方差不变。

`Earth::cne` 为 NED→ECEF。以当前滤波 BLH 的旋转 `C_en = C_neᵀ` 得到 `z_n=C_en b_e`、`R_n=C_en R_e C_enᵀ`，所有非对角项保留。预测 `h=C_bn b_body`，残差 `h-z_n`；KF-GINS 的左乘误差反馈约定给出 `H_phi=[h]×`，其他误差列为零。这里采用短基线局部导航框架近似，忽略位置误差引起的切平面旋转微小项。单条基线对绕自身轴的旋转不可观，不是独立完整三维姿态观测。

外部 R 是上游给定的工程观测模型。固定整数条件协方差不包括整数选错风险；候选选择、共同 GNSS 原始源和 RP/INS 相关性也不会因保存完整 R 自动消失。EKF 保留原 B3 的非 basic 3DOF NIS 阈值 11.34 和 source-aware 整体 R 缩放；这是后端观测门，不是 AR 完整性验收。

## 时间、重复源与诊断

新 research 实验三臂/四臂共同使用实际时间事件循环。在 IMU 区间内按时间顺序处理每个有效事件，按同一比例拆分原始 dtheta/dvel 和**测得 dt**，不使用旧 1 ms 对齐提前更新；每个原 IMU 末只写一条 NAV/STD，独立载波事件不增加输出时刻。无效 carrier-only 行与完全缺失观测导航/协方差逐值相同。

carrier-only 事件不再触发 RD/RP/HV/FGO。研究 RD/RP 只取不晚于更新时刻的、容差内最近源样本，每个时间戳最多尝试一次（被拒也算已尝试）；source-aware 的 readiness 上下文也只取过去样本，允许多个观测共享同一上下文。历史 legacy 模式仍按原规则。

`BASELINE3D_DIAGNOSTICS.csv` 为实际 B3 事件记录；外部模式新增 source、测量/可用时刻及完整 NED R。pAcc 两列为空，旧 `base_variance_m2` 仅对应 R_nn；完整 R 应读取新增九列。debug 模式的 `PORT_EXACT_EVENT_INTERVAL_TRACE.csv` 为每 IMU 区间聚合计数及真实输入首末事件时间，不冒充逐事件日志；原逐 GNSS 日志仅用于旧调度。

## 实现与检查

- `baseline3d.cpp`：完整协方差检验、ECEF/NED 模型。
- `gnss_file_loader.cpp`：新 CSV、精确事件合并与商业 yaw 关闭。
- `GIEngine::newImuProcessWithEvents`：因果事件消费、实测 dt 拆分、invalid 仅诊断。
- `GIEngine::applyBaseline3dUpdate`：实际 EKF 更新和完整 R。
- `PortConfigLoader` / `PortRuntime` / `FileSaver`：研究身份、模块合同、输入角色和真实计数。

在 Ubuntu 22.04 WSL 使用 `python3 -m pytest -q tests/paper_rebuild/test_external_carrier_fusion.py tests/paper_rebuild/test_t5bc_baseline3d.py`：39 项通过。覆盖 ECEF/NED 和接收机交换、完整协方差旋转、有限差分 Jacobian、同一 IMU 区间多事件、invalid/缺失逐值等价、合法测得 dt 与时标微差的尾段、RD/RP past-only/单次使用、商业 yaw 无关、新研究身份与科学禁止项，以及原 B3 回归。此检查不包含真实导航精度结论。
