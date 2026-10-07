# 足端 unrestricted-cross 反例：真实封存读出独立复核

结论：登记的2510个事件全部支持具有严格数值裕量的工作模型反例 V=R−HPHᵀ≻0。若真实允许集合仅规定这些有效边缘二阶矩、并允许全部joint-PSD state/noise cross，则存在C*=−PHᵀ使创新与状态误差不相关；K=0为固定线性校正的PSD加权trace minimax解。因此这里的全部SKIP不只受限于原Young族或epsilon网格。此结论没有识别真实SDK cross，也没有认证实际边缘误差界。

## 1. 只读范围与身份链

注册：f9ec34d75401a05f5466fdd4a8b92377f5fd770e。唯一stage：<SCRATCH_ROOT>/TRUSTED_HEADING_CONTINUATION_20261007/FOOT_UNKNOWN_CROSS_ATTEMPT01。外层EXIT returncode=0、elapsed=1.16610684秒；SUMMARY内部计时0.750749724秒，口径分列。

独立审查仅使用Python标准库读取小元数据、全部2510条EVENT_WITNESSES、旧qualification字段及完整保存openat/execve文本；未import科学模块、未重跑矩阵/特征值/诊断/native/eval。没有读取旧原生P/H/R dump内容或原始/参考数据，也未重复hash那些大dump。

登记计划与两份源/测试实际字节等于注册commit，source hash匹配plan pin。原ALL_NATIVE_SEALED和READOUT_COMPLETE实际小文件hash匹配登记pin。每窗dump pin同时等于旧native seal.files条目及旧READOUT_COMPLETE source pin；每份旧qualification实际hash同时等于本轮计划与cd81069已提交foot_information/READOUT_RECEIPT的旧pin。

EVENT_WITNESSES实际hash a068c61371dafa798ef18c7f0e5ccd33ca1aabdb3933a2ff42b847322d1c59d9 与SUMMARY相同；SUMMARY实际hash 4c1553b6e6703c0716fb552431c236d488d302f2f6edbcfa658c3b269fef6650 与COMPLETE相同。没有发现新的身份断链。

## 2. 全分母及数值裕量

|序列|事件数|状态|最小直接lambda(V)|最小归一化lambda(V)|最小裕量/容差|
|---|---:|---|---:|---:|---:|
|BY2|687|全部STRICT_WORKING_MARGIN|0.0015999980949976383|0.9999988093735239|1.172811006579568e13|
|BY2H|666|全部STRICT_WORKING_MARGIN|0.001599997881526631|0.9999986759541432|1.1728108501036633e13|
|BY2O|1157|全部STRICT_WORKING_MARGIN|0.0015999980096772053|0.9999987560482534|1.1728109440390295e13|

已从保存字段独立核对三个计数及极值，与SUMMARY完全一致；2510个(sequence,time)键唯一，各窗严格时间递增，与旧qualification逐行时间及全分母一致。所有旧spectral/full-model资格true；本轮所有witness_supported/centered_model true，minimax_trace_working_class=T。T与旧诊断T的最大差1.7763568394002505e-15，符合不同求和次序的浮点量级。全部输出数值有限，反例innovation-state cross记录为0。

原P仍是roundoff-tolerant工作PSD资格：2476/2510条记录的归一化最小P特征值略负，负值最大为原容差的0.000424921。这不是物理非PSD证据，也不能被改写成精确实数/区间PSD证明；本命题的P有效PSD前提仍显式条件化。V的正裕量远离其边界，三值分类没有靠容差勉强通过。skip_uniqueness_established、actual_cross_identified、physical_marginals_qualified均false，没有误称真实cross或唯一最优。

## 3. 独立访问核验

完整解析兄弟FOOT_UNKNOWN_CROSS_ATTEMPT01_OPENAT.strace：461条openat、0未解析；成功exec为1次/usr/bin/python3和3次/usr/bin/git，没有native/evaluator/test程序。trace实际hash为6e879c922a1d37ef700a9ffc20bb1e20d106acc29da82201b4d834794f0d72fb。

科学输入只包含原FOOT_INFORMATION_TRIAL_ATTEMPT01的8个唯一文件：原native seal、原readout完成回执，以及三个dump/三个qualification。各dump/table实际各有2次成功打开（hash与解析），native seal也2次；因此3 source_dumps/3 tables是唯一身份计数，不是声称只发生6次open。新stage仅生成EVENT_WITNESSES、SUMMARY、COMPLETE及其hash读取。

所有科学路径均为明确允许输入文件或新stage内输出；无其它科学输入、raw observation/nav/reference打开记录，无科学越界写。仓库侧读取只见登记计划、源码/测试及Git对象元数据。结论限于所跟踪openat/execve，不夸大为全部系统调用的形式证明。

## 4. 可引用结论与限制

本次证据将负结果从“当前Young族无法改善”推进到“在允许全部合法未知cross的固定工作不确定集合下，不能保证任意固定线性校正严格改善PSD加权trace”。它不说明每个实际cross都无益；C=0或有来源支持的部分cross结构可能属于更小、更有信息的假设类。V不满足条件也不反证保证改善，本轮恰无此类别。

停止epsilon细调有依据；下一步应验证能够排除该反例的真实误差来源结构/独立成分，而非缩小R制造接受。结论不涉及实际yaw误差、真实足端物理可观性、非线性残差选择策略、绝对heading连续保证或导航效果。没有新增状态更新、native或评价调用。
