# 完整窗口因果集合前端：最小工程设计

工程设计已落实专用 provider 内核（局部合成验证另有回执），尚未执行完整窗口枚举或 NAV。首个闭环建议只运行 `GPS_GAL_BDS_DUAL`，三原 V3 窗口 1370 / 1350 / 1885 个预期 RAWX 槽全部保留；其他 families 作为已准备输入保留，不按误差或搜索结果选择回退族。模型须来自 `full_window_prepare` 新封存 MODELS，不拼接旧开发窗口弧历史。

## 1. 完整来源与有界调度

每个 acquisition 用截至当前的 5 个连续槽，复用 `prepare_selected_likelihood` 的既定几何/Q/弧交集 selected6。保留码和只依赖选中整数的相位、主子阵 Q；这是删去未选相位的新似然，**不是 profile 所有未选整数**。使用完整 `enumerate_candidate_envelope`、原 `chi2(n,.99)` 原始 n 维成本设计值及全历元长度必要过滤；长度仍精确 .35 m。不调用旧 top2 来代替集合。

固定每 5 个原始 RAWX epoch 给一次 acquisition opportunity，从第5槽开始（预期上限 274+270+377=921；在正常5Hz下约1s）。物理 SD 弧支持改变记入逐槽日志，仍等待下个固定块，不额外滑窗搜索；current residual、角宽、GLRT 或合法纯 pivot 换坐标均不能触发额外搜索。精确机会分母以 sealed MODELS 序列登记，不能据结果删窗。

只设一个 acquisition worker，无任务队列；忙则记录 drop。只有一个 active owner 和一个 pending/probation 槽位，正在搜索也占 pending。pending 非空时新机会记录 pool drop，不能用搜索成功/候选数挑选先后。pending TTL 建议 source selected_at 后 3 s；active TTL 建议同一原 selected_at 后 10 s。TTL 是登记的资源/陈旧度政策，不是可靠性界；超时完成仍保存结果；pending 对象可以已构造，但未到可用时刻即超 TTL 者会退休而无发布，不中途重试。pending_providers_constructed 只数构造，不能称可用或固定次数。成功来源也不续写 selected_at。

建议每次沿用 100000 nodes / 10000 raw candidates / 30 s 协作超时。完整来源经长度必要筛选后若 >64 类，保存完整输出、标 `SOURCE_COMPLETE_NOT_ACTIVATED_RESOURCE_LIMIT`，绝不截前64。最多两套活跃来源；保守上限为 921 次完整枚举及同数 LAMBDA decorrelation，激活状态的组合上界为 589440 次各 GLS/GLRT/geometry（2×64×4605），但阶段实际资源上界收紧为 **400000 GLS / 400000 GLRT、总处理 1200 s**；geometry 与 sphere 各自显式计数，sphere 绝不超过9210（2×4605）。这些是资源终止条件而非候选裁剪；到限后全部未执行槽仍保留。12 开发窗数毫秒不能外推全窗最坏耗时，理论 921×30 s 只是最大搜索许可之和，不是预计耗时。

## 2. 集合生命周期、来源切换与验证

每个完整 source 独立维护 `ConditionalCandidateSet`。按原物理 token 退休并做精确整数关系投影；相同当前关系可并类但 origins 集合不能丢。所有 source 整数始终保留，current raw/length/phase 失败只令本槽不可发布并清零连续验证，不永久删除 N；全失弧永久终止，不继承新弧。来源全域完整性只针对原 selected likelihood / 工作 Q / 原成本域；投影后不升级为当前全局整数完整性。

独立水平椭圆及 sphere-cap 对所有类报告分量并集和 hull；phase-bad 类不能因诊断而从并集删除。初版 point gate **保守地仍要求原 lifecycle 当前兼容类数为1**，不使用几何必要域删类把 multi 变成 unique。若单类仍全圆/多连通或球面 ML 非唯一，仍不发布。多类始终保留分离集合，不平均、不挑中心最接近历史的类。

每个 source 的 **连续5个严格晚于 selected_at 的槽**，均须当前单类、原质量合格、phase>=4/rank3，并且所含 origins 的5槽交集非空。单槽调用既有有限 Python sphere ML，按同一真实投影 y/A/B/Q 复算原始完整 raw cost <= 原 expanded tau 才计入 streak；不能只看自由 b 中心或长度必要球。多 origins 合并为一个当前类允许保留共同 origins，但不声称原整数唯一。临时失败只重置 streak；物理资格退休也重置 streak，再在存活域重计5槽；允许同一仍连续物理源随后重新累计5槽。

新 source 不与旧 source 相乘、拼成独立先验或再缩 Cb，重叠 selection 信息不算第二份证据。同槽最多输出一次当前原始观测。owner 到期/结束后才接已独立完成5槽验证的 probation，接管当槽不发布、下一槽重新检查后才可输出；健康 owner 不因新 source 更窄而提前更换。本轮不把不同 source 作联合一致性检验或取交集；存在多来源时仍只有固定 owner 的条件域，不能宣称已排除其他来源的整数冲突。所有未输出新来源依然完整记录，不声称新旧 origins 共同覆盖当前全局空间。

## 3. 时间与专用接口

新增专用 `CompleteSetPointProvider` 内核，内部调用现有 lifecycle，避免重复 GLS；返回当前 domain、逐类 geometry、`SetValidationReceipt` 和可用/不可用测量。不构造旧 primary/competitor `AdmissionDecision`。receipt 绑定 source fingerprint、原 selected_at、来源处理完成的可用时间、5个当前原始/变换模型及 domain 指纹、origins 交集、L、原成本阈值及全部质量口径。

acquisition 完成可用时刻必须为 selected_at + **实际整次 selection / 枚举 / 长度过滤处理耗时**，不能用 result yield 或旧 inner timer 代替。最早输出槽不早于该时刻及第5 future。晚完成来源从原第1 future 逐槽只消费物理弧元数据，历史模型显式设为 None：不补历史验证、不输出，streak 从重新可处理的当前槽开始。原 selected_at 永不改写。pending TTL 已过则不 catchup 构造可用测量。

provider 的 `decision_time_s` 是明确登记的 **offline 观测事件时间**；只有当前 model.time == decision_time 且来源已可用才可导出。每次 fit/geometry/sphere 的真实处理耗时单列账本，不能称硬实时零延迟。若调用方传入包含本次真实计算延迟的完成时间、因而与观测时刻不同，内核不导出。完整实时单CPU调度/OOSM未实现；现 native current-time 接口只能接明确标记的 offline filter replay，不以 catchup 伪造硬实时性能。

## 4. 能输出什么、仍缺什么

通过上面条件后只能输出 `RESEARCH_CONDITIONAL_SOURCE_SET_POINT`：当前 sphere ML 基线、原固定 N 的 Cb + 既定1.5°角 floor，以及方向集合/来源/延迟侧车。该协方差不是非线性投影精确协方差，也不包含离散错 N、筛选条件化、时域相关或相位模型失配；五次重叠/重复验证没有已校准总体置信率。`integer_truth_known=false`、`global_alternatives_covered=false`、`false_fix_probability=null`、`production_validated=false` 必须保留。

可检验的缺口包括：宽域与多方向别名仍可能存在；已知安装/有向运动信息尚未进入本闭环；当前工作 Q 未经真实噪声标定；原15质量拒绝不能靠方向收紧解除。完整 source + 原质量 + 条件5槽足以定义可重复研究 provider，**不足以宣称正确固定或生产可信性**。先登记并实现单元语义，再登记三个完整窗口 frontend；NAV/参考评估另按已有固定合同推进，不改门追精度。

虚拟 worker 计入当前输入读取/状态检查/内核及整次 acquisition 的实测服务耗时；公开候选 JSON/CSV 的诊断序列化和磁盘输出不作为在线算法服务，外层 wall time 包含这些开销。current_result_runtime_available_s 是当前结果服务完成时间估计，CARRIER.csv 的时间仍为离线滤波事件。两种时间口径分列，不能把它们当成同一个硬实时交付时刻。
