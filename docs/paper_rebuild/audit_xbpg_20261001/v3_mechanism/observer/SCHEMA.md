# GIEngine 只观察 JSONL schema v1

状态：实现和合成验证已完成（288/288 检查通过）；实际编译及 fixture 门见 READY.json。真实对象身份门尚未在此回执执行。适用源为 ca73cb1fb48a020fd2a450d79e520562c34eeb24 隔离快照。正式 cpp 与 source_frozen 均不修改。

`LEGSA_V3_OBSERVER_DIR` 未设置时不创建观察目录/日志；设置时写该目录的 `events.jsonl`，拒绝覆盖已有同名文件。`LEGSA_V3_OBSERVER_RUN_ID` 为运行 ID，未设置则取目录名。所有 double 以 classic locale、17 位有效数字序列化；非有限值保存为字符串 `NaN` / `Infinity` / `-Infinity`，不能当作数值零。

每条 envelope：`event_seq`（从 1 连续递增）、`run_id`、`event`、`available_time=UNKNOWN`、`data`。真实到达时刻没有观测，不以 measurement time 代替。`OBSERVER_BEGIN/END` 的 data 是直接元数据；其余事件有 `data.context` 和 `data.snapshot`。最终 END、连续序号及完整 JSON 行用于检查正常结束，缺失 footer 明确为不完整。

`context`：`imu_seq,gnss_input_seq,measurement_attempt_seq,sa_seq,ekf_seq,source,row_id,measurement_time,gnss_time,imu_previous_time,imu_current_time,state_time,res`，加原科学更新计数。row_id 是已加载 vector 的 **zero-based** 行号；GNSS loader 原行号未传入 GIEngine，GNSS_INPUT 明记 UNKNOWN_NOT_PASSED_TO_ENGINE，不以 GNSS 输入序号冒充原文件行号。sa_seq=0 表示该 attempt 尚未调用 SA；context 的 ekf_seq 是最近/当前 EKF 序号，SA 与 EKF 应以 measurement_attempt_seq 和事件顺序关联。

矩阵完整导出为 `{rows,cols,layout:"row_major",data:[...]}`；维度与 data 长度必须一致。不省略 P/H/S/K 的非对角项。state 包含 BLH(rad,m)、NED velocity(m/s)、rpy(rad)、Cbn、wxyz quaternion、gyro/acc bias、scale、antlever(m)。IMU 包含 time、原 dt、dtheta、dvel、compensated 标志。

## 调度与测量选择

- CONFIGURATION：实际 enable/source modes、LSIM/OIM source masks、阈值、source/global cap、rolling 开关、辅助开关与匹配容差、yaw gates、parity 模式。
- IMU_INPUT：原输入与 compensate 参数。IMU_OPPORTUNITY：每次原 newImuProcess 调度的初始化状态、res、effective_update_time、GNSS 三 flags/OR/isvalid、两 IMU 和明确原因；GNSS_ALL_FLAGS_FALSE、GNSS_INPUT_NOT_PENDING、NOT_DUE、NO_TIME_BRACKET、GNSS_UPDATE_SCHEDULED 分开。
- GNSS_INPUT：传入和原逻辑规范化后的 GNSS；auxiliary_candidates 对每源保存 loaded_rows、selection_eligible_rows、config_enabled、solver_enabled、provider_status、time_tolerance_sec、nearest_any_row_id、selected_row_id、原输入字段和匹配结果。只在每个新 GNSS 输入做观察用独立匹配扫描，不在每个 IMU 重扫。候选扫描不改变原 matcher、vector 或 cursor。原 `<=` 的等距最后一行规则保留。HV selection_eligible 只指原 update_flag 条件，不包含后续质量门。
- GNSS_UPDATE_ENTRY/BLOCKED/DISPATCH/CONSUMED：原 GNSS 入口及 QA/aux dispatch；MEASUREMENT_ATTEMPT 开始实际 helper 调用，不能将 loaded candidate 视为尝试。
- MEASUREMENT_SELECTED：原 helper 实际选中指针到 vector 首地址的 row_id、匹配 dt、全部辅助字段。RP 没有独立 valid/update_flag 字段，明记 NOT_PRESENT；active 由原 source_status 表示。HV 保留 update_flag、diagnostic_only、truth claim、质量、prior_policy、contact/frame；RD 保留 valid、lineage、provider、sat_count、source time。
- MEASUREMENT_DECISION：accepted 与精确 return/gate 原因（配置关闭、源不可用、空输入、无时间匹配、质量门、残差门、SA reject、ACCEPTED）。实际重复消费由同 source/row_id 的 accepted 序列离线计算；不把重复匹配候选当重复更新。

## 同快照 SA / EKF

SA_EVALUATION_BEGIN 为原 evaluate 前：dz、H、dx_before、P_before、base_R。SA_EVALUATION 为原 evaluate 的唯一调用结果：相同五项、effective_R、state、metadata、innovation、result、source_enabled、qm_active_scaling。

metadata 是原 SourceMetadata 全字段（含 std_xyz、valid、quality/provider、yaw/baseline available fields、readiness）。innovation 是原 dz-based NIS、dof、normalized、R/HPH/S traces、used_innovation_covariance。result 包含原 LSIM/OIM scores/scales、combined_R_scale、source_cap、accepted/rejected、reason_codes、rolling median/MAD、relative anomaly、metadata_summary。`oim_alpha_available` 仅在原 N6B 分支确实执行 alpha 赋值时为 true；此时复制最终实际 alpha、实际分支 multiplier (1/1.2/1.6) 和 cap 前 scale_value 为 `oim_alpha,oim_multiplier,oim_raw_scale`。早返回/非该分支没有实际 alpha，字段 NaN，不补算。没有为日志第二次 evaluate，没有 live 影子公式或 LSIM 分量重算。

SA 关闭但原 helper 仍调用 applySourceAwareWeighting 时，仍导出单位权重结果与 source_enabled=false。HV/RP 若本源 sourceaware 配置关闭，原 helper 不调用 SA，只有 EKF 事件；此时不能捏造 SA_EVALUATION 或说权重变化。CONFIGURATION 与 MEASUREMENT/EKF 共同解释缺事件。

EKF_BEFORE：实际 dz、H、R、dx_before、P_before、state。EKF_AFTER：原代码已经计算的 actual_innovation (=dz-Hdx)、actual_Hdx、actual_S、actual_K、actual_delta、dx_after、P_after、state。FEEDBACK_BEFORE/AFTER 保存真实 error-state feedback 前后状态。因 observer 不修改数学表达式/原调用顺序，任何新影子计算仅由离线分析脚本实施。

YAW_GATE_INPUT 保存原 yaw observation/prediction/std/residual；基线向量不在原 GnssData 中，明记 UNKNOWN_NOT_IN_GNSS_STRUCT。VELOCITY_KINEMATICS 与 RAW_DOPPLER_KINEMATICS 保存实际原 dt/fallback、omega、杆臂速度/天线速度及输入 IMU；IMU_COMPENSATE、PROPAGATION、IMU_SPLIT 前后保存真实字段，用于分支与补偿条件取证，不新生成修正。

## 合成测试与门

fixture 只创建合成小数组，科学输出和原 SA trace 在冻结库、观察库关闭日志、观察库开启日志三种条件逐字节比较。每个进程、失败与重试另有回执。该门只验证测试覆盖内的无干扰；真实 11 对象的输出身份由根代理逐对象核对。真实调用前只允许合成测试通过及编译，不授权扩展 case 或使用 trace/reference。所有测试明确 data_mode=synthetic_fixture_only；不写入真实性能表。
