# A2：保留航向时，哪些辅助更新真正发生

固定对象 `D62_20s_seed_00`：F03=`ADD_RUN_00399`、A04=`ADD_RUN_00402`、F04=`ADD_RUN_00400`。三者保持原66..340 s完整运行与初始化，anchor206.2，中断 `[196.2,216.2)`。实际边界与所测A1相同，但A2保留heading，基础HV文件也保留；不能把两种输入状态合称完全GNSS拒止。A2是BY2录制上的半合成对象，3方法不是3次独立自然实验。

6次真实native均退出0，15项新原版输出匹配历史recorded hash、15项观察版输出匹配新原版字节；科学manifest与访问检查通过。本组没有evaluator/provider/reference新调用，原已释放载荷未重新取得，新全采样NAV/STD及事件均保留。入口：[IDENTITY](IDENTITY.csv)、[OUTPUT_HASH_CHECKS](OUTPUT_HASH_CHECKS.csv)、[实际文件索引](EVIDENCE_LOCATIONS.csv)。

## 中断内的100个GNSS输入时机

每方法的yaw_valid及整体OR都为真100次，实际GNSS入口100次。以下按GNSS触发时刻统计，行键为 [SCHEDULING_COMPACT](SCHEDULING_COMPACT.csv) 的`run_id/window=during/source`：

|来源|A04/F04每方法创新前合格候选|每方法函数入口|每方法实际接受|未接受的实际原因|
|---|---:|---:|---:|---|
|position|0|0|0|原has_position=false，分源入口不调用|
|RV|0|0|0|原has_velocity=false，分源入口不调用|
|yaw|100|100|100|本窗无硬门拒绝|
|RD|0|100|0|有匹配行，但100次在PROVIDER_VALIDITY_LINEAGE_OR_SATELLITE_REJECT返回|
|HV|100|100|100|原准备支持、匹配与更新条件成立|
|RP|100|100|100|原匹配与质量条件成立|

本组没有N09“合格但被全失效GNSS入口挡住”的事件。RD的0不是没有函数入口，也不是创新拒绝；与A1整体入口关闭时RD未调用不同。F03在同窗也接受100次yaw，但RD/HV/RP分别100次以DISABLED_BY_CONFIG返回，无选中或接受，不算N09触发。数据行仍存在、配置开启、匹配、合格、函数入口和接受分别保留，不能互换。事件键、row_id与原原因词见 [输入/调度细节](INPUT_AND_SCHEDULING_NOTES.md)。

这支持“原A2此对象中HV与RP实际参与估计”，不支持“完整GNSS拒止”或“中断期间RD提供了改善”。F03与A04/F04有多模块差别，状态也已受此前更新影响；没有HV-off单因素闭环对照，不能定量归因所有位置差给HV。

## 全程接受与拒绝

|方法|position|RV|yaw|RD|HV|RP|
|---|---:|---:|---:|---:|---:|---:|
|F03|1269|1269|1348|0|0|0|
|A04|1269|1269|1348|970|1369|1369|
|F04|1269|1269|1348|1008|1369|1369|

六来源接受数均与原生manifest逐字段相等。三方法各21次yaw硬门拒绝，均不在所述中断窗。A04的1369次RD函数入口=970接受+100资格拒绝+38 SA-off残差门拒绝+261无匹配；F04=1008+100+0+261。此开关改变原权重路径和SA-off门，不能用跨方法同时间NIS作同状态反事实。1370个GNSS输入中最后t=340的一条没有已观察到的时间条件；实际调度1369，不把它算成创新拒绝。

## N12/N16：同一未改状态上的局部影子

F03/A04/F04分别3886/7594/7632个SA包装快照全部VALIDATED，无失败或不可复算。F03/A04关闭SA，不给其算术差异记实际SA权重影响。F04按原baseR、实际dof/normalize、原LSIM/OIM/cap进行独立核算：

|来源|全程快照|N12影子最终R不同|N16单独影子最终R不同|
|---|---:|---:|---:|
|position|1269|0|0|
|yaw|1348|98|0|
|RV|1269|356|0|
|RD|1008|418|0|
|HV|1369|0|1369|
|RP|1369|0|0|

N12合计872次最终影子R不同，接受决策变化0；RD另15次原始OIM变化被cap遮蔽。按provider测量时刻的during窗，yaw100次Hdx/NIS无变化；HV/RP分别101次NIS有差，OIM原始scale分别9/90次有差，均被LSIM遮蔽，N12最终R变化0。这个“局部被遮蔽”不意味着闭环修补无影响：中断前后状态路径也会影响后续，尚未运行修补版本。

N16的1369次HV均为实际二维更新，第三维999参与旧maxStd；只移除该禁用维的贡献、保留其他条件时最终影子R均不同，其中按provider时刻的during为101次。它证明原权重包含这个路径，未证明其损害精度。所有影子不反馈filter，没有修后RMSE；全精度派生值及矩阵索引见 [INNOVATION_COMPACT](INNOVATION_COMPACT.csv)、[KEY_EVENT_VALUES](KEY_EVENT_VALUES.csv) 与各run的KEY_SNAPSHOT_INDEX。

必须区分时轴：调度窗during HV/RP各100次；创新窗during各101次。A04 first-after入口约216.200000048 s接受的源行时刻为216.197080612183 s，属于provider时间窗的额外一条；HV与RP都如此。F04小表有相同分窗计数，不能因此假定跨方法完整状态相同。保留原半开边界和两种分母，arrival仍UNKNOWN。

原A2全窗均值或配对均值仍是原实现结果，不能改称中断末误差或新对照收益。本次只闭合指定seed/时长的历史输出与事件；如果下一阶段需要HV因果量，最小新增对照是固定该对象的独立HV-off版本，必须另行登记，不能由本轮两种影子替代。
