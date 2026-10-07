# 六次 ARC 被动回放结果：独立科学解释复核

结论：PASS_WITH_OFFLINE_WORKING_PRIOR_BOUNDARY。登记9c0641beea49e541fc4d64cde5446e4f052e74cc的6次native全部returncode=0、未超时、无retry；3对新NULL/TELEMETRY配对身份门通过。真实执行取得918组两端联合工作prior；这不是921全部覆盖，也不是可信航向、相位信息收益或导航收益通过。

## 1. 证据与独立复核范围

stage为 <SCRATCH_ROOT>/TRUSTED_HEADING_CONTINUATION_20261007/ARC_NATIVE_REPLAY_ATTEMPT01。
COMPLETE.json SHA-256为198fe2a336e8293f768ad16c6e25758d694be33b29e7b25c0071286c55d579fc；
ALL_NATIVE_SEALED.json SHA-256为828361466eeb723743ee6941e9ef0dd9c2cb9e52e249c56cbc59b1fe620e91d4，核与COMPLETE引用一致。没有FAILED.json。

本复核只读取完成/封存/过程回执、6份manifest与output seal、3份NULL lifecycle和conditioning ledger；独立重数状态与来源身份，另按根代理授权只摘每窗首3条未来报告HV源时刻示例。没有重读ARC_JOINT_PRIORS矩阵数组、provider、raw/reference、相位模型或追加信息/PSD/导航计算；没有重跑native/测试。矩阵shape/finite/zero-error/prefix通过来自已登记runner的一次结构汇总，不将本复核说成另做了全矩阵数值验证。

## 2. 全分母与终端缺支持

|序列|source块|两端prior|终端未覆盖|原合法模型与prior交集|模型不齐但有prior|已消费/原端点|
|---|---:|---:|---:|---:|---:|---:|
|BY2|274|273|1|239 / 240|34 / 34|547 / 548|
|BY2H|270|269|1|242 / 243|27 / 27|539 / 540|
|BY2O|377|376|1|376 / 377|0 / 0|753 / 754|
|全部|921|918|3|857 / 860|61 / 61|1839 / 1842|

初始未覆盖为0。独立重数3份lifecycle与COMPLETE一致；921个START均实际创建并退休，918个END保存prior，3个ARC_TERMINAL_RETIRE不造END。61个模型不齐块没有因空fingerprint被删除。它们有状态prior不等于有可用相位因子。857只是下一轮条件信息诊断的模型/状态已有交集，不是857可信航向更新。

三个终端块分别为BY2:BLOCK:273、BY2H:BLOCK:269、BY2O:BLOCK:376。均created=1、owner_at_creation=ARC、START_DISPATCHED_END_UNCOVERED，END state空/NOT_DISPATCHED；所需END时刻与最后serialized state如下：

|序列|所需END source time / s|最后状态time / s|
|---|---:|---:|
|BY2|339.99799990653992|339.997056|
|BY2H|682.99799990653992|682.995050|
|BY2O|3562.9979999065399|3562.997055|

终端未覆盖与已执行状态支持吻合；没有改窗口、吸附、外推或补最后pose。输出seal中NAV/STD/IMUERR逐窗同时间键、分别56642/58580/76548行。此为输出支持检查，不是参考精度。

独立ledger计数同时吻合manifest：START=274/270/377、END=273/269/376、terminal retire各1；普通更新7490/7253/10043，其中ownerARC普通联合更新5910/5740/7913；full reset1369/1349/1884。计数是实际执行，不等同独立观测数或信息自由度。

## 3. 配对身份与空相位边界

注册runner封存每对12个共有文件字节一致，包括NAV/STD/IMUERR、ARC lifecycle/conditioning/IMU segments、heading、BASELINE3D诊断及SOURCE_AWARE_WEIGHT_TRACE；只有TELEMETRY多出ARC_JOINT_PRIORS.jsonl。6份manifest另经本复核解析比较，除实际arc_native_telemetry_enabled=false/true外整个对象完全相等。真实NED模式没有BODY_VELOCITY_EVENTS.csv，与冻结生产设置相符。

三窗cov_health均PASS、fail_count=0，arc_phase_updates=0、arc_foot_pair_updates=0、heading_carrier_attempt_count=0。evaluator、phase_math、information_readout调用均为0。既有PVT heading仍在普通更新内；“空相位”不是无全部航向源。

只证明新同时间表两臂序列化不改变共同输出，不声称与历史PVT_CONTROL轨迹相同。有限性及对角健康不能替代独立完整PSD或物理协方差校准。离线进程用时不是实际传感器延迟或实时性能认证。

## 4. NED-HV报告源时间：已证计数与未证影响

重数3份ledger得到与COMPLETE完全相同的计数：

|序列|实际NED-HV更新|报告source_time > state_time|重复vector index|
|---|---:|---:|---:|
|BY2|1369|553|0|
|BY2H|1348|540|0|
|BY2O|1883|787|0|
|全部|4600|1880|0|

这1880是全窗NED-HV更新事件的报告时标关系，不是1880个相位因子、异常/周跳或物理提前到达。没有统计受其影响的prior组数，不能声称所有918组都被影响。RD更新666/525/927、RP更新1369/1348/1877；其未来报告时刻、重复vector index均0。三类source identity unavailable和index/time不一致均0。重复为0不证明误差独立。

根代理另授权每窗仅首3条future-HV例，读至ledger第41/33/95行即停止，没有新全窗幅度统计。解码SOURCE_TIME_BITS后的精确示例如下：

|序列/ledger ordinal|state time / s|reported source time / s|source−state / s|
|---|---:|---:|---:|
|BY2 / 19|66.599999905|66.603052139282|0.00305223428199497|
|BY2 / 33|67|67.001044034958|0.001044034957999429|
|BY2 / 41|67.200000048|67.201059103012|0.001059055011992882|
|BY2H / 6|413.200000048|413.201192378998|0.0011923309979806618|
|BY2H / 25|413.799999952|413.801065444946|0.0010654929459974483|
|BY2H / 33|414|414.001050949097|0.001050949097020748|
|BY2O / 6|3186.200000048|3186.201062440872|0.0010623928719724063|
|BY2O / 60|3187.799999952|3187.801065444946|0.0010654929460542917|
|BY2O / 95|3188.799999952|3188.801062345505|0.001062393505435466|

这些例子约1–3毫秒，不能仅解释成6位小数时间序列化的舍入差；但也不代表全部1880的幅度分布。物理时钟同步和实际arrival未知，未做影响试验，不能从例子推断收益损害大小或把全部事件称为实质信息泄漏。准确结论是继承NED择近政策尚不具备严格报告时标因果保证；本轮如实记录，未按该值删块或修改原行为。

## 5. 可继续的范围

918组P应称离线已执行前缀下的继承工作联合prior；actual availability为NA，phase-state cross为UNKNOWN，物理baseline/extrinsic和噪声资格未新增。相同执行前缀并不等于物理时刻已经可用的在线信息集。

可随后单独登记：在固定857模型/状态交集及921全分母下检验工作矩阵一致性和明确假设下的条件信息；不自动读phase或融合。若要主张在线可靠性或导航改善，NED因果策略、物理来源/误差界、phase-state/跨块相关性和失效准入仍需各自资格。任何NED政策修改属于新的科学改变，不能事后改本次封存结果。

本次实现了真实执行联合prior的获取及被动配对资格；没有解决持续可信绝对航向、真实载波中断恢复或稳定导航增益。
