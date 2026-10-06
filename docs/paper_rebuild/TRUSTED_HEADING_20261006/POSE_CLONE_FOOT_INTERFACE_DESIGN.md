# 单历史位姿克隆的足端约束：工程接入判断

状态：只读源码审查与解析设计，尚未实现、未执行任何新算法测试或实测。审查时 HEAD 为 af3843a3328d458536d2df32cbd1a82a1642d0a1。本记录不是论文材料或效果结论。

若目标是接入有限位移，建议采用 **21 个当前误差状态 + 6 个历史位姿误差的完整联合克隆**。当前航向主线则优先考虑末节更小的 **21+3 历史姿态克隆**，精确消去未标定平移/杆臂，不先推进完整位移接口。共享 IMU 对两时刻姿态的影响留在联合协方差中，直接比较同一支撑足的世界坐标，避免把外部 gyro 旋转当成另一份独立观测。当前 21 维机械编排和 F/G 方程可保留，但联合更新、反馈/reset、所有观测的 cross-P 维护必须改变，不能称为只增加 provider。

当前足端数据与杆臂资格不足，故这只是工程设计；不启动真实接入。单克隆也不自动处理 SDK 内部相关性或重复使用足端样本。

## 1. 已核源码与物理点

- cpp/legsa_v23_port_core/include/legsa_v23_port_core/types.hpp:38–50：位置、速度、姿态、陀螺零偏、加计零偏、陀螺比例因子、加计比例因子各三维，共 21。
- cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp:475–531：预测 P←ΦPΦᵀ+Q；更新 dx←dx+K(dz−Hdx)，Joseph P；反馈位置减 DRi·δr、速度减 δv、姿态左乘 Exp(δφ)，bias/scale 加，然后清零 dx。**当前没有协方差 reset。**
- 同文件 :951–961：位置预测使用 IMU→GNSS1 的 antlever_m。它不是本因子所需的机体原点→IMU 杆臂，不能直接复用。
- cpp/legsa_v23_port_core/src/common/earth.cpp:47–55,71–78,96–113：E=cne(BLH) 将 NED 转到 ECEF；DRi 将 NED 米转成 BLH 增量，高程符号为负。
- cpp/legsa_v23_port_core/src/kf_gins/insmech.cpp:54–76：机械编排使用移动 NED，两时刻的 NED 分量不能直接相减当成共同世界坐标。

以下 p_k 是足端相对机体原点的位置，l 是机体原点→IMU 的固定杆臂，q_k=p_k−l。p、l 必须处于机械编排姿态 C 使用的同一刚体轴。SDK FLU→FRD 和 IMU 安装变换需明确绑定，不能因都叫 body 而略去。SportModeState.foot_position_body 的命名及内部一致性不证明它是原始编码器纯 FK，也不证明与 IMU 独立。

既有 foot_translation.py 仅作条件有限位移的 oracle/诊断对照。其作者已执行 24 项局部测试，本审查未重跑；有限位移除以 dt 仍不是转动时末时刻的瞬时 body velocity。

## 2. 残差与反馈符号一致的 H

建议只把历史 clone 保存为 ECEF 位置 r₀、body→ECEF 姿态 C₀，当前保留原 BLH、body→NED 的 Cbn₁。不必重写 INS 为 ECEF。

每个连续支撑足的三维零观测残差：

    h = r₀ + C₀q₀ − r₁(BLH₁) − E₁Cbn₁q₁ ; dz = h
    u₀ = C₀q₀ ; u₁ = E₁Cbn₁q₁

[a]× 表示叉乘矩阵。按照 h'≈h−H dx，clone 反馈定义为 r₀'=r₀−δr₀ᴱ、C₀'=Exp(δφ₀ᴱ)C₀。当前沿用源码 BLH'=BLH−DRi·δr、Cbn'=Exp(δφ)Cbn。

不能漏掉 E 随位置反馈变化。定义 K 的第 j 列：

    K[:,j] = vee( ((∂E/∂BLH) DRi[:,j]) Eᵀ )

于是 δE≈−[Kδr]×E。每足 H 的非零块为：

    H_current.position = −E₁ + [u₁]×K₁
    H_current.attitude = −[u₁]×E₁
    H_clone.position = +I₃
    H_clone.attitude = +[u₀]×

当前速度、bias、scale 的直接 H 块为零，但仍可经 P 交叉项更新。按仓库 cne，K 的三列是：

    [ −east_E/(RM+h), z_E/((RN+h)cos(latitude)), 0 ]

east_E 为 E 第二列，z_E=(0,0,1)。仅在原导航非极区、DRi 有定义的域使用。这是 cne 的位置导数，不是新增动力学。

固定局部切平面也可安全使用：选定不再随状态改变的 E_*，将整个 ECEF 残差/H 左乘 E_*ᵀ、R 同步变换，结果等价。**不可直接混用两个移动 NED，或略去基变化却称精确。** 采用 ECEF 残差或固定切平面不需要“短窗足够小”的坐标近似；EKF 仍是一阶线性化。

## 3. 增广、传播与所有观测更新

在 t₀ 已消费观测完成反馈/reset、dx=0 后，从当前状态创建 clone。其 6×21 增广 J：

    J_position,P = E₀
    J_attitude,P = −K₀
    J_attitude,PHI = E₀
    其余块 = 0

    P_aug = [ Pxx,       Pxx Jᵀ
              J Pxx,     J Pxx Jᵀ ]

不能把 cross-P 设零、把历史位姿当确定值，或另编独立历史精度。确定性增广允许全 P 奇异，不能为通过正定 Cholesky 而补虚假噪声。

clone 名义 ECEF 位姿在预测中固定；保留原 Φ21、Q21：

    Pxx⁻ = ΦPxxΦᵀ+Q ; Pxc⁻ = ΦPxc ; Pcc⁻ = Pcc
    dx_x⁻ = Φdx_x ; dx_c⁻ = dx_c

所有旧 GNSS/RD/RP/HV/carrier 观测都须以 [H21,0] 进入联合更新。即便 Hc=0，也通常有 Kc=PcxHxᵀS⁻¹，因此 full clone 的历史均值/Pcc 会受当前观测更新。只在足端更新时维护 cross-P 会出错。

足端使用 H=[Hx,Hc] 和完整 S=HPHᵀ+R，联合 Joseph 更新；source-aware 创新统计也必须使用同一完整 dx/H/P。旧 21 维观测构造可以保留，由联合入口自动 padding，但不能保留另一份未同步 P。

删除 clone 时只取后验当前均值与 Pxx 主块（边缘化），不能做“clone 误差已知为零”的 Schur 条件化。新的 clone 从新的 Pxx 重新增广。

## 4. 新分支的反馈/reset 边界

现有 stateFeedback 清零 dx 而不变换 P。新研究分支应明确 reset 坐标规则，legacy 默认路径不改。

按 true=Exp(δφ)C_old、C_new=Exp(a)C_old：

    δφ_new = Log(Exp(δφ)Exp(−a))
    Gφ = J_l(a) = I + 1/2[a]× + O(||a||²)

可用完整 SO(3) 左雅可比及稳定小角分支。该正号已由独立解析复核确认；当前尚未执行 retraction 有限差分，实施前仍须独立 FD 核验。常见负号属于其他误差定义。它是 reset 的局部导数，不是非线性后验的精确协方差。

沿用当前 BLH retraction，位置 reset 局部块为：

    G_current,P = DR(BLH_new) DRi(BLH_old)

当前速度/bias/scale 加性块为 I，姿态为 J_l(a₁)；ECEF clone 位置为 I、姿态为 J_l(a₀)。整块执行 P←GPGᵀ，包含全部当前—clone 交叉项。第 2 节 cne 导数与此 reset 是两件事。

首版研究支路应关闭 QA recovery 的 yaw correction clipping，或另推导其实际残余均值及协方差。现源码可能截断姿态反馈后仍清零整个 dx，不能用未实际应用的 a 做 reset。

建议研究开关开启后，有无 active clone 均使用同一研究 reset 约定，避免生命周期中切换误差坐标规则。历史 21 维路径不动；以后因果比较需共同采用新 reset 的 foot-off 对照，不能把 reset 差异全算成足端收益。

## 5. Full joint 与单 Schmidt clone

Schmidt 也保留历史均值、Pcc、Pxc，只人为设 Kc=0。使用同一 S：

    Kx = (PxxHxᵀ+PxcHcᵀ)S⁻¹
    Pxx⁺ = Pxx−KxSKxᵀ
    Pxc⁺ = Pxc−Kx(HxPxc+HcPcc)
    Pcc⁺ = Pcc

历史均值不反馈；当前 reset 后 Pxc 还要左乘 Gx。对于普通 GNSS/RD 的 Hc=0，仍须 Pxc⁺=(I−KxHx)Pxc，不能漏掉。

两者都需要所有当前更新的 cross-P 维护、因果生命周期及噪声合同。Schmidt 省历史增益/反馈，但不把历史变确定，也不解决足端噪声相关性；它是不同估计器，不能当成 full joint 的同结果替代。

仅一个 clone 时 dense P 从 441 增至 729 个 double，增加 2304 字节；S 的维数仍取决于观测行数。建议先 full joint，便于与独立联合线性模型核验，主要工程复杂度并不会因 Schmidt 消失。不扩展多 clone 或 FGO。

## 6. 测量协方差及尚未解决的相关性

在名义姿态条件下，输入位置/杆臂的每足雅可比：

    ∂h/∂p₀ = C₀
    ∂h/∂p₁ = −E₁Cbn₁
    ∂h/∂l = E₁Cbn₁−C₀

全部共同支撑足堆叠，以含跨足、跨时、共同杆臂项的联合 Sigma 构造 R=L Sigma Lᵀ，并登记接触运动的工作模型。姿态/IMU 已在 state P 中，不再把同一 gyro 外部积分 R 的旋转方差独立加一份。多足共滑移仍可能无法从内部残差识别；单足不提供完整相对位姿约束。

标准更新暂要求观测噪声 n 与状态误差 e 不相关。SDK 内部估计、此前同 SDK 来源的 RP/HV、重复使用足端端点、持续杆臂误差都可能破坏该假设。pose clone 只处理状态之间的相关性，不自动估计 C_en=Cov(e,n)。

若 C_en 已知，按 dz=He+n：

    S = HPHᵀ+R+H C_en+C_enᵀHᵀ
    K = (PHᵀ+C_en)S⁻¹

此时还需相应广义后验，不能称普通独立噪声 Joseph 更新严格成立。未估计 C_en 时只能记录工作近似，R 膨胀不是修复。

首版最小设计仅使用不重叠端点 pair，每区间尝试一次：(t₀,t₁) 消费后记录全部 row IDs，下一对从新 t₂>t₁ 开始，不立刻把上一终点当下一起点反复融合；同源 SDK velocity/足速度不同时作为另一独立测量加入。即便端点不重复，SDK 时间滤波和固定杆臂误差仍可能相关，不能声明已经独立。

如必须每 0.2 s 滚动复用同一 p₀ 或共享终点，单 pose clone 6 维并未封闭测量噪声；需要相关测量处理或足位置/噪声状态。这不属于本次最小设计。

## 7. 最小接口与后续实现门

建议数据接口（未实施）：

- PoseCloneSnapshot：clone_id、t₀、名义 ECEF pose、cross-P/Pcc、error/reset convention，仅由 filter 创建。
- FootContactEndpoint：source_time、available_time、row IDs、foot IDs、p_body、frame/install 身份、contact episode、完整区间连续性、来源声明。
- FootPairObservation：clone_id、t₀/t₁、共同足集合、两个 endpoint、独立 body→IMU lever 身份、联合 Sigma、一次使用 token。
- createCloneAtCurrentState / updateFootPair / retireClone，默认关闭；不得伪装 GNSS、carrier FIX 或瞬时 body velocity。

只有滤波到达 t₀、来源已可用且反馈完成才能创建；t₁ 应与当前状态时刻一致且来源已到达。若 t₁ 数据迟到时滤波已到更晚且未保留 t₁ pose，首版拒绝，不能把旧足位置绑到新姿态或回填使用时间。真实延迟处理需另设计，不暗中扩成本轮第二个 clone。IMU 分段仍遵守已审增量守恒和 availability 规则。

生命周期 EMPTY→ACTIVE→UPDATED_OR_REJECTED→RETIRED；接触中断/episode 变化/连续性未知/超时/重复 token/无效坐标或协方差即拒绝并退休，相同脚名重现不复活。clone 创建本身不构成测量，支撑状态不证明无滑移。

未来必要小测试：真实 retraction 的 H 有限差分（含 cne）；ECEF 与固定切平面等价；非零杆臂纯转/平移与既有有限位移 oracle；增广/传播/全部普通观测/足更新/reset/边缘化的独立联合线性模型；full/Schmidt cross-P；共平移/共旋转规范自由度；接触、共滑移、重复/迟到反例；默认关闭兼容和研究 reset-only 对照。当前未执行这些测试。

## 当前采用判断

SportModeState 只提供 body-report 字段；既有来源合同明确 raw_joint_encoder_urdf_fk=false。当前没有已登记的机体原点→IMU 物理杆臂标定。故现阶段 **只保留本工程设计，不触发真实 provider/native 接入**。不能用默认零杆臂、R 膨胀、字段名或内核单元测试把来源说成独立，也不能宣称解决垂向退化。

后续优先完成载波闭环。速度/完整位移分支已有有限区间运动学内核，真实接入资格仍不足；下面的脚对方向约束可作为范围更小的后续工程候选。足因子只补相对运动，不定绝对 yaw；任何 H/V/yaw 收益和风险须按三条 V3 完整窗合同验证。该结论不修改原完整目标，也不把设计交付冒充新算法成功。

## 8. 更贴合航向主线的 21+3 姿态 clone 候选

**实现前解析修订：** 前一版使用 world residual u₀−u₁，其解析 H=[−skew(u₁),+skew(u₀)] 本身正确；但非零 residual 时 H[I;I]=skew(u₀−u₁)，不能保持共同世界旋转的零空间。没有执行该准备形式，也不是已运行代码失败。最终首版选择下列 body0 相对残差；旧 world 形式仅保留为推导历史。

对同一连续支撑的有序足对 i、j，d₀=p₀,i−p₀,j、d₁=p₁,i−p₁,j。两足世界静止约束相减精确消去共同平移和 body→IMU 杆臂，再转到历史姿态 body0：

    R₀₁ = (C₀ᴱ)ᵀ E₁ Cbn₁
    h_body0 = d₀ − R₀₁ d₁
    u₁ = E₁ Cbn₁ d₁

两端 C 是 filter-state linearization，不是另两份独立姿态测量。位置应处于同一物理 body 轴；SDK FLU/FRD 和静态安装映射仍显式输入。此形式不需外部 gyro R。

世界角误差（current/clone 顺序）和保留当前 NED retraction 的 H 为：

    H_world = [ −(C₀ᴱ)ᵀ[u₁]×, +(C₀ᴱ)ᵀ[u₁]× ]
    H_current.position = +(C₀ᴱ)ᵀ[u₁]×K₁
    H_current.attitude = −(C₀ᴱ)ᵀ[u₁]×E₁
    H_clone.attitude = +(C₀ᴱ)ᵀ[u₁]×
    J_clone,P = −K₀ ; J_clone,PHI = E₀

任意非零残差下共同世界旋转仍保持 null；单非零脚对的联合角灵敏度 rank 2，不补绕脚对方向的第三轴。当前位置的小块是移动 NED 参数化耦合，不是脚对量测获得平移信息。相对角约束不单独确定绝对 yaw，长度差不是第三个旋转自由度。

输入四点处于统一 body 轴时：

    L_pair = [ I, −I, −R₀₁, +R₀₁ ]
    R_pair = L_pair Sigma_(p₀i,p₀j,p₁i,p₁j) L_pairᵀ

输入有 FLU/FRD 与安装映射时，L 对应块显式右乘该端映射。保留四点全部跨足/跨时相关项。多脚对共享足时不能独立逐对融合；需独立差分组及联合协方差，或显式处理冗余/秩，不能用 floor 制造独立信息。首版只需预先确定的一对，不按残差选脚。

clone 的传播、所有旧观测的 cross-P、正号左乘 reset、退休规则沿用前述设计，尺寸从6降到3；dense P增加135个double，即1080字节。优先full joint。首次内核仅验证残差/J/Sigma/reset，不实现24维滤波。

相减可消掉每个端点所有足的共同平移报告误差，但不证明消除 SDK 共享姿态误差、时间相关性或共同接触运动。保留端点不重用、完整支撑episode、source identity与GNSS输入声明分离、IMU独立性未知。该因子仍可经P影响H/V，因此不能说“方向因子就没有垂向风险”。

结论：21+3脚对方向因子比先接21+6有限位移更适合下一小步航向工程假设，可避开未标定杆臂；不能以此跳过来源/时间/相关性和三窗完整导航采用门。本记录及局部内核都不宣称真实航向改善。
