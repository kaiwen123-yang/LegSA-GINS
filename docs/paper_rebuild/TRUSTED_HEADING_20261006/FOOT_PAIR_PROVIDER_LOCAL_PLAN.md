# 足事件 provider：有限本地检查计划

本次只运行6个唯一纯合成检查，不读取原始body/参考/导航结果，不运行native、AR或evaluator。所有合成文件由tests写入临时目录。一次完整pytest，失败保留；如需修正，仅另记并运行受影响项，不重跑已通过项。

固定科学规则不变：0.2s机会、首actual source、0.1s目标/0.15s最大区间、0.05s源间隔与机会迟到界、canonical足序、既有force滞回/dwell、每点0.01m非校准工作marginal界。四点任意相关上界压为Sigma6=8*sigma²*I6，不能写成实际误差独立。

执行前审查修正：完整stamp块必须唯一。原STAMP.search配合H5最后赋值，可能允许相同stamp重复；此为schema防错，未读取真实记录确认发生率。异常完整保留，失效后原support token不复活。

## 六项检查

1. 固定机会使用首actual source时间；当前START只依赖当时support，不因之后成功/失败更换起点或足对。
2. 每个clone最多一次END，固定0.1s区间下endpoint不重复；重复/逆序source拒绝。
3. 没有后来消息也可在既定gap/deadline退休；window_end cleanup仅结构事件，不可引导native向无IMU支持处传播。
4. 合成完整消息prefix建立真实support；FLU→FRD仅翻y/z，禁止字段不解码；50列schema、START无Sigma、END完整上界与旋转无关传播。
5. 无timestamp、非单调、重复相同stamp均留fault并断episode；恢复后新token与旧token不同。
6. 所有固定机会保留：过迟、坏source、支撑不足与无后续source不消失；error_code故障拒绝而不补零。

native末端口径已与实现者协调：晚于最后IMU的RETIRE只记UNCONSUMED_TERMINAL_CLEANUP并在laststate边缘删除；剩余START/END记UNCONSUMED_OUTSIDE_IMU_SUPPORT，不回填或增加NAV。此处单元只检查provider事件时间，不冒称native已验证。

产物：tests/paper_rebuild/test_foot_pair_provider.py；scratch/FOOT_PAIR_PROVIDER_LOCAL_ATTEMPT01的调用、日志、receipt与源码SHA。结果不是接触真值、无滑移证明、SDK独立性或导航改进证据。
