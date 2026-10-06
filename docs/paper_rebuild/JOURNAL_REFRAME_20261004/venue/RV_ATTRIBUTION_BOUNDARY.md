# RV 归因：原 F02/F03 不是单开关对照

日期：2026-10-04。本更正只限制文稿归因，不改变任何数据、指标、原 V3 选择或运行。

原 F02→F03 同时改变接收机速度 RV 与航向处理支路：F02 使用 basic dual-yaw 固定标准差支路；F03 使用 strong dual-yaw/Scheme-C 标准差与残差门限。因此，即使两者共享安装、序列和初始 heading，也不能把两者成绩差识别为 RV 的独立效果。可称“RV 与航向处理共同变化的结构对照”，不可称 pure-RV 或“只开接收机速度”。

本研究线此前 GPS/TIM 文档没有直接的 pure-RV 正面声明，但“单模块诊断”概括过宽，现限定为已闭合的 RD/HV 条件对照。RD 单开关只删除独立 Doppler-derived aid，RV 仍保留；HV 收益只在 heading 与实际调度准入成立的域内解释。D61 没有故障内 accepted HV，D62 有条件 HV/RP；两类 fault 内 RD accepted=0，均不能称故障内新 RD 桥接。

## 本小块实际读取证据

两份原封存 RUN_MANIFEST 的字段独立读取范围均为70–80、320–355行（368行总长），只读元数据，未读取轨迹/reference/raw，也未运行 native/evaluator。

|原始封存文件|主要字段|SHA256|
|---|---|---|
|[RUN_00002 manifest](/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN8_PROTOCOL_V3/03_NATIVE/RUN_00002/RUN_MANIFEST.json:72)|algorithm basic；basic=true；Scheme-C=false；RVcount=0；yaw NORMAL/DOWNWEIGHT/REJECT=1369/0/0|65397db8aebc5d1c2f0bd35dabea75a7a979ec1e6ba482cbc34ef3b521541244|
|[RUN_00003 manifest](/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN8_PROTOCOL_V3/03_NATIVE/RUN_00003/RUN_MANIFEST.json:72)|algorithm strong；basic=false；Scheme-C=true；RVcount=1369；yaw NORMAL/DOWNWEIGHT/REJECT=1285/63/21|1a1e7a098cb9d8dbb513e7433dc68dd4b833d8fb58a83536b22f53400eccceef|

原 ca73 C++ 分支位置由本轮 FGO 独立审查提供：port_config_loader.cpp420–421、gi_engine.cpp367–373/basic 与931–946/Scheme-C。本小块没有重新逐行阅读这些旧源码，不能把 peer 来源记作本小块新源码覆盖。两份 manifest 的直接字段已经证明“只改 RV”不成立；无需为更正文字运行新实验。

修订后的 GPS/TIM 说明仍按各自模型、量与准入域讨论信息作用。若未来要识别 RV 独立效果，应另有实际匹配控制（航向处理、物理点、初始化、噪声等固定）的研究合同；本轮没有创建该实验，也不要求重跑旧全矩阵。先前 Block03 收据保持更正前身份，当前文件身份由 [RV 更正收据](RV_ATTRIBUTION_CORRECTION_READY_RECEIPT.json) 绑定。
