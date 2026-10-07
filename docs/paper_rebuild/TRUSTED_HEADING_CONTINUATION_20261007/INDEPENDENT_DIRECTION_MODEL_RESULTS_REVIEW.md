# 侧向投影单因素试验：独立结果审查

日期：2026-10-07。状态：PASS_EVIDENCE_SCOPE_CHECK_EFFECT_GATE_FAILED。登记 a40c59153a9e6e1cfd897f0782a94fa53cd14471；试验根 <SCRATCH_ROOT>/TRUSTED_HEADING_CONTINUATION_20261007/DIRECTION_MODEL_ATTEMPT01。独立子代理只读既有配置、台账、seal/回执、原生访问日志、heading事件及比较小表，使用独立标准库CSV算术核delta/采用门；没有重跑solver、evaluator或comparison，没有读取原始传感器/参考payload，没有重新hash大NAV/STD/误差载荷。只新增本报告。

结论：证据范围与单因素身份成立，未见结果替换或支持裁剪。相对原V3，三窗九指标在事前非退化容差内、覆盖不减；A失败，0窗达到5%航向RMSE收益。相对匹配Euler控制，BY2/H航向变差、BY2O微小改善，P99三窗均升。因此不推荐本次模型切换替换正式V3，不把工程非退化写成新收益。B无相应恢复试验，仍NA。

## 身份、调用、参考和支持

- 独立逐字节比较旧/新三个运行配置：只改变stage_id、protocol_id、case_id、run_id、run_label、outputpath及dual_yaw_prediction_model；删去这七行后原字节完全相同，行数相同。模型确由euler_yaw改为lateral_projection，五provider、HV、参数、来源策略和carrier旁路未改。
- 复用native binary SHA256 7f8a8f332fa36b957a88231228ad73c1cab206327e701dc9f98d0abb1da1b0a2、checker 346f502e8b6cb2cbf54ad446e424221d3331f043517efb592478aa5660b57db8。native源码身份属于旧登记3c81e5b8e4df4bece69c5f4635f0a60bd12c4369，不属于当前工作树。
- loader/native/evaluator账本各3个唯一身份、retry均0。3个loader返回0；3个native完成、返回0、未超时；3个评价完成。小型PLAN/native seal/evaluation seal哈希链相符。全部native预留时刻加实测运行时间均早于首个evaluator预留；native seal时间早于首个评价，并由评价回执绑定其哈希。
- 三个native访问审核PASS：原始/参考打开0，缺输入0，越范围写0，各native执行1次。独立检查原生strace中不存在任一锁定reference路径。三评价audit PASS、各参考只读打开1次并核锁定hash，父进程reference payload读取0。评价raw_open_count=1指其获准读取的参考，不是额外传感器读取。
- NAV支持时间键hash、封存匹配error时间键hash均与旧Euler相同。比较表保留完整窗和真实共同键；三窗分别56642、58580、76548行，评价未匹配、相对V3缺键、额外键全部0。独立复核的是封存hash/计数和小表一致性，没有重新读全量NAV/error来再次计算同一指标。
- 独立从HEADING_SOURCE_EVENTS.csv重新计数：PVT尝试/接纳为BY2 1369/1348、H 1349/1334、O 1593/1588；carrier尝试/接纳三窗均0，与派生回执相符。旧manifest计数缺陷没有被覆盖。

## 数字独立复算

差值均为projection减对照，正值表示误差增大。以下数字由已封存CSV中的current/control/V3列重新计算，而非仅照抄gate字段。

|窗|原V3 yaw RMSE / deg|Euler控制 / deg|Projection / deg|对Euler差值 / deg|对V3变化|对Euler yaw P99差 / deg|
|---|---:|---:|---:|---:|---:|---:|
|BY2|1.886271855|1.884387395|1.900974589|+0.016587194|+0.779460%|+0.016845171|
|BY2H|1.933770135|1.934798690|1.937628935|+0.002830245|+0.199548%|+0.003672916|
|BY2O|2.433814933|2.432887650|2.431536401|−0.001351249|−0.093620%|+0.006536716|

按合同独立计算27项非退化比较：yaw容差max(0.02deg,1%)、H/V RMSE容差max(0.0005m,1%)、H/V P95/P99容差max(0.001m,1%)，均PASS。三窗覆盖也PASS，但无窗达到相对V3 yaw RMSE降低5%。重新得到nondegradation=true、A=false、qualifying=[]，与COMPARISON.json一致；所有full与common的current九指标仅有浮点舍入差、全部时间键相同。

H RMSE对V3分别减少0.000523631m、0.000393638m、0.000480249m，Up RMSE减少0.000196191m、0.000188194m、0.002087075m；这些总差不能全归因模型，因为正式V3与研究Euler控制本身有既存差异。匹配Euler的零容差九指标非退化三窗均为false，原表完整保留了微小不利项。

封存事件表的yaw连续越界段数由Euler的446/521/399变为450/522/400；它们是阈值连续段计数，不是独立失效概率。BY2O尚未确认恢复的段数由167变169，其他两窗为12/386不变。该审查没有重新计算全量误差事件，仅复核其报告范围；不能用平均RMSE掩盖尾部或恢复的不利变化。

## 科学解释与后续

本结果只否证“在冻结输入、权重、HV和调度下，仅改这一个物理观测模型即可产生合同要求的稳定收益”。它不否定侧向投影的几何公式，也不证明旧Euler模型在物理上更正确；不能据这三窗倒调roll/pitch、噪声、偏置或阈值。未检验原始载波、方向域仲裁、脚对新更新、独立FK或真正故障恢复，不应借本结果终止这些有不同信息来源的新假设。

下一局部实验优先回答信息是否存在：未知相关更新记录J/T及各候选分数，区分网格漏解和连续族也必SKIP；同连续物理弧的时间差相位先验证N消元、秩、同步/周跳和相关性。没有可进入的新增信息时不为凑矩阵运行完整导航。

对ACQUISITION_PLAN的影响：转动采集需分别保留水平转向和多轴倾斜，并具有独立参考姿态、安装向量与时标，而非只增加同类行走轨迹；支撑采集优先补原始关节/FK、body到IMU物理对应与接触/滑移证据；遮挡采集需有同层PVT/RAW影响账和独立方向参考。以上不自动要求新购设备，先取得用户现有设备信息。当前共享GNSS商业参考不能解决微小差异的独立真实性或不确定度校准，故不把本批亚百分比差值写成统计显著结论。

原V3/main继续保持；本报告不授权合并，不改变先前负结果、注册门或用户审核权。
