# XBPG 2026-01-05 探索协议（首次算法运行/性能评价前冻结）

本轮是现有实现的输入适用性和运行探索，无优于任何算法或精度达标的验收条件。原始数据只读；不修改正式求解器、旧参数、旧输出；不进行文献复现、网格搜索、半合成故障、参考定符号/时差或几何调参。此文与输入质量表在新分支先提交并推送，之后才启动新数据科学 native；既有原生合成测试单列。

## 已知事实与方法资格

|段|GNSS目录时间后缀|唯一相交Go2|交集秒|完整G1 RAWX跨度秒|主方法状态|
|---|---|---|---:|---:|---|
|S1|12-25-13|xb1|395.635981044|405.2|F01物理身份未闭合；其余无双fixed输入|
|S2|12-33-29|xb2|358.658834995|376.2|同上|
|S3|12-40-53|xb3|346.430599892|351.399|同上|
|S4|12-49-30|xb4|356.0|356.0|同上|

完整16格交集和整数ns见 SEQUENCE_PAIRING.csv。唯一交集证明录制配对，不证明两个时钟零偏/零延迟。四段全部 NAV-PVT carrier state 无 fixed=2；v3 BOTH_FIXED 有效航向均为0。HPPOSECEF双位置差长度中位11–35m，不能作可信短基线。已有raw目录内几何登记绑定较早11点session+nmb1，不授权将其0.35m/杆臂迁移到这四段。Go2→APC安装与采集同步未独立确定。

主方法槽保留4×F01/F02/F03/A04/F04共20项。F01的IMU/GNSS物理时间与安装条件未闭合；其余同时缺v3双fixed观测。均记 NOT_RUN_INPUT_UNQUALIFIED，不通过全invalid航向或假定杆臂伪造完整算法。任何后续新物理证据触发独立补充协议，不在看结果后默改本协议。

正式身份：v3 标量航向，F03=A02=AB0000；F04=A01=AB1111；A04=AB1011。F01含RV而F02不含RV，不作单因素因果消融。冻存二进制96ae436d…实际源码ca73cb…；当前eb3cbed新编译cbf554ba…含B3候选，不能混作正式。METHOD_IDENTITY.csv记录完整SHA。

## 可执行独立子模块

1. `EXPLORATORY_RTKLIB_UNCONSTRAINED`：四段全部有效UBX帧按原顺序恢复，经既有convbin转换完整OBS/NAV，保留窗前可得星历；GNSS2为rover、GNSS1为base，现有原生rnx2rtkp做movingbase，输出GNSS2−GNSS1 ENU向量。使用HX02原config所有科学参数，唯一设备适配是 `pos2-baselen: 0.350→0.000` 禁用未确认的BY2长度约束；basesig原样但该项不再启用。固定GPS+BDS(navsys=33)、L1+L2、forward、15°截止、continuous AR、ratio3，不按结果改变星座/阈值，不下载新星历寻优。只输出基线方位与长度，不加90°称body yaw。
2. `EXPLORATORY_CURRENT_RAW_DOPPLER_HELPER`：从G1全窗OBS/NAV调用当前自有rtklib_doppler_helper_builder生成的C helper。其位置是内部伪距线性化辅助，输出速度来自Doppler estvel；不取NAV-PVT速度、不取商业reference作为输入。保留ECEF速度和原ECEF对角std标签，不使用已发现的旧Python代码将ECEF std直接改名NED的路径。helper未输出的历元列入缺失；其成功码不代表全历元速度可用。

RTKLIB source `180043ee24b6d2b168f98b64be15f69d50046b1a`，工作树tracked干净。rnx2rtkp SHA256 `3a0ad1c55435b45e1f83b2e713a0b0fb837a5f0a118d76ead3df1f9e3e531eda`；convbin `85b6b981374c7df957492d9423a3c650a35cb5e7253598651070adf4d9f1df2a`。helper在独立scratch编译，构建命令、实际修改和hash写RD_BUILD/PREPARATION。所有数值线程1。

## 顺序、支持和失败

完整原始消息审查 → 8次convbin及helper构建 → 协议提交/推送 → S1最初30s GPST技术smoke → 各段全OBS记录单次RTKLIB和单次RD → 固定输出hash → 统计可用性/作图。smoke不评分、不选最优窗；最大5次RTKLIB（1smoke+4full）和4次RD。技术路径/解析失败可以有保留记录的修复重试；数值失败不调参救回。

RAWX两接收机原始时标相差7–8ms，保留原标签交给RTKLIB标准异步观测处理；不人为强制同历元，不把严格零容差配对失败当无数据。RTK输出对G2输入时标匹配容差0.02s，仅用于报告对应输入epoch（不是改输入时刻）；RD对G1同样0.02s。G2和G1各自完整RAWX历元为分母。Q1/Q2/其他状态、无输出历元、首末跨度、连续段与最大缺口分别报告；统计历元重用禁止。断线阈值为本源中位正dt的3倍，无跨缺口连接。

无足够独立证据将商业reference的姿态/POI对应到机载天线基线或Go2 IMU，因此本协议不报告绝对位置/姿态精度RMSE、不做NEES、不计算F04相对其他方法百分比（20个主槽均NA）。本轮可报告真实原生输出可用性、向量长度/方位与ECEF速度；商业/Excel均不叫independent ground truth。任何输出对raw HPPOSECEF/PVT的后续差分只可称同源一致性、post-hoc，不进入绝对精度表。

每调用保存argv、退出码、线程、wall time（含strace）、输入/输出hash和文件访问；合成、真实和blocked分开。总耗时不冒充最坏时延或硬实时证明。完整轨迹/日志留 `<AUDIT_ROOT>/gnss_exploration`，小汇总进RUNS/METRICS，图PNG+SVG/PDF来自真实输入与实际输出。

复现：`python3 scripts/paper_rebuild/audit_xbpg/run_gnss.py --local configs/paper_rebuild/DATA_PATHS.AUDIT_XBPG.local.yaml --phase prepare`，提交本协议后同命令 `--phase run`。已存在的运行目录拒绝覆盖。
