# HX-02D 起点核查与 A 部分只读记录

状态：`BLOCKED_PREREQUISITE_REPORT_COMMIT_NOT_FOUND`。本文件为部分记录，HX-02D 未完成。

## 起点事实

任务要求 HEAD 包含 HX-02 结果提交及其后的报告提交。`git pull --rebase` 返回 `Already up to date.`。
当前 HEAD 与远端 `origin/stage/clean3-math-repair` 均为 `e612eeb0ad37bf150a4076eb636424fe85f1d222`；
`git ls-remote --heads origin` 也确认该分支同一哈希。`HX02_RESULTS.md` 最近一次提交就是该结果提交。
未找到其后的报告提交。需要提供该提交或明确允许当前 HEAD 作为起点；不自动放宽本次任务的起点要求。
命令结果字段见 `PREREQUISITE_CHECK.json:head,origin_branch_head,git_pull_rebase_result,report_path_last_commit`。

A 部分以下结论均从本次实际读取的文件核实。路径 H 指 `<CLEAN4>/07_LSE01_HARTLEY_CONTACT_INEKF`。

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

## 尚未执行与计数

B1、B2、B3、B4、C1、C2、C3、C4 全部为 `NOT_EVALUATED_PREREQUISITE_PENDING`，数值为 null。
H1/H2/H3 均为“不能判定”。不存在本次生成的姿态、接触、腿里程计或参考误差统计。
计数见 PREREQUISITE_CHECK.json:counters_this_task：LegSA/外部原生解算 0/0，评估子进程 0，
控制器参考打开 0，trace/bag/fpl 打开 0，HX-02 写入调用 0；没有评估器 strace，因为未启动评估子进程。
HX-02、方法本体、合约、原文档、AGENTS.md 均未写入；未进行 HX-02 全目录前后内容哈希验收。

封存表两次核对见 00_CONTROL/SEALED_TABLES_START.json 和 SEALED_TABLES_PREREQUISITE_STOP.json：
各自 counts.MATCH=65，csv_match=59，MISMATCH/MISSING/UNREGISTERED 均为 0。
第二次是本次起点阻断收束检查，不替代未来真正提交前的检查。
尚未提交或 push，保留任务最终一次提交的额度；未制作交接包。

## 用户起点裁定与续作（2026-09-26）

以上阻断是历史记录。用户已明确允许从 `e612eeb0ad37bf150a4076eb636424fe85f1d222` 开始，后续报告提交当时未做成。
本次 `git status --short` 中 HX02 docs 无改动；七个已有同名文件与 HX02/90_AGGREGATE 的 SHA256 一致。
主表 SHA256 为 `7475d7ef9780cdc9b2d82943dc786d58732076b9bad819f945f5010346190fba`。
两边均无 RESULTS_NOTES.json 或 AGGREGATE_RENDERS.json；源端 AGGREGATE_MANIFEST.json 是已有汇总清单，不是第二次渲染报告。
裁定执行结果：**无需补提交**；无需新增补提交哈希，HX-02D 继续从上述 e612eeb 执行。
出处：00_CONTROL/REPORT_COPY_CHECK.json:pairs,hx02_docs_status,render2_notes_present,table_sha256。
本任务产生的 HX02D 未跟踪目录与既有 29 个未跟踪文件分开登记；既有文件不动。
本次 B/C 状态以 HX02D_HARTLEY_DIAGNOSTIC.md 和 DIAGNOSTIC_TABLES.json 为准。
