# SDK持续速度差异进入共同状态：实现与集中核对

后续状态：本文封存实现与数学检查；其后2＋2 NMB1匹配实测已完成，水平收益判据失败，见SDK_JOINT_NMB1_ATTRIBUTION.md。实现正确性与实测效果分开报告。

已按`SDK_COMMON_STATE_DISCREPANCY_DESIGN.md`实现唯一研究模式`go2_body_velocity_discrepancy_mode: joint_constant`；默认off保持原路径。开启要求research_experiment、support-pose开启、body-FRD SDK水平速度。没有修改V3输入、IMU安装角/比例/时钟、原SDK替代时序、足点XYZ模型、工作sigma、NIS概率或已有撤销窗口。本报告只说明实现与合成数值核对，尚不代表实测导航收益。

## 实际统一状态

current原21维及其原NAV/cov导出接口保留；首个合格SDK源行后，持久状态为current21＋b2＝23。pose START再增广ECEF p/姿态clone6形成29，顺序为current[0:21]、b[21:23]、clone p[23:26]、clone phi[26:29]。也支持先有原27维clone，再由首SDK插入b两维形成29。b是工作body轴上的持续有效速度差异，并非宣布识别出的独立SDK硬件偏置。

观测为z_sdk_xy=Pxy Rᵀv+b。residual=h+b−z，b采用加法反馈，因此SDK直接列H_b=−I。首行bhat=z−h(xhat)，关联误差均值mu_b=H_x mu_x，P_xb=P H_xᵀ，P_bb=H_x P H_xᵀ+R_seed，未知源cross N=0明确只是工作假设。若已有clone，所有旧clone-b cross按同一原joint P计算。R_seed只用既有provider标准差及scale；该行不ordinaryUpdate、不计SDK导航接受、也不进入source-aware rolling创新统计。首行没有制造“零残差观测”。

b均值按bdot=0持续，Q_b=0，没有新调参随机游走。传播执行Phi P_xb，Pbb及b-clone cross保留；START的clone Jacobian对b直接列0，但J P_xb不为0时完整保留。普通GNSS/RP/carrier因子对b直接列0，仍以全joint P更新b。足点END直接列也为0；它通过current/clone/b交叉项共同更新导航和b。SDK第二行起的source-aware条件创新及S使用完整[H_x,−I]与23/29维P，包括两个负cross项；没有仅用旧21维S作资格判断。

feedback执行b←b+delta_b，并通过完整reset运输current-b、clone-b及current-clone全部协方差；b reset块I。RETIRE/END只移除clone，保留已更新的23维current+b marginal。0.5s回放使用现有whole-GIEngine深复制，自动包含b均值/误差/P/cross/seed身份、SDK唯一消费时刻与质量历史，未创建另一份补丁滤波器。

## 代码入口

|职责|文件与行号|
|---|---|
|关联seed、H_b符号|`src/factors/body_velocity_model.cpp:22,43`|
|23/29 pack与unpack|`src/kf_gins/gi_engine_support_pose.cpp:12,36`|
|clone创建／退休，foot列映射及完整更新|同文件74、112、145–163|
|Phi传播与所有普通joint更新|`src/kf_gins/gi_engine.cpp:572,583`|
|完整feedback/reset，含b加法|同文件635起|
|首SDK独立seed、后续SDK联合模型|同文件1748起|
|fulljoint source-aware创新与S|同文件2268起|
|23/29数学增广及reset|`src/factors/pose_clone.cpp:55,105`|
|诊断|`src/kf_gins/gi_engine_support_pose.cpp:190,205`|

以上C++路径以`cpp/legsa_v23_port_core/`为根。原pose-only足点模型保持27列，engine在启用b时显式将clone列平移+2；没有把b列误当旧clone位置。`marginalCurrent`与旧`footUpdate`便利接口仍保留旧21/27合同，新engine明确使用动态joint ordinaryUpdate及自身retire，不调用这些旧尺寸接口。

## 一个集中的合成检查

检查脚本`scripts/paper_rebuild/unified_legged_heading_20261007/sdk_discrepancy_check.py`，真实C++引擎fixture为`tests/paper_rebuild/native_sdk_discrepancy_harness.cpp`。检查未读实测raw/reference，也未调用实测navigation CLI。独立oracle用自由b先验的加权QR batch，同时包含第一SDK、独立运动锚和第二SDK；不以实现自己生成的预期值代替oracle。另核SDK似然的速度-b平移规范方向H_full g=0。

|必要数值核对|结果|
|---|---:|
|顺序结果对QR batch均值最大差|1.3444e−17|
|完整23协方差对QR batch最大差|9.0206e−17|
|已有27维clone时首seed旧mean/P最大改动|0，逐项相同|
|首seed无SDK普通更新、无source-aware计数|通过|
|先seed23，再START29及J P_xb|逐项相同|
|包含所有cross的传播最大差|1.0842e−19|
|独立有限旋转reset Jacobian对应P最大差|6.0628e−12|
|retire后23维marginal最大改动|0|
|实际whole-engine REVOKE回放后P23/b/v对never-consumed|全部0差|
|撤销前受足点影响的b差异|0.188810 m/s，非空效应|
|撤销回放后保留carrier接受|3次|

`SDK_DISCREPANCY_CHECK_01`保留首次fixture失败：合成provider忘写`provider_status=available`，导致SDK未启用、预期seed未发生；仅修fixture后同一检查在`SDK_DISCREPANCY_CHECK_02`通过，生产算法未因此变动。已复制精炼`SDK_DISCREPANCY_CHECK.json`，完整矩阵/日志留在scratch；没有展开旧测试矩阵。

## 二进制与输出语义

独立build为`.../UNIFIED_LEGGED_HEADING_20261007/SUPPORT_SDK_JOINT_BUILD/legsa_v23_port_core_demo`，SHA256 **c42f1609d98fe7d60e96b5e477420393acae3ae544075e48ea9cc28d39ebe327**。旧0a69及4f79构建没有覆盖。该身份已交root与实测runner，实测启动由root冻结PLAN后单独通知。

`SDK_DISCREPANCY_EVENTS.csv`字段：time/source_time/kind/identity/initialized，b_forward/right_before/after，Pbb00/Pbb01/Pbb11，Pxb_frobenius/Pbclone_frobenius，nis、innovation_dimensions及innovation_0…5，delta_p_N/E/D_m、delta_v_N/E/D_mps、delta_phi_N/E/D_rad、delta_ba_x/y/z_mps2。SDK与foot行source_time是真实provider/event时刻；其他普通因子行该列为state update时刻，不冒充其原源采样时间。

b前后都是nominal＋error的条件均值。delta项是该次条件error mean变化按反馈符号映射到的切空间增量；delta_phi是NED左旋向量，**不是Euler差，也不是包含传播的精确NAV输出跳变**。Pbb/cross范数记录在该次更新之后、reset之前。SDK行innovation是含b及full H mu条件项的实际创新，NIS采用本次scaled R；foot行保留原同一NIS/residual。首seed行innovation_dimensions=0；`BODY_VELOCITY_EVENTS.csv`首seed accepted=false且reason=`seed_joint_sdk_discrepancy_no_navigation_update`，之后接受照旧计数。

`SDK_DISCREPANCY_SUMMARY.json`保存seed数/源身份、最终b及Pbb、Qb=0、N=0工作假设和诊断语义。主manifest明示启用模式、23维持久状态及最大29维joint；原NAV导出依然21维当前导航marginal。回放后的引擎诊断描述修正轨迹，原前沿接受历史仍由现有replay journal区分。
