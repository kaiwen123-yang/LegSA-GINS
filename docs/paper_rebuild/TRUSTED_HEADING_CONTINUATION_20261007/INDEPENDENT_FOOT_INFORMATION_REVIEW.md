# 足对信息诊断：独立数学、代码与执行边界审查

日期：2026-10-07。结论：修复下述发现后，所读被动诊断实现和三PAIR身份回放runner未见剩余阻断，可进入主代理的最终登记检查。此结论不是实测根因判定或导航收益。独立审查者未运行测试、编译、loader、native、evaluator、readout或原始/参考读取，只读代码/计划/已有局部测试回执。只新增本文件，未改他人算法、runner、计划或Git。

所核最终源码：foot_information_diagnostic.py SHA256 c04e7c90ab47468d64b4b25b8c185371c2ad89c349aab596cc485d97524940c1；foot_information_trial.py SHA256 6b2382bf2927506fed53aca503af7fdd6f8d0384b67e0218d890d81c90a43d73；attitude_clone.cpp SHA256 11568fb2d4bb69198c8aed15bd8a095f0bbe48fd4b5969eba2f95eb7bb1db47b。登记前仍须由主代理将实际计划、最终源码、局部资格和二进制绑定，不可用此静态审查代替运行回执。

## 1. 原Young更新是否被保持

对比旧实现，五个epsilon及顺序1/64、1/16、1/4、1、4、gain/B矩阵算术、score、64 machine-epsilon tie、顺序选择、最后均值修正均未改变。新增日志在原value/tie计算后记录当步旧best和是否入选；不以残差、参考或诊断结果重新选择。T/J诊断在原候选选择及可选均值修正之后计算，使用const prior，J不可解或非有限时只记不可用。未引入jitter或改R。

gi_engine_attitude_clone.cpp仅把同一attitudeJointState值保存为prior并可复制到日志；原safe-innovation门、NULL路径、setAttitudeJointState、stateFeedback、计数、退役顺序保留。开关为显式环境值0/1，默认关闭。新增数据包含完整24维P、mean、3x24 H、完整3x3 R、dz、21个固定W权、T/J、五步分数/比较分数/tie/action及最终epsilon；时间可关联既有唯一事件表。它足以对照旧网格选择并诊断当前工作模型，不证明SDK噪声或物理来源已校准。

## 2. 连续判据的成立范围

固定一次线性化的P、H、R、W，要求P半正定、R正定、W半正定，T=tr(WP)>0。对完整未知cross的同一Young/CI上界族，f(omega)=tr(W B_omega)为凸，f'(0+)=T-J，其中J=tr(W P H^T R^-1 H P)。因此连续族存在严格加权trace改善当且仅当J>T；J<=T不应靠加密epsilon网格期待改善。

这只是同一局部工作上界族的目标，不是实际yaw误差、全导航收益或普遍可观性定理。数值边界返回未定，T=0不计算比值。若P/R没有界住真实误差二阶矩，矩阵不等式不能替代物理资格。更新后reset的完整矩阵运输和实际误差也不由局部trace下降自动保证。

修订实现另给continuous_beats_original_skip_tie，区分数学上J>T的微小存在性与能超过原有限精度SKIP代价的候选。实际旧网格是否漏解必须同时看原native action、连续候选资格和超过tie的收益；不能只数J>T。

## 3. 独立发现及修复

初版按P原始混合单位的最大尺度阈值删小正特征值，但T/J来自全P、continuous_score来自截断谱。反例：P包含1和1e-16，W对应1和1e16，H=0、R=I；T=2、J=0，真omega=0目标应为2，截断后却可能为1，虚报收益1。原24测试未覆盖这一情况。

修订先按非零对角归一化分解P，保留所有正谱；numerical rank仅报告，不删除计分质量。omega=0直接返回全P的T，最终连续候选用全P Joseph-Young公式复算；T、J与目标分数分别按各自尺度核谱一致性，失败返回UNRESOLVED并将连续量记NA。该修复在代码上覆盖上述反例和单位变换问题。

另已修复：native T/J及五候选分数、当步比较分数、tie、顺序action和最终epsilon逐项核验；非有限J不进入JSON；不能认证的Gmax/零噪声不可能结论置NA，谱rank/m0/Gmax_numerical只作数值描述。不能拿数值秩当物理可观性，更不能从阈值截断推导降低R永远无效。

这些是浮点一致性资格而非严格区间数值证书。极病态或资格未决时应保留UNRESOLVED；不可为了得到根因分类再放宽阈值。

## 4. 已有测试证据的实际范围

已读FOOT_INFORMATION_LOCAL_PLAN、REPAIR_PLAN、两次scratch回执及日志。ATTEMPT01原16回归加8诊断共24/24通过并保留。独立发现后登记2个边界例并重跑8个受影响诊断：ATTEMPT02首轮9通过、1因numpy bool JSON序列化失败；原失败保留，仅修纯bool报告转换并单测重跑该1例通过。修复批为10个唯一案例、11次案例执行，不应将它写成首轮10/10或新的24全量回归。

新增边界为小正方差/高W权不产生假收益、坐标单位变换不改目标/连续解，并覆盖native action篡改拒绝。局部旧/新harness输出、诊断开关输出身份是合成资格；最终三完整窗NAV/STD的字节一致门仍须实际通过，不能由局部PASS替代。

## 5. 三PAIR只读输出回放runner边界

foot_information_trial.py固定三个旧PAIR_YOUNG身份，0 evaluator。新stage和--scratch-root均须对应旧封存aliases，不能换根/换目录绕过同登记预算。原配置完整字节复制，仅CLI指定新输出目录；已核port_demo/PortRuntime使用该CLI目录写科学输出，不把旧config中的outputpath当写目标。

每次native前持久化唯一预算预约；native目录已存在即拒绝重试。新NAV、STD及原ATTITUDE_CLONE_EVENTS须与旧封存hash完全相同，否则保留失败并停止、不得新增评价。旧event hash来自原ALL_NATIVE_SEALED.files，不能现场新算pin冒充旧封存证据。dump条数、五候选结构、严格时间次序及每行时间/应用action要逐项对应旧PAIR事件；新时间不能替换旧事件身份。

原始/参考读取继续由native access audit约束；只在三身份完成封存后解释新diagnostic dump。所有回放产物与诊断留新stage。此回放只是取回旧状态下未记录的P/H/R/W和候选分数，不是新方法效果实验，也不需要重读reference。

## 6. 回放后的判定政策

- 若大多数/全部合格事件J<T且远离数值边界，应将本次固定工作模型解释为连续同族也无增益；继续调epsilon没有依据。不能据此宣称真实足端没有信息。
- 若J>T且连续候选超过原SKIP tie，但旧网格SKIP，则得到网格漏解的证据；先保持诊断，不自动将连续增益写回状态或声称导航改善。
- 若谱/全P/原生回放不一致或数值边界未定，则该事件未定，保留分母与原因；不能把未定放进成功或必然SKIP。
- 真正更紧融合仍需可证明的来源结构或合格独立成分；不可因全SKIP缩小R、删除被动cross、假定SDK与IMU独立。下一采集优先补原始关节/FK、时序、body到IMU外参和接触/滑移证据。

本审查没有计算2510个真实事件的J/T或根因比例；所有实测结论等待已登记回放回执。原V3、原Young状态算法及历史无收益结论保持。
