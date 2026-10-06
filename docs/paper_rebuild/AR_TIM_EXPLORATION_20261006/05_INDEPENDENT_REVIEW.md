# AR 有限探索的独立审查

状态：阶段 1 的静态合同、真实封存与离线输出一致性审查通过；这不等同于整数真值、风险或独立精度验证。本文件由独立审查者撰写，不运行 SPP、C-ILS、导航或评价器，不读取商业参考内容。

## 1. 审查身份与固定范围

- 执行前冻结：`529487e10eac459e950c084945d7562239de7cef`。
- 最终准备目录：`<AR_SCRATCH>/PREP04`。
- PLAN SHA-256：`18906fccddc3d419ea40df0cd31f55c32db446de774384becbfacdd59a67e9a4`。
- runner SHA-256：`3c7c63963e4d66289b9197043200294b2e532b6b9ef80c1a6ef63b2d34c19c73`。
- 15 项 source pins 和合同 hash 已逐项核对当前文件；脚本语法通过只读 AST 解析。12 条预选 exact RAW pair、RP 全部 time≤RAW time、age≤0.02 s。
- 本审查不是对底层 C-ILS 全部实现的重新证明，也不是对现有文献方法的作者代码全流程复现。

依据：[AR_CONTRACT.md](AR_CONTRACT.md)、[AR_PREREGISTRATION.json](AR_PREREGISTRATION.json)、[experiment.py](../../../scripts/paper_rebuild/ar_tim_exploration_20261006/experiment.py)、[reproduction_backend.py](../../../src/legsa_gins/paper_rebuild/horizontal_literature/reproduction_backend.py)、[HX02 固定角度语义](../../../src/legsa_gins/paper_rebuild/hext/hx02_heading_evaluation.py)。

## 2. 执行前检查与修正

| 项目 | 审查事实 | 结论 |
|---|---|---|
| 科学处理差别 | A 为固定 0.350 m 长度的已有 C-ILS；B 只在相同 RAW/DD 模型上增加 b_D=−L sin(roll)cos(pitch)、σ_D=0.030 m 的独立标量行；C 只保留 A/B 同枢轴同排序整数完全一致的 B | 处理定义明确；固定弱先验是工程敏感性尺度，未标定 |
| 位置与时标 | 每预选历元 cold code-SPP；不读取 PVT、A1、旧 SPP 答案、GNSS heading 或参考；exact RAW pair，逐接收机自己的发射时刻与几何地球自转由原 backend 完成 | 没有将 Jan5 的异步 RAWX 标签强行重贴，也没有追加 NAVCLOCK 或相位偏置 |
| 输入资格 | 原 backend 的 PR/CP/half-cycle、CNO、仰角、星数、秩与共享枢轴 DD 协方差门保留；220/260/280 s 的 raw-only 三星支持仍进入分母 | 不凭结果挑选历元、邻点补位或放宽资格 |
| 单支异常 | A/B 各自捕获已有可预期后端异常；A 失败仍进入预定 B 尝试；共同 SPP/建模失败时没有可用 A/B 输入 | 避免单支失败造成另一支被静默跳过 |
| 预算与终止 | 原 timeout 只针对 strace 的实现已修为独立进程组，超时 killpg(SIGKILL) 后 wait；最多 12 SPP、24 C-ILS，单支 60 s，整体 2100 s | 该修正只影响超时执行控制；未改科学参数 |
| 保存与评价 | 每历元记录、调用开始/结束账本、source/input hashes；封存后在线参考读取必须为 0，才允许一次离线读取 | 后续仍须由实际回执确认 |
| 投影角语义 | 输出遗留字段 body_yaw_deg 实为 atan2(b_E,b_N)+90°；HX02 参考为商业 Euler yaw，未在结果后转换参考或拟合偏移 | 两者一般姿态下不是严格同一被测量，只允许既定近似 agreement 描述 |
| 合成单元 | 已有 12 项、16 次 C-ILS 是两种无随机观测噪声几何的确定性检查；±0.15 m 错先验时 A/B 仍同正确整数，C 仍保留 | 不能称 C 检出了错误先验；不是误固定概率、风险或 MC 完整性验证 |

上述修正后的静态实现与有限合同一致，没有执行前阻断。PREP01–PREP03 等准备历史仍须保留；它们不能算作额外真实 solver 结果。

## 3. 不因数值改善而放宽的证据边界

全局目标最优证书只对给定模型和搜索目标成立，不是整数真值。真实整数正确率、wrong-fix probability、integrity risk 仍为 NA。约束目标 ratio、原始白化残差和先验残差可记录模型自洽性，尚不能解释为校准置信度。

A 与 B 的候选可用性和误差必须同时给各自支持及共同 A/B 支持；C 的保留数需同时对全部 12 个预选历元和共同候选支持给分母。C 自带选择条件，不能只拿保留样本误差与 A/B 全支持误差比较后宣称更稳健。

12 个稀疏 cold 历元用于输入与候选资格，不验证连续跟踪、重固定时间、导航收益、跨日泛化或独立统计试验。底层假定噪声、相位整数可兼容性、安装几何与时标仍须承接 [测量验证边界](04_MEASUREMENT_AND_VALIDATION.md)。候选小角 agreement 也不能替代这些资格。

## 4. 封存后独立核验

审查脚本 [review_sealed_outputs.py](../../../scripts/paper_rebuild/ar_tim_exploration_20261006/review_sealed_outputs.py) 仅打开封存结果与来源源码；没有再次读取 raw/参考，没有调用原 backend、SPP、C-ILS 或 evaluator。机器可审计结果见 [INDEPENDENT_NUMERICAL_REVIEW.json](INDEPENDENT_NUMERICAL_REVIEW.json)。

| 检查 | 独立核对结果 |
|---|---|
| 来源及封存 | 15 个 source pins、12 个逐历元 JSON pins、PLAN/REAL_SEAL/EVALUATION_SEAL/CSV/调用账本/两份 strace hashes 一致；12 记录的预选字段与 PLAN 逐项相同 |
| 调用账本 | 12 SPP_START、18 CILS_START、18 CILS_END、12 EPOCH_END；A/B 每个被调用历元各恰一次，无重复补跑；C 调用 0 |
| 实际失败分母 | 220/260/280 s 均在 HALF_CYCLE_VALID=3<4 阶段拒绝；两支没有可建模输入，其余 9 条两支均给候选。失败三条仍在 12 总分母和 36 行评价表内 |
| I/O 审计 | 对已存 strace 重新解析得到 real 参考成功打开 0、evaluate 1；两份回执 passed，raw 输入只读。真实阶段 23.82 s，离线阶段 0.72 s |
| 坐标与长度 | 另写 WGS84 ECEF→NED 变换，仅使用保存的 cold-SPP anchor；18 基线 NED 最大差 5.55e−17 m，0.350 m 长度最大差 5.55e−16 m |
| 目标与弱先验 | 从保存的 y、H、整数矩阵、完整 Q 独立计算白化原始残差、(b_D−prior)/0.03 与总目标；残差平方差 0，先验标准化残差最大差 1.83e−15；总目标与 float residual＋candidate objective 最大差 1.84e−10 |
| 投影角与统计 | 保存 NED 的 atan2(E,N)+90°、36 行 wrap 误差、各自及共同支持统计重算均完全一致；此处复核保存的参考角列算术，没有重开参考去重新验证插值 |
| A/B/C | 18 个候选都有 backend 全局证书、无超时/节点上限触发；A/B 整数完全相同恰 5 条，C 恰保留其 B；4 个改变整数的 B 未被 C 保留 |

160 s 的 B 证书 frontier 在 JSON 中为 null：源码在 frontier 穷尽时使用 +∞，序列化将非有限数转 null。审查只接受其既有 GLOBAL_BOUND_CERTIFIED 标记并记录该特殊项，没有虚构一个数值下界，更没有重新证明搜索完备性。首遍只读审查在这个 null 上遇到类型错误；修正审查器的字段解释后第二遍完成，solver/evaluator/MC 调用计数均未增加。

## 5. 阶段 1 的结果与可支持结论

| 处理 | 候选 / 全部预选 | 角一致性 RMSE | MAE | 最大绝对差 |
|---|---:|---:|---:|---:|
| A：只有长度约束 | 9/12 | 60.181840° | 32.265600° | 140.211344° |
| B：加固定弱垂向先验 | 9/12 | 2.443953° | 1.891482° | 4.981739° |
| C：仅保留 A/B 同整数的 B | 5/12；共同支持中 5/9 | 2.840567° | 2.427800° | 4.981739° |

A/B 的误差表恰好使用同一 9 点支持；C 的 5 点来自它自己的选择条件，不能与 9 点当成无条件同支持比较。C 删除的 100/200/240/300 s 四点，B 自身 RMSE 为 1.831123°；其中 A 在 100/240 s 约为 +140.21°/−111.92°，B 约为 −3.58°/−0.62°。这直接显示“必须与不加先验结果同整数”的 C 规则会排除弱姿态先验产生的候选改变，**本轮不能把 C 写成已经证明的鲁棒升级**。

B 对这批预选数据有明显的候选选择作用，足以支持下一项有限的已知整数、带错先验合成机制检查。但真实角度一致性显著改善仍不足以证明 9 个整数正确；本轮没有外部整数真值，参考共享 GNSS 来源，且投影角与 Euler yaw 有定义差异。新机制还未解决整数正式验收、错误先验识别、输入时标资格与广泛泛化，不能替换 V3 已完成主稿或宣称 TIM 方法已成立。

后续若基于这些结果设计合成试验，必须明确为 **观察真实阶段 1 之后**的机制研究；不得称其假设和实例在真实结果前已注册。本次阶段 1 到此完成，额外合成合同及执行结果另补章。
