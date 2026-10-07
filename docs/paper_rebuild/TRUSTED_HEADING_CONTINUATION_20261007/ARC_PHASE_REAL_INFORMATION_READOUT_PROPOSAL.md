# 已有两端姿态下的相位信息读出提案

状态：**仅提案，未执行，未读取本轮真实 prior 或相位载荷**。须先确认 `ARC_NATIVE_REPLAY_ATTEMPT01` 六次调用封存、三对共同输出身份门及独立审计通过，再冻结读出源码、全部输入 SHA、目标和有限预算。native 正在运行不代表这些前置门已满足。本轮问题仅为：在同一 END 条件信息集及明确的工作假设下，已有相位对比能否收紧已有联合姿态二阶矩界。

## 固定来源与连接

只消费已封存的三份 `ARC_JOINT_PRIORS.jsonl`、三份 `ARC_LIFECYCLE.csv`、对应 source CSV/manifest、native COMPLETE/ALL_NATIVE_SEALED，以及 `ARC_PHASE_SAVED_MODEL_ATTEMPT01` 的三份 `*_DETAILS.jsonl.gz` 与原封存摘要。不重开 NPZ、RAWX、原始关节、reference、NAV/STD、provider 载荷，也不重建原相位模型。

原 producer `scripts/paper_rebuild/carrier_phase/arc_phase_saved_model_qualification.py:326–354,384–397` 的精确键为：

- 全部 921 行：`row.sequence/block_index/first_epoch_index/last_epoch_index/start_s/end_s/status/endpoint_models_available`，及原 unknown availability/未准入标志。
- 有合法两端模型时：`epoch0_fingerprint/epoch1_fingerprint`、`relations`、`G0/G1`、`endpoint0_Q_contribution_m2/endpoint1_Q_contribution_m2`、`conditional_unknown_cross_second_moment_bound_m2`、`bound_scope`。它们已经按保存的关系映射；不可再次用 `F0/F1` 重映射 Q。
- `z_m`、`F0/F1`、旧谱/秩等字段随 JSON 解码会接触，但本次不作为数值诊断输入；不算残差、不用旧 rank 挑块。缺失模型行只读 `endpoint_model_status` 和行身份。

连接键固定为 sequence + block_index + 两端 epoch_index + 两端原始 binary64 时刻 + 两个已封存 PhaseEpoch 指纹。native `block_id=sequence:BLOCK:index`、端点 ID 是已声明的派生 ID，不能冒充原 RAWX key。核 source/replay/state 的精确 bits；只用 `COVERED_END_PRIOR` 的真实 END 快照，绝不取最近 IMU/NAV 或重用相邻块。缺失模型的 61 块仍保留，空指纹不补造。指纹是 PhaseEpoch 内容摘要，不是 NPZ 文件哈希。

## 同条件先验与线性化

使用 native END 经 ordinary update/full reset 后的完整 `P24`、`dx24`、`clone_C0_given_end`、`current_cbn/current_blh/current_C1`、`J1/B6/P6` 与 `conditioning_information_id`。不能用 START 时未修正的 `start_C0` 替换 END 的 clone nominal。

先按已冻结 Earth/clone 公式由 END BLH 重算 `E=cne(BLH)` 和 `J1=[−K at position, E at PHI]`（`attitude_clone.cpp:144–161`），核 `current_C1=E current_cbn`，并构造

    B6 = [[0_(3×21), I3], [J1, 0_(3×3)]],
    P6_check = B6 P24 B6ᵀ.

保留位置 frame 项和完整 cross；不得直接截 PHI/clone 两个 3×3 边缘。核封存 B6 的零/单位/复制 J1 块；P6 比较在其正对角自然尺度下最大误差 ≤2e−10，零对角行/列必须精确为零。J1 非零项相对尺度误差 ≤2e−10（尺度下限1e−15），结构零必须仍为零；C1 矩阵最大差 ≤1e−10。这些容差在读数据前冻结，不按失败放宽。P24/P6 的有限、对称与数值 PSD 资格复用既有对角归一化规则；无 jitter、截谱、删 cross、投影 PSD 或重标定。允许现有 API 对已通过对称性门的计算表示，保留原输入与误差，不替换封存矩阵。

固定旧配置向量 **l=[0,−0.35,0] m**，仅称 `INHERITED_ENGINE_FRAME_WORKING_ASSUMPTION_NOT_PHYSICAL_EXTRINSIC_PROOF`；没有新的安装资格，不再凭观察结果做 roll 旋转。设 C0=`clone_C0_given_end`、C1=`current_C1`，bi=Ci l；调用现有 `arc_phase_information.linearize_geometry(G0,G1,C0,C1,l)`：

    h = G1 b1 − G0 b0,
    H = [G0 [b0]×, −G1 [b1]×],
    z − h = H e + n,   e=[δθ0_ECEF; δθ1_ECEF].

这与 native “从 nominal 到 truth 的正左姿态误差”一致。保留该函数给出的两端 baseline-spin gauge；报告 HN，不把有限 proper prior 造成的投影变化说成相位直接观测 gauge 或绝对 yaw。SO(3) 资格沿用 API 的1e−10门，不归一化旋转。

## 两层未知相关性与严格条件措辞

原跨端点噪声 cross 未知，冻结

    Q0′ = endpoint0_Q_contribution_m2,
    Q1′ = endpoint1_Q_contribution_m2,
    Rbar = 2(Q0′ + Q1′).

与保存的 `conditional_unknown_cross_second_moment_bound_m2` 做同尺度一致性核；不改 R、sigma、间隔或关系集合。**只有假设这些 Q′ 在当前 I_END 下仍上界对应端点误差二阶矩，且 native P6 在同一 I_END 下上界姿态误差二阶矩，Young 结果才是有效上界。** 原 RAWX 工作 Q 与 native 工作 P 没有证明这些物理前提，也没有覆盖已知的全部偏置/安装/同步误差。将输出显式置 `physical_second_moment_bounds_qualified=false`；数值结果只能称“在这些假设下的工作界”，不能称实测可信度。

state/phase cross `C_en` 始终 UNKNOWN；state-state P01 不提供 C_en。只调用 `diagnose(..., mode=UNKNOWN_CROSS, covariance_kind="SECOND_MOMENT_UPPER_BOUND", error_model="SECOND_MOMENT_ABOUT_NOMINAL", C_en=None, actual_available_time_s=None)`，qualification_note 明写上述假设及缺证。此轮 **不运行 ZERO_CROSS 或 SUPPLIED_CROSS**，不把 unknown 写成零。与 END 同条件的 PVT/GNSS、SDK/anchor 依赖及未来源时标/重复来源计数一并报告。真实 NED-HV 是绝对最近源选择，故 P 仅为 **offline executed-prefix working prior**，不声称所有来源在线因果；源时刻未来也不等于知道实际到达时间。

## 预先冻结的四个目标与调用次数

全部在同一 ECEF 误差坐标下计算：

|目标|固定 W|解释|
|---|---|---|
|current|diag(0,0,0,1,1,1)|END 三轴 trace|
|joint|I6|两端总 trace|
|relative|LrᵀLr，Lr=[−I3,I3]/√2|归一化相对扰动 trace|
|common|LcᵀLc，Lc=[I3,I3]/√2|归一化公共扰动 trace|

沿用原 **ε={1/64,1/16,1/4,1,4}** 与 skip(ε=0)，原逐候选 tie/选择顺序不变。只报告 T、J、J/T（T=0则NA）、连续存在性/边界状态、原五点 grid 分数及选中 ε；不搜索连续最优、不调 W，不在四目标中挑最好的作为总成功结论。不改善仅指已声明 Young 族/目标，不自动证明所有未知 cross 算法都不可能改善。

现有 `diagnose` 每次返回 joint/current/declared 三目标。每个已通过资格的合法交集块固定调用 **两次**：declared=relative 和 declared=common；joint/current重复结果须一致，只报告一次。因此上限860次 geometry linearization、1,720次 diagnose、5,160次内部 Young 目标计算（含固定重复）、25,800个 ε 候选分数。无 phase residual API 调用；不是把真实残差设成零，也不创造零观测。所有结果保持 `navigation_admitted=false/state_updated=false/P_posterior=None`，没有状态或文件输入回写。

## 全分母、失败与输出

预先以921块为主表，保留 coverage（covered/initial/terminal）×保存模型合法/不齐的交叉表；再逐层列合法且有prior交集、身份/映射资格、P24/P6 PSD、Rbar SPD、H/旋转有限、诊断成功/UNRESOLVED。61不齐块不能消失；covered不等于合法，合法860不等于都有prior。四目标的通过/无改善/边界/未解析均用共同交集及全921双分母展示，不按任何收益、源时刻未来、复用或 residual 筛块。

身份/哈希/文件截断/重复键是全局技术失败，立即停并保留部分输出；预登记的 PSD/SPD/有限性或 API `InformationError` 是该块资格结果，记原因与NA后继续全分母，不修复矩阵或换参数。未知来源字段原样NA，不伪造0。native COMPLETE 已保存的三来源时刻/复用汇总直接继承；为给每块来源标志，允许将每序列已封存 conditioning ledger 单次流式读入并按 START/END ordinals 绑定，不读 provider。标志只分层报告，不门控或删除块。

产物限制为 `BLOCKS.csv`（921行）、`OBJECTIVES.csv`（至多860×4行，含原5grid+skip的固定列）、`SUMMARY.json`、`RESULTS.md`、调用/访问记录及输出 SHA 清单；大矩阵细节仅留注册 scratch。没有图、NAV精度、故障阈值、方向点、整数搜索或跨块信息累计。

## 后续需登记的有限预算

|项|上限|
|---|---:|
|新离线诊断进程|1，单线程，建议600 s硬超时，0重试|
|真实 TELEMETRY prior|3文件，合计≤921行，每文件单次解码|
|保存 phase DETAILS|3文件，合计921行，每文件单次解码；包含z但不使用|
|生命周期 / source endpoint 元数据|921行 / 1,842行，单次解码|
|conditioning ledger|三份单次流式读取；确切行数/字节上限须由native封存清单在登记前固定|
|P24→P6/PSD资格|≤921个已有prior，不按相位资格挑prior|
|geometry / diagnose|≤860 / ≤1,720，以上固定4目标|
|native / evaluator / phase residual / provider / raw / reference / NPZ|全部0|

读取时流式核输入封存 SHA，避免另开大载荷做重复遍历；前后检查输入 stat 与固定来源 pin，输出逐文件 SHA。确切 prior/DETAILS压缩和解码字节、行长上限、metadata闭包、源码/hash及已有数学局部资格引用要在实施后由根代理登记，不能以本提案代替执行授权。新增实施只做有限本地合成接口资格，预算另列；已通过的12项数学内核不默认全套重跑。

即使该读出发现条件工作界可缩小，也只回答“这个先验/几何/二阶矩假设下有没有可用增量”。持续可信航向仍须补实际来源/噪声/相关性与可用时标资格，再另登记故障与导航收益验证。

## 原生结果到达后的登记收紧

9c0641b真实六回放现已完成，三对共同输出相同，独立科学与访问复核通过：918个完整prior，857个合法相位模型交集，3末端未覆盖，全部921块保留。后续执行计划按实际数量收紧为918 prior / 857 geometry / 1714 diagnose，而非直接使用本提案上方先验上限。

H只属于一阶线性化工作替代模型（LINEARIZED_WORKING_SURROGATE_ONLY），nonlinear_remainder_qualified=false。若要把Young结果解释为物理残差误差上界，Rbar必须在同I_END下界住包含相位噪声、偏置、安装、同步及非线性余项的总有效误差二阶矩；原Q没有证明此前提。本轮不把余项默认为零，也不追加R或新假设数值。
