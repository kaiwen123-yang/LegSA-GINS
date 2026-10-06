# 完整来源候选集合的五槽生命周期资格计划（已授权局部实现与测试／实测未授权）

本计划已获授权进入接口实现和最多 16 项针对性局部测试；真实 60 槽处理仍须代码审查、登记冻结后另行授权，不启动整数搜索、NAV 或参考评估。来源是已冻结 `78114f5019e2ec1586df0be9fb680194434fe55a` 的固定 12 窗 pilot，完整结果见 `candidate_envelope_pilot/RESULTS.md`。不修改已执行源、阈值或 V3/main，也不形成论文材料。

## 1. 固定输入与来源语义

仍用 BY2 保存 `REAL_100_340_V2`，起点索引 0,100,…,1100；每个来源的 selection 是索引 start…start+4，后续仅 start+5…start+9 五个原始时间槽。全部 12 窗保留，三空源直接给出不可用，不补窗、不重获；9 个非空源共有 23 个长度必要筛选保留的整数假设。禁止读取旧 top2/旧准入/导航误差挑选来源。

这个源集合是原 selected-observation 似然、登记 raw 成本域和同长模型的**完整数值必要外包**，并不证明每个保留整数确有满足所有长度球的连续解。selected6 删除依赖未选整数的相位行、使用 Q 的主子矩阵，不能改称原全观测中的 float/integer nuisance profile。继续保留数据依赖选择、未标定 Q、浮点外包、开发窗口等限制；不设真实整数正确率或置信覆盖率。

每个来源记录 source ID、原 selected_at、完整 selected labels/N、原 problem fingerprint、原 raw threshold、raw/length support 完整性和原数值 guard。只接收完整源；不完整源不能靠后续观测自动补成完整。新模块不得承接旧 top2 的全局排序证书。

## 2. 永久弧退休与临时观测拒绝分开

先按当前槽已到达的物理 receiver/signal/arc 事件更新每个来源的 `FrozenIntegerGraph`。对同一完整 SD arc 可以通过旧整数势之差保留新的 DD 关系；新 token 不继承旧整数。现有 `transport_epoch` 对当前观测给出 U：保留所有 code，且只重建可识别旧关系的 phase；使用 y′=Uy、B′=UB、Q′=UQUᵀ，不做 conditional Schur。未知新 pivot 的整数和相位噪声可在幸存 target 差中消去，但它的 code 行和 code 噪声仍保留。

物理 arc 退休永久生效；全失去可识别旧整数关系时来源终止，不能因后面观测更好而复活。若只暂时缺模型、当前几何不足或质量拒绝，则记录本槽不可发布，不能擅自永久删除整数假设；完整弧事件仍须因果推进。是否具备 phase≥4、rank3 单独记录，不能把 code-only 的几何解误称载波航向。

每个槽对所有来源使用相同 U、y′/A′/B′/Q′、物理弧支持和阈值。按当前**精确整数关系**合并完全相同的 projected class，并保留所有 origins。不得按方向相近、残差大小、浮点整数容差或旧 top2 顺序合并。合并仅是原有限来源集合的像，不是当前观测全部整数解，也不是新全局 top2。

## 3. 每槽从当前观测重建完整连续域

对每个当前 projected class m，令 z_m=y′−A′m，当前基线仍为未知三维 b。以完整 Q′ 做 GLS：

- c_m=(B′ᵀQ′⁻¹B′)⁻¹B′ᵀQ′⁻¹z_m，C_m=(B′ᵀQ′⁻¹B′)⁻¹；
- S_m=min_b (z_m−B′b)ᵀQ′⁻¹(z_m−B′b)；
- 当前 raw 成本阈值 τ_t=χ²(n_t,0.99)，n_t 是当前 U 后标量观测数，不能用 n−3 或中心误差代替该域；
- 若 ρ_m=τ_t−S_m 非负，则完整连续椭球为 (b−c_m)ᵀC_m⁻¹(b−c_m)≤ρ_m；按既有向外数值 guard 扩张，不把条件中心作为全集。

由 r_m²≥ρ_m λmax(C_m) 得到整个三维球外包。只有 | ||c_m||−L |>r_m+guard 才能证明与长度球不相交。本轮第一实现沿用必要筛选及连续水平圆盘→圆周角外包，不增加 sphere 优化。保留的当前类不能改称已证明 sphere-feasible。若轴/协方差/秩/数值检查不合格，返回未资格；水平外包含原点（含近竖直）返回全圆，不强造 heading。

当前方向域须并合**所有当前 raw/长度成本兼容的类的整个连续域**，包括 ±π wrap。当前成本兼容为空/一个/多个分别照实输出；这些是条件来源集合的当前可用性状态，不叫整数 FIX。某类本槽成本不兼容只让该槽不可发布，它的源整数仍保留到下一槽；不累计淘汰，也不把当前 τ_t 与此前不同 n 的阈值拼成未经定义的历史准入。

## 4. 相位质量诊断不能用于隐性缩窄集合

继续采用给定 N 的 full-Q residualized 单故障 GLRT；故障列来自 receiver-SD signal phase design，经同一 U 投影，pivot 污染不能误作单个 DD 行故障。严格零投影故障列且基线 gain 为零时标记 `NA_NO_CURRENT_EFFECT`，不构成质量失败；残差不可观而基线 gain 非零时标记危险不可观并使该类未资格。非零列的其他数值未决也不能冒充无影响。模板别名只说明不能唯一归因，本身不阻止健康集合。所有分类都保留原始 F、U F、白化残差信息和基线 gain 的证据。

保持现有每类 family alpha=0.01 的 Holm 诊断，逐类报告所有 raw p、校正 p、不可观/并列标志；不新增跨 classes×templates 的 pooled family。对多个来源、5 个槽和整个生命周期不声明联合风险概率，source/Q/弧选择依赖的限制继续披露。没有显著故障仅表示当前条件诊断未拒绝。

phase 显著或其他质量不通过，只标本槽该类不可发布，不删除其源假设。**不能删掉 phase 有问题的 raw 兼容类后，只拿剩余类的窄区间宣称完整覆盖。** 对外域仍是全部成本兼容类的 union；只要其中有质量未清楚的类，则整体方向输出标 `UNQUALIFIED_CURRENT_QUALITY`，保留未通过原因和未筛去的区间。后槽重新检验。没有显著故障也不证明无故障或整数正确。

## 5. 最小接口与执行预算

建议一个独立 `candidate_lifecycle.py`，复用 `arc_relations` / `arc_projection` / `faults`，不改原 CILS/selected_likelihood/frontend。数据类与入口：

- `CompleteSourceSet`：源集合 fingerprint、原 selected_at、labels、所有 N/origin IDs、source numerical completeness 与 likelihood scope；
- `ConditionalCandidateSet.advance(model, qualified_arc_events)`：只因物理弧演化和 exact projection merge 改变 source membership；永久 retired 与暂时 unavailable 分开；
- `CurrentSetDomain`：time、原 current model fp/U、各 projected class 的 origins/N、S/τ/ρ/c/C、长度必要检查、连续方向域、全部物理故障诊断、整体 union 与资格理由；
- 所有输出 `all_global_current_alternatives_covered=False`、`search_certificate_transferred=False`、`accepted_integer_measurement=False`、`false_fix_probability=None`。本阶段不转 Gaussian yaw 量测、不进 EKF。

预算：12 固定来源×5 槽=60 槽记录；最多 23×5=115 次固定 N GLS，最多 115 次单故障 GLRT。投影合并可减少调用，但不得用额外循环补足预算；每槽每类仅调用一次。0 整数枚举、0 LAMBDA、0 CILS、0 sphere 优化、0 raw UBX、0 reference、0 NAV/evaluator。新实测目录必须独立；总处理工程上限建议 120 s，超时停止并标剩余 NOT_EXECUTED，不补跑。该上限不是 online deadline。

指标固定：60 槽完整状态；物理退役/全失弧；projected classes 及 origins 合并；当前成本兼容 none/single/multi；phase rows/rank；原始成本与阈值、长度必要筛除；全源 union 宽/全圆；phase family 与未资格原因；每项成本和调用数。不得报告整数正确率、实时达标或导航增益。

## 6. 实现前局部反例与停止条件

只需针对性合成测试，不再重复大套件：

1. 真整数遇一槽异常观测被临时拒绝，下一干净槽仍能重新资格；它不是新造 N；
2. 真正新 arc token 永不继承，即使信号 ID 和后续观测数值相同；
3. 新 unknown pivot 的整数/相位共模经 U 正确消去，全部 code 与完整 Q 保留；
4. 多源投影为一个类仍保留全部 origins，不能借合并授予全局证书；
5. 单整数的连续域跨 ±π/接近竖直时不能因只取最优点得到窄区间；
6. 某成本兼容类 phase 显著时，整体质量未资格且该类仍在 union，不能获得虚假的窄域；
7. 不完整来源、候选相关 U、来源 fp 不匹配及资源中止均不可发布。

真实执行必须在接口/这些测试/计划完成并由 root 冻结登记后另行授权。三空源、失弧、全圆、质量全拒绝都属于允许的真实结果，不能通过放宽 Q、原始成本、相位门或几何门强行形成 FIX。后续若需新获取或方向域向导航转换，必须另登记；本计划不授权累计源淘汰或新整数搜索。

本次修订由 root 明确要求：每类原 Holm 口径保持、严格零当前影响与危险不可观分开、别名不自动拒绝。局部测试上限 16 项，旧测试不重跑；日志持久保存。全实测调用仍为 0。

## 实现与局部资格回执（实测仍为 0）

新库 `src/legsa_gins/paper_rebuild/carrier_phase/candidate_lifecycle.py`，新入口 `scripts/paper_rebuild/carrier_phase/candidate_lifecycle_pilot.py`，新测试 `tests/paper_rebuild/test_carrier_candidate_lifecycle.py`。原 candidate_envelope/solver/frontend 没有修改。入口逐字节校验登记提交的 plan/runner 和完整导入依赖 SHA，绑定原 pilot source seal/details、保存 PLAN、物理弧事件和 60 个固定 future 模型；再次验证输入/源后才封存结果。线程必须明确均为 1；总 120 s 为 processing 的协作式上限，preflight 身份核验在此之前，不是硬抢占或在线截止时间。

16 项唯一新测试首轮全部通过（0.41 s）。随后源长度/保存 fingerprint 绑定增加后，只重跑修改的 test_06（1 PASS，15 deselected）；按 root 审查补 finite/positive 水平协方差谱检查后，只重跑修改的 test_11（1 PASS，15 deselected），没有重跑其余测试或旧套件。随后自查补了 fixed-N GLS 输出 finite 守卫，防止极大但有限观测发生浮点溢出后被误当空成本域；仅修改的 test_15 单项通过（1 PASS，15 deselected）。合计 19 个 pytest 测试实例、17 次纯合成 fixed-N GLS 和 16 次 GLRT（含显式辅助调用）；整数枚举、CILS、LAMBDA、真实模型/UBX/参考、NAV 均 0。全部原日志与前后 source SHA 在 `CANDIDATE_LIFECYCLE_LOCAL_TEST_RECEIPT.json` 可追溯。

入口将每个固定槽异常保留为 `CURRENT_SLOT_EXCEPTION_NO_PUBLICATION`，不输出部分候选的伪完整 union；物理图已推进时仍保持因果退休，未永久删除被当前统计拒绝的源。达到总预算则剩余固定槽为 `NOT_EXECUTED_PROCESSING_LIMIT`，不补跑。`direction_domain_qualified` 只表示已构造条件连续外包且当前登记质量/几何未拒绝，完整圆周外包仍可能成立，不能当成有用的点航向或整数 FIX。所有输出仍明确 `accepted_integer_measurement=False`，没有融合或导航调用。

原 pilot `DETAILS.jsonl.gz` 的完整 scratch 路径和 SHA 不变；Git 结果记录仅放小表/回执，压缩详情保持本地，不依赖 Git 中存在 gzip 才恢复源。

冻结前 root 与 comparisons 完成独立只读核查，未发现阻断，未增加数值运行。这里的物理弧退休指保存的 receiver/signal/arc 连续性资格丢失；它不证明现场确实发生了物理周跳。执行须用本次包含完整源码/计划的登记提交，另由 root 明确启动一次。
