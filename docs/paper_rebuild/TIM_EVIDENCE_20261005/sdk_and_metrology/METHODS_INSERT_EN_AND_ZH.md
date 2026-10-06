# 可直接插入Methods的英文与中文说明

用途：供根代理TIM正文分支选择/精简。下列“Current evidence”写当前事实；“Required validation”写尚未执行的验证，不得将后者改为过去时。原V3结果不变；不把后续诊断替换为作者选择的主版本。

## A. Current evidence: installation and interfaces

The commercial sensor was mounted with its camera side facing the forward direction of the robot. The author confirmed that the supplied mechanical designs describe the configuration used during collection; later file dates reflect saving and organization. The mechanical models and manufacturer dimensions were treated as nominal geometry, not as a survey of the IMU sensitive center, antenna phase centers, or their uncertainty. The public Unitree SDK2 interface provides an IMU submessage containing quaternion, angular-rate, acceleration and roll–pitch–yaw fields, while the enclosing sport-state message contains a timestamp and reported position and velocity. The IMU submessage has no separate timestamp, frame identifier, point-of-measurement definition or covariance. The inspected public interface snapshots before and after the collection date have identical relevant IDL blobs, but this does not identify the installed firmware or establish the physical interpretation of every field. The auxiliary velocity is therefore described as a robot-reported estimate rather than an independent leg-kinematic measurement.

中文解释：可以写相机方向及同安装构型；不能写杆臂已量测。公开消息的字段存在，不等于实际firmware、采样时刻、速度frame/点位已证。官方URDF和xacro的名义IMU原点不一致，不能任选其一填实机外参。

## B. Current evidence: clocks and event matching

According to the author, the body IMU and the GNSS receivers used different clocks. Alignment was based on a deliberate motion event observed in receiver position/velocity and body IMU signals, rather than on the fused commercial reference trajectory. The inspected parser reconstructs time from the enclosing stamp fields as s=sec+10⁻⁹nanosec; subsequent processing uses a declared origin and offset. These operations define the software time mapping but do not constitute a clock calibration. A candidate relative mapping is t_G=s+b+d(s−s_0), where b is an offset in seconds and d is a dimensionless relative frequency deviation. An observed marker difference also contains the signed difference in output/filter latency, differences in mechanical response and onset definition, and marker-selection error. A single marker identifies only an effective start-time difference under an assumed drift model; it cannot identify both clock offset and drift or isolate clock offset from fixed latency. Per-session marker records, applied offsets, and drift/latency estimates have not yet been fully established.

中文解释：对齐使用receiver P/V而不是fusion trace应明确。踢动尖峰、P/V起动是不同物理量，不保证相同峰值时刻；一次起点只能给有效差，不能凭此填每段drift或宣称GNSS同步。若只截公共起点而没有校正时轴，也须写明实际执行方式。

## C. Measurement model and propagation

The intended quantities are specified at a stated time, coordinate frame and physical point. For an ordered transverse baseline b=p_A2−p_A1, the projected heading is ψ_perp=atan2(b_E,b_N)+π/2 under the declared antenna/body-axis convention. Its local sensitivity is j_ψ=[−b_E/r²,b_N/r²,0], where r²=b_N²+b_E². The relative-position covariance is U_b=U_22+U_11−U_21−U_12, so shared receiver errors cannot be represented by summing marginal covariances alone. Vanishing horizontal projection makes the local heading sensitivity singular; a numerical nonzero-projection guard does not establish a practically acceptable uncertainty. Projected heading and Euler yaw are also distinct under general roll and pitch.

The historical horizontal-velocity provider is represented as z_H=kSĈMv_SDK, where M=diag(1,−1,−1) implements the declared FLU-to-FRD conversion and S selects the north/east components. Ĉ is an engineering orientation proxy formed from pre-generated baseline heading and SDK roll/pitch, including the frozen negative-pitch convention. It is not an independently calibrated attitude. With a right-multiplicative body-angle perturbation, the joint Jacobian contains A=kSĈM, B=−kSĈ[Mv_SDK]×, the scale sensitivity SĈMv_SDK and the time sensitivity ż_H. Propagation must retain velocity–attitude, scale, timing and other cross-covariance terms; different SDK fields are not evidence of independent errors. A point mismatch additionally requires a rigid-body velocity correction. Timing residual δτ=t_acquisition−t_nominal contributes local terms vδτ, aδτ and ψ̇δτ to position, velocity and heading, respectively, with the stated comparison direction.

中文解释：这是输入预算模型，不是本次已估joint covariance。未知frame不能用一个小角度sigma替代；先辨识frame/点位，再谈局部U。SDK速度还经A1旋转，与GNSS/prior有关。固定measurement std、工程比例和历史噪声调参都不自动成为标准不确定度。

## D. Shared reference and reporting limits

The commercial fused reference shares GNSS sources and potentially correction/environmental errors with the navigation method. Camera and internal-IMU participation do not remove this lineage. For a same-point, same-time and same-measurand difference d=z_m−z_r, the covariance is U_d=U_m+U_r−U_mr−U_rm. The measured difference alone cannot uniquely identify the method and reference uncertainties or their correlation. Consequently, the reported RMSE values remain empirical agreement metrics on their stated support; they are not instrument uncertainty estimates, and RMSE values cannot be linearly subtracted to remove common reference error. Unknown installation, timing, input covariance and correlation quantities are explicitly retained as unresolved budget entries. The analysis preserves the original V3 matrix and identifies later diagnostic versions separately.

中文解释：必须同时写reference与方法的cross；reference自身cov也不是已校准truth。共享reference下小RMSE仍有研究价值，但支持的是条件agreement，不能反推出absolute accuracy。

The eight newly supplied receiver packages contain recorded identity transforms between POI and VRTK in their FP_A-TF messages, as established by the separate checksum-verified metadata audit. This is evidence for those packages, not a tutorial default. It does not establish the output-point configuration of the older BY2/BY2H/BY2O recordings or the physical robot-to-sensor and antenna transforms.

中文解释：新八包实际message证明POI/VRTK同点同向；旧三序列与实物外参另核，不能回贴。

## E. Required validation: future tense only

A calibrated uncertainty claim would require session-specific timestamp semantics and marker records, independently supported geometry/point-of-measurement definitions, and justified joint input uncertainty information. Offset/drift fitting will require temporally separated timing information and held-out validation, with latency and mechanical-response assumptions stated. SDK frame/point interpretation and uncertainty propagation will be checked against independently characterized quantities where available; otherwise, correlation and model-discrepancy bounds will remain explicit. Validation will retain rejected/missing outputs and use appropriate session or dependence-aware statistical units. No such new calibration or estimator experiment was performed for this documentation block.

中文解释：这些是下一步协议，不可当已有Methods成果。现有八包实际配置可减少缺项，但不能逆向替旧三序列证明POI/时钟。TIM主张仍须展示有测量意义的创新及验证，不能只把导航RMSE表改标题成uncertainty。

## 关联资料

接口与作者事实：`OFFICIAL_INTERFACE_AND_AUTHOR_FACTS.md`；完整方程/定义：`TIM_MEASUREMENT_CHAIN_AND_CLOCK_MODEL.md`；输入项：`INPUT_UNCERTAINTY_BUDGET.csv`；验证：`MINIMAL_VALIDATION_PROTOCOL.md`。正式参考来源与选读范围另见`OFFICIAL_METROLOGY_SOURCE_MAP.csv`。
