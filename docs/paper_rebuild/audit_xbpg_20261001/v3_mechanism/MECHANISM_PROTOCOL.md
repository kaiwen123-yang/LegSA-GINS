# V3 最小机制取证协议

本协议在首个真实诊断调用前提交。接续展示更正及暴露补注；不把原科学结果改成新诊断版本。源码适用性、输入身份、历史输出复现、观察版无干扰、事件触发、影子权重和闭环影响分别判定。

## 队列与调用上限

选取由元数据预定的 BY2 C00、A1/A2 20 s seed_00、D15_seed_00。A1/A2 的实际注册 anchor 均为206.2 s，区间均为[196.2,216.2)，不是从性能挑选。D15为全序列位置高斯噪声，不把anchor当局部噪声窗。

|组|F03|A04|F04|
|---|---|---|---|
|C00_clean_normal|RUN_00003|RUN_00006|RUN_00004|
|D61_20s_seed_00 / A1|ADD_RUN_00102|ADD_RUN_00105|ADD_RUN_00103|
|D62_20s_seed_00 / A2|ADD_RUN_00399|ADD_RUN_00402|ADD_RUN_00400|
|D15_seed_00|不新增|RUN_01403|RUN_01401|

11唯一身份，每个至多一次原冻结binary和一次观察版，共至多22次真实native。技术失败保留退出值、已产文件和原因，不自动重试；若必要技术重试，先独立登记具体原因和计数，不新增科学case。合成fixture执行另列。主GNSS/RV/辅助开关逐对象取原配置；F03是关闭辅助的负对照，不能把关闭记为N09触发。未扩大方法/种子/时长。

旧SOURCE_AWARE_WEIGHT_TRACE与PORT时序日志先查已有字段。旧SA表可说明已记录的权重，但没有同事件H/dx/P/baseR；旧循环日志没有完整辅助匹配/未调用原因。因此新重放用于这些缺失量和无干扰对照，不冒充重新找到历史创新日志。

## 身份、输入及隔离

正式求解源`ca73cb1fb48a020fd2a450d79e520562c34eeb24`，原binary SHA256 `96ae436d82ba8922c68382bd73fc42c8bf4bcb22d72a43a8bd05f506043a9c1c`。runner `7d43b9af26120ed5dde21f53e515386361072ba6`另列；原RUN_MANIFEST的`source_commit=5a4471efd4fcfcdc31e258a677af354c652ff16f`字面值保留，外层登记实际freeze，不据此混同科学版本。B3不进入本队列。

`DIAGNOSTIC_QUEUE.csv`及`INPUT_USES.csv`以原V3_NATIVE_SUMMARY、配置及OUTPUT_SEAL逐键登记。五类直接输入按实际文件去重，全文读取并核实一次hash，记录数值字段、缺失、非有限、有效位与时间域。`QUALIFIED_INPUTS.csv`与`INPUT_FIELD_QUALITY.csv`为本轮读取结果；hash与生成语义审查分开。原raw生成历史只以明确的bundle/source证据链接，不声称重新运行生成链。缺项或pin冲突仅阻塞该身份。

原配置原字节只读使用；用原CLI `--output-dir`和`--debug-output-dir`明确重定向，不YAML往返。原start/end与初始化不变，全运行范围66..340 s，并保持原provider前置数据可见与原读取/跳过行为。不得仅运行故障局部窗。输入不生成、不修复、不替换。

`INPUT_STAT_CHECKPOINT.csv`是在全文资格/hash读取完成后单独保存的文件元数据检查点，不伪称hash扫描同时取得。后续每槽检查bytes/dev/inode/mtime不变，不重复扫描provider。`INPUT_ECHO_CHECKS.csv`的66个开关与原RUN_MANIFEST逐值一致。独立`replay_one.py`锁定已提交协议/输入/pin，非阻塞排他锁、一次只收一个显式槽；22个正常调用槽不自动重试。原版/观察版全部RUN_MANIFEST键精确比较，只有`source_commit`允许构建来源差异，科学counter/开关没有例外。strace确认实际exec数与预约次数分列；1800 s技术超时终止进程组，失败与已有载荷保留。

隔离根由ignored `configs/paper_rebuild/V3_MECHANISM_ROOTS.local.json`解析：`<MECHANISM_ROOT>`保存所有真实运行的NAV/STD、事件、strace和失败；`<MECHANISM_BUILD_ROOT>`保存ca73源码快照和构建。源快照成员见`SOURCE_MEMBERS.csv`。观察patch只应用于隔离副本，正式cpp不变。原flags为GCC11.4、C++17、Release `-O3 -DNDEBUG`，单线程。实际编译器/flags/patch/hash另存构建回执。

## 预先固定的无干扰判据

1. **历史对原版**：新原版的KF_GINS_Navresult.nav、KF_GINS_STD.txt及原OUTPUT_SEAL明确列出的其他数值输出逐文件SHA比较。原载荷已释放，只与可信recorded pin核对，不说读了旧文件。
2. **原版对观察版**：完整NAV/STD字节和科学counter/有效配置首先要求精确一致。允差不用于掩盖字节门失败。输出路径、日志、用时、观察开关/计数是允许差异；原科学状态与开关不在此例外中。
3. 仅对本轮“新原版与观察版”两份实际载荷，若数字格式/编译差异导致字节不等，保存完整逐行差异。在相同行数、相同列、严格时间对应、所有有限的前提下，备用数值界限为每值`abs<=1e-12+1e-12*abs(original)`，时间`abs<=1e-9 s`，计数精确。只能记`NUMERICALLY_CONSISTENT_WITH_FIXED_TOLERANCE`，不能记字节相同；超过即`IDENTITY_NOT_ESTABLISHED`。历史载荷已释放，历史pin与新原版不等时不能应用数值备用；必须记`HISTORICAL_IDENTITY_NOT_ESTABLISHED`并停止该对象历史机制归因，不能由新两版接近补救。
4. 不以RMSE是否改善作为观察插桩有效性判据。历史输出字节已对应时无需重开reference或重新评价。若后续确需冻结离线评价，须先确认原评价源码/pin、物理点、时轴并在调用表中单列；本协议默认计划evaluator调用0，不为取证增加新的性能排名。

## 观察字段与调度分母

日志精度为可往返double的17位，时间单位沿原相对秒；每条有run、递增event/update序号、source、GNSS/IMU/measurement时刻、res分支。`available_time=UNKNOWN`，因为测量时刻不是真实到达时刻。

观察必须覆盖入口外：每个原GNSS输入的position/velocity/yaw三有效位与OR值、IMU机会及res，辅助enable/loaded row数、原row_id和time、active/valid/update_flag、原匹配容差及nearest结果；既记录实际进入更新，也记录入口阻断、尚未到时、无行、时间不匹配、质量拒绝、创新拒绝、接受。按原nearest选择观察，不能推进原索引或调用会改历史的函数。重复消费按相同source/row_id的实际接受序列另计，不假造网络到达事件。

数量链为：输入存在→源字段合格→调度条件→实际尝试→接受/拒绝。输入行数、IMU机会、GNSS事件和更新次数各自为分母，不能相加成独立量测总数。A1无有效HV输入与有合格RP但入口被阻断分列；A2仍有heading，不套用A1的GNSS整体失效。F03 `DISABLED_BY_CONFIG`独立于入口阻断。

窗口摘要使用固定full[66,340]、before[66,196.2)、during[196.2,216.2)、after[216.2,340]。after不是声称测得恢复时间。D15/C00全窗比较，不按误差重新选段。

## 同快照创新与权重核对

每个顺序更新保存dz、H、dx_before、P_before、判别当时的baseR及effectiveR、dof、旧NIS/normalized、LSIM/OIM/cap/combined、source metadata、accept/reject与更新顺序。EKF实际更新同时保存dx_after及实际创新；实际姿态、IMU原始/补偿状态、bias/scale、杆臂和分支足够时用于N11/N01/N02条件核查。所有中间量为`replay_observed`。

观察代码只读原调用实际变量。不为日志第二次调用SourceAwarePolicy::evaluate，不改变rolling history、计算顺序、缓存、触发、残差或R。原策略及滤波函数逻辑不改。影子公式仅离线作用于该事件同一快照：

`nu=dz-H*dx_before; S=H*P_before*H^T+baseR; nis_expected=nu^T*S^-1*nu`。

先用同快照dz重算旧NIS以校验导出和矩阵约定，再比较nu。NIS核对固定`abs<=1e-9+1e-8*abs(recorded)`；scale比较`abs<=1e-10+1e-10*abs(recorded)`，Hdx非零阈值1e-12。落在门限数值容差内的跨界另列`BOUNDARY_AMBIGUOUS`，不事后放宽。矩阵无法求解或原fall-back定义不同则单列不能计算。

使用真实N6B/clean_v1 policy：normalized=sqrt(NIS/dof)，deadband/moderate/strong=原1.5/2.5/4；alpha取实际最终赋值（position0.00003、RV0.04、yaw0.03、RD0.35、RP0.02、HV0.03）。delta=max(0,normalized−1.5)，raw_scale=1+alpha*c*delta²，c在normalized>4时为1.6、>2.5时为1.2、否则1；不是将整个scale乘1.2/1.6。source/global cap、LSIM max合成和reject_extreme=false均沿原值。rolling仅诊断不反馈原权重。不是引入新的统计定义后判错。

N12逐层统计Hdx非零、NIS改变、deadband/OIM改变、被metadata/cap抵消、最终R/接受决策是否改变。A04 SA关闭，其影子算术不记作实际权重变化。跨A04/F04的状态一般不同，不能将同时间两状态的NIS差称同状态反事实。

N16仅对SA+HV记录旧std三分量/999哨兵与实际二维R。影子只取消vertical_disabled维度对std_max的贡献，保留二维std及其他metadata、OIM、cap；逐项计算去除该条件前后的LSIM/finalR。仅命中reason不是权重实质影响；最终R变化也不证明位置误差受损。

原实现和观察版均未接入影子决策，故没有“修正后的RMSE”，没有闭环修复效果。有限11组不能外推全部6468组；未触发仅限本组，真实触发不自动使全部旧结果作废。

## 保存与后续裁定

每组依次C00、A1、A2、D15，保存结果、限定staging、commit/push并核验远端后再继续。所有native/evaluator实际调用、失败和合成测试另列，技术失败不隐藏。raw/provider/原V3/旧审查及保留时序只读，大NAV/STD和事件不提交Git；公开小表保留alias/source/event键与固定判据。

最终分别回答N09/N12/N16及同批可回答的N11/N15/倾斜条件。参考独立性、匹配前支持、STD坐标传播仍是独立待办。本轮不修正式算法、不生成新provider、不扩大队列、不删除资产、不做新ZIP。
