# 固定十二窗候选集合资格 pilot

状态：计划与代码资格准备；**未执行实测枚举，须等 root 登记提交和明确启动**。本文件只定义算法接口、数学边界和实验预算，不涉及论文材料。机器参数以同名 JSON 为准。

## 固定输入和选择

只用 `<CARRIER_INTEGRATION>/REAL_100_340_V2` 已保存 BY2 开发输入的1200历元，family=GPS_GAL_BDS_DUAL。固定起始索引为 0,100,…,1100，每点只读其后5个 selection 历元（约每20s，共12窗）。没有按旧残差、准入、候选、参考或导航效果筛窗；不加载旧 frontend case 结果。此阶段不执行后5个 future 槽，不做新 V3 对比。

复用 `prepare_selected_likelihood` 和既有 `PartialPolicy(selection_epochs=5,min_ambiguities=4,max_ambiguities=6,dt=.2,tolerance=.01)`。选集只依据选择窗的弧/几何/Q。保留全部码和仅依赖选中整数的相位，Q 为完整主子阵；删除的相位不再进入本次似然。未选 N 不是设0、不是完整似然的整数 nuisance、也不是实值 nuisance 消元。记录实际 source rows、选中 labels 与 reduced problem fingerprint。

输入 PLAN、60个可能读取的 NPZ 与既有审计 pins 一致；LAMBDA 库只用于整数去相关，独立 pin。禁止原始 UBX、评价参考、NAV/STD 或误差序列读取。元数据检查失败不进入新搜索；不可用窗保留，无替代窗。

## 原始成本阈值

每窗 n=`len(problem.y)`，固定 `tau=chi2.ppf(.99,n)`。这里 n 是保留的标量观测总数，不是 n−p；阈值覆盖原始白化残差成本及浮点残差常数，不是 ratio 或 top2 差。枚举库同时记录扩展浮点阈值、`absolute_cost_guard=1e-9`、`relative_numerical_guard=1e-10` 和 condition limit=1e12。

0.99 仅是声明 Gaussian 工作模型的设计覆盖。既有 Q 未物理校准，selection6 和弧资格依赖数据，因此不能宣称真实99%覆盖、正确固定率或完整性风险。若将来加未来窗0.99预算，两个域交集也不自动具有联合0.99覆盖；本轮不执行该扩展。

## 整个连续域的长度必要筛选

Gaussian 松弛枚举保留所有历史整数列，基线为实值 nuisance。对每个 N，`rho=tau_work−Jfloat−JN`。第 k 个基线的条件椭球包含在以 c_k 为中心、半径 `sqrt(rho*lambda_max(Cb_kk))` 的欧氏球内；Cb_kk 是完整条件协方差的边际块。

任何长度 L_k 的向量与 c_k 的距离至少为 `abs(norm(c_k)−L_k)`。因此只有该距离严格超过外包半径并留出明确数值 guard，才能排除该 N 的整个长度可行域。任一历元不相交即可排除；中心自身不在球面不能作为排除理由。必要筛选通过也不证明椭球与球面确实相交。

调用独立 `filter_length_necessary_support`，原枚举默认逻辑不变。分别保存 raw support 与 necessary support 的完整标志和数量；原域不完整时，即使已见候选全被排除也仍不完整。无球面最优点剪枝，无有向先验，无错误先验替代方案。

第5选择历元的 baseline 方向使用该历元保存的 raw-code anchor 定义 WGS84 local north/east；只称基线方位，不称机器人 yaw。外包包含水平原点时返回全角。连续角域按圆周包络处理±pi；不只投影条件中心，也不新增角宽接受阈值。

## 预算和记录

最多12次整数域枚举，每窗最多1次；100000 nodes、10000 candidates、30s枚举工程 timer。setup/BLAS/外部 decorrelation 不能由此 timer 严格抢占，完整 API wall time及超限单列，不宣称进程硬30s或在线实时。普通不可用/超时/容量/数值失败继续剩余固定窗但不重试，输入/源/登记身份不一致停止。raw UBX、reference、原CILS、球面优化、准入、GLRT、native导航、evaluator 均0；整数去相关API最多12次，另行计数，不混称无整数计算。

必须记录：12窗全部状态；实际枚举调用数与预选不可用数；n/tau/扩展tau、维数/labels；raw/长度必要集合完整性与数量；全域方向外包角宽和水平原点退化；节点/叶/失败原因；float/decorrelation/enumeration API/长度后处理及总窗口耗时（内核无法拆开的部分记合计，不编造）。小表进repo，候选全集/连续域和日志保留新scratch，拒绝覆盖已有输出。

## 单元资格与之后的接口

原18测试只保留既存回执，不为日志重复执行。新增6项长度测试仅运行一次，10次低维枚举API调用、21节点/11叶，6 PASS/0.12s；stdout/stderr及开始前 source pins 已同步保存，见 `CANDIDATE_ENVELOPE_LENGTH_UNIT_RECEIPT.json`。包括非球面中心但域相交、边界相切、非目标历元排除、5个已知真球面点、不完整域及 problem 绑定。

后续真正闭环需冻结整个来源完整集合，对每个候选进行同物理 SD 弧投影并保留合并 origins；再用新观测构造该候选的当前连续域，未见/新弧不继承 N。原top2投影不能代替完整集合。该未来更新/准入/导航不在此次12窗预算内，必须在本次规模与完整性结果出来后另行登记。

## 执行入口与完成前资格

入口 `scripts/paper_rebuild/carrier_phase/candidate_envelope_pilot.py`；运行时必须显式设置 `PYTHONPATH=<REPO>/src`，以及 OPENBLAS/OMP/MKL/NUMEXPR 线程均为 1，避免调用已安装旧包或改变线程资源条件。参数为 `--prepared <CARRIER_INTEGRATION>/REAL_100_340_V2 --input-audit <TRUSTED_HEADING>/ARC_SUPPORT_AUDIT_ATTEMPT01/INPUT_IDENTITY.json --output <TRUSTED_HEADING>/CANDIDATE_ENVELOPE_PILOT_ATTEMPT01 --registration-commit <ROOT冻结的完整HEAD>`。输出目录必须不存在，禁止自动重试/恢复。

入口在运行前逐字节核登记提交中的 plan/runner，并核所有已登记模块源、60 个固定 selection 模型和 LAMBDA 库；完成后再核一次。只解析保存 PLAN 与哈希审计表，不打开旧 case 准入/误差结果或参考轨迹。桥接层计数器只包裹 `decorrelate` 的 API 入口，不改变实参或返回值；这不是整数 CILS 调用。所有窗口保留，即使预选不可用、数值不合格或资源中止也不替换。

已完成资格：原 18 个 envelope 测试没有重跑；整域长度过滤新增 6 项通过（10 次纯合成枚举，0 LAMBDA）；入口新增 5 项通过，涵盖固定窗口不读旧状态、禁止补窗/future、更改时间/计数失败关闭、WGS84 N/E 方向和 SHA 门（0 枚举/原始数据）。回执分别为 `CANDIDATE_ENVELOPE_LENGTH_UNIT_RECEIPT.json` 与 `CANDIDATE_ENVELOPE_PILOT_ENTRY_UNIT_RECEIPT.json`。另有 planner 独立只读审查，未新增数值调用。

本计划源文件和接口检查完成后等待 root 登记冻结与明确启动；写计划、导入定义、静态检查均不代表已经运行真实 12 窗。
