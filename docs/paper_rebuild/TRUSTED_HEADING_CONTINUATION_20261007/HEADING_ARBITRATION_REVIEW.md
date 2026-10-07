# 航向入口与量测域仲裁：工程审查

日期：2026-10-07；检查时 HEAD 8cd93b2c3e7f9ff0cecbeac5c25cbe4d5234dab3。本记录只读源码和已封存小表；没有读取新 reference/error series、按误差挑窗、运行算法或测试。只新增本文件，不改变 V3/main。

## 结论

上轮主要检验“PVT 航向标志无效时载波补缺”，没有检验“标志有效但方向可疑时怎样辨别”。它未覆盖主要尾部不意味着已找到尾部原因，也不证明原始载波无用。

优先做已有数学实现的结构消融：原 PVT-control 的输入、HV和参数全部固定，只把 Euler yaw 预测改为实际侧向基线水平投影。该收益属于观测模型，不能归因 AR。之后再检验只依赖已到达量测的方向域仲裁；不人为关闭良好商业航向来制造弱对照。

## 1. 原V3量测与状态不能混称

|层级|事实|边界|
|---|---|---|
|正式GNSS18 scalar|exact-iTOW两端HPPOSECEF，GNSS2−GNSS1，BOTH_FIXED，名义5Hz，std标记2.933193°|不是GNSS2单机course，不是本算法的原始载波AR；FIX不证明方向无偏|
|yaw_valid|上游资格结果；native接收独立P/V/yaw三标志|native不持有原双端状态、整数弧或有效原因|
|scalar物理量|左侧向基线水平投影方位+90°|倾斜时一般非ZYX Euler yaw|
|冻结HV|SDK速度经旧status-A1整窗插值航向与SDK RP旋到NED|未独立于GNSS，不因scalar换成HPPOSECEF而更新来源|

身份以 [V3_BASELINE_LOCK](../AR_V3_RESEARCH_20261006/V3_BASELINE_LOCK.json) 为准。
[T5a provider](../../../src/legsa_gins/paper_rebuild/hext/t5a_provider.py):45–106明确双方相同iTOW，使旧builder走精确分支，不能把旧status builder的一般插值错指为正式V3 scalar也在插值；240–254明确双方carrier状态2门。

[旧HV](../../../src/legsa_gins/paper_rebuild/clean6_sensor_v21/providers.py):142–195确实使用整窗np.interp(A1 yaw)、FLU→FRD、SDK RP和旧K_HV；[旧V3解释器](../../../scripts/paper_rebuild/interpret_v3_core.py):194明确只替换yaw/yaw_valid而保留HV。故仅抑制scalar入口不能声称隔离了可疑航向、实现整链因果或解决同源相关性。

## 2. PVT优先策略的作用范围

[HeadingSourcePolicy](../../../cpp/legsa_v23_port_core/include/legsa_v23_port_core/heading_source_policy.hpp):24–47先保存到达PVT原yaw_valid，再决定来源。有有效PVT时carrier被阻断，即使随后scalar被15°门或source-aware拒绝也不会触发fallback。仅已知、年龄≤0.21s的PVT无效状态允许carrier尝试；unknown/stale不等于invalid。0.01s互斥只由实际EKF接纳占用；这是工程去重，不是接收机周期或统计独立性证明。原P/V正常处理，被抑制carrier不切分IMU或触发额外辅助模块。

[GIEngine](../../../cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp):1215–1256的状态创新门与raw-source validity是两层。不能用已融合状态的创新挑N，再把挑出的carrier当独立观测回灌。

|完整窗|前端条件点/全部paired epochs|scalar尝试/接纳|carrier尝试/接纳|
|---|---:|---:|---:|
|BY2|168/1370|1369/1348|0/0|
|BY2H|319/1350|1349/1334|0/0|
|BY2O|166/1885|1593/1588|12/8|

来源：[前端结果](../TRUSTED_HEADING_20261006/full_window_frontend/RESULTS.md)、[六臂导航](../TRUSTED_HEADING_20261006/full_window_navigation/RESULTS.md)、[clone六臂](../TRUSTED_HEADING_20261006/clone_window_navigation/RESULTS.md)。653/4605点不是653次融合或整数正确数。BY2/H两臂NAV/STD字节相同；O相对control yaw RMSE 2.432887650→2.424148690°（降低0.3592%），P99不变。封存归因已指出12次补位不覆盖最高误差尾部；本次不重读误差，也不据此挑新时刻或断言尾部由哪个源造成。

最长无条件点为68.6/46.6/104s；单改优先级不能凭空填满。owner/pending质量拒绝、多类、失弧统计不是4605个互斥类别。PAIR2510次全SKIP只否证该固定更新方案的增量，不能证明所有足对/相对运动信息无效。

## 3. 先完成物理量模型消融

C为body-FRD→NED，r=(0,−1,0)，b=Cr，s=bN²+bE²：

- h(C)=wrap(atan2(bE,bN)+π/2)。
- 按本项目正左姿态反馈、predicted−observed，Hphi=[bN*bD/s,bE*bD/s,−1]。
- s趋零时方向不定义，应不可用，不能仅增大R假装正常。
- 标准ZYX下h=ψ−atan2(sinθ*sinφ,cosφ)，不是任意倾角的ψ。

当前gi_engine.cpp:1187–1211已有实现。该模型使roll/pitch正确进入方向预测，也可能改变H/V相关更新，不能预言必有收益。

已存在：[native FD测试](../../../tests/paper_rebuild/test_native_v3_innovation_contract.py)覆盖倾斜、多轴左扰动、wrap、竖直退化、legacy；[fallback测试](../../../tests/paper_rebuild/test_pvt_carrier_fallback.py)覆盖显式Euler/lateral与旧公式。本次未重跑。[IMU_CLAIM135](../v3/IMU_CLAIM_SUBSET_20261004/README.md)等实跑含projection，但共同IMU8/数值修复/调度或HV也不同，不能复用作当前三全窗唯一改变h/H的因果对照。已查材料未找到完全同条件的这组实验。

最小路线为复用原PVT_CONTROL已封存、支持显式选项的7f8a…二进制，仅新增三条projection；旧三Euler输出/评价复用。若改f290…则off尚无旧binary全窗parity，严格应另三Euler匹配，不能只因默认off就说结果相同。Root已选择前者。保持HV不变是合法单因素诊断，不能因此称新链已因果化或HV独立。

## 4. 只依赖到达量测的仲裁接口

独立前端返回不可变HeadingArbitrationReceipt；不改接收机FIX状态、不伪造PVT精度：

- 两源物理receiver IDs、week/iTOW/采样键、source/available/decision time与原消息身份；decision不得早于任何被用输入。
- 统一GNSS2−GNSS1、FRD左侧轴及ECEF/NED水平基准；比较同一基线投影量。不用EKF后验RP/yaw把不同量临时变成相同航向。
- PVT方向、长度、资格原因及报告噪声语义；2.933193°是工作噪声，非已校准覆盖区间。
- carrier全部圆周组件、source/候选全集/物理SD弧身份、完整性范围、当前raw支持/成本、质量与故障资格；空域不等于全圆。
- 输出PVT_KEEP、CARRIER_CONDITIONAL_REPLACE、CONFLICT_UNRESOLVED或NO_COMPARABLE_DOMAIN，附单一owner和动作原因。
- 两源不同物理历元时，只能用已登记的过去相对运动及外包误差运输，或报不可比较；0.01s近邻不证明同步。不把旧点改名为当前点，不把决策时刻回填到选N时刻。

现有15列carrier CSV只有点向量、3×3协方差、time/available/valid，不能容纳集合和共享来源，需独立receipt/sidecar。合法单点最终可复用现有native入口；多峰/宽域不能取中点并假造小Gaussian R。

可证伪的条件策略：相容时保留PVT；carrier缺失/宽域/质量不足时不据此降级PVT；独立于PVT/EKF构成的完整carrier条件域明确冲突，且carrier单点自身已有资格时，研究臂才条件替换。此标签不能升级为“证明PVT错”。若要求未知故障来源时不选胜者，则冲突必须UNRESOLVED；这一保守策略与强制替换必须分开定义。

## 5. 完整性与相关性没有被仲裁解决

当前envelope只在原selection selected6观测域内numerical complete；lifecycle投影原source持续SD弧，不是在当前全部观测上重新获得global候选集。旧条件域排除PVT只说明工作假设冲突，初始漏真类/模型失配也可产生冲突。投影top2不能继承新子集global second；新弧不继承旧整数。

[set_provider](../../../src/legsa_gins/paper_rebuild/carrier_phase/set_provider.py):177–185只允许一个cost-compatible class、质量合格且单连通非全圆域。合法多类但方向集中的信息尚未使用；其利用需新的集合/有界量测接口，不应把宽度冒充Gaussian精度。

商业HP/PVT与raw carrier共享接收机观测。相容不是独立验证；互斥只避免近时两份heading重复注入，不消除它与P/V、历史状态、重叠窗的相关性。fixed-N Cb+angular floor不含错误整数/选择风险。R膨胀不能声称修复未知cross。

SDK速度/足位置也未获纯encoder-FK、IMU统计独立或完整物理标定；相对足/gyro能提供相对运动，不能单独定绝对yaw。先用于carrier selection再后端更新时必须保留共享信息关系。原PVT恒优先改成数据域仲裁本身不保证新增信息，更不能凭组合就声称新AR原理。

## 6. 可证伪假设与统一消融

主假设：完整V3原窗内，当前测量方向域能在不读reference/后验状态、不人为关掉良好PVT时，识别足够的信息冲突，并产生超出匹配控制的稳定导航收益。数据也可能没有足够冲突，或条件域误排良好PVT。

先做第3节模型单因素，之后新前端各臂共同同一h/H、backend、可用时刻、因果HV合同与参数：

|臂|归因|
|---|---|
|原V3复用|正式完整性能参照，不能替换成削弱版|
|匹配PVT-priority|共同模型/时序/输入变化的控制|
|方向域仲裁|source策略增量|
|登记本体相对运动模块|本体增量；旧全SKIP不能当新方法成功|
|两者联合|交互及完整方法，不只报最佳联合|

这是结构建议而非此刻全部运行授权。原全窗BY2[66,340]、H[413,683]、O[3186,3563]、初始化/物理评价点/冻结evaluator均保留。全4605配对及全部PVT行都入ledger，按观测元数据列valid/unknown、可比较/宽/冲突/一致、选择/拒绝，不按误差分层挑窗。新作用臂无测量增量时不为凑矩阵运行导航。

必须保留的否证与门：

1. 已知整数/方向的独立物理合成包含好PVT、坏PVT、坏carrier、共同坏、宽/多峰、竖直退化、换弧；机制成立不等于false-fix风险率。
2. 三原完整窗全支持及实际共同键；H/V/yaw九指标、覆盖、延迟、缺测/右删失；相对matched control净增益单列，不把模型/调度收益归因AR。
3. 同RAWX故障/可用时刻下的carrier恢复，不把只损坏raw却保留商业PVT当同层V3导航故障；现B仍NA。
4. 机制与完整导航收益过门后才按冻结方法做独立数据/跨日资格；共享开发窗重复不能填泛化证据。

继续遵守[导航评价合同](../TRUSTED_HEADING_20261006/NAVIGATION_EVALUATION_CONTRACT.md)；不移动原非退化/5%门。共享商业reference只是agreement，不能证明独立真实精度、完整性或三项均已成立。新一轮目标继续，旧负面结论只关闭原固定支线，不限制有新数学理由的新方法。
