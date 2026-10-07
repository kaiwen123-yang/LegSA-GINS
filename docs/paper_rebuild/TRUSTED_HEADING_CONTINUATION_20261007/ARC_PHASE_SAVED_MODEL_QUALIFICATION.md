# 未固定载波跨时相位差：已封存模型资格计划

状态：计划与入口待根代理本地 commit 登记；**921 块尚未执行**。本次只问
原三窗存在多少连续物理弧的合法消 N 时差观测、是否覆盖旧 singleton 未用机会，
以及噪声模型还缺什么。无方向点、无导航准入或实测可信通过结论。

## 已做的只读字段审查

检查了三个封存 PLAN.json、各一个已构建 NPZ 的数组头、ARC_EVENTS 字段片段，
以及原准备代码；另计算三个旧 CARRIER.csv 身份。该工作未逐块检验模型或弧连续性。
输入身份和本地全部实际导入源 SHA 见 ARC_PHASE_SAVED_MODEL_PLAN.json。

- 固定 GPS_GAL_BDS_DUAL。NPZ 仅有 y/A/B/Q；phase 行是第二个 m 行，
  A 的 phase 部分为物理波长对角阵、code 部分为零，code/phase 几何相同。
  y 已减过 known-SD 几何项，本入口不重复修正。
- GNSS2−GNSS1、target−pivot、ECEF、CPMES_AS_REPORTED_NO_SECOND_HALF_CYCLE_SHIFT；
  explicit SD arc 标签包含双方接收机物理 token。各端使用封存时自身几何。
- Q 是单历元完整 code/phase 工作模型；取 phase 子块并完整映射。
  原计划写 cross_epoch_covariance: assumed independent，没有 Q01 或实测时域校准。
  不能把此声明解释成已知零跨时相关；同一弧跨块也可能相关。
- 标签时刻是接收机 GPS week/TOW 对齐到封存本地时标；原始硬件 arrival、
  model-ready 时间未封存，actual availability/latency 保留 NA。
  exact receiver tag pairing 不等于物理同步已经校准。
- anchor 来自当前可用 code SPP，工程半径 100 m 不构成实际误差界；
  星历/时钟、安装、同步、大气、多路径等误差未被“消 N”消除。
- ARC_EVENTS 保存每接收机每信号 eligible/continued/metadata_continuous/
  temporal_link_qualified/reasons。端点同 token 不足以证明整段连续：
  必须检查区间中包括未成对事件在内的全部记录。

## 固定执行与全分母

| 原窗口 | 原历元 | 固定不重叠 5 历元块 |
|---|---:|---:|
| BY2 [66,340] s | 1370 | 274 |
| BY2H [413,683] s | 1350 | 270 |
| BY2O [3186,3563] s | 1885 | 377 |
| 总计 | 4605 | 921 |

每块仅取原第 1/5 历元，通常间隔 0.8 s；原步长 0.2 s、容差 0.01 s。
不换窗、族、端点、pivot 规则或重采样。source grid gap、无 anchor/model、
无连续关系等均保留在 921 全分母；模型 BUILT 不意味着隐藏周跳已排除。
原始 ARC_EVENTS 全区间检查会允许块首为新弧起点，但后续每条 link 均须合格；
原 max_gap_s 保持原值。可跨合法 pivot 重参数化，不能跨物理断弧继承整数。

与旧 singleton 的比较仅用精确对齐的 valid flag：
(1) 有合法差分而块末 valid=0；(2) 有合法差分而全块 5 次 valid 都为 0。
这两个计数是“未用观测机会”，不是新增可信航向率、正确固定率或收益。
旧 CSV 会被解析，但其中基线、协方差和误差不参与选择、线性化或噪声拟合。

## 预定输出和数学边界

- 每块 status 与机会/缺失原因；full OPPORTUNITIES.csv 保留 921 行。
- 各端消 N 地图 F0/F1、物理系数、z、G0/G1、relations/physical nodes 与来源指纹。
- 两个映射边缘工作项 Q0'=F0 Q0 F0^T、Q1'=F1 Q1 F1^T 分别保留。
  另列条件二阶矩上界 2*(Q0'+Q1')。其依据是
  E[(u1-u0)(u1-u0)^T] <= 2(E[u0u0^T]+E[u1u1^T])，
  对任意合法 cross 成立；但 RAWX 工作 Q 能否上界实际误差二阶矩尚未证明。
  **该矩阵不是已校准 joint covariance，也不证明各块独立**。
- G0、G1、[-G0,G1] 的代数秩、全部奇异值和机器精度阈值用于结构/病态性诊断。
  满秩不等于姿态可观性或可信方向，短间隔微小几何变化不能据此宣告绝对 yaw 已解。
  未引入姿态线性化，attitude_rank 保留 NA。
- actual_available_time_s、actual_latency_s、joint_covariance_m2、
  direction_point_ecef 均保持 JSON null / CSV 空值（NA）；导航准入始终 false。
  输出不含 baseline estimate/heading point、N 搜索或误差评估。

## 预算、登记和停止规则

一次固定遍历、单数值线程、最多 600 s；最多读取三套 PLAN/seal/ARC_EVENTS 与三张
旧 valid 表，各一次；最多 1842 个端点 NPZ、921 次几何差分和条件界。
metadata 预算 500 MB、NPZ 预算 100 MB（十进制）。已知原 PLAN 总约 128 MB、
ARC_EVENTS 总约 304 MB；按序列顺序处理并释放，不并行堆积全部 JSON。

入口校验源和计划均与 registration commit 字节相同；固定 scratch 布局下
旧 round TRUSTED_HEADING_20261006 下 FULL_WINDOW_PREPARE_ATTEMPT02、
FULL_WINDOW_FRONTEND_ATTEMPT01，以及新 round TRUSTED_HEADING_CONTINUATION_20261007
下唯一新输出 ARC_PHASE_SAVED_MODEL_ATTEMPT01。输出已存在即拒绝，不能换目录掩盖失败。
首次失败保留 FAILED/partial；本计划不授权重试、调参数或额外跑完整窗。
输入只限已封存模型/元数据与旧 valid 表；不读 raw/reference、不调用 native、
evaluator/CILS、不读旧导航姿态。import 依赖有底层函数定义，不执行其 raw/solver 路径。

局部资格已执行：原 26 项首次通过；geometry-only/未知 cross 条件界扩展后
原 26 回归 + 新增 5 项共 31/31 通过；adapter 的新弧块首、中间 link 失效、
额外未成对中间失效 3 项首次自检通过。原始回执各自保留。

下一阶段需独立相位故障准入/撤销和有来源的误差界；只有这些成立才考虑因子
消费/状态互相关以及受控导航对照。本次不自动接导航。
