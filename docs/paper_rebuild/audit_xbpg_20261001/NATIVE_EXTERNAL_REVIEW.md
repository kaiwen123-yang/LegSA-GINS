# Hartley 自有移植与官方驱动：源码身份、语义和复现缺口

本次增量范围为 **8 个自有 C++ 文件、5,257 行**：`hext/hx02e_official_driver.cpp` 166 行，以及 `horizontal_literature/hartley_inekf` 下 header 292、backend 1,301、两测试 632、三 tools 2,866 行。全部读完并按下面函数/连续语句组审查。源码基线 `eb3cbed314693358c7c38442b6fbbb7afcf0342e`；逐文件 blob/hash、调用边界、语义深度见 `NATIVE_EXTERNAL_COVERAGE.csv`。CMake 仅作为附加链接身份线索读取，不重复计入这 8 个文件。

**本增量没有编译、启动外部滤波、运行这些测试、打开历史性能结果、读真实缓存或建立横向比较。** `dynamic_test=NOT_RUN_THIS_INCREMENT`。下文 test 阈值、期望计数和字符串 `PASS` 都是源码内容，不是本轮测试结果。没有修改正式源，新增的只有本报告和对应两张 CSV。

最重要的判断：这里确有较完整的自有 InEKF 数学代码和多类验证代码，不能把它当作仅有名称的空目录；但现有代码和测试设计也不能推翻“目标三篇文献的完整复现及公平比较尚未完成”的用户状态。实际数据的 IMU/足端/时标身份、FK proxy 与关节编码器的差异、初始化、noise sampling 合同、真实 binary/library/config 身份及评价物理点仍须分别闭合。

## 1. 本次已确认与保留的结论

- **已确认静态缺陷 NX01：** `validate_backend.cpp` 各检查只把 `pass=false` 输出到 stdout，`main:1939–1947` 不累计失败并直接 return 0。只有 exception 才 exit 1。外层若只看 returncode 会误判；本轮未运行 validator、未判定其任何具体 case 失败。
- **已确认静态防护缺口 NX02：** backend constructor/最终检查仅验证 P 尺寸、有限、对称；`P=-I₁₅` 满足这些条件，R=2I 的 nominal 也不被 SO(3) 检查拒绝。`run_h5` 另加每历元 SO(3)、指定 checkpoint 的 PSD gate，缓解 runner 路径；不能据此宣布所有 public API 输入安全。
- **条件风险 NX03：** H5 用 `[t0,t0+5 s)` 数据估初始姿态/bias 后从 t0 输出整个回放；官方 driver 也先读 `initial_seconds` 前缀、再从首记录运行。这是带初始化等待的离线重放，最初若干秒不能被描述为当时零延迟可用输出。
- **条件风险 NX04/NX05：** native 重新计算 H5 config 文本 hash，但 cache/raw/source/executable hash 主要来自 cfg/header 回显；cache payload 没有在 native 重新 hash。Table-1 参数类型区分了连续 ASD 和所谓 discrete std，然而数值路径仍为 `σ²·dt`，仿真按 `σ/√dt` 注入 rate noise。类型名称不单独证明真实采样模型及硬件可迁移性。
- **身份及适用性缺口 NX06/NX07：** H5 真正输入是 cache 中已有 `foot_position_body`，R 是 5/10/20 mm 的 isotropic proxy；可选 encoder Jacobian API 不被 H5 runner 调用。官方 driver 的 `paper_initial_covariance` 分支在接触扩维后重设整块对角 P，与自有 H5 保留 Eq32 交叉项再加独立脚点 prior 的操作不同。
- **条件风险 NX08/NX09：** lifecycle 名为“atomic”的测试没有验证异常回滚；非法新增可在已校正、已移除后抛错。`applyInitialGaugeTransform` 接受任意 SO(3)，但不转 gravity；其安全 gauge 范围应为保重力旋转。H5/H6 实际只传绕 z 的 yaw，不能据泛化 API 风险否定该已知调用分支。
- **验证声明限制 NX10/NX11：** 多个 synthetic recovery 分数混合不同单位；单固定随机 realization 不是 NIS/NEES 统计一致性。early official regression 不是 reported IJRR backend 的数值身份测试。

所有“已确认”仅指可以从完整控制流或代数直接证明的代码事实；`NATIVE_EXTERNAL_FINDINGS.csv` 标明 `STATIC_ONLY/NOT_RUN`，不捏造新测试回执。

## 2. 身份与原论文关系

|实现/入口|实际数学与输入|本轮身份判断|
|---|---|---|
|`HartleyInEkf`，`HARTLEY_IJRR2020_REPORTED_BACKEND`|world-centric、右不变误差、15+3N 维、偏置扩维；Gamma nominal、解析 Phi、Eq61近似Qd；point-contact更新|自有数学移植，不能因名字含reported就认定正式结果/论文全部重现。|
|`EXACT_QD_REFERENCE_DIAGNOSTIC`|nominal/Phi与上项相同，Qd改64点Gauss–Legendre积分|独立诊断模式；“EXACT”是标签，固定节点积分仍是数值近似，未提供所有ωdt的误差界。|
|`OFFICIAL_CPP_EARLY_REGRESSION`|nominal比力用旧R，Phi=I+A dt，Qd=Phi LQcLᵀPhiᵀdt|为早期官方代码设计的回归分支，和Gamma/解析Phi主分支不同。|
|`official_regression.cpp`|同一测量文件同时喂官方 `inekf::InEKF` 与自有early分支；对contact顺序重排；期望固定数据量|测试early实现相符程度；本轮未运行/读既有结果。|
|`hx02e_official_driver.cpp`|cache+简单config→官方公开API `Propagate/CorrectKinematics`→NAV|驱动自己不实现滤波数学；实际官方library来源/版本不能由该TU的 `#include "InEKF.h"` 唯一确定。|
|`run_h5.cpp`|本地固定H5/H6/H6R run_id binding、Go2数值噪声或Table1 process、FK proxy|自有reported backend运行器；本轮仅源码审查，无实数据运行。|

本目录 `CMakeLists.txt` 构建自有库、两个单元测试、validator、H5 runner；只有两个单元测试注册到 CTest，validator 不在 CTest。`official_regression.cpp` 和 HX02E driver 不由该 CMake 链接；编译命令、`InEKF.h` include搜索顺序、官方库 binary/源码 pin 在此8文件内 **UNVERIFIED**。本轮没有把记忆中的官方 commit 当成本机已验证身份，也没有扩展审核整个第三方 Eigen/OpenSSL/官方库。

对照作者稿可确认 Eq50为区间常值IMU的解析积分，Eq60为左右不变转移经adjoint转换，Eq61是Qd近似而非积分精确值。本文也明确使用FK/关节输入并讨论绝对位置及绕重力轴方向的不可观性。[作者公开稿，Appendix A、Section 5/8](https://robots.engin.umich.edu/publications/rhartley-2020a.pdf) 以下推导来自本机代码采用的扰动定义，不以“参考实现如此”为证明，也不复制论文整段推导。

## 3. Header合同与 backend 逐函数语义

本节 `B:L` 指 `src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/src/backend.cpp:L`，`H:L` 指同模块 `include/hartley_inekf/backend.hpp:L`。

### 3.1 状态、frame、误差与单位

H:18–24 的三个 identity 影响 **实际传播代码**，不是单纯label。H:125–181 定义 R=body→world、v/p/contacts 在world，gravity默认(0,0,−9.81)，与正式 LegSA NED 不同；body物理轴是否FLU以及IMU原点必须由上游cache合同验证，不能因gravity向下就倒推出传感器轴。group状态排序为 rotation、velocity、position、按leg_id有序contact；bias末6项。contact可任意int ID，H5另限制实际4腿映射。完整误差维数15+3N，群部分9+3N，噪声12+3N。

以代码 `discreteErrorMap` 为证据，定义 `η= X_hat X_true⁻¹=Exp(ξ)`，`δb=b_hat−b_true`。故真值为 `Exp(−ξ) X_hat`，修正是左乘 `Exp(delta)`、bias+=delta。这里 rotation error/position invariant error 不等同于正式 port 的局部21维误差，不可复用其H/reset结论。H:195–203 getter为const引用/计数；H:205–272 划分传播、接触更新/增删、初始化、gauge、三种Phi/Q API；H:274–289为私有状态与policy开关。H中每个声明的定义均在下表覆盖。

### 3.2 数值助手与Lie运算

|函数/语句组|输入、计算、异常和限制|
|---|---|
|B:17–53 `requireFinite/requireFiniteNorm/requireFiniteLieResult/requirePositiveDt/requireNonnegativeDt`|检查 scalar/vector有限、norm溢出、矩阵结果有限；传播dt>0，解析mean/Phi允许dt=0；错误抛invalid_argument/overflow_error，不静默改dt。|
|B:55–76 `gammaSeries`|计算Γ_m(φ)=Σ[φ]×ⁿ/(n+m)!，m=0/1/2；64项上限、term最大值<2e−16提前停，入口小角阈值0.1rad。|
|B:78–96 `gammaClosedForm`|令K=[φ/θ]×。Γ0=I+sinθK+(1−cosθ)K²；Γ1=I+(1−cosθ)K/θ+(1−sinθ/θ)K²；Γ2=.5I+(1−sinθ/θ)K/θ+(.5−(1−cosθ)/θ²)K²。1−cosθ使用2sin²(θ/2)；避免直接小角相减，所有外部入口先查norm。|
|B:98–130 `psiSeries`|按乘积求导 `∂Aⁿ/∂φ_j=ΣAᵏ[e_j]×Aⁿ⁻¹⁻ᵏ`，返回∂(Γ_m(φ)a)/∂φ，m=1/2；使用和Gamma相同系数。预存64幂，仅用于小角。|
|B:132–166 `psiClosedFormDerivative`|Γ=constantI+c1A+c2A²；导数=−c1[a]×−c2([Aa]×+A[a]×)+(c1′/θ)Aaφᵀ+(c2′/θ)A²aφᵀ；逐式核对c1/c2及θ导数，与Gamma定义一致。极大但norm有限时θ⁴/θ⁵可溢出；外层只保证最终finite，不是所有巨大φ的精度保证。|
|B:168–187 `sortedContactIds/groupDimension/contactOffset`|map天然排序；9+3N；lower_bound找active ID，否则throw。稳定ID而非当前足下标决定P块位置。|
|B:189–231 `gaussLegendre64`|Legendre多项式递推、最多20次Newton、对称64节点/权重；无显式convergence flag；用于诊断Qd积分，不在H5 Eq61分支运行。|
|B:233–246 `symmetrized/requireCovariance`|P对称平均；3×3观测cov要求finite、绝对对称误差≤1e−12、LLT正定。真实JΣJᵀ可能仅半正定，退化FK姿态会被拒绝而非自动增噪。|
|B:419–469 `skew/vee/gamma0/1/2/psi1/2/expSO3`|skew/vee为标准反对称映射；wrapper查finite norm、根据0.1rad选series/closed、查结果finite；exp=Γ0。零点Ψ1=−.5[a]×、Ψ2=−(1/6)[a]×。|
|B:471–489 `logSO3`|只查matrix finite，再Eigen quaternion normalize、统一w≥0；near-zero用atan展开，其他用2atan2。未查输入R∈SO(3)，不合格矩阵可能被投成某个q而不是拒绝（NX02）。|
|B:491–519 `compose/inverse`|同一contact集合才可compose；R乘法、v/p/d按半直积；inverse用Rᵀ以及−Rᵀ各向量，因此只在R为旋转时才是真逆。|
|B:521–555 `expSEK3/logSEK3`|exp检查tangent长度/finite和有序唯一IDs；每个平移向量用Γ1左雅可比。log检查IDs一致，SO3主值log后Γ1显式逆还原各列；不支持跨主值切面的全局唯一log。|
|B:557–577 `adjointSEK3`|每个3块对角R，旋转列依次[v]×R/[p]×R/[d]×R；维度与有序contact同步。用于同一物理状态换world gauge下的cov变换。|

### 3.3 噪声类型与有效参数

|定义/实现|实际流向|
|---|---|
|H:26–53;B:262–306 `ContinuousNoiseDensity::validate/continuousPsdFromDensity/discreteSampleStdFromDensity`|连续ASD五项finite且非负；Qc只平方一次；诊断conversion把measurement std=ASD/√dt，bias/contact increment std=ASD√dt。production不调用sample conversion。单位按随机微分模型使用，单/双边频谱归一仍应追Allan标定合同。|
|H:55–83;B:308–342 两Table1 validate|五process值和额外1deg encoder值分开typed容器，finite非负；只核数值合法，不证明该采样率的离散方差解释。|
|H:85–98;B:343–382 `H5Eq61NoisePolicy`两factory/validate/tag|Go2 IMU continuous＋paper contact组合必须contact ASD=0；另一policy只接受五process值。tag只表示代码策略；非法enum强制转换的防护未实现，但常规typed调用不会产生。|
|H:100–113;B:384–417 measurement APIs|isotropic R=σ_m²I，σ必须>0；encoder R=σ_rad²JJᵀ，J为finite3×N，单位m/rad；不从degree用单标量直接换m；此API只接受已给J，不实现关节正运动学/编码器decoder。|
|B:716–734 `continuousQc`|gyro、acc、各contact、bg/ba按ASD²填独立对角noise；不建不同腿的encoder/机体公共误差相关。|
|B:840–915 两Table1 mapper、Go2/paper mixed mapper|将paper五数值平方、经L映射；Go2 mapper先建continuousQc，再填contact=.05²而不经过contact ASD；encoder字段不进Qc。程序分支区分成立，但同一`Qbar·dt`路径的物理noise模型仍需声明（NX05）。|
|B:917–943 两typed Qd wrapper|解析Phi与相应Qbar，返回对称(Phi Qbar Phiᵀdt)；这不是根据实际record dt反解离散sample std。|

**NX05 的确定数学含义。** 一维无姿态模型 `v_dot=a_meas`，该映射给 `Var(Δv)=σ²dt`；若σ确指每条独立rate测量标准差、区间零阶保持，则应为 `σ²dt²`。在dt=.004s，两者差250倍。validator:1049–1056使用σ/√dt采样，验证的是前一种假设，而不能用这段仿真证明Table1的“discrete”语义已独立确认。作者Table1数值与本代码默认一致，但这项软件类型隔离不足以解决采样解释；本轮裁定为条件风险，不声称作者论文或所有历史结果已被反证。[作者稿 Table 1、Appendix A](https://robots.engin.umich.edu/publications/rhartley-2020a.pdf)

### 3.4 传播：逐块推导

|函数/语句组|状态与矩阵|
|---|---|
|B:579–615 constructors/activeContactIdentities/stateDimension|constructor存mean/P/noise/identity/g，H5构造强制reported identity并开启policy；维数15+3N。|
|B:616–634 `validateStateAndCovariance`|所有mean/contact/P finite、P尺寸、对称；**没有R正交/det及P PSD检测**。例mean合法、P=−I通过；此为静态反例，未运行（NX02）。|
|B:636–670 `exactMeanStep/officialEarlyMeanStep`|reported：R⁺=RΓ0，v⁺=v+gdt+RΓ1adt，p⁺=p+vdt+.5gdt²+RΓ2adt²；contacts/bias保持。early：v/p用初始Ra，R同样exp；二者在非零ω下数学不同。|
|B:672–690 `continuousA`|φ-bg=−R；v-φ=[g]×、v-bg=−[v]×R、v-ba=−R；p-v=I、p-bg=−[p]×R；每contact-bg=−[d]×R；其余0。bias随机游走，没有GM回复。|
|B:692–714 `continuousL`|gyro公共列[R,[v]×R,[p]×R,[d]×R]，acc列只v=R，各contact velocity列R；bias noise=−I。共享gyro引起的跨块项由LQcLᵀ保留，不能因Qc对角就说整个state noise无相关。|
|B:736–775 `analyticalPhi`|根据Gamma/Psi、初/末state构建所有非零块，下方独立导数给出；不是I+A dt。|
|B:777–825 `analyticalPhiEq60`|构建body左不变常系数A_l，θ/v/p/各d对角−[ω]×，vθ=−[a]×，bias输入−I，p-v=I；expm后用末adjoint与初inverse-adjoint变回右不变，bias尾6恒等。作为alternative oracle仍共享group/exp工具。|
|B:827–838 `eq61ProcessCovariance`|Qd≈Phi LQcLᵀPhiᵀdt，是论文近似形式；正dt、QcPSD时保PSD，不等于时间变L/Phi积分。|
|B:945–972 `eq52ProcessCovarianceGaussLegendre64`|每τ点精确推进nominal、构建剩余区间Phi与L(τ)QcLᵀ，64权重累加；调用相同解析Phi，故不能独立发现该Phi的共同错误。没有声明任意high-rate均exact的理论界。|
|B:974–1035 `propagate`|减当前bias、记录A/L/Qc、根据identity选early/analytical与Eq61/GL64；H5实际policy使用last_qbar和Eq61计数；最后P←PhiPPhiᵀ+Qd、对称、validate。mean在validate前已改，失败后不保证对象可继续用。|

令 `φ=ωdt`，`B_g=−RΓ1(φ)dt`，`D_m=∂(Γ_m(φ)a)/∂φ`。从上面的误差定义对 exact mean 求导，

```
δθ+ = δθ + B_g δbg
δv+ = δv + [g]×dt δθ
      + (−R D1 dt² + [v+]×B_g)δbg − RΓ1 dt δba
δp+ = δp + dt δv + .5[g]×dt² δθ
      + (−R D2 dt³ + [p+]×B_g)δbg − RΓ2 dt² δba
δd_i+ = δd_i + [d_i]×B_g δbg
δbg+ = δbg; δba+ = δba
```

例如真ω=估计校正ω+δbg，对Γ1a的导数项带 `−R D1 dt²`；最终右不变速度误差还要减最终姿态误差作用于v_true，给 `[v+]×B_g`。这解释了两个项的符号和为什么必须使用v⁺。取dt→0即得B:672–690的A；零bias部分仅[g]×与积分链，符合不变误差模型。contact增量无真实运动但仍有姿态/bias误差耦合；它不能被当作独立已知世界点。

本次对Gamma/Psi/mean/Phi/A/L/H及增删映射完成语义及上述独立代数核对；没有动态重跑case。GL64的有限节点误差界、大角float精度及noise谱约定仍列未闭合，不把“静态公式一致”写成外部精度/统计验证完成。

### 3.5 观测、反馈、增删与gauge

|函数/语句组|计算、状态和边界|
|---|---|
|B:1037–1071 `processContactLifecycle`|reported-only；ended不得重复，survivor ID集合必须等于active减ended；依次 survivor correction→remove→augment，再加counter。没有先验证所有ended/added合法，也没有异常rollback（NX08）。|
|B:1073–1093 `initializeContactsEq32WithIndependentPrior`|仅从无contacts初始化；先做相关扩维，再在每脚3diag加prior²I，保留原交叉块；和全P重设diag不同。|
|B:1095–1115 `applyInitialGaugeTransform`|检查输入SO3后左旋R/v/p/d、P对每群3块旋转，bias不变；gravity没旋转。仅保gravity的yaw才是该固定world重力模型的gauge，H5/H6实际调用满足（NX09）。|
|B:1117–1129 更新wrapper|production `correctContacts`要求每active脚恰一次；early subset API限定early identity；无contact时不能调用空correct，应直接传播或用lifecycle空survivor。|
|B:1131–1174 `correctContactsImpl`建模|strict sorted ID、active检查、每R_body正定；r_i=p+R y_i−d_i；H位置=−I、contact=I，其余0；R_world=R R_body Rᵀ。各脚堆叠R块对角，若共享FK/姿态误差不独立，这是假设。|
|B:1175–1195 `correctContactsImpl`更新|S=HPHᵀ+R，LLT失败throw；solve求K与NIS，无显式inverse、无门控、无R inflation；delta=Kr；左反馈后Joseph并对称，记录NIS=rᵀS⁻¹r。没有额外state error未注入dx，不能套port sequential dz−Hdx指控。|
|B:1197–1212 `applyLeftCorrection`|delta必须匹配维数且finite；群部分Exp后左compose，bias尾6直接加。不是Euler加法。Joseph来自该不变测量更新，未额外调用MEKF reset本身不证明这里错误。|
|B:1214–1265 `augmentContacts`|sort新增；拒重复/已active和不合格R；新d=p+Ry；F保旧state与bias索引、每新脚row=原p误差，G新脚=R；Pnew=FPFᵀ+G Rmeas Gᵀ，同次新脚间共享position交叉项保留。|
|B:1267–1299 `removeContacts`|先验ID存在/唯一，M选剩余分量与末bias，Pnew=MPMᵀ；这是边缘化删除，不是对被删脚施加观测的Schur条件化。|

观测符号可直接核对：无测量噪声时 `r_i=ξ_p−ξ_di=−H_i ξ`。左修正后新误差约为 `ξ+Kr=(I−KH)ξ`，因此代码 H 为(−I,+I)、delta=+Kr具有一致方向。新增脚的右不变误差满足 `ξ_dnew=ξ_p−R n_fk`；独立noise的符号在 G R Gᵀ中消去，因此F不显式含lever/skew并非遗漏。缺的是独立性/校准条件，不是普通欧氏lever H照抄即可修正。

## 4. 两个驱动及官方回归的完整函数组审查

### 4.1 `hext/hx02e_official_driver.cpp`

|行/函数组|实际输入、行为、失败与缺口|
|---|---|
|16–61 `Record/require/decode/read_cache`|256字节header/192byte记录；memcpy按宿主endianness，magic/version/尺寸/count∈(1,10⁷)、截断、trailing bytes、IMU/foot有限、4bitcontact、严格ns递增、首尾time与header一致；不校验payload内容hash，header内raw/prefix/hash不使用。读取全量vector。|
|64–78 `contact_observation`|4个leg ID固定，pose rotation设I、translation取foot，6×6cov按rotation_var/FKvar两对角3块；setContacts再CorrectKinematics。没有关节角/J、没有足底朝向测量；rotation covariance是否被官方当前实现使用须查已pin库。|
|80–101 main解析/初始化|必须3参数，空格key-double config、duplicate拒绝、未知key可存在、缺key at抛；读完整cache后平均`initial_seconds`内acc；仅norm>1e−9，不核static运动；roll/pitch来自比力，yaw0。常值平移加速度会污染该初始化，不能按reference修角。|
|102–131 initial state/noise/P|v/p/bg/ba=0；可选initial diag std；官方初始contact更新后再次全P重置diag，清除交叉相关；NoiseParams五setter来自config，无native范围有限性逐项校验。NX07。|
|132–153 propagation/output|首记录写初始化；后续用前一IMU rate×真实dt调用官方Propagate，再当期足端更新；输出R/v/p/Euler/bias/contactcount/dim；finite检查覆盖P但不查SO3/PSD；不转到GNSS POI，也不引入参考。|
|154–166 termination|写该行后再查位移/速度/高度上限；超限exit20，超限点会留在部分NAV；其他exception exit2，前缀ALGORITHM_FAILURE_DIVERGED→20；每1e4 flush，末out.good检查在最终close之前。结果消费者必须保留截断/失败而非按已有NAV文件判成功。|

这里的 `initial_rotation_std_rad` 等是真实生效字段；不存在per-record姿态/速度reference输入。安全读取cache并不证明cache内foot/IMU未经过上游参考派生；该问题只能追provider。对原论文的缺口是输入物理角色、初始化/协方差选择和真实官方实现身份，不能归罪于仅负责编解码的driver没有复制数学函数。

### 4.2 `tools/run_h5.cpp`

|行/函数组|实际作用|
|---|---|
|29–60 packed structs/require|cache/header、H6R contact binary固定layout，static_assert总字节数，未显式endianness标记。|
|64–92 `config/sha256/recomputedConfigHash`|按第一=`key=value`，不trim，duplicate emplace保留第一项、不报错；hash仅去掉所有行首config_hash=的行再加换行。包含额外未知keys仍可hash匹配； hash保证该文本一致而非scientific参数完整。|
|94–101 `verifyThreads`|四个环境thread值必须恰好字符串1，Eigen线程也设1并检查；是可追踪线程限制，不是运行最坏延迟证明。|
|103–120 `readCache`|magic/layout/截断/trailing/reserved/严格time检查，先按header.count分配全vector；没有大小上限、header时间端点/finite/mask一致性/内容hash验证；cfg.expected_records比较发生读取后。NX04。|
|122–149 `vec/foot/median/initialRotation/measurements`|固定values offset gyro0、acc3、force6…9、foot10…21；median sort；比力roll/pitch；4腿mask→R=σ²I。没有raw关节FK、foot_speed使用或在线速度输入。|
|151–177 `checkpoints/reasons`|首末、contact event、每整数秒最近record选P检查点；tie取前；这里只调度审计写出，不改变滤波观测时间。|
|179–203 `validateRotationAndCovariance/topology`|每epoch旋转正交/det+finite；checkpoint时对称/特征值PSD容差相对max(1,尺度)；topology用leg label array.at检查ID。没有所有epoch Cholesky。|
|205–224 输出助手|CSV header，stream fail/bad exceptions，flush+close显式检查；hex raw hash字节。比其它native writer强，但数值有效性不由stream异常保证。|
|228–298 main guards/binding|canonical cache/config/output；output只能有一个config；重新config hash；4种H5或固定H6/H6R yaw bindings，限制sigma/policy/phase；禁止Eq52 selector；仅身份声明字段不执行生物/机械校准。|
|300–336 init|expected rows比较、非空；前5s平均，median gyro<.05rad/s、accnorm接近9.81±.5；初R、bg=平均gyro、ba=平均acc+Rᵀg，设P orientation30deg/velocity1/position.1/bias指定std；H6 yaw绕负world-z。中位数门不能排除全部初始化运动；全prefix不足5s仍可接受。NX03。|
|337–380 policy/初脚/gauge|四Go2噪声数硬编码，无本次硬件校准；初脚Eq32扩维+.1m独立prior；H6非零yaw后左gauge并记录congruence误差，0yaw数值no-op。|
|382–423 output初始化|NAV、diagP、contact/events、innov/NIS、execution ledger、binaryP；H6R可附完整float64 contact；**只有NAV/diag显式17位精度**，默认contact/innov输出6位有效数字。|
|424–443 primary loop|首record只写init；之后前IMU rate＋当前dt传播，mask算survivor/ended/added→production lifecycle；没有GNSS或reference；每record最多一组stackedcontact。mask真实性来自cache，不在此处重估contact detector。|
|444–461 per-epoch gates/injection|state/contactdim一致；可由三个env注入gate失败，其中rotation/P注入只改验证副本，不改filter；covariance injection仅checkpoint会被PSD门捕获。构造预定失败路径不是实际故障数据。|
|462–495 writes|R/v/p/bias/state-role；P diagonal含activecontact空值；gauge yaw=φ_z variance，translation用(位置+各脚)/√(N+1)方向；contactfloat64 inactive NaN明确；创新按survivorIDs；无更新时NIS默认0/factorizationfalse不能算NIS样本；binaryP写Eigen column-major内存和dim，需消费者按合同读取。|
|496–509 final counters/timing|output failure env可抛；要求N−1传播、Eq61同数、Eq52=0；elapsed从cache后init前到loop后，包含init/solver/审计I/O/PSD，排除cache解析及后续flush。NATIVE_COMPARISON只有norm，不是reference误差。|
|510–532 summary/exit|初始化残差由所设bias代数上约为0，不能当独立校准成功证据；大量data role/forbidden/nonfinite计数硬编码，cache/source/executable SHA取cfg/header；成功后所有输出flush/close，异常统一exit1前缀FAIL。未输出完整失败summary，外层应记partial目录。|

H5“无reference打开”的源码证据是本入口只读cache/config；`reference_open_count=0`字段自身是硬编码，不是openat日志。`nonfinite_output_count=0`也没有逐CSV numeric扫描。若cache force含NaN，event ledger可写NaN而filter状态正常；此反例是静态输入路径，不代表现有冻结cache有污染。H6R完整contact binary解决该模式contact精度，但不能自动替代其它模式CSV或创新日志精度。

### 4.3 `tools/official_regression.cpp`

|行/函数组|语义/证据范围|
|---|---|
|27–73 Counts/Differences/jsonArray/split|计数、最大差统计；JSON数组17位、空白tokenizer；不支持任意CSV数据。|
|75–142 `reorderOfficialCovariance/updateDifferences`|官方X列转error offset=3column−6，selection重排contact到sorted ID，bias末6；state/contacts/P最大差。ID不同时计数增加但仍可能在.at抛错，failure会退出；没有所有差的显式finite检查。|
|146–184 initialize|官方R=diag(1,−1,−1)、v/p/bias0，五noise(.01,.1,1e−5,1e−4,.01)；自有P=I₁₅，明确使用**early identity**。|
|185–213 IMU/CONTACT|每非空行先取time；IMU8列，用previousIMU，仅1e−6<dt<1传播；CONTACT成对ID/active，官方setContacts、自己存indicator。注意previous_time在每种record末尾更新，不单独记录最近IMU；该策略只适合目标官方文件记录时序。|
|214–263 KINEMATIC decode/classify|每脚44tokens=ID+quat(wxyz)+p+6×6cov；q.normalize；官方接受完整pose/cov，自有只取translation/cov后3块；按既有contact map分survivor/add/remove。|
|264–292 correction/removal/addition|官方一次CorrectKinematics；自有先subset校正后remove，再add。为复刻早期库same-call pre-R语义，将新增foot和cov用R_afterᵀR_before变换；这是明确的回归适配，不是按reference挑结果。|
|294–319 all-row difference/pass|unknown类型throw；每行更新时间/previousIMU并比较；pass固定59976rows/19992各类/prop、add34/remove33/correct19780/meas26741，配合max差阈值。计数证明特定输入结构，不能当通用数据解析验收。|
|321–382 finalserialization/exit|构造最终群matrix/bias/P，打印全量summary，exit pass?0:1；PSD/min-eigen与asym只是输出，不纳入pass布尔；没有reference精度计算。|

即使该程序曾通过，最多证明被pin官方库与early移植在**那份输入、初值、noise、dt/时序、contact机制**下的回归；它不比较自有reported的Gamma/Phi，更不证明高层Go2 proxy与原论文编码器输入相当。

## 5. 测试与 validator 的逐函数语义

### 5.1 `tests/backend_tests.cpp`（本轮未执行）

|行/函数组|设计覆盖与限制|
|---|---|
|27–59 `require/requireNear/groupPart/withGroup`|断言计数只是assert调用，不是实验次数；错误抛runtime_error；群/完整state转换保留bias。|
|61–92 `discreteErrorMap`|按η=hatXtrueX⁻¹构造真状态与bias偏差，分别exactMeanStep再log得到下一误差；FD直接测试生产Phi，但与被测共享mean/group原语，需其它oracle补充。|
|94–183 `testLiePrimitives`|Gamma/Psi零极限；tiny/normal大角Exp/Log；SEK roundtrip/adjoint；NaN/Inf/finite-overflow拒绝。它不检构造函数非法SO3/不定P。|
|185–240 `randomState/testExactMean`|固定seed随机PVA/contact；4dt×4ω、20000 substeps midpoint积分对Gamma mean；contacts/bias保持断言。substep数不是独立Monte Carlo样本数。|
|242–284 `testAnalyticalPhi`|N=0…4、5dt含0；2e−7中心FD全列、Eq60对照、zero identity；阈值2.5e−7/1e−9。测试使用明确代码扰动，无法凭测试代码推断当今实跑数值。|
|286–476 `go2Noise/testNoiseAndLifecycle`|平方一次、sample std、R；Table1 J映射与负encoder拒绝；五process/mixed矩阵代数；contact排序、共享position crosscov、subset/unsorted/early API拒绝、增删PSD、Eq61/GL64PSD。很多mapper expected重复实现公式，验证连接/单位常数而非独立证明物理noise正确。|
|478–527 `testBackendIdentitySeparation/main`|reported vs GL64同mean/Phi异Qd；early mean不同；调用5组test，异常exit1。测试经过运行才可计PASS；本轮动态次数0。|

### 5.2 `tests/h5_backend_tests.cpp`（本轮未执行）

11–27 `require/go2/contacts`构造固定noise与两脚。29–51验证混入contact ASD被拒、prop/eq61/eq52 counter；53–62验证五字段process类型大小和Qbar shape，不能凭sizeof证明全部语义；64–91比较Eq32与额外独立脚点prior的**全交叉P**、合法survivor-remove-add顺序。名称 `AtomicLifecycle` 只测试合法执行结果，不测试非法addition/ended时事务回滚（NX08）。94–105依次执行三组，异常exit1，不代表本轮已运行。

### 5.3 `tools/validate_backend.cpp`（本轮未执行）

|行/函数组|真实计算和验收口径|
|---|---|
|34–99 constants/emit/number/integer/boolean/flatten/contactIds/groupPart/withGroup|打印分组key=value，数值17位；**emit不登记pass值、不throw**（NX01）；无全局fail计数。|
|101–121 deterministicState/两个noiseprofile|构造固定synthetic状态与noise；Go2数值与pure synthetic分别命名，不能把后者当BY2证据。|
|123–165 OdeState/addScaled/derivative/rk4Mean|独立常ω、a欧氏矩阵ODE RK4，至少2000steps、h≤2e−5，验证mean；导数用production skew而非Gamma解析式。|
|167–198 discreteErrorMap/independentAngleAxisExp|同右误差FD oracle；独立Eigen AngleAxis用于rotation。|
|200–233 independentGammaQuadrature/independentPsiFivePoint|Gamma用20000区间Simpson积分；Psi five-point对**production Gamma**求导，不能把这一项叫完全独立oracle。|
|235–276 BlockExponentialLieOracle/independentBlockExponentialLieOracle/adjointConjugationError|9×9 block exp同时给Γ0/1/2；18×18 Fréchet block exp给Psi，独立于series/closed coefficients；adjoint用群共轭对照，log主值有效区间需保持。|
|278–482 validateLieGroup|零点、21项非法输入函数组合、nearπ、2π±、20/50/100rad、branch continuity与adjoint stress；各行输出pass/误差/阈值，没有把failure传main。|
|484–539 validateMeans|7组已定义dt/ω与RK4；rotation矩阵/geodesic、v/p误差、contact/bias不动分别检查；其中“stress”的阈值与normal不同明确回显。|
|541–639 validatePhi|N=0…4×6dt，5point step1e−5，全matrix/max/blockrelative、Eq58/60、zero_dt；normal与stress门限不同。分母max(1,norm)是尺度保护，不是相对于每个近零块的百分比。|
|641–817 validateCovariances前半|随机state20组N×dt，Eq61 vsGL64差值、PSD/对称/gauge congruence；**pass不要求Eq61等于GL64**，这是有意近似诊断；还输出eq52matrix供外部oracle、零noise。|
|819–1012 validateCovariances噪声连接|Qc已知ASD²常数、dt线性bias比例、Go2/paper contact/FK分离；Table1五process与encoder JΣJᵀ逐项连接。属于实现合同测试，不独立验证真实噪声识别。|
|1014–1112 Table1 stochastic propagation|单seed、300step、rate noise=Tableσ/√dt、bias increment=Tableσ√dt；无contact随机游走注入但P含contact过程项；无correction/NEES，只比bias trace预测和粗state-error阈值。声明使用相同Qbar模型，不能作为真实Table1 discrete语义证明。|
|1114–1180 encoder correction|给定人工J、两脚故意offset、一次非零correct，检查R映射及残差下降/正NIS；没有从原始关节角实际FK，也没有NIS分布检验。|
|1182–1249 exactMeasurement/contactPredictionRms/observableRecoveryError/validationContactOffset/nontrivialCrossCovariance|真值脚点→body测量；contact RMS分母为3N scalar（不是每脚norm RMS）；observable分数把gravity方向、body v、foot m和两bias单位直接相加；只可当自定义软件诊断分数，不能称单一物理误差（NX10）。|
|1251–1315 augmentationOracle/removalOracle/contactMeanMaximumError|独立代码重组F/G/M，实际数学与被测高度相似；核indices/crosscov有用，但不能以此独立证明建模假设。|
|1317–1417 lifecycle cases|非平凡crosscov/anisotropicR，单/多增删及混合顺序；检查全部P和ID，不是只shape；没有异常rollback反例。|
|1419–1486 static recovery|独立扰动初值、4脚静止1200step，无GNSS绝对gauge评价；有限比例门限来自mixed-unit observable score；单case不是四段数据结果。|
|1488–1601 switching/flight recovery|600step按既定事件进入0…4脚，10stepflight；truth用同exactMeanStep，量测由truth生成；会检contactcount/非零innovation；“INDEPENDENT_DETERMINISTIC_SYNTHETIC_TRUTH”意为独立状态变量，传播oracle不是独立实现。|
|1603–1684 synthetic stochastic|单seed300step；IMU/bias按ASD采样，脚位置噪声σ=.01m而R指定σ=.0123m；无contact process truth drift但Qc含contactnoise；因此不是matched-noise NEES/NIS验证，代码也只阈值state/bias/PSD。|
|1686–1721 dwell check|本地lambda重写三样本dwell，对12次chatter与3次stable检transition；没有调用真实cache producer的contact detector，不能据它给上游接触识别标动态通过。|
|1723–1743 stress|大姿态/ω、P对角跨8个数量级、20step传播，检查det/finite/PSD；没有长期一致性或运行时间测量。|
|1745–1935 fullGaugeTransform/gaugeState/validateGauge|给yaw+translation群，adjoint扩bias；base/gauge两filter同inputs更新；恢复base比较state/P、测量不变/innovation旋转、非零innovation、native yaw separation；只测normal/stress两个case，不能取代所有偏置/接触可观性证明。|
|1939–1952 main|6组validator串行；**不检查任何输出pass**，只exception→exit1，其余return0。外层必须解析所有记录且保证数量/coverage，不能以进程成功代替数学通过（NX01）。|

静态gauge理由也可独立给出：固定重力g下，任意平移t与满足Qg=g的world旋转Q，使R→QR、v→Qv、p/d→Q(p/d)+t，body脚观测 `Rᵀ(d−p)` 不变，IMU nominal方程也保持。因此纯接触+IMU系统的全局三平移及绕g一转不能被这些观测确定。是否还有退化不可观方向取决于运动/contacts/bias；代码中两个gauge实验不是完整结构rank证明，不能把密集轨迹/低内部残差当绝对yaw/position精度。

## 6. 原论文完整复现和公平比较仍缺什么

这里只记录现有边界，不启动后续论文任务。当前源码能支持的有限主张是：已实现特定world-centric bias-augmented point-contact InEKF数学与相应验证工具，另有官方API驱动和明确early回归模式。尚不能从这些文件推出：

1. 官方library/binary/include实际pin已与任何历史运行一致；文件内没有完成这一绑定。reported、GL64、early三身份不可合并成一个“Hartley”结果。
2. Go2高层foot位置等价于原论文的关节编码器＋完整几何/J与噪声；H5 encoder adapter调用计数事实上固定0，输入是声明的proxy。contact force/dwell/cache producer不在这8文件，没有借本地lambda覆盖其真实性。
3. noise Table1/Allan定义、实际采样率、Go2高层IMU独立更新频率与足端滤波相关已统一；shared-source/shared-estimator误差相关没有从类型系统消除。
4. 初始化等待、首5s重放、IMU/body/POI杆臂和reference frame已被真实数据证据闭合；h5内部代数zero-acc residual不是独立安装标定。
5. synthetic tests、validator输出记录或early库回归曾在当前源码/环境全部通过；本轮未运行，旧文档PASS不能自动迁移。即使通过也不是非独立reference精度验证。
6. 本地reported实现完成原论文所有实验、随机初值统计、运动捕捉评价、原QEKF对照，或其他两篇文献完整复现/公平横比。

后续最小修正建议是：先独立修NX01的退出状态/外层严格聚合，明示初始化可用时间与cache实际identity；对backend API补SO3/PSD和异常状态合同；用物理输入身份确认何时只能叫FK proxy；固定noise解释和初始P关系后再决定需要哪种最小原生验证。不能根据新数据RMSE选择reported/early/GL64、更换初始prior或FK sigma。候选修改须独立版本并通过合成回归，不替换冻结正式版本；改变正式版本另行确认并独立回归，本次没有应用。
