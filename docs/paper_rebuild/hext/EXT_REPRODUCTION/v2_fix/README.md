# EXT V2：物理修复后的新九组合验收与论文数字入口

2026-10-04 后结果源码保护更新：[竖直投影保护与有效标志修复](post_result_heading_guard/README.md)已通过19边界/75相关测试及独立peer；全部9,100有效保存基线未触发。下列表/图仍对应原guardless九组运行及其执行快照，新3源身份没有回贴旧9/135成绩，没有重跑科学实验。

2026-10-04 已完成全九独立原生运行、全量封存准入、三次离线评价、保存误差独立复算和三图实际目视检查。新运行是 RAW_REPRO_V2__TECH_RETRY_2；旧V1表、图与运行完整保留。源码为0625cea基点加经审阅的实际worktree overlay，尚未commit/push，不能以base HEAD冒充完整执行源码。

## 最新自身支持

以下不是Euler姿态同量/同输入排名。方法输出是机体 −y 横向基线的水平投影方位+90°；参考是商业融合Euler yaw，仅离线诊断且非独立真值。若 R=Rz(ψ)Ry(θ)Rx(φ)，两者差为 atan2(−sinθ sinφ,cosφ)，须水平投影非零。表列全窗内实际有效输出；失败及边界未输出保留1370/1350/1885原分母，不把全历史1509/1483/2231当评价窗分母。

|序列|方法|原生有效/原完整窗分母|投影航向相对参考 RMSE（°）|全历史有效/配对|原生wall（s）|
|---|---|---:|---:|---:|---:|
|BY2|EXT01|980/1370|85.015472|1077/1509|366.218|
|BY2|EXT02|961/1370|85.179795|1057/1509|8.589|
|BY2|EXT03|541/1370|79.931845|609/1509|11.748|
|BY2H|EXT01|1059/1350|89.127388|1172/1483|376.564|
|BY2H|EXT02|1029/1350|89.192923|1128/1483|8.206|
|BY2H|EXT03|467/1350|63.994556|526/1483|11.456|
|BY2O|EXT01|1173/1885|81.273465|1511/2231|1317.865|
|BY2O|EXT02|1210/1885|81.486071|1527/2231|14.622|
|BY2O|EXT03|269/1885|103.754200|493/2231|14.141|

所有未舍入值、P95、max、MAE、circular bias、首有效/首fixed时刻、最长失联、held年龄及来源字段见 [完整63行总表](COMPARISON_TABLE.csv)。EXT01/02没有接受检验，其ratio_fixed为NOT_APPLICABLE，不能写成0正确率。EXT03窗口ratio支持分别78/70/5，RMSE40.062654/56.439130/43.407232°，不等于整数真值正确。

## 共同支持与新旧差异

|序列|三方法共同有效key数|EXT01 RMSE（°）|EXT02 RMSE（°）|EXT03 RMSE（°）|
|---|---:|---:|---:|---:|
|BY2|506|73.380490|73.380490|78.508921|
|BY2H|451|79.765226|79.765226|64.623900|
|BY2O|227|79.621907|79.621907|105.241841|

[全部450行共同支持](COMMON_SUPPORT_ALL.csv)涵盖12个三方法×RTKLIB成对组、三方法组、四个三方法+RTKLIB组和ALL7。320行可计算、126行fixed不适用、4行空交集都保留。ALL7 native交集仅6/39/55；同key不消除GPS L1与GPS+BDS双频、固定长度WLS与递推模型、状态/质量门及物理量差异，不能升级为公平求解器排名。旧RTKLIB四变体明确标REUSED_FROZEN_HX07R_NO_NEW_RUN。

[27行V1/V2同法同key复算](V1_V2_SAME_METHOD_COMMON_SUPPORT.csv)表明，EXT01/02原生共同支持RMSE差的绝对值均小于5.3e−6°，EXT03全部支持逐项相同。SPP物理修复成立，但没有消除真实大误差/缺测。BY2O EXT01两版自身均1173有效，只有1170共同key；三旧独有/三新独有key完整列在 [支持变动](V1_V2_SUPPORT_CHANGE_KEYS.json)。其自身RMSE81.363602→81.273465°和held差−0.193101°不能全部归因SPP：固定wall预算搜索与支持更换的影响保留，不作纯单因素确定性改善声明。

## 真实源与访问证据

[最终回执](FINAL_EXECUTION_RECEIPT.json)、[原生访问/守恒审计](NATIVE_ACCESS_AUDIT.json)、[341项独立RMSE复算](INDEPENDENT_METRIC_RECOMPUTATION.csv)和 [视觉验收](VISUAL_REVIEW_RECEIPT.json)闭合。15669原生历元记录逐项索引、valid/failure守恒、压缩证据行数及输出hash均核；22输入/缓存/NAV逐文件只读pin、两库pin、16全局源/配置/评价协议pin与各run13科学源+config snapshot均前后匹配。成功openat审计在线reference/禁止数据打开均0；该计数是成功读取的审计，不将失败尝试静默冒称不存在。三offline child共三次只读reference打开，无自动重试。

Python package初始化额外加载三init、manifest和paths五文件，全文审查为声明/定义及import，无顶层科学输入/reference访问；当前同HEAD且loaded pyc代码与当前源compile相等。它们不在13科学源码运行前快照，另存bootstrap补核回执，不把事后hash冒充运行前完整package pin，也不声称整个Python package逐行执行覆盖。

全九HEADING中9100有效输出均有非零水平基线；全局最小水平范数0.0198182443m、最小水平/全长比例0.0566235552，投影公式差≤5.69e−14°。本批未触发纯竖直未定义角落；legacy helper对此会返回90°的源合同问题仍待下一独立版本guard修复。本批未使用该guard，不选删历元或改指标。

实际新stage位于E宿主WSL ext4，别名<EXT_REPRO_V2_RETRY_ROOT>，328文件113,306,700逻辑字节（封存时；后补核小JSON增加单独记账）。原生runtime包含SPP/adapter/多worker与固定预算，不能宣称在线最坏延迟。G保留小根映射/收据/报告/图，旧partial根及旧V1不移动或覆盖。

## 三序列图与论文使用范围

[BY2](evaluation_results/BY2/README.md)、[BY2H](evaluation_results/BY2H/README.md)、[BY2O](evaluation_results/BY2O/README.md)保留真实角度跳变、缺测和EXT03米级基线异常；PNG/PDF原绘制无裁剪数值、无跨缺测或wrap连线。Panel(a)原字段标签Body yaw须连同本节物理量说明阅读；正式论文应标projected lateral-baseline heading，黑线commercial fused Euler yaw reference。三图已经实际逐项查看，不用hash代替视觉审阅。

三方法可称“原文核心算法独立实现及明确工程实例”，不能称作者原实验/全系统完整复现。EXT02多天线三轴未实现且全候选池失败整历元拒绝政策不改；EXT03依赖项目声明的noise/state/reinitialization工程实例；没有作者整数真值、完整作者数据和全部参数。未新跑V3、动基线、RTKLIB、LC01，也未作同层RAWX退化矩阵。旧provider退化不能借名迁移成新raw算法鲁棒性证明。

用户清空间中断的前BY2O EXT011250历元/955有效证据保留，整组终止而非SIGCONT后计时；54文件前后byte/hash相同。全九新identity从epoch0调用，只旧BY2O EXT01此前实际启动，其余八项本矩阵为首次实际调用。完整历史见 [V2修复记录](../V2_REPAIR_NOTES.md) 与 [进度历史](../PROGRESS.md)。
