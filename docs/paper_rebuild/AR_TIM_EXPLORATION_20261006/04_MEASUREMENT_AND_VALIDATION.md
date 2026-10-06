# 航向测量链、标准误差传播与最小验证

本节可用于现有论文的测量模型与局限说明。它给出**标准的几何投影和联合不确定度传播**，并完成独立合成检查；不把这些公式宣称为新理论，不把合成结果称为实机标定。若未来相对载波 AR 提供经过验证的短基线向量及其联合协方差，才可以在同一测量链下比较它与当前双位置差的差异。原 V3 成稿无需等待该探索。

本轮只运行一次 Ubuntu 22.04 WSL 合成验证进程；原始数据、参考轨迹、native navigation、evaluator 调用均为 0。种子、参数、软件环境及来源哈希见 [验证清单](measurement_validation/VALIDATION_MANIFEST.json)。合成清单的计数标签在审查中作元数据更正：15 个方位/ENU/顺序断言与 5 个倾角闭式断言分列；没有重跑或改动计算及结果数值。当前源码与运行时源码哈希均保留。另见 [源码与交付哈希](04_SOURCE_LEDGER.json)。本节复用既有 [23 项不确定度账本](../TIM_EVIDENCE_20261005/sdk_and_metrology/INPUT_UNCERTAINTY_BUDGET.csv) 和 [最小验证协议](../TIM_EVIDENCE_20261005/sdk_and_metrology/MINIMAL_VALIDATION_PROTOCOL.md)，没有另建假定已标定的预算。

## 1. 先区分现有实现的身份

| 环节 | 可审查的实际源码 | 当前含义 |
|---|---|---|
| 历史 BY2/H/O 的 A1 双位置差 | [final_v23_clean_input.py:255–383](../../../src/legsa_gins/paper_rebuild/final_v23_clean_input.py)；[status_yaw_builder.py:72–105,184–244](../../../src/legsa_gins/input_generation/status_yaw_builder.py) | 两接收机 status 的同名 N/E/D 相对位置相减；GNSS2 对 GNSS1 时间插值，原 exact 版本保留端点 hold。必须有共同参考原点/坐标系及明确时标；不是一次双接收机载波联合解算。 |
| 基线到角度 | [providers.py:118–187](../../../src/legsa_gins/paper_rebuild/providers.py)；exact builder:336–364 | GNSS2−GNSS1，机器人右侧天线指向左侧天线；NED 中 atan2(E,N)+90°；ENU 约定为 90°−该角。没有用参考轨迹选择正负号。 |
| 长度资格 | 同上:134–179；[clean5_sequence/provider_chain.py:72–94](../../../src/legsa_gins/paper_rebuild/clean5_sequence/provider_chain.py) | 旧 BY2 链为全组中位数 0.20–0.60 m、出现 3.5–4.5 m 回归即失败；单历元另打 in-band 标签。不能误写成所有旧 provider 都逐点用长度剔除。 |
| 历史 5 Hz GNSS18 的稀疏 A1 | [clean5_parity/providers.py:57–143](../../../src/legsa_gins/paper_rebuild/clean5_parity/providers.py) | GNSS1 HPPOSECEF/PVT 形成位置／速度；旧 1 Hz A1 来源时刻映射决定 yaw support。不能把此历史 GNSS18 行频率当成独立航向频率；它不是下行当前 V3 的最终 yaw 来源。 |
| 当前 protocol V3 的 5 Hz R5 航向 | [protocol_v3/providers.py:200–240,128–170](../../../src/legsa_gins/paper_rebuild/protocol_v3/providers.py)；[hext/t5a_provider.py:45–118,236–260](../../../src/legsa_gins/paper_rebuild/hext/t5a_provider.py) | 两接收机 RAW HPPOSECEF 的 exact iTOW 配对位置经共同固定 ECEF→NED，直接调用冻结 A1 几何变换；此路径不插值接收机位置。R5 要求 raw 对应且双方 PVT carrSoln=2；不受旧 1 Hz A1 support 限制。adapter 的 rel_acc=0 只是未参与角度变换的占位，绝不能当观测协方差。该 R5 函数没有逐点 0.2–0.6 m 长度门，不能套用 Jan5 R5 的门限描述。 |
| 冻结角噪声 | [clean6_sensor_v21/providers.py:27–29,220–238](../../../src/legsa_gins/paper_rebuild/clean6_sensor_v21/providers.py) | SIGMA_YAW=2.933193° 写入第 15 列；早期版本为 1.5°。这是冻结的工程观测参数，不是从完整两天线位置协方差逐历元传播出的校准标准不确定度。 |
| 原冻结 stage 与 10 月 4 日修正 | [gi_engine.cpp:971–1036](../../../cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp) | 仅 stage_id=IMU_V3_TIME_CONTRACT_FIX_20261004 使用倾斜侧向基线的投影预测和三分量姿态 Jacobian；其它冻结 stage 仍使用 Euler yaw 与 Hφz=−1。不能将后来的修正回贴原 V3。 |
| 运行时角度门与方差 | 同上:995–1036；[gnss_file_loader.cpp:129–163](../../../cpp/legsa_v23_port_core/src/fileio/gnss_file_loader.cpp) | deg→rad 后使用 wrap(pred−obs)；R 初值为冻结角方差，经 scheme/source-aware 放大。当前 C00 诊断配置的 min/soft/hard std 为 0.5/3/6°，残差 soft/hard 为 6/15°；这些是滤波规则，不是误固定率保证。 |
| 1 月 R5 是另一 provider 实现 | [run_new_sequences.py:38–79](../EXISTING_DATA_R5_20261005/new_data/run_new_sequences.py) | 两天线 HPPOSECEF 的同 iTOW 差经 ECEF→NED；yaw 要求双 FIX、HP 有效、逐历元长度 0.2–0.6 m。勿把其门限语义混同上述旧中位数门。 |

历史 status 差分的相对位置字段必须有共同原点；若两向量各自引用不同基站坐标，则不能不经转换直接相减。既有物理长度检查只能支持已审查安装的几何一致性，不能证明共同原点、误差相关性和 carrier state 都正确。主三窗与 R5 的实际 FIX/FLOAT 准入事实分别见 [主窗统计](../HEADING_REASSESSMENT_20261006/PROVIDER_FIX_COUNTS.csv) 和 [R5 补充](../HEADING_REASSESSMENT_20261006/R5_FLOAT_ADMISSION_NOTE.md)。

## 2. 同量定义：侧向基线投影角不总是 Euler yaw

令 C=C_b^n 表示机身 FRD 到当地 NED；l_i 为 IMU 原点到第 i 天线相位中心的机身向量。同步且刚性安装时：

$$
p_i^n=p_I^n+C l_i,\qquad
b^n=p_2^n-p_1^n=C d^b,\quad d^b=l_2-l_1.
\tag{1}
$$

当前名义安装是 d^b=[0,-L,0]^T。令 b=[b_N,b_E,b_D]^T，r=sqrt(b_N²+b_E²) 为**水平投影长度**，观测定义为

$$
z_A=\operatorname{wrap}\!\left[\operatorname{atan2}(b_E,b_N)+\frac{\pi}{2}\right],
\qquad z_{\mathrm{ENU}}=\operatorname{wrap}\!\left(\frac{\pi}{2}-z_A\right).
\tag{2}
$$

若 C=R_z(ψ)R_y(θ)R_x(φ)，则在有定义的投影上：

$$
z_A=\operatorname{wrap}\left[
\psi+\operatorname{atan2}(-\sin\theta\sin\phi,\cos\phi)
\right],\qquad
r=L\sqrt{\cos^2\phi+\sin^2\theta\sin^2\phi}.
\tag{3}
$$

因此只在相应姿态条件下，z_A 才等于 ZYX Euler yaw。合成例 φ=15°、θ=10°、ψ=37°，z_A=34.3360°，差 −2.6640°；这不是从实测参考反推的安装修正。10 月 4 日分支直接预测式 (2)，比把观测先误称为任意姿态下的 Euler yaw 更准确。真实安装存在非零 d_x/d_z 时应使用式 (1) 的实际 d^b，不能凭名义高差、经验 offset 或参考残差替代标定。

## 3. 双接收机误差的交叉相关必须保留

令两个同步、同坐标系的天线位置误差为 e_1、e_2。对同一条件状态，其联合协方差是

$$
U_p=
\begin{bmatrix}U_{11}&U_{12}\\ U_{21}&U_{22}\end{bmatrix},\quad
U_b=[-I\ \ I]U_p[-I\ \ I]^T
=U_{11}+U_{22}-U_{12}-U_{21}.
\tag{4}
$$

共同改正数、共同传播误差、共同基站和环境均可能产生相关性。只有两个边际 reported accuracy 值不能辨识 U12；不能默认它为零，也不能把对两标准差取 max、hypot 或对插值标准差线性插值当成联合协方差传播。先在 ECEF 求差时，若当地旋转可视作已知，应对 U_b 同时作 R_e^n U_b^e (R_e^n)^T 变换，其中 R_e^n 明确定义为 ECEF 分量到 NED 分量的旋转；当地框架本身不确定时再将其加入联合输入。

对式 (2) 的位置 Jacobian 为

$$
g_b=\frac{1}{r^2}[-b_E,\ b_N,\ 0],\qquad
u_A^2\simeq g_bU_b g_b^T.
\tag{5}
$$

以上是 GUM 的相关输入一阶传播在本几何下的展开，不是新估计理论。[JCGM 100 §5.2](https://www.iso.org/sites/JCGM/GUM/JCGM100/C045315e-html/C045315e_FILES/MAIN_C045315e/05_e.html)

设 t_perp=[−b_E,b_N,0]^T/r，s_i²=t_perp^T U_ii t_perp，ρ为该方向的接收机误差相关系数：

$$
u_A^2\simeq
\frac{s_1^2+s_2^2-2\rho s_1s_2}{r^2},\qquad
\frac{|s_1-s_2|}{r}\le u_A\le\frac{s_1+s_2}{r}.
\tag{6}
$$

后一个范围仅是给定可信边际且 |ρ|≤1 的单项数学界；它不涵盖时间、安装、错固定等未建模项。共同误差在差分中可能消去，这正是“绝对位置误差／FIX 标签”不能直接替代相对航向质量的原因。若能得到有独立检查值的基线向量误差，可直接估计该条件下的 U_b；无需假装已经分别辨识完整 U11、U22、U12。

**0.35 m 水平基线的直观预算：**

| 目标角标准不确定度 | 允许的横向差分位置标准不确定度 |
|---|---:|
| 1° | 6.108652 mm |
| 0.5° | 3.054326 mm |

这里使用 u_perp≈r u_A，角度先转弧度；只计算这一项、小角条件，尚未给其它来源分配预算。它说明相对载波基线求解可能有价值，但既不证明本设备达到毫米级，也不证明移动基线 AR 已成功。实际数值在 [ANGLE_TARGET_BUDGET.csv](measurement_validation/ANGLE_TARGET_BUDGET.csv)。

## 4. 与当前误差状态反馈一致的符号

10 月 4 日实现采用 C_true=Exp(δφ)C_nominal，残差为 h(C_nominal)−z。由 δb=−[b]×δφ 可得

$$
\frac{\partial h}{\partial\delta\phi}=-g_b[b]_\times,\qquad
H_{\phi}=g_b[b]_\times
=\left[\frac{b_N b_D}{r^2},\frac{b_E b_D}{r^2},-1\right].
\tag{7}
$$

Hφ 是**残差对误差状态的系数**，与预测函数的导数相反；两者不可混写。式 (7) 对应 gi_engine.cpp:989–990，不是把三个姿态角的 Euler 导数直接塞入误差状态。有限差分按实际左乘扰动、wrap-safe 差分独立检查，最大误差 3.20e−9；位置 Jacobian 最大误差 4.70e−9。软件中 r²>1e−12 的检查对单位基线只是数值定义域检查，不能推出角精度达到实用要求。

## 5. 异步运动、杆臂及安装项

若天线 i 的物理采样时间为 t+δτ_i，则一阶差分污染为

$$
\delta b_\tau\simeq
-v_1^n\delta\tau_1+v_2^n\delta\tau_2,\qquad
v_i^n=v_I^n+C(\omega^b\times l_i),\quad
J_\tau=[-v_1^n\ \ v_2^n].
\tag{8}
$$

同步时公共 IMU 到安装面的平移从基线中消去；异步时杆臂速度一般不会消去。目标历元选在第一个天线时刻还是两者中点，也会改变展开中各 δτ 的定义；不能只把两个时间标签改成相同字符串。单纯双接收机记录标签相差 7–8 ms，尚不能直接认定式 (8) 的物理 δτ 就是 7–8 ms，必须先解决 RAWX receiver clock、时间尺度及观测量改正的一致性。u-blox 的移动基线接口也明确要求匹配观测时刻，且不匹配时可输出无效相对位置；这不是对当前记录已满足条件的证明。[u-blox Integration Manual §3.1.5.6、§3.12](https://content.u-blox.com/sites/default/files/ZED-F9P_IntegrationManual_UBX-18010802.pdf)

一个**纯假设**的物理错时例：r=0.35 m、垂直于水平基线的速度=0.5 m/s、δτ=8 ms，则一阶角误差 0.654809°，精确 atan2 为 0.654780°。它只解释灵敏度，不把原日志时差估成了真实误差。完整表在 [TIMING_SENSITIVITY.csv](measurement_validation/TIMING_SENSITIVITY.csv)；包含转动杆臂的时间 Jacobian 有限差分最大差 2.78e−10。

对机身安装向量误差 δd，以及小安装旋转 δα，可写 δb_l≈Cδd−C[d]×δα。把天线、时间、安装等组成 x，令 J=[g_bD, g_bJτ, g_bC, −g_bC[d]×,…]，完整一阶预算应是 J U_x J^T，保留交叉项；只有已有依据证明独立时才能改写为平方和。固定安装偏差在同一次安装的所有历元共享，不会因为高采样率自动按 sqrt(N) 消失。对应既有 U01–U06、U09、U11–U13；本节没有估计这些未知量。

## 6. 长度门与单个 Gaussian R 的边界

若正确解与错误固定解混合，条件误差分布可写
p(e)=(1−π)p_c(e)+πp_w(e)。在选定且未跨角分支的局部误差坐标中：

$$
\operatorname{MSE}(e)=
(1-\pi)(\sigma_c^2+\mu_c^2)
+\pi(\sigma_w^2+\mu_w^2).
\tag{9}
$$

即使两个分布都很窄，错误分量的偏置也可主导 MSE；跨 ±π 应使用圆周误差/完整分布而非硬展开。FIX 是接收机或解算器的决策标签，不能充当“整数必正确”的证明。长度约束最多排除部分不合理候选；相同长度的错误方向仍可能通过。它也不能修复近竖直情况下 r→0 的退化。

合成混合例预设 π=1%、错误方向偏置 20°、两分量条件标准差均 1°，每个向量长度都保持 0.35 m。200,000 次样本的长度门通过率 100%，角 RMS 为 2.2233°，理论混合 RMS 为 2.2361°，|误差|>10° 比例 0.988%；±1.96° 覆盖为 94.09%。这是故意构造的**错误方向混合模型**，不是在这些 GNSS 原始观测上运行 AR，也不是估计设备真实错固定概率。[WRONG_FIX_MIXTURE.json](measurement_validation/WRONG_FIX_MIXTURE.json)

## 7. 已实际执行的合成验证

固定 PCG64 seed=20261006，每个 Gaussian 场景 N=200,000；每接收机各轴 σ=10 mm，跨接收机 ρ按表设置，其余跨轴为零。全部参数是事前情景输入，没有读参考或调参。这里的 Monte Carlo 是假定分布传播，不是实际不确定度验证；这与 JCGM 101 的适用范围一致。[JCGM 101](https://www.bipm.org/en/doi/10.59161/jcgm101-2008)

| 合成场景 | r (m) | ρ | 一阶 u_A (°) | MC wrapped RMS (°) | 解释 |
|---|---:|---:|---:|---:|---|
| 水平 L=0.35 m | 0.3500 | 0 | 2.3151 | 2.3202 | 小角传播通过 |
| 同长度、正相关 | 0.3500 | 0.75 | 1.1575 | 1.1583 | 差分共同误差部分抵消 |
| 同长度、负相关 | 0.3500 | −0.5 | 2.8354 | 2.8427 | 不能只由边际确定航向方差 |
| L=0.70 m 条件对照 | 0.7000 | 0 | 1.1575 | 1.1555 | 仅长度灵敏度，不是0.35 m装置的采集结果 |
| roll=60°，L=0.35 m | 0.1750 | 0 | 4.6302 | 4.6401 | 三维长度不变、投影减半 |
| roll=89°，L=0.35 m | 0.0061 | 0 | 132.6521 | 86.3904 | 小角传播失效；长度门仍100%通过 |

前五个事前小角场景的 MC 与一阶值相对差均<0.3%，通过事前3%检查；近竖直场景明确作为失效边界保留，未放宽门槛把它改成“通过”。源码另检查 5 个姿态下的位置与误差状态 Jacobian、倾角闭式关系，以及方位、ENU、换天线顺序与角度 wrap。结果和参数分别见 [GAUSSIAN_PROPAGATION.csv](measurement_validation/GAUSSIAN_PROPAGATION.csv)、[JACOBIAN_CHECKS.csv](measurement_validation/JACOBIAN_CHECKS.csv)、[TILT_MODEL.csv](measurement_validation/TILT_MODEL.csv)、[PARAMETERS.json](measurement_validation/PARAMETERS.json)。

## 8. 最小实测设计：沿用既有账本，不伪造缺失项

| 既有账本 | 现有日志可完成 | 最小外部检查／仍不能声称的内容 |
|---|---|---|
| U06、U01–U05：时标 | 审 week/TOW/iTOW、有效位、时钟复位、配对残差及实际支持；区分时间标签与物理 epoch | 记录开始/中间/结束至少三个独立可观测时间事件，其中一段留出。若只有一个 kick，不能分离 clock offset、drift、传感延迟与机械响应。需同步信号/独立时标或有不确定度的事件定义。 |
| U07–U09：位置及交叉 | 核实际 reported accuracy、common reference/corrections、baseline 分布；给相关性敏感性 | 用有不确定度、独立于主要 GNSS 输入误差的基线方向/长度或天线位置检查量。至少两个水平朝向、水平与一个非零 roll/pitch 姿态，可辨轴序与倾角模型；不能把厂商边际值自动当完整 U_b。 |
| U11–U13：安装与点位 | 核天线顺序、声明 d/l、配置版本，计算 nominal 几何的灵敏度 | 登记相位中心与 IMU 敏感中心，测量 d^b 与坐标安装。至少两个独立重新安装/时段用于区分固定安装项与重复测量项；这些少量块只验证机制，不支持广泛泛化。 |
| U10：错固定与资格 | 保留全部候选、ratio/残差、FIX/FLOAT/invalid、长度及 r、无输出分母 | 在独立方向检查下事前定义不一致事件，按独立 session/block 报告。没有外测不能从FIX标签测出错固定概率；连续epochs不是独立试验，不能以零观测错误承诺高完整性。 |
| U21–U23：参考和统计 | 明确商业融合参考的共享 GNSS 来源、输出点及时间；保留 rejected/no-output | 用未用于安装参数、时间参数或阈值选择的块作验证；报告参考 U 与共享来源。只有共享参考时仍称 agreement；不称 absolute accuracy 或校准通过。 |

建议先完成这些最小、能区分模型的块，再按目标 u_A 将外部检查能力写成预算。上表数量是本项目的最小设计建议，不是标准或期刊强制次数，也不代表已经采集。没有相应外部记录时，止于“条件模型 + 灵敏度 + 已知输入支持”；不等待它们补齐也可以诚实完成 V3 现有结果稿。

## 9. 可直接入稿的表述

> The dual-antenna observation is the azimuth of the ordered lateral baseline after a fixed frame conversion, rather than the ZYX Euler yaw at arbitrary roll and pitch. Its first-order angular uncertainty depends on the horizontal projection of the baseline and the joint errors of the two antenna positions: \(u_A^2 \simeq g_b(U_{11}+U_{22}-U_{12}-U_{21})g_b^\mathsf{T}\), where \(g_b=[-b_E,b_N,0]/(b_N^2+b_E^2)\). The implemented observation noise is a frozen engineering parameter; the receiver cross-covariance, timing and mounting uncertainties have not been independently calibrated. Synthetic checks verify the projection and error-state Jacobians and illustrate the limits of first-order propagation, but do not establish real-world uncertainty coverage or ambiguity-fix integrity.

与旧冻结结果配套时，再明确其采用 Euler 近似；只有对应 10 月 4 日修正 stage 的结果才能描述为已执行完整投影模型。本公式为标准传播关系，本工作的价值若成立，应来自经过证据支持的测量资格、时间/几何处理与可靠性机制，而不是公式本身。

复现：

```bash
python3 scripts/paper_rebuild/ar_tim_exploration_20261006/measurement_validation.py \
  --code /home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001 \
  --out /tmp/AR_MEASUREMENT_VALIDATION_RECHECK
```
