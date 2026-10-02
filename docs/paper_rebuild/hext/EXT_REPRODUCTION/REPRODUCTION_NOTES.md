# 论文、实现与本次版本

本机 ZIP 的成员及本轮 SHA256 见 `PAPER_PACKAGE_INDEX.csv`。三篇主文实际全文阅读：EXT01 15 页、EXT02 期刊 15 页、EXT03 14 页；另读 EXT01 理论 15 页、实验 14 页及 EXT02 预印本 14 页，共六份、87 页。主要公式还查看原页：EXT01 pp7–11；EXT02 pp8–11、13；EXT03 pp3、4、7。PDF 与页图仅在 `<PAPER_CACHE>`，不上传。全文阅读不等于所有实现已验证；本文件先固定数学目标和差异，再运行。

论文未提供的实验数据/整数真值不编造。本次交付是核心算法实现与项目数据应用，不是作者原实验数据或图表数值的再生产。有限原始来源/作者代码检索未取得三文的可执行作者版本；因此继续使用现有独立实现与原文，而不把 RTKLIB moving-base 当作三文的替代实现。RTKLIB 仅提供已验证的广播星历、原始码 SPP 与 LAMBDA/MLAMBDA 基础设施。

## EXT01：硬长度约束的混合整数最小二乘

主文 §4 Eq(19)–(32)、理论文 Eq(7)–(16)、实验文 Eq(3)–(7) 的目标是

\[
\min_{a\in\mathbb Z^n}\;\|\hat a-a\|_{Q_{aa}^{-1}}^2+
\min_{\|b\|=l}\|\hat b(a)-b\|_{Q_{b|a}^{-1}}^2,
\quad \hat b(a)=\hat b-Q_{ba}Q_{aa}^{-1}(\hat a-a),
\quad Q_{b|a}=Q_{bb}-Q_{ba}Q_{aa}^{-1}Q_{ab}.
\]

复用 `horizontal_literature/ext01_clambda.py` 的 `joint_gls`（白化 SVD，保留交叉协方差）、`conditional_float_baseline`、`constrained_baseline`、`evaluate_candidate`、`search_strict_lambda`。一般各向异性下必须求球面二次约束最小值；径向归一化仅是各向同性特例。现有搜索用 RTKLIB 去相关与初始整数提供上界、用包含条件基线球面项的连续放松下界剪枝，最小未探索下界达到次佳目标后才给证书。这是同目标的工程 branch-and-bound，不是作者逐行代码，也不是任意 top-K 普通 LAMBDA 后归一化。

沿用既有 8 seeds、1,000,000 节点预算；本轮在运行前固定 60 s/历元保护预算（原长预算不作为实时保证），耗尽保留 `SEARCH_INCOMPLETE` 等实际状态，不输出假固定。原文没有规定 ratio 接受检验，所以整数候选返回/全局证书与正确固定率分开。逐历元冷启动由实验文明确支持。项目 0.350 m、RAWX sigma floors、数值容差均不是论文实验参数。旧 R1 精度失败与 R2 搜索验证保持原版本。

## EXT02：单基线 C-WLS

以期刊 Algorithm 1/2、Eq(54)、(58)、(62)–(75) 为准：先由模糊相位的整数可行范围得到球面圆，遍历圆对的交点及近切 peak；按完整码/相位协方差的 wrapped 目标排序，保留 K 并从这些起点细化。基线写成 `b=l*r, ||r||=1`，观测/设计统一为 cycle / cycle·m⁻¹，堆叠顺序 `[phase, code]`。

\[
f(r)=\begin{bmatrix}\operatorname{wrap}(\psi-lHr)\\\rho-lHr\end{bmatrix}^{T}
Q^{-1}\begin{bmatrix}\operatorname{wrap}(\psi-lHr)\\\rho-lHr\end{bmatrix},
\quad \operatorname{round}(x)=\lceil x-1/2\rceil.
\]

现有 `ext02_cwls.py` 的设计、圆对几何、完整 Q 的 `wrapped_objective`、各向异性球面细化可复用。论文单基线支路适用于两天线，本次不实现或伪称多天线三轴姿态。相关 Q 下仍计算原 wrapped 目标；不把论文对角 Q 的等价充分条件推广成任意 Q 下与 C-ILS 等价。

本次需补的具体边界：旧 `intersect_sphere_circles` 切点分支提前返回；Algorithm 1 的 else 应分别检查两个 peak，另一 peak 在 `|Delta|<0.05` 时也要入池。反例：第一圆 normal=x、offset=0.02，第二圆 normal=z、radius=0.02、offset=sqrt(1−0.02²)，两个 peak 距第一圆平面分别 0、−0.04。新版本补该候选并测试，旧文件保留。

期刊明确 `delta_Delta=0.05`，预印本未给数值；两版的核心公式/Algorithm 1/2 相同。K 的固定值原文未给，沿用项目 `K=全部唯一候选`；这是执行 best-K 且 K 取池大小，不称该步骤“可选”。20 次、方向容差 1e−10、整数稳定、任一候选未收敛则拒绝该历元，是既有工程失败策略，保持并单列，不能称论文规定。子问题最优性不等于整个 C-WLS 全局证书。

两版原文自身还存在精确半整数边界差异：Eq(24)/(26) 用 `psi−round(psi−pred)`，Eq(75) 用 `psi+round(pred−psi)`；half-down 不是奇函数。`psi−pred=0.5` 时，前者残差 +0.5，后者 −0.5，完整相关 Q 的交叉项可能不同。现有代码逐字保留 Eq(75) 的细化，最终用 Eq(54) 排序。本次不暗改负号；新增半整数及邻近浮点测试、并列保存两种目标，适用边界可见。

## EXT03：DD-KF 中的带噪声长度伪观测

Yang §II Eq(1)–(9)、§III-C：联合状态 `x=[b_N,b_E,b_D,N_DD...]`；GPS L1/L2 与 BDS B1/B2 分星座双差；长度行线性化在 `b0`，`h_s=b0/||b0||`、观测 `s`、有限方差 `sigma_s²`，加入 KF 后用 MLAMBDA 返回两个候选，次佳/最佳目标比达到 3.0 再恢复 fixed baseline。这是随机伪观测，不是 EXT01 的精确定长或输出后长度筛选。

复用 `ext03_yang2024.py` 的 `build_dd_observation`、`reconcile_ambiguity_state`、`map_prior_dd_ambiguities_to_target_basis`、`detect_cycle_slips`、`constraint_update`、`mlambda_resolve`、`process_epoch`。码/相位顺序与论文互换时必须连同 H/R 一起置换。验证包含伪观测顺序/堆叠等价、pivot 与交叉协方差、周跳重置、ratio 两候选和无先前 fixed 的启动。

论文明确的数值是 ratio=3.0，初始 baseline 方差 900 m²、ambiguity 方差 900 cycle²。0.350 m 是本项目物理安装；原论文静态/动态 7.99/1.23 m。旧 registry 把 0.350 写为 paper-disclosed 的错误在本次参数表纠正，不改封存旧合同。原文完整 Q/F/R、长度 sigma=0.010 m、GF/MW/prior-DD 阈值、首次均值和 fixed 值过期规则没有充分给出；沿用已登记工程默认并保留这些实现假设。原文静态 BDS B1/B3，动态 B1/B2；本次必须验证数据确有动态双频，不把 GPS-only 名称换成 GPS/BDS。

“single-epoch mode”与 KF、周跳检测、前次成功 fixed 方向同时出现在全文，不能仅凭这个词证明每历元清空全部状态。沿用已有 moving-base 工程实例：每历元原始码 SPP 重置 baseline 先验及其交叉项，ambiguity 递推/重映射，保留上次成功 fixed 方向用于长度行；明确不是声称取得了作者唯一实现。主文精度使用 fixed-only，本次同时报 ratio-fixed 精度、全 valid、失败与因果 held，绝不把 all-valid 偷换成论文 fixed-only。

## 三方法共同的输入修正与保留近似

现有 `shared_raw_backend.build_gps_l1_double_difference_model`、`phase3_runner.build_epoch_blocks` 用两接收机伪距均值生成一份共享卫星状态，没有表示各接收机的卫星发射时刻。既有 DG01R 证明这项差异可达到多个 cycle 的量级，但其 HPPOSECEF 诊断不是可在线复用的答案。本次只用各自原始码/载波、广播星历和 code-only SPP。

官方 [u-blox RAWX 接口](https://content.u-blox.com/sites/default/files/products/documents/u-blox8-M8_ReceiverDescrProtSpec_UBX-13003221.pdf) p410 定义 rcvTow 为接收机本地时刻、近似对齐 GPS。已有 RTKLIB `satposs` 从每个接收机自己的 `(T_raw,P)` 得到 `t_tx=T_raw−P/c−dt_sat`，在码与时标一致的契约下已经消去接收钟；本次不再扣 NAVCLOCK。对各自卫星状态使用几何飞行时间作 Earth rotation，不把含钟偏的 P/c 当几何飞行时间，也不重复添加 Sagnac。

令 `x0` 为接收机 1 的 code-only SPP，`rho_i,s=||sat_i,s−x0||`，`e_i,s` 为对应 LOS。对同系统同频信号，先移除

\[
k_s=\rho_{2,s}(x_0)-\rho_{1,s}(x_0)-c(\delta t_{s,2}-\delta t_{s,1}),
\quad y_{DD}=\Delta_s[(y_2-y_1)-k_s],
\quad H_{DD}=-(e_{2,s}-e_{2,p})^T.
\]

共接收钟在卫星差分中消去，整数未改变。若使用大气项，码与相位电离层符号不可混同；极短基线剩余大气按既有模型处理。新纯模型测试固定检验符号、零基线/已知 baseline、卫星钟、时间规范不变性、交换接收机/pivot、各向异性相关 Q；不借参考挑符号。

保留近似：`x0` 误差乘两时刻 LOS 差；相位几何项对含噪原始码的极小依赖尚未传播入旧 R；两天线的物理采样时刻并非严格相同，因此输出连接两个采样时刻的位置，运动导致的长度差不能无证据称已知亚毫米。不得把这些限制隐藏为严格同步/精确随机模型，也不得从同一误差曲线反求校准。SPP2−SPP1 仅为 EXT03 明示的 float 初始化，不作 fixed/文献法输出替代。

## 冻结配置和结果边界

每方法一套配置跨三序列：EXT01/02 GPS L1 单历元；EXT03 GPS+BDS 双频递推实例；长度 0.350 m。保留原 RAWX 有效位、half-cycle/lock/周跳及按系统/信号分块的整数结构，不二次补半周。所有方法从完整原始文件历史开始；BY2H 旧合同起点结果另列，新运行不沿用只含 1,423 对的缓存代替 1,483 对完整输入。评价窗沿用 BY2 [66,340]、BY2H [413,683]、BY2O [3186,3563] s，时间与固定安装转换不调优。

新实现/测试与输入 pin 完成后登记九个方法×序列运行身份。搜索或数据失败保留原分母；整数真值未知。旧 RTKLIB V0/V0E/V1/V2 和原 V3 只读取原结果，不因本次输入修正自动重跑；同窗不同有效支持分别报告，另列共同支持。退化只有原始码/载波故障同层适用才可比较，否则写“暂无同层退化对比”。

新输入已完成同一次读取CRC/hash核对，详见 `INPUT_PINS.csv` 和 `INPUT_PREPARATION.json`；三序列配对为1509/1483/2231、配对失败均0。六个raw源CSV与既有锁一致，六UBX/六NAV与原OUTPUT_HASHES一致。九个新增身份见 `RUN_QUEUE.csv`；执行科学源码与库hash在调用时再次绑定到已提交版本，未启动科学运行。
