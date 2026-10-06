# 最小 AR 资格试验合同

本轮范围承接 [00_SCOPE.md](00_SCOPE.md)：1–2 天内完成有限诊断，原 V3 成稿继续。本文、AR_PREREGISTRATION.json 与 runner/source hashes 必须由根代理提交冻结后，才开始真实 RAW 解算。

## 问题与处理

问题是现有 GPS L1 双差/已知长度 C-ILS 链是否具备继续研究的基础，以及弱姿态先验是否改变整数候选。不是声明新 AR 方法成立。

- A：现有 EXT V2 的逐接收机发射时刻、卫星钟差、迭代几何地球自转、共享枢轴全协方差模型；仅施加 0.350 m 基线长度约束。
- B：A 加一行附加的垂向基线弱先验。锁定 GNSS2−GNSS1 为机体侧向向量 [0,−L,0]，采用 b_D = −L sin(roll) cos(pitch)。只使用已审计的 raw Go2 RP provider 的因果最新行；不输入 GNSS 航向、PVT、A1、导航结果或参考。
- C：后处理保留 B，当且仅当 A/B 均获得全局目标最优证书且同枢轴同排序整数向量完全相同；否则未决。C 不新增 solver 调用。它只是 candidate consistency retention，不是正式验收规则，更不宣称新颖性或可信 FIX。

B 的先验标准差固定 0.030 m，近水平约对应 4.9°。这是事前工程敏感性尺度，较现有 RP 1.6° 弱，并非安装误差标定或从参考拟合。新增 Q 块对角结构是本次试验假设；标量行暂不建模 RP 与 GNSS 误差相关性，SDK 内部来源及统计独立性尚未标定。机体轴和天线物理向量沿用当前约定，未据本试验重新标定。

## 真实输入与分母

只用 BY2 已有完整 RAW 的 exact GPS week/tow 接收机配对缓存，共 1509 对。目标相对时刻事前固定为 80、100、…、300 s，共 12 个；每目标取第一个不早于目标的原始配对历元。实际时刻均为目标 + 0.197999954 s，索引 121、221、…、1221。没有根据卫星数、整数、参考角度或输出选择历元。

所有 12 个历元均进入结果；SPP、星历、几何秩、信号有效性或候选失败保留。不得用邻近历元补位。220/260/280 s 已在 raw-only 统计中只有 3 颗 common integer-compatible satellites；仍保留，绝不扩大门限。该 raw-only 数量不等于完成星历/仰角筛选后的 DD 数量。

每历元独立 cold GPS L1 code-SPP，initial_position=None，iterated_geometric 地球自转；不沿用前一历元 warm seed，不读取旧 SPP 答案。这与现有连续 EXT 运行不同，因此本轮不是其全流程数值复现。SPP 或建模失败时不调用 A/B，但仍计入 12 个计划历元。RP 取 time≤RAW time、age≤0.02 s 且 source_status=active；缺失时 B/C 未决，A 仍可执行。

## 固定科学参数与预算

继承 backend 原有 exact signal identity、PR/CP valid、resolved half-cycle、CNO≥20、仰角≥10°、至少 4 星、几何秩和全 DD 协方差。保持原始 cpMes，不加观测偏置，不再额外加 NAVCLOCK，不对 Jan5 重新对齐时标。

每次 C-ILS strict=True；LAMBDA 初始候选 8；最多 1,000,000 节点、60 s 搜索；全局最优未认证则无可用候选。最多 12 次 cold SPP、24 次 C-ILS；C 调用 0。整个真实子进程 2100 s 壁钟上限，超限保留调用账本并终止整个独立进程组（含 strace 与 solver 子进程），不自动重试或补跑。A 或 B 单支失败不删除另一支的既定尝试。库和所有直接后端源文件 hash 冻结。

初步合成已执行 12 项/16 次 C-ILS：两种几何各含正确/±0.15 m 错误垂向先验、接收机交换、整数枢轴变换，另含公共 +7 周抵消和未解决半周拒绝。是无随机噪声/确定偏置的已知整数代码检查，不是 Monte Carlo 风险验证。A/B 在六项先验对照中整数均正确、C 均保留；因此 C 没有识别这些错误先验。合成与真实结果严格分表，不据此调整真实先验或阈值。

## 验收口径与停止规则

现有 C-ILS 的 global optimum certificate 只证明给定观测模型和搜索目标最优，不证明真实整数正确。后端没有正式整数验收检验。constrained second/best objective ratio 仅记录，不以 ratio≥3 声称固定，也不把其映射为风险概率。实测 integer correctness、wrong-fix probability 和 integrity risk 均为 NA。

记录每支的候选整数、ECEF/NED baseline、lateral projected heading（接口字段仍名 body_yaw_deg）、目标函数、白化原始残差平方和、先验标准化残差、证书及耗时。R 与先验噪声尚未完整实测标定，白化/χ² 类数值仅称模型自洽性诊断，不能解释为已验证置信度。C 保留率分母同时列全部 12 历元和 A/B 共同候选支持。

只有全部 12 条记录和调用账本封存，且 strace 审计确认在线参考读取 0，才能做一次离线参考读取。沿用冻结 HX02 yaw 语义，在原 RAW unix 时刻插值，支持外 NA、不外推、不 hold、不拟合符号/角偏移/时偏。评估量事前固定为 atan2(b_E,b_N)+90° 的侧向投影航向，未用 RP 反解欧拉角。参考仍采用 HX02 商业 Euler yaw；两者在一般 roll/pitch 下存在投影几何差异，本轮只将其视为沿用既有语义的近似一致性，不声称严格同被测量；不在结果后改为 RP 投影参考。插值支持为参考首尾范围，不额外设置 gap 阈值；固定原始 RAW unix keys，不调整时标。商业参考共享 GNSS 来源，只检查一致性，不当作独立整数或航向真值。本轮为 12 个独立稀疏历元，不测试连续滤波、恢复时间或持续跟踪。A/B 同支持比较与各自可用支持都列出，C 单独注明其选择条件。

如果源资格、几何或整数验收链仍不足，或真实候选仍有大角度不一致，本轮结束并记录限制，不以强姿态先验、参数搜索或新观测偏置绕过。结果只用于决定是否值得下一项有限研究，不宣告原始 AR 路线永远不可行。

## 执行与交付

代码入口 scripts/paper_rebuild/ar_tim_exploration_20261006/experiment.py。ignored roots 配置 configs/paper_rebuild/EXT_REPRODUCTION_ROOTS.local.json。机器实际路径仅留在 WSL scratch；tracked JSON 使用 <RAW_ROOT>/<CLEAN_ROOT>/<EXT_REPRO_ROOT>/<EXT_REPRO_BUILD>/<CODE_ROOT>/<AR_SCRATCH>。

READY stage 为 <AR_SCRATCH>/PREP04（如纯准备脚本修复需要新的准备目录，最终 AR_PREREGISTRATION.json 指定的 stage 为准；真实运行前冻结）。首次 PLAN 与合成 payload 保留。Linux Ubuntu 22.04 WSL；OPENBLAS_NUM_THREADS=1、OMP_NUM_THREADS=1、PYTHONPATH=src。

按顺序执行 prepare、root Git freeze、supervise --child real --execution-commit <frozen SHA>、验证 REAL_SEAL/REAL_IO_AUDIT、supervise --child evaluate。真实命令前后验证 inputs 和 source pins；根代理在 REAL_SEAL 完成前不追加提交。审计输出与在线/离线封存均不覆盖。tracked 交付小表、JSON 回执及中文资格报告，原生产源和 V3 结果不变。
