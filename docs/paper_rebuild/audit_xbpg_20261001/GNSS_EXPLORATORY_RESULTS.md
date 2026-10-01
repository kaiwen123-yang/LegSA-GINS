# 四段实际全窗运行：无解、部分支撑与数据潜力

本轮实际调用了既有 rnx2rtkp **5次（1次技术smoke、4次全窗）**、当前源码生成的 native RD helper **4次全窗**、convbin **8次**。所有原始命令、stderr、退出码、输入/输出hash、strace保存在 `<AUDIT_ROOT>/gnss_exploration/`。没有实际运行不满足物理输入条件的20个LegSA主方法槽；它们全部保留在 RUNS.csv/METRICS.csv。没有调用参考性能评价器。不是20个方法都成功，也不是只做10秒smoke。

冻结探索协议提交 `2271d5a38a49aa957bbc3539244ec18ad7fa55ff` 于09:24:58 UTC，首次新数据native smoke在09:25:19 UTC开始；push/远程核验在先。以下可用性/图属于对首轮输出的 post-hoc descriptive analysis，不新增或调节算法参数。RTK全窗结果和RD无解原样保留。

## 全分母结果

|段/配对|G1/G2 RAWX历元|G1时长/s|RTK退出码|RTK输出/覆盖|Q1/Q2|输出跨度/s|RD退出码/有效输出|
|---|---:|---:|---:|---:|---:|---:|---|
|S1 / xb1|2027 / 2027|405.200|0|0 / 0%|0 / 0|0|6 / 0：NO_USABLE_DOPPLER_SOLUTION|
|S2 / xb2|1882 / 1882|376.200|0|7 / 0.3719447%|3 / 4|1.2|4 / 0：INPUT_NAV_READ_FAILED|
|S3 / xb3|1758 / 1758|351.399|0|0 / 0%|0 / 0|0|6 / 0：NO_USABLE_DOPPLER_SOLUTION|
|S4 / xb4|1781 / 1781|356.000|0|0 / 0%|0 / 0|0|6 / 0：NO_USABLE_DOPPLER_SOLUTION|

S3 G2分母时间跨度351.400s，与G1相差1ms，表中不强行改为同一时轴。RTK输出严格按G2测量时标±0.02s唯一匹配；7条均有限、递增且没有重复消费。完整RTK文件缺解历元分别2027/1875/1758/1781。S2输出GPST tow=132001.2–132002.4；最大相邻dt=.2s。其基线长度15.289586–16.919228m，中位16.305757m；Q1仅表示软件的整数解状态，不能证明它对应合理机载短基线，更不能加90°当body yaw。

所有绝对位置/速度/姿态RMSE、P95、最大误差、F04相对F03/A04/F02差与百分比均为 **NA**：没有合格LegSA输出，GNSS2−GNSS1向量与商业POI并非同一物理量，且Go2/天线/POI几何与时钟链未闭合。方法间有限配对分母为0；不是0误差或0%改善。图不绘制不存在的误差/算法连续轨迹，不用商业内部输出替换被测估计器。

## 技术smoke、输出检查和异常回执

S1最初30秒smoke退出0、文件只有合法RTK表头。其意义是输入/程序技术路径完成而**无科学解**，没有据此挑好窗口；随后照冻结方案跑全部完整记录。原始COMMAND.json早期用`COMPLETED`标进程退出0、用`TECHNICAL_FAILURE`统称非零，这不够表达科学状态。本轮追加OUTPUT_VALIDATION.json绑定原receipt SHA及输出hash，原COMMAND和解输出没有修改。

校验完整RTK 15列（week与tow分开，Q索引5）、严格数字/有限性/非负std、week/tow有效域、输出时间唯一递增；header-only记NO_SOLUTION。RD分别识别空表的返回6、NAV失败返回4、一般进程失败、缺输出/坏列/非有限/状态和源时间不一致。未来技术smoke若launch、timeout或输出损坏，只阻断受影响RTK路径，独立RD仍可执行；有效无解smoke允许全窗运行。进程组超时清理、OSError、缺strace都写终止回执，不让异常停留STARTED。新增14项测试通过，含真实独立子进程timeout；这些软件测试是synthetic，未混入本表。

本轮为检查/补回执调用新的`--phase validate-retained`，科学native重跑=0。汇总再次检查原receipt、输出和validation绑定；不匹配即停止该汇总，不能继续画旧hash对应的新文件。无需重跑解算证明退出码0不等于有解。

## 为什么不能据这些结果判定原始数据完全无潜力

RTK用已核实既有GPS+BDS/L1+L2参数，仅按未确认安装长度禁用旧BY2的0.35m基线约束，未更改噪声/截止角/ratio。源码 `RTKLIB/src/rtkpos.c:971` 在baseline≤0跳过长度约束；1519处连带取消该约束的额外2次迭代，这是选项本身行为，不隐瞒成“其它执行完全相同”。1813–1827 moving-base以SPP及估计速度×age传播base，TTOL_MOVEB约1.05s；保留7–8ms原始时间差不代表硬件已同步，pos2-maxage=30也不是该模式的这道门槛。

当前RD helper虽然设`opt.navsys=SYS_ALL`，实际构建没有`-DENAGLO/-DENAGAL/-DENAQZS/-DENACMP`，编译能力为GPS/SBAS，不能描述为多星座完整RD。它调用pntpos→estvel→resdop，来自L1 raw Doppler，依赖伪距SPP及有效卫星筛选/卫星状态；速度全零也不输出。没有把PVT速度当raw Doppler。

|段|G1完整转换NAV记录（按星座）|RD stderr证据|
|---|---|---|
|S1|G6/R6/C4/J3|`rows=0 obs=16420 nav_eph=6`|
|S2|R5/C4/J1，没有GPS|`read nav failed`；现有helper不识别这些已编译关闭的星座|
|S3|G2/R4/S1|`rows=0 obs=13109 nav_eph=2`|
|S4|G2/J2/R4/C1|`rows=0 obs=11182 nav_eph=2`|

上表NAV是广播记录数，不是唯一可见卫星数或全时窗有效覆盖数。obs是helper读取的观测项数，不是RAWX独立历元数。S2无可识别导航与编译能力的对应已明确；其余三段的无解并未逐内部残差/卫星健康原因分类，不能伪造“所有失败都是输入坏了”的结论。补齐通用多星座编译能力可作为独立软件修复候选，须另列版本和协议；本轮没有看到结果后换星座反复试到成功，也未追加下载星历。

四段RAWX/SFRBX完整流和高层运动记录仍有价值：可以研究真实严重GNSS退化、采集时间语义、已知安装下的位置+IMU融合和可用性。当前配置未得到可用连续RTK/RD轨迹，不能支持完整F04、稳定高精度或优于基线主张；也不能证明修正软件能力/补齐采集证据后永远不能用。

## F01独立阻塞证据

**F01不需要双fixed。** 不运行F01的原因有且仅有尚未确认的传播IMU到GNSS观测点安装与采集时钟关系，以及由此派生的初始化/测量转换不可证实：

1. 四段tf_static只有ENU→VISION、BODY→CAM、ECEF→ENU；userio中四段POI→VRTK单位变换、VRTK→CAM已完整扫描，但没有Go2 body/IMU→GNSS1 APC边。文件中的BODY是设备内部帧，不能直接指定为机器人机体。BY2−1°安装/杆臂与另一个11点session的0.35m配置都不绑定这四次录制。
2. Go2有整数sec/ns且与对应GNSS窗口交叠，证明配对。终端没有逐消息到达时间，未定位采样/发布stamp生产代码、PPS/chrony硬件同步记录或固定时差标定；不能从重叠或相关性假设零时差。GNSSRAWX测量/到达的完整统计不能证明Go2时钟映射。
3. 商业设备的imu-data没有Go2 IMU身份，不换作正式F01输入；商业POI姿态不能给被测估计器参考初始化。高层Go2世界yaw与GNSS NED的安装/初始heading也没有独立基准。

这些证据缺口逐段都存在；没有把“GNSS不fixed”或“效果不好”替代为F01阻塞理由。后续取得本次mount/采集链记录后，可先冻结不含航向模块的F01迁移协议并执行，仍须保留GNSS自然退化而不挑窗。

## 图、计算开销与复现

每段一张六面板：共同WGS84原点的原始GNSS APC与商业POI位置（明确不同物理点，无拟合）；原始双位置差长度；实际RTK点/无解及全窗分母；两接收机carrier与RTK Q；实际Go2 dt；测量与到达时差。S2嵌图显示全部7点，仍保留全窗轴。相邻间隔>本源正dt中位数3倍断线，Go2 dt用原点散点；不平滑、不删除异常跳变。SVG留存储盘，合理大小PNG可随审查报告共享，索引给hash。没有画假精度图，参考不可评价明确标NA。

4次RTK全窗含strace耗时分别2.626/2.528/2.526/2.832秒；RD .974/.823/.973/.821秒（无解/失败），8次转换约4.7–5.9秒/次。单数值线程、rnx2rtkp既有二进制和RD新gcc -O2构建身份见METHOD_IDENTITY/EXPLORATORY_IDENTITY。耗时含审计、磁盘I/O和读取全窗；不是算法最坏时延、也不是通过实时性验收。解码/转换/求解/汇总/图分别有调用记录。

```bash
python3 scripts/paper_rebuild/audit_xbpg/run_gnss.py --local configs/paper_rebuild/DATA_PATHS.AUDIT_XBPG.local.yaml --phase validate-retained
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python3 scripts/paper_rebuild/audit_xbpg/summarize_gnss.py --local configs/paper_rebuild/DATA_PATHS.AUDIT_XBPG.local.yaml
PYTHONPATH=src python3 -m pytest -q tests/paper_rebuild/audit_xbpg/test_run_validation.py
```

validate-retained是一次性追加回执，已存在拒绝覆盖；需要重现时用另一授权输出根。汇总不调用解算器；当前已生成的图/表可从保留输出重建。本轮20个blocked主槽、8个full、1个smoke、8个转换=37行RUNS；METRICS保留20+8=28行，不把smoke或转换当独立性能试验。全部科学输入均真实；原生合成反例另表。
