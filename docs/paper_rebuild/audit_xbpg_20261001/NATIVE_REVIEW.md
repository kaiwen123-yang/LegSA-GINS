# 原生求解链语义审查与可复现实验

本报告审查 `cpp/legsa_v23_port_core` 的 **56 个自有 cpp/hpp、11,475 行**，并审查 `cpp/CMakeLists.txt` 的 81 行。56 个文件已逐文件读完并完成本报告所列函数/连续语句组的语义审查；这不是其余 C++、Python 或全仓已审完的声明。动态测试是有界反例、有限差分、集成和回归，不能理解为全部分支测试完毕。逐文件身份和真实深度见 `NATIVE_COVERAGE.csv`；独立问题见 `NATIVE_FINDINGS.csv`。新增脚本、原生测试均在本轮目录，正式求解器未改。

## 1. 主要结论和证据边界

1. **辅助观测在 GNSS 全失效时失去调度（N09）。** 两个真实可执行文件分别走 config→loader→runtime→GIEngine，在完整合成输入中每种观测各更新 10 次；仅将 GNSS 三项 validity 全置零，RD/RP/HV 即使各有可用 provider，也全部变为 0 次。100 个 IMU 传播和 100 个有限 NAV 仍然成功输出。这是调度缺陷，不是“辅助数据也自然缺测”。
2. **顺序更新的 SA NIS 用了 `dz`，未用实际创新 `dz-Hdx`（N12）。** 原生构造 `dz=1,Hdx=1,S=2`，应为 0，实际报告 0.5。真正 EKFUpdate 使用正确创新且使用 Joseph 更新；错误在权重决策层。多个源顺序融合时会影响 OIM 缩放/拒绝。
3. **异步杆臂速度会用未补偿当前 IMU（N11）。** res=1/3 更新时 `imucur_` 尚未补偿，res=2 已补偿。纯陀螺 bias 的反例在 res=1 产生 0.152882 m/s 假杆臂速度，res=3 的 Hφ Frobenius 同为 0.216208，res=2 为 0。真实影响与安装杆臂、估计 bias/scale、触发分支有关。
4. **输入防护和失败证据有可复现缺口。** Matrix 列越界落入下一行（N04）；Inf/巨大有限角 wrap 不返回（N05）；`1e-16 I` 逆被拒绝、NaN 逆被传播（N06）；坏/缺失 provider 数值能成为零观测并实际更新（N15）；covariance health 只查对角，允许不定矩阵和非对角 NaN（N13）；普通 writer 打开失败可返回成功，STD 把负数/NaN 对角转成 0（N19）。这些输入级缺陷的存在不等于历史正常运行已经触发它们。
5. **倾斜时横向基线投影加 90° 不是 Euler yaw（N01）。** 原生旋转在 roll=0.3 rad、pitch=0.4 rad、yaw=1.1 rad 下差 −6.868822°。C++ 没有 provider 倾斜补偿信息，是否在上游消除须结合 provider 审查裁定。标量 Euler yaw 的 H=[0,0,−1] 是小 pitch 近似（N02）；不能因为 B3 雅可比正确就认定标量链正确，也不能据此认定 B3 在真实数据更好。
6. **已反证的过度结论：** 当前 B3 的雅可比符号正确；单基线绕自身轴的零空间精确存在；标量 yaw 在 pitch=0 和 ±180° 跨界的符号/一阶导数正确；位置 H 的初次微小差异主要是 BLH 有限差分消减，步长扫后最大误差 2.47e−7；Joseph 更新在 2,000 次独立已知噪声的零杆臂 RV 线性试验中满足所测 NIS/NEES 均值与 SPD。不能把这些局部反证扩大为整个非线性惯导系统通过。

源码数学审查与构建身份已闭合到本地原生目标；正式 provider→物理点→独立评价的整体闭合由总报告负责。以下结果全部为 **synthetic**，真实数据打开次数 0，参考轨迹打开次数 0，未将任何合成数值写入实测结果表。

## 2. 当前、正式冻结与候选的身份

|角色|源码/二进制|核实结果|
|---|---|---|
|本轮审查源码基线|`eb3cbed314693358c7c38442b6fbbb7afcf0342e` 下 port core|审查工作分支后续只加审查材料；正式 cpp 未改。逐文件 Git blob 和 SHA256 见 CSV。|
|本轮原样 Release 构建|SHA256 `cbf554baf9c83490e40b207b97f04ef77f51d9962f7bce463f1e644416ef789e`|GNU g++ 11.4.0，CMake Release，构建 −j4，数值线程 1；实际 `legsa_v23_port_core_demo` 链接成功。|
|正式旧二进制|SHA256 `96ae436d82ba8922c68382bd73fc42c8bf4bcb22d72a43a8bd05f506043a9c1c`|主审从活体和 BINARY_FREEZE 核实；metadata source 为 `ca73cb1fb48a020fd2a450d79e520562c34eeb24`。本分审每次调用前核对该 SHA。|
|正式源码→当前源码|`git diff ca73cb1..eb3cbed -- cpp/legsa_v23_port_core`|11 文件、444 增/9 删，为可选 B3 接口/解析/更新/输出；这里列出的非 B3 原始数学与输入问题存在于两份源码。当前 B3 不是旧正式算法的身份。|
|数值防护候选|`NATIVE_CANDIDATE_NUMERIC.patch`，binary `f498eeece34611a4496e13b4a4ccb235e35dbbdf992c1a61ab69f54741ebbb54`|仅 isolated cpp 副本增加 Matrix 二维边界及 Rotation 有限/有界 wrap；未安装、未替换正式算法。|

当前/旧二进制在六个已有 synthetic/toy 模式的 18 个 NAV/STD/EVAL_NAV 文件逐字相同；在两个新增 config/file-loader/runtime 合成用例中的 6 个文件也逐字相同。这是 **24/24 个特定输出的正常输入回归证据**，不是“所有科学输入必然等价”的证明。不同编译环境导致哈希不同本身不证明科学算法不同；这里另有源码差分和相同输入实际数值关系。

旧/current 六个 toy 路径的原生 manifest 都错误保留 `data_mode=""` 和 `synthetic_data_used=false`（N20）。本审查外层 receipt 明确记录 synthetic，避免该错误污染数据角色。原生 manifest 的 `source_commit` 固定为上游 `5a4471e...`，并不能指认构建树。`actual_solver_input_paths` 由 options 回显，并非 open 系统调用证据；硬编码 false 的 trace/reference 标志也不能排除上游把参考值写入 provider。

## 3. 坐标、状态、测量与独立推导

### 3.1 状态约定与物理点

`types.hpp:38–65` 定义 δx=[δp,δv,φ,δbg,δba,δsg,δsa]，每组 3 维，P/V/PHI/BG/BA/SG/SA 索引为 0/3/6/9/12/15/18。位置误差为 NED 米，速度为 NED m/s，姿态误差为导航系左乘旋转向量 rad；bias 单位 rad/s、m/s²，scale 无量纲。名义状态位置为 BLH（rad,rad,m），高度向上；`DR=diag(Rm+h,(Rn+h)cosL,−1)` 将 BLH 差转换成 NED 米。`Cbn` 是 body→NED，body 输入按 FRD 使用；native 不再做 FLU→FRD。四元数顺序 w,x,y,z，ZYX 的 Euler 顺序 roll,pitch,yaw。

`stateFeedback:480–509` 做 p←p−DR⁻¹δp、v←v−δv、C←Exp(φ)C、IMU bias/scale←原估计+δ。故局部测量推导使用 C_nom=Exp(−φ)C_true，p_nom=p_true+DR⁻¹δp，v_nom=v_true+δv，b_nom=b_true−δb。不能换用另一种扰动定义后凭符号对照判错。

位置观测预测 GNSS1 天线相位中心：p_ant≈p_IMU+DR⁻¹Cbn l_b，残差 DR(p_ant−p_GNSS)，H_p=I，H_φ=[Cbn l_b]×。线性地理杆臂近似忽略 O(l²/R_E)；亚米 l 的位置误差量级 <1e−7 m。评价参考若是 POI，需要另一个已知 `l_IMU→POI`；native writer 不做此转换。BY2 安装值不能成为 XB 标定。

### 3.2 标量双天线与 B3

若物理横向向量 GNSS2−GNSS1 在 FRD 为 b=[0,−L,0]，n=Cbn b。固定加 90° 的投影航向为 α=atan2(n_E,n_N)+π/2。对普通姿态 cos roll>0：

`α−ψ = atan2(−sin(pitch) sin(roll), cos(roll))`。

因此仅 pitch 或仅 roll 非零时可巧合为 0，同时倾斜时通常不为 0。L 消掉，不由基线长度统计恢复安装方向。两天线反序会翻转 n；必须从安装与采集身份确定，不能看 reference 误差择符号。近竖直 n_N²+n_E²→0 时 α 不可观。

一般投影方位的梯度为 `g=[−n_E,n_N,0]/(n_N²+n_E²)`；当前扰动下 H_φ=g[n]×=[n_N n_D/r²,n_E n_D/r²,−1]。若实际测量是前向 Euler yaw，则将 n 换为 Cbn e_x，得到 `H_ψ=[−cosψ tanθ,−sinψ tanθ,−1]`。`applyYawUpdate:968` 和 `applyBasicDualYawUpdate:1012` 使用 [0,0,−1]，只有 θ≈0 时近似成立；原生 FD θ=0.4 时遗漏最大 0.376796。θ=0 的三组含 ±179.99° 案例误差 ≤2.23e−10，已排除“始终错号”和“正常跨界一定错”的说法。

`baseline3d.cpp:10–29` 实现 h=Cbn[0,−L,0]，r=h−n_obs，H_φ=[h]×。FD h=1e−6 的最大误差 3.42e−11；H_φ h=0 精确成立。单基线提供两维姿态约束，不独自提供绕基线转角。R=k_b²(pAcc1²+pAcc2²)I₃ 要求各接收机误差可当各向同性、每轴 std 且互相独立；一般应为 Σ1+Σ2−Σ12−Σ21，并考虑共同GNSS信息。pAcc 的原始定义必须由 decoder/device 文档闭合。位置与差分基线也不独立：若位置用 p1、baseline=p2−p1，则 Cov(p1,baseline)=Σ12−Σ1。三个残差分量的 S 可以满秩，H 的秩 2 **不自动意味着 NIS 应改成 χ²₂**；在所假定满秩三维噪声模型下 χ²₃ 才相配。真实统计适用性另需检验。

`applyBaseline3dUpdate:1021–1116` 的专用 NIS 确实用 dz−Hdx、S=HPHᵀ+R_QA，阈值 11.34、3 自由度；后续 SA 层仍有 N12 的 dz 问题。B3 质量/长度/准确度/时间字段的严格读取由 loader 和本体共同负责；现有 13 个 B3 pytest 加其他 math tests 共 21 项通过，不构成真实安装或 covariance 模型验证。

### 3.3 IMU、机械编排与 21 维传播

IMU 文件是 7 列增量：t,Δθx,Δθy,Δθz,Δvx,Δvy,Δvz；不是 rate。loader 由相邻接受行算 dt，首行沿结构体默认 dt。补偿 `(Δθ−bg dt)/(1+sg)`、`(Δv−ba dt)/(1+sa)` 逐轴进行，`compensated` 防正常路径二次补偿；−1 scale、非有限值和非正 dt 未统一拦截（N14/N24）。

`insmech:18–78` 按 vel→pos→att：旋转/划桨项包括 1/2 Δθ×Δv、1/12 上一与当前交叉项；重新计算中间纬高、地球率和运输率；速度中有 g−(2ω_ie+ω_en)×v；位置平均速度经 DR⁻¹ 积分；姿态为 Exp(−(ω_ie+ω_en)dt) C_prev Exp(Δθ+1/12 Δθ_prev×Δθ)。这些 1/12 双样本系数有等间隔/平滑变化前提；乱序、长缺口或 res=3 切分后不等间隔未重新推导，不能笼统称任意采样下等价高阶积分。`propagateOneStep` 用相同一帧当 prev/current，交叉项退化，是便利路径，不等同真实两样本历史。

`gi_engine:811–850` 中非零 F 块是：

|块|当前值|依据/限制|
|---|---|---|
|F_pv|I|局部位置误差积分|
|F_vφ|[C f]×|由 −φ×Cf 推得，符号正确|
|F_vba,F_vsa|C,C diag(f)|bias/scale 当前线性补偿约定|
|F_φφ|−[ω_ie+ω_en]×|导航系误差旋转|
|F_φbg,F_φsg|−C,−C diag(ω)|由 C_nom 右侧 gyro 误差推得|
|bias/scale 对角|−I/τ|一阶 Gauss-Markov；τ 被下限截为 1 s|
|G_v,VRW 与 G_φ,ARW|C,C|独立白噪声 covariance 下 gyro 符号不改 GQcGᵀ|
|G 的四个参数噪声块|I|Qc 对应 2σ²/τ|

其余全为 0，不是完整旋转地球 NED 误差方程。即使忽略运输率，名义速度中已有 −2ω_ie×v，它的导数 F_vv=−2[ω_ie]×；高度重力梯度给 F_vD,pD≈+3.1e−6 s⁻²。当前均缺失，rmh/rnh 算后直接 `(void)`（N17）。ω_ie=7.29e−5 rad/s，忽略 Coriolis 的传播算子累积尺度约 2ωT，在 T=10 s 时 0.00146、T=300 s 时 0.0438；不是等量位置/RMSE，也不是足以直接宣布发散。要支撑“完整 KF-GINS 传播”，须补全推导或明确短时近似，并用真实 dt 范围、停更时长量化。Phi=I+Fdt；Qd=dt/2(ΦGQcGᵀΦᵀ+GQcGᵀ)，若 Qc 正半定、dt>0 则该噪声离散式正半定，但未包含更高阶转移项。

### 3.4 各观测、相关性与权重

RV/RD 均预测 `v_ant = v_IMU + C(ω_ib×l)`；H_v=I、H_φ=[C(ω×l)]× 在所实现模型内 FD 最大 1.52e−10。相对地面的刚体杆臂速度更严格应使用 ω_nb，遗漏地球/运输率项对 0.3 m 杆臂量级约 2.2e−5 m/s，通常小但必须说明。补偿后的 ω 对 δbg/δsg 的导数却也被置零：H_bg=−C[l]×diag(1/(1+s_g))、H_sg=−C[l]×diag(ω/(1+s_g))。原生反例缺失最大 0.252182 m/(rad/s) 与 0.113399 m/s/scale（N18）。RV 的 std 是 `(provided_std+0.05)*scale` 后平方，不是额外独立噪声方差 0.05² 相加；RD 是 provider std² 乘 `raw_doppler_R_scale`。

RP 弱先验为 roll/pitch 圆周残差。`go2_weak_prior_factor:31–48` 在当前扰动下 Jacobian 的 sec(pitch) 型表达在温和姿态正确；但 sec 绝对值限制为 2，75° 测试一项误差 −0.845369（N22），故这是保护性近似，不是全姿态精确测量。R 最终使用 config 的 roll/pitch std；CSV std 参与有效性和 SA metadata，不直接代替 R，必须区分“读取了”与“真正用于噪声”。

HV 在 `horizontal_2d` 模式只取 N/E 两维，H=I_v 的前两行，R=diag(stdN²,stdE²)×scale²，FD 2.88e−11。但 metadata 把关闭的 vertical std 写成 999，再由 `maxStd` 当有效 std 比较 >10，固定触发 LSIM 至少 2 倍（N16）。只改 `vertical_disabled`，同一观测 R00 从 6 到 8；分母 6 还有 fixture 质量默认的 1.5 倍，但额外改变确来自哨兵。应该让权重只统计实际观测维度。

Go2 RP/HV 常来自同一个内部融合器；若 propagation IMU 也是同一机器人数据，误差会相关；RV/RD/GNSS position 也可能同接收机共享时钟、卫星、滤波和轨道。现有顺序更新没有这些跨源互协方差。R inflation 可以降低重复信息权重，但不能自动证明一致性，不能称独立观测数增加。来源链和 XB 上游身份由数据审查继续闭合（N10）。

### 3.5 更新、NIS、reset 与 covariance

`EKFUpdate:458–477` 使用 S=HPHᵀ+R，K=PHᵀS⁻¹，dx←dx+K(dz−Hdx)，Joseph `P←(I−KH)P(I−KH)ᵀ+KRKᵀ`。顺序观测同名义状态线性化并保留 dx 的方式本身成立；正是因为 dx 保留，SA 层再用 dz 计算 NIS 才不一致（N12）。S 使用未缩放 R 来决定权重是可定义的设计，但必须说明，与最终更新的 S 不同。

2000 次**独立**零杆臂、已知 Gaussian 速度 prior/measurement 的原生更新，R=diag(0.25,1,4)、P_v=I、seed=20261001，无门控：mean NIS=2.986458，posterior velocity NEES=3.046883，均在理论均值 3 的约 95% 均值区间 3±0.107354 内；所有 posterior Cholesky 成功，最小 pivot=0.2。它只检验三维线性 RV/Joseph/反馈，不是全 21 维非线性 NEES，且不拿真实商业 reference 当真值。

反馈后 Cov 完全不改（测试 maxdiff=0）。由 C_true=Exp(φ)C_nom、C_new=Exp(φhat)C_nom，新的误差 `log(Exp(φ)Exp(−φhat))≈J_l(φhat)(φ−φhat)`，其中 J_l≈I+0.5[φhat]×。因此若 P 是旧加性 tangent 后验，应做 reset covariance；忽略它是 O(|φhat|P) 的近似，小校正可很小，大校正/多次反馈可能影响一致性（N08）。不能仅见“没有 reset”就判整个姿态符号错误或直接宣布历史结果全部无效；本轮未量化真实 φhat 序列。

`checkCov:547–553` 不查全部元素、对称或 PSD；[[1,2],[2,1]] 块的负特征值 −1 仍 PASS，非对角 NaN 也 PASS（N13）。这使 runtime 的 fail-closed 覆盖不完整。常规四类 10 s/1000 步集成实测 P 有限、最大非对称 9.1e−13，不能由此把未检出的病态也说通过。

## 4. 逐文件、逐函数/关键连续语句组解释

以下路径均相对 `cpp/legsa_v23_port_core/`。声明文件与其所有实现一起审查；纯存取器、字段序列与 serialization 样板合并列示，不把函数枚举当语义结论。

### 4.1 基础类型、旋转、地球

|文件/行组|语义、输入输出与异常|
|---|---|
|`include/.../types.hpp:18–129`|Vec3/Matrix3 为固定数组，Quaternion wxyz；Matrix 动态行列+flat data；21 状态/18 噪声索引；声明加减乘、transpose、inverse、block，没有类型级单位/坐标校验。|
|`src/common/types.cpp:16–25`|分配 rows×cols；两个 `operator()` 只查 flat `.at`，列越界被下一行吸收（N04），乘积溢出也未守卫。|
|`types.cpp:28–158`|三维 norm/dot/cross、单位矩阵、向量/3×3 加减缩放乘转置、逐轴乘除；无零除/非有限保护，调用者须给有效尺度。|
|`types.cpp:160–225`|动态 Matrix 加减/矩阵乘/矩阵向量乘、identity/diag/transpose；维数不合抛 `invalid_argument`，正确维度下 triple loop，没有 BLAS 隐性多线程。|
|`types.cpp:227–277`|Gauss-Jordan 列主元交换、每行归一、消去；非方阵异常；绝对 pivot<1e−15 抛 singular，无输入有限性/相对条件检查（N06）。|
|`types.cpp:280–314`|setBlock/block/identity block 依赖上述下标；block 尺寸也需验证，flat 列越界可能静默改错块。|
|`include/.../common/rotation.hpp:16–39`|无状态 rotation 工具接口；只有名称提示 Euler/quat，单位为 native rad。|
|`rotation.cpp:15–65`|normalize、quaternion product、matrix→quat；product 总会normalize；极大quat范数平方溢出返回全零（N24）；rotation matrix 非正交未检查。|
|`rotation.cpp:67–105`|quat→matrix、matrix→Euler；常态 ZYX atan2；|C20|≥0.999 时把roll置0，但pitch尚非90°，不能保持原旋转（N07）。|
|`rotation.cpp:107–145`|rotvec→quat 小角分支、quat→最短旋转向量、Euler→quat/matrix；长度/finite输入无统一校验。|
|`rotation.cpp:147–173`|skew、qleft/qright Hamilton乘法矩阵，兼容别名直接转发；不新增坐标转换。|
|`rotation.cpp:175–192`|wrap 保留 ±π 双端点或 [0,2π)；逐周while对Inf/巨大值不收敛（N05）。|
|`include/.../common/earth.hpp:17–43`; `earth.cpp:17–131`|WGS84半径/重力；NED→ECEF Cne；qne与逆BLH；BLH/ECEF；DR/DRi；地球率 [ΩcosL,0,−ΩsinL]、运输率 [vE/(Rn+h),−vN/(Rm+h),−vE tanL/(Rn+h)]。高程向上、D向下；纬度极点、ECEF原点和cosL≈0无专门有效域，当前中纬度用途条件成立，不是全球无条件数值保证。|

### 4.2 核心状态、配置与入口

|文件/行组|语义、调用者、有效参数|
|---|---|
|`include/.../nav_state.hpp:16–25`|时间、BLH、NED速度、Euler/quaternion/matrix及IMUerror同存；没有自动一致性约束，initialize/feedback/mech负责同步。|
|`include/.../imu.hpp:16–24`|增量、dt和compensated标志；非正dt不在结构中拒绝。|
|`include/.../gnss.hpp:16–35`|GNSS1位置/速度、scalar yaw deg/rad双份、std及显式validity；legacy15列默认all-valid，B3 sidecar另字段。|
|`include/.../options.hpp:23–208`|科学参数、运行身份、模块开关和结果计数混存；默认scalar；RP/HV/RD/QM/QA另config结构；字段存在不代表任何路径实际使用。|
|`include/.../kf_gins/options.hpp:1–10`|薄转发到上项，不是另一套配置。|
|`include/.../config/port_config_loader.hpp:17–21`|两个入口都返回PortOptions；`loadKeyValue`直接调用YamlLike。|
|`config/port_config_loader.cpp:25–125`|trim、先去#注释、替换括号逗号为可读列表、scalar/bool/string读取；科学计数与负数正常，非法bool默认回退，向量不足3回退，unknown键不拒绝。带引号#路径被截断（N14）。|
|`config_loader:127–218`|hasKey；历史AB四位、Canonical run/case身份和compact readiness白名单的字符串规则；它们不构成新数据科学有效性。|
|`config_loader:220–443`|formal mode必须给6个开关、4个false truth字段，严格 stage/protocol/case/data_mode/run 白名单、共同初始化和数据角色；F01=位置+RV，F02=位置+fixedstd basic yaw且关闭RV，F03=位置+RV+有门控scalar yaw；F04=RV/yaw+RD+SA+RP+HV。F01→F02不是单项增加。此门不接受任意新XB标签，应保持探索身份并显式记录，不能伪装旧Canonical。|
|`config_loader:445–469`|行级 map；优先找`=`再找`:`，重复键last wins；没有YAML作用域、锚点、多行、schema或duplicate拒绝。机器路径须由外层alias解析，runtime config逐字克隆不能YAML roundtrip。|
|`config_loader:476–570`|加载身份、路径、forbidden布尔；B3新增严格正数/finite必填L,k与sidecar及model枚举，余scalar字段仍宽松。|
|`config_loader:572–611`|输入initpos/initatt degree→rad，bias deg/h→rad/s、mGal→m/s²、scale ppm→fraction；ARW deg/√h→rad/√s，VRW /√h→/√s；corr h→s；std alias先后级明确。|
|`config_loader:613–822`|RV开启与stress/outage/noise参数；yaw scheme C std/residual软硬阈值；BASIC开关；QA/FGO开关；RD参数及backend身份与禁止fallback声明。短alias覆盖长alias，误拼仍默认。|
|`config_loader:828–965`|RP路径/std/time/sourceaware；HV开启同时开velocitydiagnostic，horizontal路径覆盖diagnostic路径；std scale多别名；yaw-rate diagnostic字段仅记录，native state-model不支持实际更新。|
|`config_loader:966–1168`|SA模式/分源开关/caps/OIM参数、readiness/QM及Go2 sequential joint选项；joint是已有RP/HV顺序调用，不是新FK/关节动力学。|
|`config_loader:1169–1300`|声明边界、CLEAN3guard、B3必须QA/QMoff、formal验证；非formal BASIC强制关闭RV和全部aux，覆盖输入中对应enable；最后生效值须看返回options。|
|`src/demo/port_demo.cpp:17–76`|CLI识别模式、config/output和debug；未知/缺参数走usage或异常，不是隐式执行旧runner。|
|`port_demo:79–133`|dry模式分支优先；否则runFromConfig；异常stderr加`legsa_v23_port_core_demo failed: `且return1，usage return2。外层classifier必须剥精确前缀，不能把未分类异常改成功。|
|`src/demo/legsa_v23_port_core_demo.cpp:1–7`|仅注释marker，没有main；真正入口是port_demo。|
|`cpp/CMakeLists.txt:9–81`|分别构建3套target；port自有src GLOB，移除真实main构库，再链接demo；external原版不参与编译。target同名不能代替binary/hash证据。|

### 4.3 FileLoader、providers 与因子接口

|文件/行组|语义、分支、异常/缺测|
|---|---|
|`fileio/imu_file_loader.cpp:16–43`|全文件读取非#非空7列，解析失败行静默略过，缺失不计数；dt由保留行相减，接受重复/乱序（N14）；超大输入全内存，非流式。|
|`imu_loader:45–67` 与头文件 `16–34`|vector游标next/EOF/isOpen，isOpen实为非空；start/end取首尾，非min/max。|
|`gnss_file_loader.cpp:21–113`|B3构造先读GNSS；sidecar严格header/列数/finite/time/order/accuracy/baseline合同，按精确时间映射并保持missing/invalid语义；不会在B3缺测时恢复scalar yaw。|
|`gnss_loader:115–169`|15基础+可选3validity；lat/lon用大小启发式决定deg还是rad，不能支撑低纬小经度的通用度格式；坏行略过；15列implicitallvalid，18列分源flag。|
|`gnss_loader:171–194` 与头文件 `18–36`|next/EOF/isOpen，allValidityExplicit用于formal门；无排序去重，不证明时序连续。|
|`factors/raw_doppler_types.hpp:18–90`|RD measurement/time/source_time/NEDvelocity/std、质量及lineage字符串；config的R_scale乘variance；status计数只表示provider/更新记录，不是独立卫星实现。|
|`raw_doppler_factor_loader.cpp:22–118`|简CSV/数值fallback/字符串、SHA格式及formal lineage字段合同；检查的是声明格式和一致性，未在C++内打开原OBS/NAV重算hash。|
|`raw_doppler_loader:120–237`|formal必需列和row lineage/time/quality；vn/ve/vd缺值仍默认0，无finite/维度强制（N15）；valid+available统计，enabled结合config返回，缺文件回status不抛，由runtime formal门决定能否继续。|
|`raw_doppler_factor.cpp:14–28`|provider-backed仅valid/lineage/status；std absolute+floor1e−3；残差范数；不解Doppler卫星方程。两个factor/loader头文件声明接口和测量容器，不另算值。|
|`satellite_state_provider.hpp:14–25` + `src/...cpp:11–17`|抽象available/status，唯一Null返回false/provider_missing；不是卫星轨道实现。实际RD生成在上游另审。|
|`go2_weak_prior_types.hpp:19–180`|RP/HV/readiness/yaw-rate诊断的数据和开关；RP默认5°、HV默认2m/s；disabled≠不存在；不包含关节编码器FK方程。|
|`go2_weak_prior_loader.cpp:22–109`|CSV引号翻转支持逗号但不完整RFC双引号/跨行；scalar失败/缺字段fallback；confidence计数与最近秩percentile，不修改观测。|
|`go2_loader:111–179`|RP active就valid，缺roll/pitch默认为0，可真正更新（N15）。std来自row或config，无姿态来源验证。|
|`go2_loader:181–296`|HV NED速度/std/status/updateflag，truthclaim阻断，horizontal允许非diagnostic；std_vd≥999或policy含horizontal只是status标识；汇总百分位/计数，不是安装/参考验证。|
|`go2_loader:298–354`|readiness metadata读取并标solver_visible，质量状态不是运动学因子；不反查原Go2原始消息身份。|
|`go2_weak_prior_factor.cpp:19–66`|isActive检查状态和正std；roll/pitch wrap残差；H精确到sec裁剪前；R用config不使用measurement.std数值；独立wrap while存在与N05同类风险，候选未改此重复实现。factor/loader头分别声明数学与读取，不隐式转换坐标。|
|`baseline3d.hpp:12–63` + `src/baseline3d.cpp:10–32`|输入vector/pAcc/有效性和诊断计数，返回预测/残差/H/R；体内guard有限正参数，几何固定body负Y；N03的正确性及统计条件见3.2。|
|`fgo_feedback.hpp:18–100` + `fgo_feedback.cpp:21–159`|禁用时不读文件；简单按逗号分割、缺数字补0；std取absolute下限；角输入degrees转rad；no-future由window_end<=obs.time；solver_enabled不要求valid_count>0；wrap重复while。默认off、正式禁用；代码存在不表示完成任何目标论文FGO复现。|

### 4.4 GIEngine 与 INSMech 的完整连续组

|GIEngine 行组（src/kf_gins/gi_engine.cpp）|状态流与审查结论|
|---|---|
|29–94 helpers|取dx三块、对角/diag3、正std、trace、norm、dot、percentile。dot用min尺寸会掩盖一般API错误，当前已核调用尺寸一致；percentile每次copy+sort。|
|97–132 constructor/initialize|验证B3参数及QA/QMoff；构造policy/supervisor；名义PVA、IMU误差、P/Qc、dx初始化。复用同engine的initialize没有重置全部历史计数/provider状态，当前runtime每run新对象，复用风险需另测。|
|136–246 set*providers|拷贝RD/RP/HV/readiness/FGO表和status、初始化统计；只信传入含义；RD/HV排序统计，不生成观测。|
|249–327 add/schedule/interpolate/compensate|IMU滚动两帧；legacyGNSS恢复allvalid，explicit保分源；±1ms调度；按时间比例拆增量；零时间分母NaN；bias/scale补偿；N09/N11/N14。|
|330–346 propagation|补偿指定imu对象→INSMech→F/G/Phi/Qd→EKFPredict；timestamp置该样本time；计propagation。res3可一帧两次propagation，不能用count直接当输出行数。|
|355–440 gnssUpdate|无任一GNSS有效直接return；QA可缩R/拒绝；位置先；BASIC只yaw后return；parity时yaw→RV、非parity RV→yaw；然后RD→HV→RP→FGO，末尾消费GNSS。aux没有独立时钟；唯一GNSS对象正常不重复，但重复时间行仍可再次add。|
|442–478 EKF predict/update|默认预测调用/显式Phi Qd；检查dimension；线性dx传播；正确innovation和Joseph，但inverse底层有N06。|
|480–553 feedback/newImu/health|PVA与bias/scale注入；QA恢复时仅裁φz；dx归零不resetP；四种时间分支；只对角health；N08/N11/N13。|
|556–682 accessors/status|返回状态/flatP/timestamp/不同模块计数和providerstatus；只是读取，不能把attempt/yaw counter一概称accepted。|
|684–784 trace/statistics|FGO/QA/SA/QM trace行及统计写出；部分禁止标志硬编码false；write未统一检查失败；trace开关会影响统计汇总完整性而非强制验证物理。|
|786–850 P/Qc/F|见3.3；初始化bias floor取对应noise的第0轴给所有轴；每轴显式initstd存在时正常。|
|853–885 position|DR残差，leverH，R std²；source metadata主要为std/valid/默认nominal，无原始GNSSfix/carrier细分到此路径；SA后更新并计pos。|
|887–927 RV stress|time window启停、deterministic pseudo-noise/hash和stdscale view；诊断选项，正式应off；新XB本轮不使用人工故障。|
|929–1001 RV/yaw|RV预测/leverH/std额外0.05；yaw先硬残差/std拒绝，soft乘R，再SA；H仅φz；attempt与accepted分别计。|
|1003–1020 basic yaw|fixed std，不使用provider yaw_std和schemeC门控；与F03不是仅多RV之差，不能错误解释F01→F02→F03消融。|
|1021–1149 B3/diagnostics|专用参数/validity/准确度/QA/创新NIS/SA，拒绝原因计数、未替代scalar；CSV诊断记录H/R/S等，current候选专用。|
|1151–1233 RD|全表nearest对称窗口、未consume，provider/卫星数门、残差门（SA开则不用旧gate）、leverH、Rscale，计数/全历史排序统计；N09/N11/N18/N21。|
|1235–1290 RP|nearestactive+std筛选；residual/H/R来自factor；SA有quality与时间差，readiness可enrich；接受后记RP计数与残差p95；N09/N22。|
|1292–1370 HV|nearest带updateflag，active/truthclaim门，2D/3D选择、Rstdscale、SA sentinel；仅有效两维不更新vD；N09/N16。|
|1372–1515 FGO|最近反馈加window_end未来检查和mininterval；位置相对init、速度NED、Euler姿态伪观测，gate/clipping及统计；当前正式off，历史代码已读但无本轮真实性能证据。|
|1517–1582 QA metadata|GNSS availability来自isvalid OR、baseline默认长度、RD availability和最近Go2；缺实际源信息时默认并非原始质量证据，正式QAoff。|
|1584–1686 readiness/SA|对称nearest补metadata；sourceaware计算S、NIS、policy和QM；实际dz与Hdx不一致；inverse失败fallback trace近似需标识；trace/评估计数不等于真实accepted；N12。|
|1688–1700 wrap/cov test API|wrap转发Rotation；Cov getter；setter只检查21×21，允许不定/非有限反例注入。|

`include/.../kf_gins/gi_engine.hpp:23–185` 声明上述public API、provider vectors、trace、Cov/Qc/dx、PVA/两帧IMU和计数；private公开只发生在本审查 test TU 宏，正式header未改。`insmech.hpp:16–25` 声明4步与单步便利接口；实现85行已在3.3逐步解释。

### 4.5 Source-aware、QM、QA（也审查非正式启用路径）

|文件/连续组|用途、状态与限制|
|---|---|
|`source_aware/measurement_source.hpp:18–164`|六源枚举、SourceMetadata、per-source开关、权重result；默认字段含有效/nominal/可用等，必须追调用处是否覆盖。不能用结构体有字段证明真实metadata已传入。|
|`source_aware_policy.hpp:16–44`|policy config、per-source滚动deque及计算接口；没有独立观测时间调度。|
|`source_aware_policy.cpp:23–111`|模式allow、reason、最大std/finite、median/MAD、metadata摘要，Go2readiness条件缩放；quality只受传入值约束。|
|`policy:113–237`|source名称/索引，branchId，enabled/caps，下限至少1；rolling残差归一历史仅参与输出诊断并更新deque，不自动构成统计白化。|
|`policy:239–435`|各源LSIM判断可用性、std、时间差、卫星/geometry、baseline、Go2质量；旧/新保守分支不同；只有调用者填入字段才有效；HV sentinel N16。|
|`policy:437–552`|按family字符串计算Huber/Cauchy/IGG/Student等缩放类比，参数k0/k1/c/alpha/phi；不等于复现某篇完整外部滤波算法。|
|`policy:554–650`|OIM用sqrt(NIS/dof)或旧残差比；formal conservative source alpha多次覆写，最后位置0.00003/RV0.04/yaw0.03/RD0.35/RP0.02/HV0.03，早先同变量赋值不生效。死赋值影响可读性，最终科学值以末赋值为准。|
|`policy:652–694 evaluate`|依据enabled/mode分别算LSIM/OIM，combine为max而非product，cap并给accepted/rejected；禁用也返回合法结果；名字不能冒充未实现的联合概率模型。|
|`quality_state_manager.hpp:17–138`; `quality_state_manager.cpp:14–133`|六态+动作、阈值/hold/recovery/mode数据；source类别/provider判断，字符串输出，constructor模式覆盖，QM00off到QM05按需启用。|
|`quality_manager:135–360`|每源memory、调用计数/时间gap、invalid/innovation/readiness触发，primary receiver不会仅innovation极值reject；hold/fallback/recovery随评估调用数推进；`qm_source_cap`和`qm_invalid_hold_enter_count`无实际读取（静态），不能当调参有效；正式off，已读但没有扩大实时矩阵。|
|`source_aware_trace.hpp:16–38`; `source_aware_trace.cpp:22–128`|reason/CSVescape、最近秩percentile、append/getter/stats/write。stats里的update_count对每行都加，含reject；trace关闭可丢统计，不等于算法未evaluate；应分别使用engine accepted计数。|
|`quality_state_trace.hpp:15–37`; `quality_state_trace.cpp:15–142`|六态计数、transition/action统计和CSV；log_only行也计action，命名不能直接当真实动作次数；writer状态未check。|
|`qa_fallback.hpp:15–191`; `qa_fallback.cpp:11–152`|QA输入/状态/决策/配置；raw/Go2可用性、A1物理门、测量policy；S0–S6 action/Rscale，fallback默认off，所谓物理量可能来自GIEngine默认值。|
|`qa_fallback:154–343`|logging/active、lastrecovery、evaluate状态转移、hold/recovery/degraded判据；配置`s5_hold_timeout_s`不被实现使用；正式F01–F04要求off，不据该候选的toy成败替正式claim。|
|`qa_fallback:345–391`|记录请求/实际yaw校正、trace getter、状态字符串、reasons拼接；不做另一条位置/姿态输出替代。|

### 4.6 Runtime、writer 与异常传播

|文件/连续组|行为与证据边界|
|---|---|
|`runtime/port_runtime.hpp:14–39`|debug开关/maxrows/outputdir和各toy/config入口；不声明异步实时运行。|
|`runtime.cpp:36–144`|makeInitialState/appendState、写NAV/STD/eval/manifest、从engine回收实际计数/status；全部状态与fullP留vector直到末尾，内存随时长线性。|
|`runtime:146–247`|失败前写cov manifest然后throw；formal末尾检查各方法启用模块至少一次及禁止模块0；缺一次更新即可contractfailure，不等于输入/算法原因已细分；不把fail当空成功。|
|`runtime:249–309`|单独读时间列、首末/交集计数和debug输入快照；这比完整loader宽松，计数含后来拒读行/invalid行，expected_updates并非独立有效观测数。|
|`runtime:310–481`|wrapdeg、读GNSS/nearest、近似horizontal distance；writer-source/reference快照是声明，state-measurement/residual-gain是事后nearest诊断，不是实际每次EKF创新/K的等价日志。|
|`runtime:482–548`|DryToy转SyntheticMath，构造短合成增量和GNSS，传播检查并写结果；synthetic provenance未同步options（N20）。|
|`runtime:549–740`|RD、SA toy人工构造provider与异常、按本地时钟合成更新；synthetic，不是raw RD解算，也非真实外部方法比较。|
|`runtime:741–937`|QM toy序列触发state及provider，观察trace；测试state machine不证明真实GNSS完全中断会由正式调度触发同路径。|
|`runtime:938–1106`|Go2weakprior与QA toy，合成RP/HV/QA质量；没有真实足端FK或真实Go2 truth。|
|`runtime:1108–1266`|runFromConfig加载；formal身份保留，非formal按开关覆写phase/runlabel；paper claims强制false；不得反读phase名称认定当今协议。|
|`runtime:1267–1346`|按开关loadRD/RP/HV/readiness/FGO；yaw-rate仅标notactivated；formal provider预检失败throw明确prefix；无reference open。但“不打开reference_path”仍不能排除provider来源污染。|
|`runtime:1347–1406`|二次读时间+完整内存loader，估effective overlap，检查isOpen/explicitvalidity，setprovider和initialize；运行loop实际end使用options.endtime，不以该overlap统计偷偷裁掉所有IMU。|
|`runtime:1407–1463`|parity不额外写initNAV；找首IMU≥start、首GNSS>start；GNSS等于start只作为之前记录跳过；debug行上限只限制部分日志。|
|`runtime:1464–1522`|每IMU仅刷新一条staleGNSS避免覆盖；call add→newImu→health→append；乱序/超高GNSS频率未全面规范化；不能声称最优实时排程。|
|`runtime:1524–1578`|回收模块计数、formal门、ratio=尝试update/时间列数量；先判是否有完整合同再writer；debug重新nearest原观测；run失败在末写NAV前可能无轨迹，但不能把原因抹去。|
|`writers/port_writers.hpp:19–27` + `src/writers/port_writers.cpp:15–25`|另一层统一转发NAV/STD/eval/exact可选/manifest，无数学修正；实际runtime本地writeAll同职责，存在两条writer调用入口。|
|`fileio/file_saver.hpp:19–30`; `file_saver.cpp:26–149`|目录创建；JSON只转义斜线与引号，控制字符未完整转义；STD单位scale；source-aware数组及初始化diag序列化。|
|`file_saver:151–223`|options路径/角色回显；位置v角度bias/scale列名；把导航系φ的std写成roll/pitch/yaw std是不精确命名（N19）。|
|`file_saver:229–279`|状态直接输出NAV与EVAL，std sqrt(max(0,Pii))，长度不够补0，无统一open/writecheck。数据非法可掩成0；NAV不做POI杆臂转换。|
|`file_saver:285–347`|exact 11/22/13列，检查state/P行数相同与打开成功；输出固定9小数、bias/scale转common unit；后续写盘失败仍无finalcheck。|
|`file_saver:350–746`|manifest写options身份、flag、单位、source状态/计数、GNSS/yaw/RD/Go2参数；Go2joint count为RP/HV计数min，不证明同一时刻联合因子；forbidden字段多处硬编码。|
|`file_saver:747–894`|仅B3模型输出B3diagnostics；actualpaths、SA/QM配置/计数；clean-neutral阈值硬编码是声明，不是本次已执行性能门。|
|`file_saver:895–1014`|FGO/QA/module counters、covfailure、GNSS ratio、固定上游source_commit；N20。manifest写成功不等于NAV成功或传感器身份验证成功。|

## 5. 测试回执、复现与当前验收范围

所有大输出通过 ignored `configs/paper_rebuild/DATA_PATHS.AUDIT_XBPG.local.yaml` 的 `audit_scratch`/`audit_root` 解析。共享脚本不写本机用户名或G盘路径。原生初始构建与测试：

```bash
python3 scripts/paper_rebuild/audit_xbpg/native_run_audit.py --local-config <local-config> --run-id <unique-id>
python3 scripts/paper_rebuild/audit_xbpg/native_existing_tests.py --local-config <local-config>
python3 scripts/paper_rebuild/audit_xbpg/native_compare_frozen.py --local-config <local-config> --frozen-binary <verified-binary> --expected-sha256 <verified-sha256>
python3 scripts/paper_rebuild/audit_xbpg/native_extra_tests.py --local-config <local-config>
python3 scripts/paper_rebuild/audit_xbpg/native_config_smoke.py --local-config <local-config> --frozen-binary <verified-binary> --expected-sha256 <verified-sha256>
python3 scripts/paper_rebuild/audit_xbpg/native_candidate_numeric.py --local-config <local-config>
```

候选补丁采用零 context unified diff。检查命令为 `git apply --check --unidiff-zero docs/paper_rebuild/audit_xbpg_20261001/NATIVE_CANDIDATE_NUMERIC.patch`；仅在隔离副本应用时使用 `git apply --unidiff-zero <patch>`。本轮将三行 context 转为零 context 后仅重新执行 apply-check，没有重编译或重复原生实验；代码改动及已测试 candidate 文件哈希保持不变。外部原始 receipt 保留当时补丁哈希，共享摘要另记格式转换前哈希。

脚本默认拒绝覆盖已存在的本轮输出，复现到另一个 local config 的新审查根/空scratch（初始runner支持unique run-id；后续runner依赖 `native_initial`）。不要删除历史证据来重跑。`NATIVE_OTHER_TARGETS.json` 记录另外两个target的隔离构建；构建通过不提高它们尚未完成的语义深度。

|证据|实际运行、数值与限制|
|---|---|
|`NATIVE_EXISTING_TESTS.json`|原样既有 `test_clean3_math_repairs.py`、`test_t5bc_baseline3d.py`：21 passed；pytest只把B3的build目录重定向scratch，没有改测试断言。|
|`NATIVE_TEST_RESULTS.json`|初始 native modes、6项wrap timeout、loader/parser、6个完整target smoke；观察到缺陷的进程return0表示观测器完成，不表示断言通过。timeout就是失败证据，不是“0个失败”。|
|`NATIVE_EXTRA_RESULTS.json`|步长扫、异步bias反例、HV哨兵、2000独立RV统计、非法STD/IO、缺字段provider实际更新；均为按初审发现新增的post-hoc软件实验。|
|`NATIVE_CONFIG_SMOKE.json`|当前/正式旧binary各2个1s完整config route，每run100有限输出；all-channel每模块10更新、SA60；GNSS全部invalid则aux0；4调用exit0、6/6输出一致；不是4个实测运行或期刊有效性。|
|`NATIVE_FROZEN_COMPARISON.json`|六toy old/new 18/18输出字节一致，证明特定正常输入回归。|
|`NATIVE_CANDIDATE_RESULTS.json`|两个Matrix读写越界候选return1；Inf/NaN wrap抛domain_error return1，±1e308有限返回；20,001个−10到10rad正常值逐字一致；六完整target18/18 NAV/STD/eval一致。候选只防两类边界，不修全部重复wrap、inverse、Euler、P、provider、数学问题。|

FD采用中心差分，角/scale步长1e−6，位置误差0.01m。表中“最大相对误差floor1e9”键实际分母下限 **1e−9**（旧命名少了负号）；接近零导数的逐元素relative=1不意味着大错，追加position Frobenius-relative扫明确更可靠。B3奇异不是数值求逆崩溃；其单轴零空间作为应有性质测试。Euler奇异/近奇异另测，不把正规点FD用于极点。

四类1000步native集成含静止、平移、组合倾斜转动、GNSS全中断；状态/P有限，最大cov不对称9.095e−13。fixture位置与杆臂未完全作为精度oracle统一，故这里报告健康和计数，不报告真值RMSE或NEES。10s场景也不证明分钟级实时/一致性。RD全表nearest性能实验30次update在100/10,000/100,000行约1.19/3.11/44.78ms，确认随provider表长增长，但包含同机调度/缓存，不是最坏实时延迟证明。

## 6. 上轮十三项重新裁定与历史结果处置

|上轮项|本轮裁定|证据/适用限制|
|---|---|---|
|1 横向+90与Euler yaw|已确认数学不一致；provider是否补偿须总链裁定|N01，3.2原生倾斜反例；native没有该补偿。|
|2 scalar H|条件性风险/近似|N02；pitch0/边界正常已反证错号，tilt导数遗漏已量化。|
|3 B3 H/零空间/R|H符号错误说法已反证；R是条件性风险|N03；FD/零空间成立，独立各轴pAcc和共享测量假设未被测试替代。|
|4 Matrix|已确认缺陷|N04；2×2(0,2)改(1,0)。|
|5 wrap|已确认缺陷|N05；±Inf、1e308独立子进程0.5s timeout。|
|6 inverse|已确认尺度/非有限防护缺口|N06；条件数1矩阵误拒；NaN传播。|
|7 Euler奇异|已确认近奇异表示不恢复原旋转|N07；88° max matrix error0.02248，真正90°恢复正常。|
|8 reset|条件性风险/近似|N08；本扰动J_l推导；尚无真实校正尺度/NEES证明历史致命。|
|9 nearest/调度|已确认缺陷|N09；未来+重复aux原生2次，current/old完整config全失效aux0。|
|10 跨源相关|条件性风险|N10；矩阵中无互协方差，上游共享身份由总审继续核实。|
|11 V3新yaw旧HV/std|证据不足（本分审未读历史provider）|native会继续使用HV独立provider及scalar std；不能从名字推断实跑是否改过，见主METHOD_IDENTITY/provider审查。|
|12 BY2O选择/共享reference|证据不足（本分审边界）|未打开真实历史性能，不依据native测试替历史选择记录判定盲测。|
|13 旧补丁异常分类/正常回归|候选正常回归已确认；controller分类证据不足|native probe异常return1，实际demo catch前缀明确；未启动历史controller验证新错误字符串分类。候选18/18正常输出一致仅覆盖所测输入。|

应优先重新审视使用全部GNSS停更来证明RD/Go2独立维持的旧主张、依赖SA NIS统计的解释、强倾斜scalar yaw的模型表述、把STD当Euler姿态置信区间的图、未区分F01/F02/RV的消融因果；需要修复并冻结新协议后重跑才能给修后性能。本轮不改写原历史输出，不重跑Canonical-541，不因上述代码问题擅自删除旧结果。正常输入下Matrix/wrap候选未改变已测输出，不能据输入边界反例宣布旧正常NAV都错。B3验证不影响旧scalar二进制已有身份，也不证明可把旧结果升级为B3结果。

剩余：原生完整21维独立IMU真值/噪声Monte Carlo尚未完成；P reset和完整F差异未以长时真实校正量量化；外层Python failureclassifier新异常尚未实测；raw provider身份与XB几何/参考、旧选择记录由其他审查模块闭合；cpp/src、cpp/include、legsa_v23_core 的全文件语义深审不在本报告已完成范围。所有审查结论、修复完成度和实数据可运行性必须分别陈述。
