# EXT02：独立版本的相切候选修正

本文件保留实现/运行前依据及该测试小项的历史计数；当前三序列执行状态和真实结果见[最终比较](FINAL_COMPARISON.md)。

本项实现标识为 `EXT02_CWLS_TANGENT_PEAKS_V1`，入口是
`src/legsa_gins/paper_rebuild/horizontal_literature/reproduction_ext02.py::solve_cwls(model)`。
它返回原 `CWLSSolution`，参数、模型类型和结果字段与旧 `solve_single_baseline_cwls` 相同。
本项只有合成测试，没有真实序列求解、provider 生成、评价器调用或 raw/reference 载荷读取；没有将新结果写入旧版本输出。

数学依据是 [REPRODUCTION_NOTES.md](REPRODUCTION_NOTES.md) 中已阅读期刊原文的 EXT02 段：单基线 Algorithm 1/2、Eq(54)、Eq(62)–(75)。原论文包身份在 [PAPER_PACKAGE_INDEX.csv](PAPER_PACKAGE_INDEX.csv)。本项不实现多天线三轴姿态，也不声称复现作者原实验数据。

## 唯一科学分支改动

旧 `ext02_cwls.py::intersect_sphere_circles` 在 `tangent` 分支立即返回切点，因而没有分别检查另一个 peak。新版本先复用旧圆对分类，只有返回 `tangent` 时才按原几何方向构造两个 peak，分别保留严格满足 `abs(Delta)<0.05` 的候选，继续使用原机器精度去重。其余交点、非交点、近平行、反平行和点圆分支直接返回旧结果。

明确反例是第一圆 `normal=(1,0,0), offset=0.02`；第二圆 `normal=(0,0,1), offset=sqrt(1-0.02²)`。第二圆的 radius 约为 `0.02`，两个 peak 对第一圆平面的 `Delta` 约为 `0` 和 `-0.04`。旧分支保留 1 个，新分支保留 2 个；`offset=-0.02` 的对称反例也通过。`offset=0.04` 时另一 peak 的距离约为 `0.08`，仍不入池。

圆对 `kind="tangent"` 保持原接口；该对仍只计一次 intersecting pair。新增的第二个合格 peak 计入 `near_tangent_candidate_count`，随后与全池其他方向进行同一去重。未增设候选截断、科学容差或性能导向选择。

## 复用范围与固定执行策略

模型、完整 `[phase, code]` 协方差、输入验证、integer interval/search circles、wrapped 目标、half-down 舍入、球面二次子问题、refinement、失败诊断和结果数据类都直接复用旧模块。旧求解入口没有 candidate-generator 参数，因此新文件仅重复候选池汇集和短 Algorithm 2 调度，向旧 refinement 提供修正后的全池；生产代码不修改旧模块全局变量。

| 项目 | 本版本行为 | 来源/边界 |
|---|---|---|
| `delta_Delta` | `0.05`，严格 `<` | 期刊值，与旧实现相同 |
| K | 全部唯一候选 | 原文未给固定 K，沿用工程约定 |
| 最大细化次数 | 20 | 原工程预算 |
| 方向收敛阈值 | `1e-10` 且整数向量稳定 | 原工程收敛规则 |
| 不完整候选池 | 继续记录其余候选，随后拒绝该历元 | 任一失败/不收敛不能伪装部分成功 |
| 最终排序 | 原 wrapped Eq(54) 及原确定性并列规则 | 不用固定整数 surrogate 替代 |
| 两种目标 | `objective`、`refined_unwrapped_objective` 均保留 | 每个 `CandidateDiagnostic` 原字段 |

完整相关 Q 仍参与全部目标计算。球面子问题的证书不能推广为任意数据上的整个 C-WLS 全局证书。

## 原文半整数与 binary64 边界

本版保留 `round(x)=ceil(x-0.5)` 和 Eq(75) 的 `psi+round(pred-psi)`。在恰好半整数时，half-down 不是奇函数：例如 `psi-pred=0.5`，wrapped Eq(24)/(26) 残差为 `+0.5`，Eq(75) 的残差为 `-0.5`。相关 Q 的交叉项可使两目标不同。测试检查 `±0.5`、`±1.5`、每点向两侧的 `nextafter`，并用相关 Q 验证两个目标分别保存；没有暗改 Eq(75) 符号或 tie 规则。

还明确保留一个旧 binary64 算术局限：对 `nextafter(-0.5,+inf)`，精确有理算术的 `ceil(x-0.5)` 是 0，但 binary64 的中间减法可舍入到 `-1.0`，旧/新实现均返回 -1。该差异有独立 `Fraction` 负对照；本项只修相切候选，没有更改或掩盖这一舍入行为。精确半整数的原文差异与相邻浮点数的中间舍入是两件不同的事。

## 实际测试与证据范围

完整命令、stdout/stderr、退出值、源文件 SHA256 和三次 pytest 进程记录均在 [EXT02_TEST_RECEIPT.json](EXT02_TEST_RECEIPT.json)，日志内本机路径已转为 `<CODE_ROOT>`。

| 测试组 | 最终结果 | 核查内容 |
|---|---:|---|
| 未修改旧 core tests | 38/38 PASS | 原单位/符号/完整 Q、几何、球面证书、4–8 卫星、dense oracle、失败策略 |
| 新版本 tests | 39/39 PASS | 相切双 peak、其余分支保持、全候选池、无噪声/输入不变、完整 Q 穷举 oracle、舍入边界、负例及 20 次耗尽 |

新版全相关 Q oracle 使用 3 维整数枚举和特制完整相关 precision，使 `DᵀQ⁻¹D=4a²I`。每个固定整数球面子问题有独立闭式下界；穷举全部可能 wrapped 整数单元后，确认最小下界的方向实际落在对应单元，从而对这三个合成 fixture 给出可达下界。它不调用生产 objective 或球面求解器作为 oracle，也不宣称一般 C-WLS 全局最优。

负对照覆盖非有限输入、非正定 Q、空整数区间、只有非点平行圆时无候选、单候选数值失败、全候选失败和 20 次预算耗尽。故意替换 synthetic 子问题用于半整数诊断字段及循环耗尽测试；这些注入测试只证明 bookkeeping/失败策略，不能当作被注入方向的数学最优证书。替换仅存在于 pytest 的临时 monkeypatch 中，生产版本没有此逻辑。

三次 pytest 共执行 116 项测试案例（其中重跑不是新独立案例），最终不同案例为 77。第一次新版运行为 38 PASS、1 FAIL：我构造的“无候选平行圆”负例意外含可合法产候选的退化点圆。仅把该合成设计缩至 0.2、排除点圆后重跑新版，39 项通过；实现未因此更改。失败日志与更正原因保留，未将测试构造误判记录为算法故障。

运行前后旧实现与旧测试的 SHA256 相同；新旧测试分别记数。真实 native、真实 evaluator、provider generator 均为 0。本项至实现与合成验证结束，真实三序列应用和新版本外部比较仍需后续明确调度。
