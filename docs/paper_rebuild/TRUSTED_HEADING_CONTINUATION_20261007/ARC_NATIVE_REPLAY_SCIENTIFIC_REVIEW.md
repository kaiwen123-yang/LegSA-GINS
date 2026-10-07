# 六次被动 ARC 回放：科学与动力学静态审查

审查基线为 HEAD 9428452a29b1265d1dcd0d245acf8b942239cdfb。范围为当前生产源码、已有局部/prepare/loader 回执、原提案和三份 prepared YAML；没有执行 native、测试、信息数学或读取 provider payload。本文不是六回放执行回执。新 runner/plan 的审定状态见末节。

## 1. 本轮能建立什么

可建立原921块在实际支持的端点上的、同一**已执行信息前缀**下的两端 ECEF 姿态联合工作 prior：START 确定性增广，原普通观测对24维状态联合更新，完整反馈/reset同时修正历史clone，END保存并取当前边缘退休。没有新增相位观测。两臂都完成相同矩阵计算，TELEMETRY开关仅控制最后矩阵序列化。

这可为后续条件信息诊断提供真实执行先验；不证明物理协方差标定、全源在线因果、phase-state独立、相位有效、绝对yaw可观或导航收益。新增ARC分段/联合gain/full reset可能改变旧PVT_CONTROL轨迹，比较对象须是新NULL/TELEMETRY配对臂，不是旧off-clone输出。

已有局部资格是首轮23/24通过、修复夹具后受影响2项通过；共24个独立用例取得通过证据，不是首轮全通过。prepare/parser建立921块/1842端点身份，仍不能预称921全部覆盖或860已有真实joint prior。证据见 ARC_NATIVE_LOCAL_RESULTS.md:3–11 和 ARC_NATIVE_PREPARE_LOADER_RESULTS.md:3–26。

## 2. 当前生产条件化与顺序

下述源码均相对于仓库根。

- cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp:651–779：精确double合并/排序；拆分剩余IMU dtheta/dvel/measured dt，保留增量。GNSS及原辅助先更新、完整反馈，再ARC；恰在IMU末端的ARC还等待原body-HV scheduler及反馈。纯ARC时刻只传播，不增加辅助更新。
- 同文件519–611：cross经Phi传播，活动clone用零clone-H但完整joint gain；full reset修正current/clone并运输全部P，禁止QA/QM裁剪。两块间无clone时full reset也开启，是两臂共同工作模型的一部分。
- gi_engine_arc_clone.cpp:114–180：source=replay=state精确相等、dx21/clone error全零。END保存经全部普通更新修正后的clone_C0_given_end，不是未修正START nominal；P6=B6 P24 B6转置。前3维是clone ECEF正左扰动，后3维是current ECEF正左扰动，J1包括position-frame connection，不能仅截PHI子块。
- gi_engine_attitude_clone.cpp:84–90：退休保留current marginal，不做Schur条件化。严格不重叠的source表支持单clone slot，但不证明块间误差独立。
- runtime/port_runtime.cpp:1477–1499,1530–1581,1609–1673：首对齐IMU只初始化；不处理超过endtime的下一IMU；finalize不传播、不增加NAV，之后才写日志。

初始/终端支持必须看实际执行，不从标称窗长推定；第一初始化时刻及之前不造历史pose。IMU旧量化与source保留double不相同，不构成硬件同步已标定。

## 3. 全921生命周期及计数合同

BY2 274、BY2H270、BY2O377，共921块/1842source行。原860两端模型齐全和61模型不齐都按同时间表执行；122空fingerprint不触发跳过。实际覆盖与原模型合法性须交叉列示。

|最终状态|必要状态语义|矩阵日志|
|---|---|---|
|COVERED_END_PRIOR|created=1，owner_at_creation=ARC，两state time非空且精确等源时刻，两个dispatch phase均POST_ALL_EXISTING_UPDATES_AT_TIMESTAMP|TELEMETRY恰一条对应prior|
|UNCOVERED_INITIAL_STATE|created=0、owner=NONE、START state空且NOT_DISPATCHED；END若后续有支持则实际dispatch，否则为空|无prior|
|UNCOVERED_TERMINAL|START已执行则created=1/ownerARC/START state精确，否则created=0/ownerNONE/START state空；END state空|无prior，活动clone只退休|

最终不留PENDING/ACTIVE。初始缺支持优先：即使END又越过终点，仍为INITIAL，不重复计TERMINAL。全在初始化前的两个端点只记初始通知，不增加dispatch ordinal。未来未执行端点不计consumed_event_rows。

成功收尾计数应满足source_rows=1842、source_blocks=921（逐序列原分母）；covered+initial+terminal=source_blocks；starts=created行数；ends=covered；retires=starts，含终端清理。TELEMETRY prior条数=covered，NULL无ARC_JOINT_PRIORS.jsonl。consumed_event_rows由实际dispatch及初始通知核对，可小于1842。不可预设covered=921或legal-covered=860。phase_updates=0、foot调用/尝试/更新=0，PVT_CONTROL下carrier尝试为0；既有PVT heading仍可参与。

ledger ordinal逐一增加，U/R只随实际ORDINARY_UPDATE/FULL_RESET递增。covered END的conditioning_ordinal是写ARC_END之前的ledger长度，因此其ARC_END ordinal=conditioning_ordinal+1；state bits/block/owner/U/R都要一致。information ID与run/schedule/U/R/L/time bits绑定，并由外部seal补齐config/binary/provider身份。初始化缺支持通知的状态时间不是被跳过历史source time，不应错误断言相等。源码见gi_engine_arc_clone.cpp:90–113,152–196。

## 4. 共有输出及真实NED速度先验

每序列两臂同config字节/binary/providers/source表/算术，外部仅CLI目录和序列化flag不同。至少核NAV、STD、IMUERR、ARC lifecycle/conditioning/IMU segments、heading/baseLine diagnostics及所有既有条件trace。先比较文件集合，再逐字节比较；manifest仅剔除事先登记的实际差异键，所有科学字段/健康/原观测与ARC计数相等。不能只比NAV或用容差替代字节门。

实际prepared配置保留旧NED水平弱先验，GNSS辅助流程调用GO2_VELOCITY_DIAGNOSTIC（gi_engine.cpp:488–500,1757–1758）。BODY_VELOCITY_EVENTS.csv仅在body_frd writer开启（1671–1683）；真实阶段应缺席，合成BODY_HORIZONTAL_VELOCITY=3不是真实计数预期，不为达到该计数改原科学配置。

重要新边界：真实NED HV在1694–1704按绝对时差择近，没有RD/RP的research future-source/consumed-source guard（1487–1488及1573–1574）。源码因此允许选取报告源时刻晚于当前更新的行，也不保证每行仅消费一次。未读provider，当前不能断言实际发生次数。

本轮不改生产；固定纯ledger汇总按source_tag报告未来报告源时刻和重复source/vector index次数，不以这些值删块、改调度或调噪声。HV/RD/RP provider identity为SOURCE_TIME_BITS:<16位binary64hex>:VECTOR_INDEX:<index>。可直接解码比state_time，不需重读provider。不完整identity报告UNKNOWN。即使计数全零，actual arrival仍NA。

P的准确称谓是**离线已执行前缀的继承工作prior**，不能称所有观测在当时物理可用的在线prior。普通更新仍继承原来源/过程工作假设，可能共享SDK/anchor/GNSS误差；state-state cross不提供phase-state cross，后者保持UNKNOWN。本轮范围未发现必须修改生产后才能记录空相位工作P的阻断。

## 5. 矩阵读出和基线前提

本轮只核shape/finite/源身份/时标/误差定义/dx24=0/条件前缀，不做PSD、B6重新乘算、conditioning或信息目标。生产current checkCov只检查有限和对角非负，不能冒充全END P24/P6独立PSD通过。任何jitter/删cross/投影修复均不允许。

下一轮数学读出至少需要六输出全部seal且配对门通过，以covered与原860合法交集为分子、921为完整分母；使用同END corrected clone/current nominal及P；绑定saved phase exact端点/geometry/单位/符号；明确工作条件集和P/phase矩模型/cross假设。未知C_en不能填零，端点不复用也不能默认块间独立。局部条件收益不证明绝对yaw可观、全周跳可检、真实载波中断恢复或导航改善。

三份prepared config继承baseline3d_body_vector_m=[0,-0.35,0]（BY2:181，BY2H/O:182）。IMU builder在FLU→FRD后应用固定roll−1°（src/legsa_gins/input_generation/imu_txt_builder.py:89–106）。这不能单靠SDK文档升级为硬件安装证明。

该向量可以在下一轮明确冻结为engine-frame工作基线假设，作条件于此假设的信息诊断，本次无需变更生产。若宣称其是硬件FRD向量，则须另证frame/旋转方向/安装来源；不能因看到roll−1°就再次旋转已经是engine-frame的向量。物理来源缺失不使本轮P日志无用，但阻止自动称可信航向或直接融合。时间映射pins证明计算定义衔接，不证明硬件同步。

## 6. 新入口最终静态结论

PASS_WITH_STATED_SCIENTIFIC_SCOPE：最终495行 scripts/paper_rebuild/carrier_phase/arc_native_replay.py（SHA-256 cc58f97cacc950ef8fae9f7eaf6d78aea7c0ff4759f16712c24a3fe04da5d472）和 ARC_NATIVE_REPLAY_PLAN.json 草案（SHA-256 0dba626c9e767e717013452023659e473a270bc4a1819f8c2dd11eacc4f9e8de）已静读复核；上述核心生产与helper共8项源码pin均同当前文件匹配。70项完整inventory/访问范围由根代理及独立执行审计另核，不把本科学复核写成全输入payload审计。

首版发现的covered非空state、INITIAL/TERMINAL状态边界、prior时标/误差定义、ledger累计U/R及END time/block/owner/prefix绑定已补齐。真实NED不再强制BODY输出。每对全文件集合+字节身份、manifest仅差telemetry flag、finite完整维度/零dx、六输出seal后一次字段汇总与未知cross/arrival边界均符合本轮目标。未来源与重复vector index固定报告，不以零计数作门、不筛块，不改原科学政策。

计划精确限定6个native、0retry，3窗×同算术两臂；原prepared配置不改，0相位/信息/evaluator调用，18个原provider/carrier输入只在登记运行中执行前后两次固定哈希。本科学review没有读取这些payload或执行新数字试验。草案本身仍DRAFT，不可直接运行；根代理晋状态/登记后方可执行。仅计划状态变化不改变本科学结论，任何功能/科学范围变化需重新审查。

plan的 inherited_real_baseline_body_vector_frd_m 标签须按其 installation_or_noise_physics_qualified=false 及本节5的工作假设边界解释，不能借该键名宣称物理FRD安装已验证。本轮不新增非阻断增强，也不改变生产。结论是允许进入受登记的被动工作prior获取；不是已获取真实prior、更不是相位准入或导航收益通过。
