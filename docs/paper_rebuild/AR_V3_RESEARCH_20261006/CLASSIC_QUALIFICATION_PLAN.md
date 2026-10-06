# EXT01 / C-WLS 候选器的有限合成资格计划

日期：2026-10-06。**PLAN_READY / SEARCH_NOT_EXECUTED**。准备脚本已生成并检查输入矩阵；整数候选调用 0。必须由 root 登记/提交后另行启动 `run`，本文不是算法结果。

## 1. 问题与范围

检查已有经典候选器在**真实保存卫星几何条件下、完全合成观测**中的单位、符号、共参考星完整协方差和候选恢复。使用当前维护的 `ext01_clambda.solve_clambda(strict=True)` 与 `reproduction_ext02.solve_cwls`，不修改旧实现。当前 EXT01 含后续维护/缓存改变，因此本次不是历史 V2 源码字节等价重跑。

没有真实原始观测 y、参考航向或已评分误差进入合成生成/窗口选择/求解；不重算真实绩效，不调用 SPP、广播星历、RAWX 解码、导航或评估器。JSON 容器中原本有观测和历史候选字段，读行时会解析，但只提取 `model` 的 A/B/Q、信号身份和约定，既有 y/solver/valid/误差均不参与选择或生成。

所有处理在 Ubuntu 22.04 WSL。正式效果比较仍仅 V3；本诊断是独立 `SYNTHETIC_OBSERVATIONS_CONDITIONED_ON_SAVED_REAL_GEOMETRY`，不会加入真实结果表。不能据此验证真实时钟、半周标志、原始载波正确性、观测噪声校准或整数真实固定率。

## 2. 已有测试的复用范围

此次已阅读以下测试的针对性部分，不重新执行这些旧搜索测试：

| 维护测试 | 已有覆盖 | 本次处理 |
|---|---|---|
| `test_horizontal_ext01_clambda.py` | 已知长度/整数无噪声及低噪声、全目标与白化残差一致、秩亏失败、官方 LAMBDA 矩阵约定、小维穷举与安全搜索证书、超时失败关闭 | 复用其数学职责，不再增加一套相同随机设计矩阵测试 |
| `test_horizontal_ext02_cwls.py` | 特殊半周舍入、单位/行次序适配、非对角完整 Q 目标、球面几何与候选池、球面子问题检查 | 新脚本保留这些约定，用保存的物理 DD 几何补覆盖 |
| `test_ext_reproduction_ext02.py` | tangent 分支、无噪声全 Q 恢复、特殊独立解析球面+整数穷举 oracle、失败候选不能跳过、有限迭代耗尽 | 不把特殊 fixture 的 oracle 证书推广给一般 C-WLS |

历史回执 `hext/EXT_REPRODUCTION/EXT01_SHARED_TEST_RECEIPT.json` 的 final 为 40 passed / 3 skipped；`EXT02_TEST_RECEIPT.json` 记录旧核 38 passed，新测试先有 1 个 fixture 失败，再修 fixture 后 39 passed。这里仅复用存在的记录与设计，**不把历史回执当当前维护源重新测试通过**，也不删除失败历史。

## 3. 固定输入选择与 12 次预算

来源别名 `<EXT_REPRO_V2_RETRY_ROOT>`，使用三个
`runs/<SEQUENCE>__EXT01__RAW_REPRO_V2__TECH_RETRY_2/EPOCH_EVIDENCE.jsonl.gz`。
只取按保存顺序第一条具有 `model` 字段的记录，不以候选是否正确、valid 或已评分误差筛选。是完整原始配对历史的首模型，不是重新选择评价窗内表现最好的历元。三条均恰为 epoch 0、文件第 1 行。

| 序列 | GPS week | TOW s | DD 数 | pivot | 码 H 最小奇异值 |
|---|---:|---:|---:|---|---:|
| BY2 | 2408 | 460873.998 | 7 | GPS G19 L1 C/A | 0.7243122204 |
| BY2H | 2408 | 461219.19800000003 | 4 | GPS G19 L1 C/A | 0.4624980010 |
| BY2O | 2408 | 460361.398 | 6 | GPS G19 L1 C/A | 0.6185525025 |

上述是准备阶段输入矩阵性质，不是候选器结果。三模型 `rank(H_code)=3`，A 的相位块均为 `lambda_L1 I`，码/相位几何相同，Q 正定且保留共 pivot 非对角项。原接收机方向是 GNSS2−GNSS1，DD 为 satellite−pivot，CPMES 不二次加半周。

每序列固定两个场景，均给 EXT01 和 C-WLS 一次调用，总上限 **3×2×2=12 次候选器调用**：

| 场景 | ECEF 单位方向 | 长度 | 观测噪声 |
|---|---|---|---|
| A | (0.6, 0.8, 0) | 0.350 m | 无噪声，允许浮点距离差/共模消去的约 1e−14 m 舍入 |
| B | (−0.36, 0.48, 0.8) | 0.350 m | 按 SV 确定的有界单差码与相位扰动 |

为守住 12 次预算，**这不是“两方向×两噪声”的完整因子试验**，不估计噪声单因素效应或统计正确率。B 的单差码噪声绝对值至多 0.001 m，相位至多 0.0002 cycle；DD 绝对界分别 0.002 m / 0.0004 cycle。Q 仍沿用保存模型，不按噪声大小重调；该确定性小扰动只查数值/符号，不能校准 Q。

整数先在单差域固定为 `N_sd(sv)=((7*sv+3) mod 11)−5`，再作 satellite−pivot 差。不会把该真值作为候选种子或 solver 参数。所有失败和未恢复保持；无替换场景、无自动重试。

## 4. 正向观测及独立核对

### 4.1 不直接以被测目标函数生成 y

从保存的 `H_s=u_p−u_s` 重建一组单位 LOS。由
`2 H_s^T u_p=||H_s||²` 解出 pivot LOS，再令 `u_s=u_p−H_s`；这三模型的单位长度误差在 6e−16 以内。该步骤是检查保存几何自洽，不是恢复真实卫星轨道或独立校验旧 RAWX 后端。

另构造半径 24,000 km 的合成卫星 `s_s`，将两接收机置于 `−b/2,+b/2`。用独立的稳定距离差公式

```text
rho2−rho1 = −2 s_s^T b / (||s_s−b/2||+||s_s+b/2||)
```

生成单差，再加入 SD 整数和噪声。码加入 123 m 共模，相位加入 7.25 cycle 共模，最后作 DD 消去它们。不调用生产 raw/geometry/phase-correction helper。准备阶段已确认与指定 DD 线性模型的差至多约 1.4e−14 m。

### 4.2 完整协方差、符号与单位

计划中的辅助检查不产生额外候选搜索：

- 每个码/相位 Q 块重建为 `D diag(v_sd) D^T`，`D=[I,−1]`，保留 pivot 导致的全非对角相关。Q 不对角化。
- C-WLS 适配由 `[code,phase] m` 重排为 `[phase,code] cycle`；检查 y、H 分别除以 lambda，Q 经同一置换后除以 lambda²。
- 在一个非真值参数点独立计算 `r^T Q^-1 r`；接收机反向令 y/N/b 同时反号，验证同成本。
- 换到预定的新 pivot：同时变换 y、H、整数和完整 Q，验证同一物理参数的目标不变。此项只验证坐标代数，不增加 solver 调用、不宣称不同候选启发式一定返回相同点。
- 独立白化最小二乘计算公共 float 残差常数，核 EXT01 `Jraw=Jfloat+Jconstrained`；独立 `ceil(x−0.5)` 计算 wrapped 原始目标，核 C-WLS 返回目标/整数。
- 调用前后核 y/A/B/Q 未被改变。

### 4.3 唯一性与不应强求的结论

对本次**无噪声且码/相位 H 相同、码 H 满列秩**的模型，零码残差使 `b=b_true`，零相位残差随后唯一确定 N。真值可行且总代价为零，因而是该模型唯一零代价全局解；这是输入结构证明，不依赖另一求解器输出。

这不推广到弱/缺失观测：例如只有二维码几何 `H=[e_x^T;e_y^T]` 时，`b=(x,y,+z)` 和 `(x,y,−z)` 可同时满足长度和相同码/相位数据，虽然 N 相同，方向不唯一。去掉码后还可能存在相位整数别名。若未来遇到该条件必须记录明确不可辨识，不能指定某方向才算算法成功。

有界噪声下不预设真 N 必然最优：报告是否恢复、基线差、真值点可行代价、候选代价，以及是否违反目标恒等。候选比真值点代价更高可以暴露优化不足；候选代价较低并不证明整数正确。即使本 fixture 达到已知零下界，也不把 C-WLS 的一般输出升级成全局证书：其 `global_optimum_certified` 固定为 `null`，只另报本无噪声实例是否在数值容差内达到零下界。

## 5. 求解预算、身份与输出

[可执行脚本](../../../scripts/paper_rebuild/carrier_phase/ar_v3_classic_qualification.py)，[冻结输入与参数](CLASSIC_QUALIFICATION_PLAN.json)。JSON 固定六个合成输入/真值、三份原模型结构、原行摘要、模块/脚本与既有 RTKLIB LAMBDA 库 SHA。脚本 prepare 分支不导入候选器；当前只执行了 prepare 与语法检查。

- EXT01：严格搜索，8 个 LAMBDA 种子，上限 100,000 nodes、30 s 内部搜索；外层 32 s 硬终止保护。不能将种子数当枚举上限。
- C-WLS：原完整候选池与原迭代/舍入规则保持，外层 30 s 终止保护；无迭代阈值修改、无失败候选跳过。
- 未完成为无证书/失败，继续记录其余预定 case，但不重试失败调用。进程整体中断后没有自动续跑；由 root 根据 BEGIN/END 判断已消耗预算。
- 输出目录必须不存在，避免覆盖或原地追加旧实验；写 `CALLS.jsonl`、`RESULTS.csv`、`DETAILS.json`、`COMPLETE.json`。BEGIN 在候选调用前落盘，异常和超时都占一个调用槽。
- 输出只称候选恢复、目标一致性与算例资格，不称真实 FIX、真实正确率或实时性能。

登记后运行模板（别名由调用者显式解析，不在脚本中硬编码机器路径）：

```bash
python3 scripts/paper_rebuild/carrier_phase/ar_v3_classic_qualification.py run \
  --evidence-root '<EXT_REPRO_V2_RETRY_ROOT>' \
  --lambda-library '<EXT_REPRO_BUILD>/lib/librtklib_legsa.so' \
  --plan docs/paper_rebuild/AR_V3_RESEARCH_20261006/CLASSIC_QUALIFICATION_PLAN.json \
  --output '<AR_V3_SCRATCH>/CLASSIC_QUALIFICATION'
```

## 6. 下一步的使用限制

这一步若通过，只能排除部分候选核/适配器的基本错误，不能把保存真实观测的大角误差自动归因于多路径、也不能证明真实时标、时钟或半周完全合格。若失败，先分开符号/单位/目标矛盾、搜索预算耗尽、C-WLS 候选策略未达到已知真值点等原因；不得按结果调 Q 或挑另一窗口制造 PASS。

PD-PAR 和运动机制对照的资格继续以 [文献资格说明](LITERATURE_QUALIFICATION.md) 为界，本计划不扩充它们的搜索或论文主张。
