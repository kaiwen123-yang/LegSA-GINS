# HX-02D Hartley 相对位姿只读诊断

本任务未运行任何原生解算，未修改方法本体、HX-02 输出或既有合约。最可能原因是生产移植／配置中的接触更新及零偏反馈路线（H3）；具体公式或代码缺陷不能判定。以下结论仅针对已保存的四个运行。

起点按用户裁定为 `e612eeb0ad37bf150a4076eb636424fe85f1d222`。HX02 docs 七个已有同名报告文件与源目录完全一致，主表 SHA256 为 `7475d7ef9780cdc9b2d82943dc786d58732076b9bad819f945f5010346190fba`，**无需补提交**。出处：00_CONTROL/REPORT_COPY_CHECK.json:pairs,table_sha256；历史起点阻断和裁定见 PREREQUISITE_CHECK.md。

## 数据与计算口径

- B 主表在各自 HX-02 评分窗口内取原生共同时间戳：BY2 为 [66,340] s，BY2O 为 [3186,3563] s；各支另有全原生窗口结果。出处：B_TABLES.json:sources.window、branches.<BRANCH>.full_native。
- C 沿用 HX-02 闭区间 10 Hz 网格、SO(3) 插值、参考插值和天线中点杆臂。C1 的 t=0 是评分窗口起点。位置误差为估计减参考；按 N/E/U 报告。yaw 为 NED 估计减参考，表内同时保留 wrap 到 [−180,180) 与连续展开两列。出处：C_TABLES.json:time_zero、branches.<BRANCH>.C1；计算代码 hx02d_reference_evaluation.py:evaluate,score。
- B2 以机体系 FLU／向上世界的正向 yaw 增量比较，因而其偏离速率的符号与 C 的 NED yaw 误差不同；展开后比较，不把多圈偏离折回。原始 z 轴陀螺积分不扣零偏，使用前一采样值的区间保持规则。另报安装角修正后的 z 积分和保存状态分解。
- B3 接触占空比主报按实际 dt 加权；JSON 另含逐样本比例。接触段时长只对完整段取中位数，窗口端点截断段另计。足力单位沿用原日志数值，不凭空改称牛顿。低／高足力群是代理，不能充当独立接触真值。
- B4 使用每个有效接触足 `v_b=−(ω×p+ṗ)` 并取多足平均；ω 为缓存已安装修正的角速度，p 为 foot_position_body，主 ṗ 为 foot_speed_body。另报非均匀时间轴二阶差分敏感性。状态速度以 Rᵀ 转回机体再比较。方向只在两种速度模长均大于 0.05 m/s 时定义；JSON 给出分母。积分是梯形积分，无接触区间不累加位移，并明确记录缺测，不宣称完整可观测。路程统一在 10 Hz 轨迹上计算，参考分母直接取旧 HX-02 数值。
- 漂移沿用 HX-02 的 OLS 斜率定义：水平误差范数对累计参考水平路程的带截距斜率乘 100。它不是终点百分比；C4 同时报告终点误差，避免闭环路程与负斜率造成误读。
- 数据定位：下文 B(s) 指 `EXECUTION_V2/B_REFERENCE_FREE/<s>/OUTPUT/B_TABLES.json`，C(s) 指 `EXECUTION_V2/C_REFERENCE/<s>/OUTPUT/C_TABLES.json`，D 指 `EXECUTION_V2/B_SAVED_STATE_READOUT/B2_STATE_DECOMPOSITION.json`。每张表标明对应字段；未四舍五入原值在 DIAGNOSTIC_TABLES.json。B 的来源及 SHA256 在 B(s):sources 和对应缓存清单，逐历元数组及原日志记录起始行在 B_ARRAYS.npz:source_start_line。
- 历史路径 H 指 `<CLEAN4>/07_LSE01_HARTLEY_CONTACT_INEKF`。原生率 NPZ 与初次失败数组保留在 G: 的 HX02D 阶段目录；仓库 docs 保留报告、JSON 表、抽样序列和全部 strace 审计。审计中的 scratch 绝对路径是执行时路径，归档时相对目录结构保持不变。

## A1 历史验证

| 步骤 | 验证对象与范围 | 原记录结论与出处 |
|---|---|---|
| H0–H2 | 论文、官方实现、BY2 输入、足序、安装角、接触和 FK 代理合约；尚未运行 BY2 滤波 | `PASS_LSE01_H0_H2_HARTLEY_SOURCE_METHOD_AND_BY2_CONTRACT_READY`；H/11_REPORT/LSE01_H0_H2_STATUS.json:terminal_status,filter_run_count,reference_open_count |
| H3–H4 | 公式与数学算例、官方数据回归；不是 BY2 参考轨迹精度验收 | `PASS_LSE01_H3_H4_FULL_IJRR_BACKEND_VALIDATED`；H/11_REPORT/LSE01_H3_H4_STATUS.json:terminal_status,official_regression_pass,real_BY2_filter_run_count,reference_open_count |
| H5 | BY2 原生运行、状态及协方差门、输入执行计数 | `PASS_LSE01_H5_BY2_NATIVE_RUN_COMPLETE`；H/11_REPORT/LSE01_H5_STATUS.json:terminal_status,reference_open_count,trace_open_count；参考打开为 0 |
| H6 | 原规范变换集合的一致性 | `BLOCKED_LSE01_H6_GAUGE_EQUIVARIANCE_FAILURE`；H/11_REPORT/LSE01_H6_STATUS.json:terminal_status |
| H6R | 完整精度接触点规范等价性、可观性、按接触拓扑分组的 NIS | `PASS_LSE01_H6R_REAL_DATA_GAUGE_AND_OBSERVABILITY_CONFIRMED`；H/11_REPORT/LSE01_H6R_STATUS.json:terminal_status |
| H7/H7R1/H7R2 | 计划对参考进行相对位姿评估；参考点和姿态框架门未闭合 | 三者均 `BLOCKED_LSE01_H7_REFERENCE_POINT_OR_FRAME_IDENTITY_UNRESOLVED`；H/11_REPORT/LSE01_FINAL_STATUS.json、LSE01_H7R1_FINAL_STATUS.json、LSE01_H7R2_FINAL_STATUS.json:terminal_status；参考误差字段为 null，relative_pose_metrics_complete=false |
| H7C | 参考来源链身份核对 | `BLOCKED_LSE01_H7C_REFERENCE_LINEAGE_CONTRADICTED`；H/11_REPORT/LSE01_H7C_FINAL_STATUS.json:terminal_status,metric_files_created=0；相对误差未执行；历史 trace_open_count=6 不属于本次调用 |

官方回归的数据为官方仓库 `src/data/imu_kinematic_measurements.txt`；定位代码
`src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h3_h4.py:546–570`。
官方固定提交为 `ef16e8a1df72f9272111a488880e3fe9d161f59f`；数据 SHA256
`224e03c83062fb937bfe529aa3858a04e07ed3143f92f8e0868bacbeae08491b`，出处
H/11_REPORT/LSE01_H3_H4_STATUS.json:official_execution.official_commit,official_execution.official_hashes.dataset。
回归共 59,976 条数据，传播 19,992 次、校正 19,780 次，接触增加/移除 34/33 次；
出处 H/07_SYNTHETIC_VALIDATION/OFFICIAL_CPP_REGRESSION.csv:metric=rows,propagation_calls,correction_calls,additions,removals。

| 官方回归量 | 最大差 | 容差 | 通过 | CSV 的 metric 字段 |
|---|---:|---:|---|---|
| 旋转 Frobenius | 1.4909296560104722e-10 | 5e-8 | True | max_rotation_fro_difference |
| 速度范数 | 2.9598027331364584e-10 | 5e-8 | True | max_velocity_norm_difference |
| 位置范数 | 1.468634572112833e-10 | 5e-8 | True | max_position_norm_difference |
| 陀螺偏差范数 | 2.558559636893718e-10 | 5e-8 | True | max_gyro_bias_norm_difference |
| 加速度偏差范数 | 5.301841660857872e-10 | 5e-8 | True | max_accelerometer_bias_norm_difference |
| 接触点范数 | 1.0156807278028371e-10 | 5e-8 | True | max_contact_norm_difference |
| 协方差相对 Frobenius | 8.82418920330675e-11 | 2e-7 | True | max_covariance_relative_frobenius_difference |
| 协方差最大绝差 | 4.799354802464961e-10 | 2e-8 | True | max_covariance_abs_difference |
| 舍入 stdout 字段 | 4.927314737113164e-6 | 5e-6 | True | official_rounded_stdout_fields |

本表逐项来源为 H/07_SYNTHETIC_VALIDATION/OFFICIAL_CPP_REGRESSION.csv 的 metric 对应行，
列 `absolute_difference,tolerance,pass`；完整原值收录在 PREREQUISITE_CHECK.json:official_regression.rows。

H6R 保持原 0.0005 m 容差，完整精度接触点最大差范围为
3.9206810879312983e-8 至 1.8977692824628012e-7 m；复用了 WIN000–WIN004，
理想无偏模型不可观维数为 4（平移三维加重力轴旋转一维）。
出处 H/11_REPORT/LSE01_H6R_FULL_PRECISION_RECOVERY_REPORT.md:5–21。
这是规范等价性与结构验证；该报告明确低 NIS 不代表精度（同文件:23–25）。

生产与官方回归后端有明确区别：
`HARTLEY_IJRR2020_REPORTED_BACKEND` 使用 Eq.50 零阶保持精确均值、Eq.58/60 解析转移、Eq.61 近似过程协方差；
`OFFICIAL_CPP_EARLY_REGRESSION` 使用固定旋转的速度/位置近似、`Phi=I+A*dt` 与官方近似协方差。
出处 `docs/paper_rebuild/horizontal_literature/hartley/stage_payload/06_IMPLEMENTATION/HARTLEY_BACKEND_IDENTITY_REGISTRY.yaml:8–37`。

一句话结论：HX-02 之前，此移植通过了数学回归及结构验证，未完成真实 BY2 对参考轨迹的精度验证。
没有可原样抄录的 H7/H7C 参考误差数值；其计划评估器身份为 `evaluate_nav_trace_kfgins_v2.py`，
但参考评估点未闭合，不能把计划评估器称为已执行的精度验收。
出处 `configs/paper_rebuild/horizontal_literature/hartley/stage_payload/04_METHOD_CONTRACTS/H7_EVALUATION_CONTRACT.yaml:54–89`。

## A2 坐标系链的源码核对

- 状态 `R_WB` 的合约原文为 `ROTATION_FROM_BODY_OR_IMU_FRAME_TO_PAPER_WORLD_FRAME`，主动向量规则为
  `vector_W_equals_R_WB_times_vector_B`；速度和位置是机体/IMU 原点在世界系中的表示。
  原文见 HARTLEY_STATE_AND_FRAME_CONTRACT.yaml:5–24（上述 configs 合约目录）。
- Hartley 世界 Z 向上，重力为 `[0,0,-9.81] m/s²`；同合约:28–39。
  IMU 先做绕 X 的 −1° 安装修正，得到 FLU；足点已经在机体 FLU，不做该安装修正；同合约:63–76。
- H7 合约原文为 `hartley_attitude: R_WB_ACTIVE_BODY_TO_WORLD`、`hartley_body_frame: GO2_BODY_FLU`；
  计划的世界到 NED 形状报告旋转为 `diag(1,-1,-1)`，不赋予绝对北向；H7_EVALUATION_CONTRACT.yaml:65–77。
- `run_h5.cpp` 直接按行输出 `r00…r22`、`vx,vy,vz`、`px,py,pz`，并未先转成 FRD/NED；
  出处 `src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/tools/run_h5.cpp:409,462–467`。
- HX-02 相对位姿评估器直接读取该旋转矩阵与世界位置；`hx02_relative_pose_evaluation.py:116–127`。
  该路径不是“先将 NAV 转成 FRD/NED 再评估”。它把 FRD 杆臂
  `[0.03,0.03-b_med/2,-0.30]` 用 `diag(1,-1,-1)` 转到 FLU，成为
  `[0.03,-0.03+b_med/2,+0.30]`，然后取 `p_mid=p+R*l_FLU`；同文件:48,67–69,198–204。
- 对每一支分别在窗口开始后的 10 s 上估计绕 Z 的角度与三维平移；同文件:267–289。
  对齐后的世界系是局部 ENU；水平向量按 E/N 存储，垂直分量为 U；同文件:299–305,204–207,221–224。
- 估计 ENU yaw 为 `atan2(R[1,0],R[0,0])`，正方向绕 +Z；同文件:160–161。
  参考 NED yaw 的合约为 `wrap360(90-yaw_ENU)`；H7_EVALUATION_CONTRACT.yaml:62。
  HX-02 残差明确为 `wrap180((90-yaw_est_ENU)-(90-yaw_ref_ENU))`，即 NED 估计减参考；
  hx02_relative_pose_evaluation.py:205–207。这一最终减法两边使用相同转换，没有从此式直接看到单边符号翻转。

待 B/C 证据解决的疑点：实际姿态是否符合合约；IMU 安装修正与高层 rpy 的比较应先明确二者物理框架；
Go2 FK 代理与接触更新是否造成不自洽；历史参考评估点/框架阻断如何限制本次解释。
不能仅依据源码链条排除 H1，也不能仅依据规范验证支持 H3 正确。


等价的显式报告变换为 `S_ENU_to_NED=[[0,1,0],[1,0,0],[0,0,-1]]`、`F_FLU_to_FRD=diag(1,-1,-1)`，
`R_NED_FRD=S_ENU_to_NED * R_ENU_FLU * F_FLU_to_FRD`，`p_NED=S_ENU_to_NED*p_ENU`。
两矩阵行列式均为 +1；这给出 `yaw_NED=wrap360(90-yaw_ENU)`，无需把 NAV 旋转矩阵转置。
此处是 A2 源码公式的代数展开，不是新增数据拟合；HX-02 实际实现仍在 ENU 中计算位置误差，只将 yaw 残差转为 NED。

H6R 的含偏置真实轨迹模型中，四接触的 rank/nullity 为 23/4，两接触为 17/4；在 0.1、1、10 倍秩阈值下稳定。
出处：H/10_OBSERVABILITY_R1/01_IDEAL_BIAS_FREE/OBSERVABILITY_NULLSPACE_SUMMARY_R1.json:bias_augmented[*].contact_count,raw_rank,raw_nullity；
同目录 OBSERVABILITY_RANK_SENSITIVITY_R1.csv:model=BIAS_AUGMENTED_REAL_TRAJECTORY 的 tolerance_multiplier,rank,nullity。
这确认已知规范自由度，不能证明相对运动估计精度。H0–H2、H3–H4 的原记录采用联合终端，表中按原记录分组，不虚构逐编号的单独验收。

## B1 姿态约定

原始高层 rpy 比较；均值、RMS 和最大绝差单位均为度。来源：B(s):branches.<支>.evaluation_window.B1_raw_rpy.hypotheses.identity_roll+1_pitch+1。

| 运行 | roll 均值 | pitch 均值 | roll RMS | pitch RMS | roll 最大绝差 | pitch 最大绝差 | 最接近假设 |
|---|---|---|---|---|---|---|---|
| BY2 S | -0.430 | -4.550 | 1.673 | 4.801 | 5.156 | 7.253 | 原轴序、原符号 |
| BY2 LIT | 0.561 | 0.002 | 0.765 | 0.468 | 2.211 | 1.438 | 原轴序、原符号 |
| BY2O S | -2.790 | -0.498 | 3.127 | 1.516 | 6.405 | 4.058 | 原轴序、原符号 |
| BY2O LIT | 0.442 | -0.582 | 0.692 | 0.788 | 5.823 | 4.012 | 原轴序、原符号 |

为完整覆盖互换、单轴取反和双轴取反，列出全部八种有符号排列的联合 RMS。变换作用于 Go2 对照 rpy，不修改 NAV。来源：同上 hypotheses.<假设>.joint_rms_deg。每个假设的两轴均值/RMS/最大值均在 JSON。

| 假设 | BY2 S | BY2 LIT | BY2O S | BY2O LIT |
|---|---|---|---|---|
| identity_roll+1_pitch+1 | 3.595 | 0.634 | 2.457 | 0.741 |
| identity_roll+1_pitch-1 | 3.750 | 1.306 | 2.702 | 1.238 |
| identity_roll-1_pitch+1 | 4.307 | 2.581 | 2.517 | 2.424 |
| identity_roll-1_pitch-1 | 4.437 | 2.822 | 2.756 | 2.619 |
| swap_roll+1_pitch+1 | 4.385 | 2.022 | 2.611 | 2.014 |
| swap_roll+1_pitch-1 | 3.677 | 2.040 | 2.609 | 1.810 |
| swap_roll-1_pitch+1 | 4.370 | 2.050 | 2.613 | 2.033 |
| swap_roll-1_pitch-1 | 3.659 | 2.069 | 2.611 | 1.831 |

原轴序、原符号四支均最接近，没有 180° 或互换明显优于原样的证据。安装角调整对照另存 B1_installation_adjusted_rpy，不从两者之间按参考误差选择约定。

## B2 yaw 来源分离

每对差值先各减本窗口首值，RMS 单位 °，漂移率单位 °/min。来源：B(s):branches.<支>.evaluation_window.B2.<比较>.rms_difference_deg,drift_deg_per_min。

| 运行 | 比较 | RMS | OLS 漂移率 |
|---|---|---|---|
| BY2 S | Hartley−原始 gyro-z | 318.435 | 96.926 |
| BY2 S | Hartley−Go2 yaw | 320.824 | 100.930 |
| BY2 S | Go2 yaw−原始 gyro-z | 10.381 | -4.004 |
| BY2 LIT | Hartley−原始 gyro-z | 73.104 | -35.347 |
| BY2 LIT | Hartley−Go2 yaw | 63.202 | -31.343 |
| BY2 LIT | Go2 yaw−原始 gyro-z | 10.381 | -4.004 |
| BY2O S | Hartley−原始 gyro-z | 1407.876 | -496.910 |
| BY2O S | Hartley−Go2 yaw | 1394.505 | -493.176 |
| BY2O S | Go2 yaw−原始 gyro-z | 14.197 | -3.734 |
| BY2O LIT | Hartley−原始 gyro-z | 97.119 | -15.960 |
| BY2O LIT | Hartley−Go2 yaw | 83.911 | -12.226 |
| BY2O LIT | Go2 yaw−原始 gyro-z | 14.197 | -3.734 |

Allan 记录的平均轴 gyro bias instability 为 4.550529e−5 rad/s，即 0.1564356638°/min；逐 z 轴值不可恢复。来源：configs/paper_rebuild/horizontal_literature/hartley/stage_payload/04_METHOD_CONTRACTS/GO2_IMU_ALLAN_90MIN_RECOVERED_V1.yaml:bias_instability_diagnostics.gyro_bias_instability、provenance_limitations.exact_per_axis_values_available；转换值在 B(s):gyro_bias_instability_deg_per_min。它不是本次初始常值零偏的上限：Go2 yaw 与未扣偏的 z 积分也相差约 −4°/min，不能单靠超过此 Allan 数字就断言更新错误。

接触事件对齐：epoch 相关是切换指示与瞬时偏离速率绝对值；1 s 相关是切换数量与累计绝对偏离。来源：B(s):branches.<支>.evaluation_window.B2.contact_switch_correlation。

| 运行 | epoch 绝对速率 r | 1s 有符号 r | 1s 绝对量 r | 切换处绝对速率 °/s | 非切换处绝对速率 °/s |
|---|---|---|---|---|---|
| BY2 S | -0.041 | -0.015 | -0.052 | 6.566 | 9.129 |
| BY2 LIT | 0.098 | 0.038 | -0.056 | 10.717 | 5.959 |
| BY2O S | -0.020 | -0.016 | 0.186 | 10.977 | 12.428 |
| BY2O LIT | 0.122 | -0.072 | 0.637 | 14.425 | 6.550 |

保存状态的独立逐区间恒等式将 native yaw 增量分为原始 z 积分、安装角与三维旋转、保存 gyro bias、接触旋转更新四项。每个区间从保存的 R_k 开始，不把计算结果递推至下一时刻，不调用滤波器。源代码执行顺序见 run_h5.cpp:430–443，更新改变 R 与 bias 见 backend.cpp:1197–1211。以下为各累计项对时间的 OLS 速率，单位 °/min；来源：D:<SEQ>_<BRANCH>.components.<项>.ols_rate_deg_per_min。

| 运行 | 原始 z | 安装/三维 | 零偏项 | 接触更新项 | 原生 yaw |
|---|---|---|---|---|---|
| BY2 S | 75.655 | -0.485 | -56.324 | 153.736 | 172.581 |
| BY2 LIT | 75.655 | -0.103 | -22.954 | -12.289 | 40.308 |
| BY2O S | 48.979 | -0.575 | -185.172 | -311.163 | -447.931 |
| BY2O LIT | 48.979 | 0.135 | -24.986 | 8.892 | 33.019 |

恒等式残差逐区间通过检查；完整数值见 D:exact_increment_identity_max_abs_deg，1 s 分解及接触切换数量见同目录 *_B2_DECOMPOSITION_1S.csv。接触更新包括持续接触校正，不只发生在切换时刻，因此低切换相关性不能排除更新来源。

## B3 接触与足力

S/LIT 使用同一序列的同一缓存，以下每行同时适用于该序列两支，不重复计样本。来源：B(s):B3.evaluation_window.legs.<腿>。足力分位数为 P05/P50/P95。

| 适用运行 | 腿 | 占空比 % | 切换/s | 完整接触段中位 s | off/on | 接触足力 P05/50/95 | 非接触足力 P05/50/95 | off–on 占比 % |
|---|---|---|---|---|---|---|---|---|
| BY2 S/LIT | FR | 48.764 | 4.110 | 0.238 | 24.8/34.2 | 13/53/66 | 5/6/49 | 1.352 |
| BY2 S/LIT | FL | 51.726 | 4.161 | 0.252 | 25.2/33.8 | 16/52/64 | 6/8/57 | 1.958 |
| BY2 S/LIT | RR | 53.748 | 4.131 | 0.262 | 23.4/30.6 | 17/45/88 | 8/9/52 | 3.264 |
| BY2 S/LIT | RL | 51.891 | 4.139 | 0.252 | 24.0/32.0 | 16/48/75 | 6/8/45 | 1.674 |
| BY2O S/LIT | FR | 60.423 | 3.119 | 0.240 | 24.8/34.2 | 32/46/66 | 6/8/45 | 5.451 |
| BY2O S/LIT | FL | 63.522 | 3.172 | 0.252 | 25.2/33.8 | 32/45/64 | 8/9/58 | 1.297 |
| BY2O S/LIT | RR | 64.944 | 3.130 | 0.262 | 23.4/30.6 | 28/42/85 | 10/11/53 | 1.767 |
| BY2O S/LIT | RL | 63.666 | 3.119 | 0.254 | 24.0/32.0 | 33/48/73 | 8/10/46 | 1.055 |

同时接触足数直方图，逐样本百分比；来源：B(s):B3.evaluation_window.simultaneous_contacts_sample_fraction。按时间加权版本也在 JSON。

| 适用运行 | 0 足 % | 1 足 % | 2 足 % | 3 足 % | 4 足 % |
|---|---|---|---|---|---|
| BY2 S/LIT | 0.053 | 1.393 | 92.545 | 4.675 | 1.335 |
| BY2O S/LIT | 0.018 | 0.836 | 71.370 | 4.875 | 22.901 |

足力直方图为样本计数，区间左闭右开（最末区间含右端）；来源：B(s):B3.evaluation_window.histogram_edges、legs.<腿>.force_histogram_counts。

| 运行 | 腿 | <0 | 0–10 | 10–20 | 20–25 | 25–30 | 30–35 | 35–40 | 40–50 | 50–75 | 75–100 | 100–150 | ≥150 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BY2 S/LIT | FR | 0 | 28004 | 445 | 215 | 287 | 479 | 898 | 7655 | 17202 | 1053 | 405 | 0 |
| BY2 S/LIT | FL | 0 | 26021 | 595 | 272 | 574 | 887 | 1432 | 8565 | 17442 | 797 | 58 | 0 |
| BY2 S/LIT | RR | 0 | 18791 | 7086 | 321 | 1331 | 2385 | 3515 | 10522 | 8379 | 3907 | 406 | 0 |
| BY2 S/LIT | RL | 0 | 26023 | 557 | 359 | 412 | 1144 | 2417 | 11498 | 12723 | 1504 | 6 | 0 |
| BY2O S/LIT | FR | 0 | 28897 | 612 | 187 | 346 | 3827 | 14042 | 7211 | 19834 | 1113 | 485 | 1 |
| BY2O S/LIT | FL | 0 | 15831 | 11969 | 270 | 441 | 832 | 3385 | 22701 | 20163 | 898 | 65 | 0 |
| BY2O S/LIT | RR | 0 | 487 | 26502 | 309 | 944 | 1927 | 7629 | 23605 | 9995 | 4653 | 504 | 0 |
| BY2O S/LIT | RL | 0 | 14188 | 13363 | 376 | 433 | 743 | 2669 | 21869 | 20864 | 2042 | 8 | 0 |

阈值在低、高足力主群之间；两种接触类别的分布尾部重叠，且有三样本驻留规则，不能把条件分位数当成独立识别正确率。没有独立支撑／摆动标签，阈值是否准确识别真实接触仍为“不能判定”。

## B4 腿里程计自洽

速度差为模长 RMS；另列向量差 RMS。方向中位数使用已登记的 0.05 m/s 双侧门。来源：B(s):branches.<支>.evaluation_window.B4。

| 运行 | 模长差 RMS m/s | 向量差 RMS m/s | 方向中位 ° | 方向有效行 | 零接触行 |
|---|---|---|---|---|---|
| BY2 S | 0.464 | 0.704 | 23.075 | 56613 | 30 |
| BY2 LIT | 0.204 | 0.293 | 6.132 | 56613 | 30 |
| BY2O S | 0.439 | 0.693 | 25.414 | 59077 | 14 |
| BY2O LIT | 0.180 | 0.262 | 6.506 | 59079 | 14 |

三条主轨迹水平路程及相对旧参考路程的比值；来源：同字段 path_lengths_10hz_m、path_length_ratios_to_recorded_reference、recorded_reference_path_length_m。

| 运行 | 腿×Hartley 姿态 m /比值 | 腿×Go2 姿态 m /比值 | Hartley 位置 m /比值 | 旧参考 m |
|---|---|---|---|---|
| BY2 S | 303.481 / 0.924 | 303.840 / 0.925 | 2108.391 / 6.419 | 328.471310905 |
| BY2 LIT | 303.812 / 0.925 | 303.840 / 0.925 | 688.400 / 2.096 | 328.471310905 |
| BY2O S | 310.878 / 0.921 | 310.980 / 0.922 | 3535.524 / 10.478 | 337.422046589 |
| BY2O LIT | 311.044 / 0.922 | 310.980 / 0.922 | 1130.270 / 3.350 | 337.422046589 |

有限差分足速度与日志 foot_speed_body 在接触足上的向量 RMS 差为 BY2 0.335 m/s、BY2O 0.275 m/s；差分腿轨迹路程为 285.577/292.805 m，分别是旧参考的 0.869/0.868。来源：B(s):branches.HARTLEY_S.evaluation_window.B4.foot_speed_vs_finite_difference_contact_rms_mps、path_lengths_10hz_m.leg_go2_fd、path_length_ratios_to_recorded_reference.leg_go2_fd；所以本报告保留两种口径而不把它们混同。

## C1 冻结对齐后的误差

对齐角使用原 JSON 的完整精度，平移不重新拟合。来源：C(s):branches.<支>.C1.frozen_alignment。

| 运行 | 绕 Z 对齐角 ° | 平移 E/N/U m |
|---|---|---|
| BY2 S | 87.462717751 | 0.217402606/0.408272984/-0.323070234 |
| BY2 LIT | 88.032538431 | 0.197567578/0.418824871/-0.215654638 |
| BY2O S | 89.530555739 | 0.279644877/0.434720379/0.143100077 |
| BY2O LIT | 95.150695143 | 0.014368597/0.465445937/-0.152028422 |

指定时刻误差；t 为评分窗口开始后秒数。来源：C(s):branches.<支>.C1.samples（elapsed_s 对应行），列 err_n_m/err_e_m/err_u_m/yaw_error_ned_wrapped_deg/yaw_error_ned_unwrapped_deg。完整 1 s 抽样见同目录 HARTLEY_*_C1_1S.csv。

| 运行 | t s | N m | E m | U m | yaw wrap ° | yaw 连续 ° |
|---|---|---|---|---|---|---|
| BY2 S | 10 | -0.560 | 0.531 | 0.146 | 0.092 | 0.092 |
| BY2 S | 30 | -1.231 | 5.383 | 1.835 | 7.042 | 7.042 |
| BY2 S | 60 | -12.114 | 11.274 | 5.407 | -9.469 | -9.469 |
| BY2 S | 120 | -33.320 | 113.485 | 3.905 | -52.468 | 307.532 |
| BY2 S | 240 | 96.706 | 56.449 | -3.713 | -52.169 | -412.169 |
| BY2 LIT | 10 | -0.761 | 0.201 | -0.082 | -2.865 | -2.865 |
| BY2 LIT | 30 | -1.054 | 3.428 | -0.354 | 3.785 | 3.785 |
| BY2 LIT | 60 | 0.347 | 8.013 | -0.651 | 7.848 | 7.848 |
| BY2 LIT | 120 | -1.785 | 16.977 | -1.957 | -1.540 | -1.540 |
| BY2 LIT | 240 | -56.954 | -81.501 | -6.741 | 95.187 | 95.187 |
| BY2O S | 10 | -0.629 | 0.886 | -0.473 | 2.160 | 2.160 |
| BY2O S | 30 | 11.590 | 33.818 | -0.792 | 99.445 | 99.445 |
| BY2O S | 60 | 25.173 | 21.156 | -1.015 | 39.982 | 39.982 |
| BY2O S | 120 | 32.351 | 190.740 | 2.908 | -118.651 | 241.349 |
| BY2O S | 240 | -6.989 | 64.348 | -0.369 | 7.667 | 1087.667 |
| BY2O LIT | 10 | -0.642 | 0.938 | -0.108 | 4.867 | 4.867 |
| BY2O LIT | 30 | 2.452 | 4.611 | -0.344 | 10.762 | 10.762 |
| BY2O LIT | 60 | 15.524 | 12.359 | -0.843 | 26.138 | 26.138 |
| BY2O LIT | 120 | 87.355 | 30.457 | -1.263 | 88.747 | 88.747 |
| BY2O LIT | 240 | 67.082 | -3.171 | -2.072 | 103.109 | 103.109 |

旧 HX-02 的水平/yaw RMSE 与位置/yaw 漂移均在子进程内复现，容差为 1e−7；逐值差见 C(s):branches.<支>.C1.reproduction_check。此容差只检验诊断复现一致性，不用来判定方法精度。

## C2 手性与符号

变换定义在原始冻结对齐后的 ENU 天线中点轨迹：东向镜像仅将 E 取反，yaw 取反仅改 ENU yaw，然后对每种情况重新做相同初始 10 s 四自由度对齐。这样“东”有确定含义；不改变原生输出。来源：C(s):branches.<支>.C2.transforms.<变换>。

| 运行 | 变换 | 水平 RMSE m | yaw RMSE ° |
|---|---|---|---|
| BY2 S | 原样 | 84.155 | 78.681 |
| BY2 S | 东向镜像 | 113.285 | 78.681 |
| BY2 S | yaw 取反 | 102.833 | 119.542 |
| BY2 S | 两者同时 | 81.100 | 119.542 |
| BY2 LIT | 原样 | 53.400 | 65.499 |
| BY2 LIT | 东向镜像 | 145.037 | 65.499 |
| BY2 LIT | yaw 取反 | 164.117 | 110.199 |
| BY2 LIT | 两者同时 | 82.249 | 110.199 |
| BY2O S | 原样 | 89.676 | 94.413 |
| BY2O S | 东向镜像 | 114.506 | 94.413 |
| BY2O S | yaw 取反 | 117.972 | 111.522 |
| BY2O S | 两者同时 | 91.780 | 111.522 |
| BY2O LIT | 原样 | 77.552 | 91.045 |
| BY2O LIT | 东向镜像 | 168.305 | 91.045 |
| BY2O LIT | yaw 取反 | 170.305 | 100.387 |
| BY2O LIT | 两者同时 | 72.127 | 100.387 |

没有十倍改善。不能由这组有限变换排除所有时间、杆臂或物理点问题，但它不支持简单东向镜像／yaw 反号是主因。

## C3 yaw 误差对参考转向回归

主口径为连续 NED yaw 误差对连续 NED 参考 yaw 增量的带截距 OLS，使用全部评分网格。另列 wrap 残差敏感性，避免将两种残差口径混用。来源：C(s):branches.<支>.C3。

| 运行 | 连续误差斜率 | R² | wrap 误差斜率 | wrap R² |
|---|---|---|---|---|
| BY2 S | 0.960 | 0.085 | 0.151 | 0.039 |
| BY2 LIT | -0.402 | 0.792 | -0.402 | 0.792 |
| BY2O S | -8.132 | 0.684 | 0.209 | 0.045 |
| BY2O LIT | -0.331 | 0.671 | -0.331 | 0.671 |

没有预期的 −2 反向模式；LIT 的 −0.402/−0.331 是部分转向相关误差，不是估计完全不转。BY2O-S 的 −8.132 反映额外多圈运动与路径相关，不能解释为单纯反号。

## C4 使用 Go2 姿态的输入层条件诊断

沿用同一 10 s 对齐及天线中点评估点；同序列的 S/LIT 共用此输入检查。来源：C(s):C4.<口径>。

| 适用运行 | 足速度口径 | 位置漂移 m/100m | 水平 RMSE m | 终点水平误差 m | 终点 m/100m | yaw RMSE ° |
|---|---|---|---|---|---|---|
| BY2 S/LIT | foot_speed_body | 0.069 | 6.209 | 0.799 | 0.243 | 2.306 |
| BY2 S/LIT | finite_difference | 0.107 | 10.238 | 1.237 | 0.376 | 2.306 |
| BY2O S/LIT | foot_speed_body | -0.379 | 6.322 | 3.471 | 1.029 | 6.006 |
| BY2O S/LIT | finite_difference | -0.918 | 10.966 | 3.000 | 0.889 | 6.006 |

Go2 姿态是机载姿态估计，不是独立真值；这不是数学上已证明的输入精度上限。零接触未观测时间在整个原生窗口为 0.204/1.276 s，在评分窗口为 0.204/0.116 s；来源：B(s):leg_integration_gaps 与 D:<SEQ>_leg_gap_window。C4 JSON 的 integration_gap_record 记录全原生窗口，不能误读成评分窗口缺测量。

## 四个运行的独立汇总

### BY2 S

| 项目 | 结果 | 原值字段 |
|---|---|---|
| B1 roll/pitch RMS ° | 1.673 / 4.801 | B(s):branches.HARTLEY_S.evaluation_window.B1_raw_rpy.hypotheses.identity_roll+1_pitch+1 |
| B2 Hartley−raw-z 速率 °/min | 96.926 | B(s):branches.HARTLEY_S.evaluation_window.B2.hartley_minus_raw_gyro_z |
| B3 同时两足/四足 % | 92.545 / 1.335 | B(s):B3.evaluation_window.simultaneous_contacts_sample_fraction |
| B4 模长差 RMS /方向中位 | 0.464 m/s / 23.075° | B(s):branches.HARTLEY_S.evaluation_window.B4 |
| C1 水平/yaw RMSE | 84.155 m / 78.681° | C(s):branches.HARTLEY_S.C1.metrics |
| 原位置/yaw 漂移 | 34.077 m/100m / -101.193°/min | C(s):branches.HARTLEY_S.C1.metrics |
| C2 最大水平改善倍数 | 1.038 | C(s):branches.HARTLEY_S.C2.max_horizontal_improvement_factor |
| C3 斜率 /R² | 0.960 / 0.085 | C(s):branches.HARTLEY_S.C3.unwrapped_error_vs_unwrapped_reference_turn |
| C4 腿轨迹漂移 /水平 RMSE | 0.069 m/100m / 6.209 m | C(s):C4.foot_speed_body |

### BY2 LIT

| 项目 | 结果 | 原值字段 |
|---|---|---|
| B1 roll/pitch RMS ° | 0.765 / 0.468 | B(s):branches.HARTLEY_LIT.evaluation_window.B1_raw_rpy.hypotheses.identity_roll+1_pitch+1 |
| B2 Hartley−raw-z 速率 °/min | -35.347 | B(s):branches.HARTLEY_LIT.evaluation_window.B2.hartley_minus_raw_gyro_z |
| B3 同时两足/四足 % | 92.545 / 1.335 | B(s):B3.evaluation_window.simultaneous_contacts_sample_fraction |
| B4 模长差 RMS /方向中位 | 0.204 m/s / 6.132° | B(s):branches.HARTLEY_LIT.evaluation_window.B4 |
| C1 水平/yaw RMSE | 53.400 m / 65.499° | C(s):branches.HARTLEY_LIT.C1.metrics |
| 原位置/yaw 漂移 | 36.281 m/100m / 31.940°/min | C(s):branches.HARTLEY_LIT.C1.metrics |
| C2 最大水平改善倍数 | 1.000 | C(s):branches.HARTLEY_LIT.C2.max_horizontal_improvement_factor |
| C3 斜率 /R² | -0.402 / 0.792 | C(s):branches.HARTLEY_LIT.C3.unwrapped_error_vs_unwrapped_reference_turn |
| C4 腿轨迹漂移 /水平 RMSE | 0.069 m/100m / 6.209 m | C(s):C4.foot_speed_body |

### BY2O S

| 项目 | 结果 | 原值字段 |
|---|---|---|
| B1 roll/pitch RMS ° | 3.127 / 1.516 | B(s):branches.HARTLEY_S.evaluation_window.B1_raw_rpy.hypotheses.identity_roll+1_pitch+1 |
| B2 Hartley−raw-z 速率 °/min | -496.910 | B(s):branches.HARTLEY_S.evaluation_window.B2.hartley_minus_raw_gyro_z |
| B3 同时两足/四足 % | 71.370 / 22.901 | B(s):B3.evaluation_window.simultaneous_contacts_sample_fraction |
| B4 模长差 RMS /方向中位 | 0.439 m/s / 25.414° | B(s):branches.HARTLEY_S.evaluation_window.B4 |
| C1 水平/yaw RMSE | 89.676 m / 94.413° | C(s):branches.HARTLEY_S.C1.metrics |
| 原位置/yaw 漂移 | 9.048 m/100m / 495.077°/min | C(s):branches.HARTLEY_S.C1.metrics |
| C2 最大水平改善倍数 | 1.000 | C(s):branches.HARTLEY_S.C2.max_horizontal_improvement_factor |
| C3 斜率 /R² | -8.132 / 0.684 | C(s):branches.HARTLEY_S.C3.unwrapped_error_vs_unwrapped_reference_turn |
| C4 腿轨迹漂移 /水平 RMSE | -0.379 m/100m / 6.322 m | C(s):C4.foot_speed_body |

### BY2O LIT

| 项目 | 结果 | 原值字段 |
|---|---|---|
| B1 roll/pitch RMS ° | 0.692 / 0.788 | B(s):branches.HARTLEY_LIT.evaluation_window.B1_raw_rpy.hypotheses.identity_roll+1_pitch+1 |
| B2 Hartley−raw-z 速率 °/min | -15.960 | B(s):branches.HARTLEY_LIT.evaluation_window.B2.hartley_minus_raw_gyro_z |
| B3 同时两足/四足 % | 71.370 / 22.901 | B(s):B3.evaluation_window.simultaneous_contacts_sample_fraction |
| B4 模长差 RMS /方向中位 | 0.180 m/s / 6.506° | B(s):branches.HARTLEY_LIT.evaluation_window.B4 |
| C1 水平/yaw RMSE | 77.552 m / 91.045° | C(s):branches.HARTLEY_LIT.C1.metrics |
| 原位置/yaw 漂移 | 27.699 m/100m / 13.392°/min | C(s):branches.HARTLEY_LIT.C1.metrics |
| C2 最大水平改善倍数 | 1.075 | C(s):branches.HARTLEY_LIT.C2.max_horizontal_improvement_factor |
| C3 斜率 /R² | -0.331 / 0.671 | C(s):branches.HARTLEY_LIT.C3.unwrapped_error_vs_unwrapped_reference_turn |
| C4 腿轨迹漂移 /水平 RMSE | -0.379 m/100m / 6.322 m | C(s):C4.foot_speed_body |

## 判定

**最可能的原因是 H3：本次生产移植及其运行配置中的接触更新／零偏估计路线。现有证据不能判定具体哪一行代码或哪一项数学公式有错，也不能把该结果推广为 Hartley 论文算法的精度结论。**

**H1 的支持与反对证据。** 历史 H7 的参考点及姿态框架门没有闭合，仍是解释边界，不能宣称所有坐标或物理点误差都已排除。但本次四支 roll/pitch 的原轴序、原符号均优于所列互换与取反假设；RMS 为 roll 0.692–3.127°、pitch 0.468–4.801°，没有接近 180° 的差。C2 的最佳水平 RMSE 改善仅 1.000–1.075 倍，yaw RMSE 没有改善，达不到十倍证据门。C3 斜率依次为 +0.960、−0.402、−8.132、−0.331，均不呈现简单 yaw 反向的 −2 模式；这些是描述性 OLS，不能仅凭斜率接近或远离某个数就作因果判定。所检查的轴序、东向镜像和单边 yaw 符号错误不支持作为主因。出处：DIAGNOSTIC_TABLES.json:sequences.<SEQ>.B.branches.<BRANCH>.evaluation_window.B1_raw_rpy、sequences.<SEQ>.C.branches.<BRANCH>.C2/C3；历史边界见 A1/A2。

**H2 的支持与反对证据。** 接触阈值处在日志低、高足力主群之间，但接触标签本身由足力阈值生成，不能独立证明物理支撑／摆动识别正确；接触延迟、滑动与 Go2 FK 代理的相关误差仍可能影响更新。另一方面，相同接触/FK 输入用 Go2 姿态旋转后，BY2/BY2O 纯腿轨迹的漂移斜率为 +0.069/−0.379 m/100 m，水平 RMSE 为 6.209/6.322 m，终点误差为 0.243/1.029 m/100 m；固定的足位置差分口径也给出 +0.107/−0.918 m/100 m、10.238/10.966 m。没有出现输入轨迹自身约 30% 的失效证据。零接触区间没有速度观测，主口径在这些区间不累加位移，评分窗口内未观测时间为 0.204/0.116 s。Go2 姿态来自机载估计器，这项检查是条件诊断，不能作为经证明的精度上限；负漂移斜率只表示误差范数随路程的回归下降。H2 单独足以解释全部异常的说法不受支持，但 H2 与滤波器观测模型／噪声配置的失配不能排除。出处：DIAGNOSTIC_TABLES.json:sequences.<SEQ>.B.B3、sequences.<SEQ>.C.C4、saved_state_readout.<SEQ>_leg_gap_window。

**H3 的支持与反对证据。** 在适配器和参考评估之前，Hartley 原生 yaw 已偏离原始 z 陀螺积分，OLS 速率为 +96.926、−35.347、−496.910、−15.960°/min。保存状态分解将其定位到零偏与接触更新：零偏项依次为 −56.324、−22.954、−185.172、−24.986°/min，直接接触旋转更新项为 +153.736、−12.289、−311.163、+8.892°/min；安装角及三维旋转项绝对值均小于 0.576°/min。各区间从保存状态独立计算，未运行滤波器。四支原生位置轨迹路程分别为参考的 6.419、2.096、10.478、3.350 倍，而两种姿态旋转的主口径腿轨迹约为 0.921–0.925 倍。反对把它直接定为公式错误的证据是：数学回归和结构验证曾通过，官方早期后端回归也通过；同时，噪声、接触质量、模型失配仍可使正确实现的更新不适用。官方早期后端的通过不能替代生产 IJRR 后端的真实精度验收。出处：DIAGNOSTIC_TABLES.json:sequences.<SEQ>.B.branches.<BRANCH>.evaluation_window.B2/B4、saved_state_readout.<SEQ>_<BRANCH>.components；后端差异见 A1。

**综合判定。** H1 的简单手性／yaw 符号解释未获支持；H2 的“输入只能给出约 30% 漂移”解释未获支持；最强直接证据落在生产滤波器的接触更新与零偏反馈路径，因此以 H3 为首要定位方向。接触切换相关性并非四支一致，不能进一步声称所有异常都发生在切换瞬间。准确缺陷是实现、噪声配置还是输入与更新模型的耦合，**不能判定**。

**下一步两个选项。**

1. 若后续独立坐标／物理点证据确立 H1，登记评估器或适配器修正，只重新评估既有原生输出，不重新解算。本次没有达到启用这一选项的证据门。
2. 按当前更支持 H2/H3 路线的证据，论文使用“未通过精度验证的移植、不作对比行”，将这些结果与诊断挪至补充材料。此次仅给出该建议，不修改论文、HX-02 结果或任何方法实现。

## 执行、审计与完整性

原生解算 LegSA/外部为 0/0。参考评估子进程共 2 次（每序列一次，在同一内存中处理两支），每次 trace 只读打开 1 次并按同一份字节核验 SHA256；全部 C 计算只在该子进程内执行。来源：EXECUTION_V2/00_CONTROL/EXECUTION_COUNTERS.json、EXECUTION_V2/C_REFERENCE/{BY2,BY2O}/EVALUATOR_STRACE_AUDIT.json。

B 主诊断子进程实际调用 3 次，其中第一次 BY2 因 NumPy int64 的 JSON 序列化错误失败，成功 2 次；另有无参考保存状态分解子进程 1 次。诊断子进程总计 6 次，失败前后未启动原生程序。失败的 B_ARRAYS.npz 和部分 JSON、stderr、strace 原样保留，续作只改变新诊断 JSON 编码，没有改变科学计算式。来源：00_CONTROL/SERIALIZATION_FAILURE_RECORD.json、00_CONTROL/CALLS.jsonl、EXECUTION_V2/00_CONTROL/CALLS.jsonl。

控制进程参考打开 0，B 与保存状态分解参考打开 0，bag/fpl 打开 0；来源：00_CONTROL/CONTROLLER_AND_READOUT_AUDITS.json 与三份 B_STRACE_AUDIT.json。现有 hx02_evaluation_process.py 字节未改；诊断子进程只在当前控制进程的登记表里增加一个新项，源码 SHA256 在子进程启动前写入 DIAGNOSTIC_CHILD_REGISTRATION.json。原始失败登记与续作登记都保留。

初次起点检查、暂停前、续作开始的封存核对均为 65/65、CSV 59/59 一致；记录分别为 00_CONTROL/SEALED_TABLES_START.json、SEALED_TABLES_PREREQUISITE_STOP.json、SEALED_TABLES_RESUME_START.json。提交前 SEALED_TABLES_PRECOMMIT.json 再次通过 65/65、CSV 59/59，一致性异常为 0。

新的诊断代数检查为 7 passed（包括序列化边界），没有原生解算或参考访问；源码 tests/paper_rebuild/test_hx02d_diagnostic.py。HX-02 全目录前后核对、方法字节与既有 29 个未跟踪文件保持、复制后逐文件 SHA256、scratch 清空与提交前封存状态见 FINAL_INTEGRITY.json。无交接包。

实际完整性结果：HX-02 全目录 12,678/12,678 文件 SHA256 一致，无新增/缺失；方法本体 423/423 一致；既有未跟踪文件 29/29 一致。来源：00_CONTROL/HX02_TREE_FINAL_CHECK.json、METHOD_AND_UNTRACKED_PRESERVATION.json。独立数值复核 12 项通过，C1 全部 1 s 样本与旧误差 CSV 的最大绝差为 1.1368683772161603e−13；来源：00_CONTROL/DIAGNOSTIC_VALIDATION.json。诊断完成状态与复制、scratch 清空回执见 FINAL_INTEGRITY.json。
