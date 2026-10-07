# 部分方向双分量：共同先验诊断的保存数据边界

当前 LEGACY/VECTOR 保存数据不足以判断第二分量在**载波更新前共同姿态先验**中是否仍有不可忽略支持。41/117 个双分量域不是后验多模态证据。需区分“共同姿态边缘先验与方向域重叠”和“完整后验模态概率”；仅补姿态边缘也不能认证后者。本次仅只读，无 native/evaluator 或算法修改。

## 实际保存项与缺失项

两臂共同目录为 /home/kaiwen/research/LegSA-GINS-SCRATCH/UNIFIED_LEGGED_HEADING_20261007/VECTOR_DIRECTION_SA_BY2O_01，其下分别为 LEGACY/NATIVE/BY2O__LEGACY 与 VECTOR/NATIVE/BY2O__VECTOR。

实际文件包括 LegSA_PORT_NAV.nav、KF_GINS_Navresult.nav、LegSA_PORT_STD.csv、KF_GINS_STD.txt、KF_GINS_IMU_ERR.txt、BASELINE3D_DIAGNOSTICS.csv、SOURCE_AWARE_WEIGHT_TRACE.csv 和支撑事件日志。没有更新前完整姿态先验、完整 covariance checkpoint 或 STATE_COVARIANCE_SUPPORT.csv。

- cpp/legsa_v23_port_core/src/fileio/file_saver.cpp:262–279,339–346：两种 STD 均只写 sqrt(P_ii)。名为 roll/pitch/yaw std 的列来自误差状态 phi 对角项，不能当完整 Euler 联合协方差；姿态三项非对角协方差未保存。
- cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp:1576–1589：先完成 newImuProcessWithEvents、support_replay.afterInterval，再 appendState；NAV/STD 是整个 IMU 区间处理后的状态，不是各载波更新前状态。
- cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp:1461–1475：载波诊断有 nominal h、dz、conditional innovation、完整测量 R 和 NIS，无该槽的完整 dx_phi、P_phi_phi 或 S。2279–2302 的 SA 确实使用共同条件先验，但日志只有 S trace/NIS，不能唯一反演 P_phi_phi。
- getCovariance() 内部返回完整 P（同文件 903–904），常规输出未序列化。runtime 67–88 的特殊全 P 文件只属于另一个指定 stage 且仅写区间端部；本轮 stage 为 TRUSTED_HEADING_FULL_WINDOW_NAVIGATION_20261006，未启用该输出。

具体双分量实例：PROVIDER_DETAILS.jsonl.gz 解压第 168 行，index=83，carrier time=3202.798000097275。两臂相邻 NAV 时间均为 3202.793056 和 3202.799052；后一个输出已处理 carrier。插值、逆推 posterior 或把缺失交叉项设零，都不能恢复真实更新前先验。

## 角域坐标与可计算边界

角域原产物为 /home/kaiwen/research/LegSA-GINS-SCRATCH/CONTINUOUS_HEADING_20261007/PARTIAL_FULL_WINDOW_01/BY2O/PROVIDER_DETAILS.jsonl.gz。筛选 policy=="rolling" 且 kind=="PARTIAL_GLS_LIKELIHOOD"；字段 consumed_likelihood.directed_components，每项 start_rad/width_rad 是环形区间。

continuous_arc_full_window.py:162 使用各模型记录的 anchor_ecef_m；candidate_lifecycle_pilot.py:71–74 构造源 anchor 的 ECEF 北/东轴。joint_direction_envelope.py:24–26,50–56,80–83 按北 cos(theta)、东 sin(theta) 参数化，垂向为 north×east。theta 是 GNSS2−GNSS1 侧向基线 atan2(E,N)，**不是机体 Euler yaw**。continuous_arc_partial_quality.py:75–86 保存运动约束后的 directed cover；它是几何外覆盖，没有概率权重。

记源北/东轴为 A_anchor、当前导航位置对应 NED→ECEF 旋转为 E(p)=C_ne(p)，应使用：
theta = atan2(second,first)(A_anchor E(p) Exp(phi) C_bn r_body)，r_body=[0,-.35,0] m。

当前载波日志的 h 是 nominal 预测，足以结合**精确当前 p**检验该点落在哪个弧；日志没有保存精确事件 p/完整先验，邻近 NAV 仅可作明确标记的坐标近似。不能直接比较角域与 NAV yaw，也不能混用源 anchor 和当前导航 NED。固定 nominal p 的旋转与当前因子实现一致，但忽略位置不确定性及姿态/位置相关性；不可称精确联合状态概率积分。

## 最小下一次诊断建议（未执行）

如继续，仅在 applyBaseline3dUpdate 建模后、当前载波 hard-NIS/SA/EKFUpdate 之前，记录精确事件身份、event/state time、event 序号、nominal C_bn/quaternion、nominal BLH、body baseline、现有条件 dx_phi 三项和完整对称 P_phi_phi 六项，并明确 PRE_CURRENT_CARRIER_UPDATE。已有 h/R/innovation 可复用。当前 gate 拒绝的可用 partial 槽也保留。

无需每个 IMU 时刻输出完整 21/27 维 P。此前 foot/SDK/载波已通过共同更新进入该姿态边缘，不能再叠 foot prior；nominal/error mean 必须保留同一误差图表，不能未经 reset 运输混用协方差。

上述最小记录只能在固定 nominal p、当前高斯姿态边缘及其误差图表下，检查与两个域的几何重叠或先验质量上界，以判断是否值得继续。不能直接宣称完整 carrier 后验：

- directed 域已使用 RP/重力与 gyro 资格，与共同 prior 的来源重叠；不能把域当独立概率再次相乘。
- 域是外覆盖；两个域都有先验质量不等于两个后验模态。保留域外质量，不能强行把两项归一化为总概率 1。
- 若要计入位置不确定性，还需 dx_p、P_pp、P_p_phi 和实际坐标合同；若要后验模态概率，还需明确 likelihood、资格选择条件及未知来源相关性的工作假设。当前边缘 overlap 不能升级为物理概率认证。
