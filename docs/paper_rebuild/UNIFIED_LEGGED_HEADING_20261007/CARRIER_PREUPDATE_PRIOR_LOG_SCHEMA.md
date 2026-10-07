# 载波当前更新前共同先验日志合同

起点 HEAD `57821fc`；本改动只扩展已有 `BASELINE3D_DIAGNOSTICS.csv`，不改变模型、门控、测量调度、反馈、reset、配置或参考访问。新字段用于判断已存在的方向域与当前共同先验的几何关系，不是新增观测或新的 posterior 模态概率。

## 截面与误差图表

在 `GIEngine::applyBaseline3dUpdate` 中，external carrier 建模成功后立即复制 nominal / dx / Cov，早于当前载波 innovation、hard-NIS、QA/SA 判定及 EKFUpdate。快照不执行额外反馈或 reset，因此后续拒绝的有效 carrier 同样保留先验。无效 carrier 仍保留原诊断行，新增 prior 数值为空。

`PRE_CURRENT_CARRIER_UPDATE` 只表示 **当前载波之前**，不是整个事件之前。正常 GNSS 顺序可能已经消费同事件 position，以及按配置顺序的 velocity；更早的足端、SDK、载波等也已通过共同状态进入这个条件先验。不得在读出时另叠 foot / SDK prior。此处未增加原本被 source arbitration 绕过的更新；被绕过的事件不会为了日志而执行载波建模。

当前图表标识为 `GI_LEFT_NED_PHI_POSITION_MINUS`：

- `C_bn` 把机体 FRD 向量映射到当前 nominal 位置的导航 NED。姿态扰动为 `C_true = Exp([δφ]×) C_nominal`，δφ 单位 rad、轴序 N/E/D；反馈左乘 `Exp(+dx_phi)`。
- 位置名义量是 BLH（lat/lon 为 rad，height 为 m）；位置误差 δp 是当前 nominal NED 的米量，`BLH_true ≈ BLH_nominal − DRi(BLH_nominal) δp`。位置反馈符号为减。
- `dx` 是该误差图表中的当前条件均值，`Cov` 是其协方差，不是 Euler roll/pitch/yaw 三角度协方差，也不是已经反馈后的零均值协方差。
- 记录的 3×3 块全部直接复制原 9 项，不对称化、不对角化、不截断特征值。`P_p_phi` 行为位置 N/E/D，列为姿态 N/E/D；反向块应取其转置。

## CSV 列合同

原 external 42 列保持次序和序列化方式；尾部新增 56 列，总计 98 列。非 external 输出的原 schema 不变。所有浮点量保持原 `setprecision(17)`，完整 IEEE754 时间身份另存十六进制位串。

| 新增列 | 数量 | 定义 |
|---|---:|---|
| `prior_available` | 1 | external 模型已建立、先验快照存在时为 1 |
| `prior_phase` | 1 | 有先验时为 `PRE_CURRENT_CARRIER_UPDATE`，否则空 |
| `baseline_event_sequence` | 1 | 现有 baseline 诊断行序号，从 1 开始，包含无效行；不是 IMU 序号 |
| `prior_event_identity` | 1 | `<source>:EVENT_TIME_BITS:<hex>`；本窗 source 为 `external_carrier` |
| `event_time_bits_hex` | 1 | 现有 `time` 的 double 位串，使用既有 `arcSourceTimeBits` |
| `prior_state_time` / `prior_state_time_bits_hex` | 2 | 快照时 `timestamp_` 的值及位串；不得用邻近 NAV 时间代替 |
| `prior_error_chart` | 1 | `GI_LEFT_NED_PHI_POSITION_MINUS`，无先验时为空 |
| `prior_nominal_cbn_00` … `prior_nominal_cbn_22` | 9 | 行优先 Cbn；索引顺序 00,01,02,10,11,12,20,21,22 |
| `prior_nominal_lat_rad`, `prior_nominal_lon_rad`, `prior_nominal_height_m` | 3 | 精确 nominal BLH |
| `prior_body_baseline_x_m`, `prior_body_baseline_y_m`, `prior_body_baseline_z_m` | 3 | 实际 external 模型使用的 `baseline3d_body_vector_m` |
| `prior_dx_phi_n_rad`, `prior_dx_phi_e_rad`, `prior_dx_phi_d_rad` | 3 | 原 dx 的姿态三项 |
| `prior_P_phi_phi_<ab>_rad2` | 9 | 原姿态协方差，ab 顺序 nn,ne,nd,en,ee,ed,dn,de,dd |
| `prior_dx_p_n_m`, `prior_dx_p_e_m`, `prior_dx_p_d_m` | 3 | 原 dx 的位置三项 |
| `prior_P_p_p_<ab>_m2` | 9 | 原位置协方差，同上行列顺序 |
| `prior_P_p_phi_<ab>_m_rad` | 9 | 位置—姿态交叉协方差，同上行列顺序 |

新增状态/矩阵字段仅在 `prior_available=1` 时输出。序号与 event 身份所有 external 诊断行均有。事件身份仍需与该次冻结 provider 文件哈希共同使用；它没有伪装成未保存的 raw observation ID。现有 `measurement_time`、`decision_available_time`、h、innovation、完整 R、accepted/reason 列继续保留。

额外位置块用于显式检查固定 nominal p 的读出近似或以后推导位置/姿态共同几何边界，未把固定位置的姿态边缘积分自动升级为联合概率认证；本次不需要每个 IMU 的完整状态矩阵。

## 实现、构建与核对范围

只改两个 C++ 文件：

- `cpp/legsa_v23_port_core/include/legsa_v23_port_core/baseline3d.hpp`：12 行诊断成员。
- `cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp`：既有 row 的序号、external 建模后只读 copy、原 writer 的尾列序列化。没有修改 h/H/R、NIS、权重、更新/传播/反馈或任何生产判断条件。

`git diff --check -- cpp` 通过，Release 编译通过。新 binary：
`/home/kaiwen/research/LegSA-GINS-SCRATCH/UNIFIED_LEGGED_HEADING_20261007/CARRIER_PRIOR_DIAGNOSTIC_BUILD/legsa_v23_port_core_demo`。

SHA256：`7ab65cd5d49286664c88658090df9c5529609c4dd588f0abc6834123a56b51cc`。

旧 `VECTOR_DIRECTION_SA_BUILD/legsa_v23_port_core_demo` 仍为 `317a66779dddd96c9f284e87dbcea3e874833d3a743953dd47b5a90582f44912`，未覆盖。构建命令：

```bash
cmake -S cpp -B <new_scratch_build> -DCMAKE_BUILD_TYPE=Release
cmake --build <new_scratch_build> -j 4
```

本实现任务 native / evaluator 为 0/0，未新增镜像实现的单测。根任务负责已批准的唯一 BY2O VECTOR 日志运行，以原五份 state / bias / std 文件全行字节身份验证没有数值变化；本说明不会以编译通过冒称该身份已通过。


根任务已完成唯一 native：`PARTIAL_DIRECTION_PRIOR_BY2O_01`，76548 状态时刻、285 个有效载波 prior；全部 prior_state_time 与精确事件时刻相同。五份 NAV/STD/IMU error 输出与旧 VECTOR 全文件字节相同，NUMERICAL_PARITY=PASS；online reference opens=0，evaluator=0。当前工作模型与输出状态历史均未改变。
