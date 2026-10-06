# 第二阶段：已知整数、薄弱几何与失效 RP 的最小机制合同

状态 PREPARED，尚未调用本阶段 solver。范围由作者本轮 1–2 天有限探索及根代理明确授权；真实 12 点已封存并保持不变。本机制问题在观察第一阶段真实结果后设计；本合同只为后续合成执行预注册，不回称先于真实结果。本阶段只生成合成 DD 观测，不增加真实窗口、重读参考或运行导航滤波。

## 输入选择与人工真值

从第一阶段按时间排序的可建模历元中，取首、末两个：索引 121/1221，原相对时刻 80.197999954/300.197999954 s。只使用其设计矩阵 A/B、共享枢轴全协方差 Q、信号排序和 cold SPP anchor。该选择不按航向误差、ratio 或已解整数筛选。原始真实 observation 不进入新合成 y。

每个几何构造两个已知水平基线，NED bearing 为 0° 和 90°，长度 0.350 m。这里 bearing 是基线方位，不是 body yaw；水平 roll=pitch=0，侧向安装对应 body yaw=bearing+90°。用 anchor 的正交 NED/ECEF 旋转得到真基线。DD 整数真值按冻结卫星顺序固定为 [3,−2,5,−7] 的前 m 项；m 分别为 4/3。保留各模型 pivot 与卫星身份。

每个 geometry/bearing 只生成一次标准正态向量 z，令 ε=chol(Q)z，生成 y=Bb_true+A N_true+ε。固定 PCG64 default_rng seed：

| 模型 | seed |
|---|---:|
| G121_B0 | 2606101210 |
| G121_B90 | 2606101219 |
| G1221_B0 | 2606101220 |
| G1221_B90 | 2606101229 |

所有噪声样本、矩阵和真值在调用 solver 前写入 SYNTHETIC2_PLAN.json 并冻结。生成器使用同一线性模型，是受控机制检验，不独立验证真实观测物理建模、硬件偏差或代码系统误差。

## 处理、失效注入与预算

A 对每个底层实例只解一次，无 RP，共 4 次。该结果缓存，供以下 3 个 B 条件共同对照。缓存 A 的 prior_residual_sigma 固定相对 nominal b_D=0，仅是附带诊断；不得把它当成相对各错误 RP 的残差。

B 保留第一阶段 σ_D=0.030 m 的附加先验与全部 C-ILS 参数，真实 roll=pitch=0；先验分别为：

- RP_NOMINAL：reported roll=0、pitch=0，b_D=0；
- RP_ROLL_POS：reported roll=+asin(0.15/0.35)≈+25.3769°、pitch=0，b_D=−0.15 m；
- RP_ROLL_NEG：reported roll=−asin(0.15/0.35)≈−25.3769°、pitch=0，b_D=+0.15 m。

全部从同一 b_D=−L sin(roll)cos(pitch) 关系生成，不直接把错误垂向值当作原始 RP 观测。±25.38° 是人为严重先验失效压力，不声称其真实发生率或“微小姿态误差”。原观测 y 和噪声在这 3 个条件之间完全相同。B 共 12 次。

C 与第一阶段相同：A/B 都有全局目标最优证书且整数完全一致才保留 B；否则未决，不额外调用。不得观察结果后更改门限、先验故障幅度、seed、真值或新增实例。

预算总计 A4+B12=16 C-ILS；每次 strict=True，初始候选 8、1,000,000 节点、60 s 搜索；整个独立进程组 1200 s 上限，超限杀整个进程组并保留 ledger/trace，不补跑。每项异常保留、不替代。矩阵秩、Q Cholesky、旋转正交、0.350 m 长度、RP→b_D 及 y 构造残差均在准备阶段检验。

## 输出与解释

A 独立分母 4；B 每个 RP 条件分母 4；C 每条件分母 4。列 candidate available、known integer exact correctness、错误候选、未决、C 正确保留/错误保留/拒绝，并分开报告相对人工真基线的投影角差和三维夹角。错误整数与角度误差不能互相替代。

12 个 A/B 对照只来自 4 个共享噪声实例，不独立，不用于 Monte Carlo 错固定风险或置信区间。候选可用不等于正式整数验收；对合成真值可描述“整数正确候选/错误候选”，对 C 描述“正确/错误保留”。不把原始 real data 的整数真值从此推出来。

若 B 正确先验有帮助而错误 RP 能误导 B，可支持需要先验失效建模和正式验收的下一问题；若 C 也共同错误或大幅拒绝，则如实保留。无论结果如何，不能将倾角先验+C包装成新颖完整 AR。

## 封存与执行

入口 scripts/paper_rebuild/ar_tim_exploration_20261006/synthetic2.py，借用已经冻结的 experiment.py / 现有后端；不改任何生产模块。准备目录 <AR_SCRATCH>/SYNTHETIC2_PREP02，最新具体 stage 和 pins 以 SYNTHETIC2_PREREGISTRATION.json 为准。需根代理提交源码/完整 plan 并给执行 SHA 后，才可 supervise。

准备读取第一阶段封存的真实几何/anchor 文件，运行还会读其 payload 作 hash 核验；不是宣称完全不读真实结果。solver 计算输入只来自冻结合成 plan 与既有后端库；不打开 raw 或 reference payload。strace 收集文件打开记录，完成后封存 SYNTHETIC2_SEAL.json、逐项文件及 IO_AUDIT。所有 A/B 调用在开始/结束时写入并 fsync 账本。原第一阶段 REAL_SEAL 和 12 点评估均不覆盖。
