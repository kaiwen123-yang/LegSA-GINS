# V2 物理修复与严格身份

状态：2026-10-04 全九组合原生矩阵正在执行；全部原生封存前不打开参考。此时没有完整 V2 科学成绩。V1 全部表、图、RUN、失败及原提交保持历史身份。

## 已证明的错误与修复

原始伪距 P 仍须用于卫星广播发送时刻，但它含钟项，不能作为 Earth rotation 的物理飞行时间。原新版 DD 已采用几何延时；共同 SPP 初始化路径遗漏了该修正。新 `gps_l1_code_spp` 保留 legacy_raw_code 默认，对 V2 仅允许 `iterated_geometric`：当前 SPP 位置下四次迭代几何 range/c，每次从原始发送坐标旋转一次。接收钟由 SPP 共同估计，不先从原始 P 再扣一次；无 PVT 或 reference 输入。

独立一程移动卫星无噪声 oracle 在真实位置固定而接收钟为0/0.26/0.70/5ms时，旧 SPP 误差0.013924/0.107815/0.312400/2.312308m，新误差小于2e-5m。这是 SPP anchor 错误证据，不能直接宣称为最终基线误差或姿态改善量。新九结果已取得：SPP物理修复不自动消除姿态大误差，EXT01/02同key原生RMSE变化均小于5.3e−6°，EXT03不变，详见v2_fix同法表。

另修复 phase2 的 GNSS2-only 时钟跳变在 SPP 失败记录中丢失、以及 sequence_override 影响输入选择却未入 source fingerprint。未给失败历元伪造输出。全部回归证据、测试源码和明细见机内 STEP1_HORIZONTAL_GAP_AUDIT、SOURCE_DIFF 与测试 XML。

## 执行和暂停历史

配置 [EXT_REPRODUCTION_V2.json](../../../../configs/paper_rebuild/horizontal_literature/EXT_REPRODUCTION_V2.json) 一套跨三序列；长度0.350m、noise floors、8worker、EXT01 seed8/1e6节点/60s、EXT02 K全池/20迭代/tol1e-10/任一不完整整历元拒绝、EXT03递推/ratio默认均不变。不能以选择历元或参数使结果更好。

首个 E-hosted V2 因用户清空间暂停于 BY2O EXT01 1250/2231、955有效；长暂停会影响 perf_counter 预算及 runtime。空间验收后没有恢复执行，而精确终止停止组，保留54文件前后hash无变的完整已写证据。未封存压缩流不能被冒称完整结果，也不把用户中断算算法失败。

新独立 stage 使用 `SEQ__METHOD__RAW_REPRO_V2__TECH_RETRY_2`，全九从 epoch0 执行，无 partial 拼接。技术 generation2 对应整个矩阵；其他八槽在此处为第一次实际调用。22输入/缓存/NAV文件与原V1字节一致，2基础库原pin相同，均只读；输入属于原始UBX/NAV派生，未复用旧估计。各run保存13源码+config快照，显式 reviewed source overlay 前后hash一致，baseHEAD只是来源基点。独立离线评价必须明确 `--native-version V2 --native-attempt 2 --allow-source-overlay`，拒绝其他attempt/版本、未完成结果或错误heading指针。44合成测试通过。

真实新根位于 E 宿主 WSL ext4，根映射和哈希收据在 G 的修复_20261004 中；不虚称其为旧 G stage。峰值预算2GiB，实际 E 盘剩余不足40GiB则在新launch前停止。此统计基于 E实际挂载/Windows Get-Volume，而非 WSL虚拟 ext4容量。旧 partial根与新根都完整保留。

## 科学边界

本轮是原文核心算法的独立实现和本项目观测上的工程实例，没有作者完整数据、代码和全部实验参数，不能称三篇作者原实验完整复现。EXT02多天线三轴姿态未实现；全候选池拒绝是固定工程政策，103旧失败中可存在其他收敛候选，不在本轮偷换政策。EXT03没有作者唯一实现资格；ratio-fixed不等于整数真值已知。GPS L1与GPS+BDS双频输入、有效支持、失败和held视图应分别说明，不能由名义同窗得出公平同输入求解器排名。

评价口径沿用冻结 EVALUATION_PROTOCOL：原生失败和边界保留原窗分母；native_valid、ratio_fixed、causal_held分列；只有保存误差的精确微秒key交集可进入共同支持，不插值方法输出或择时延；商业融合参考仅离线读取，非独立真值。旧 V3、RTKLIB四变体、LC01及动基线不重跑。本轮没有同层raw故障矩阵，不能把旧provider退化诊断自动当新三方法鲁棒性证明。

## 航向物理量与未定义边界

本三方法保存的 `body_yaw_deg` 是估计基线的水平投影方位，再加固定90°以对应机体 −y 横向基线。它没有同时估计完整 roll/pitch，不能自动解释为 Euler yaw。若真实机体旋转为 Rz(ψ)Ry(θ)Rx(φ)，且基线为 [0,−L,0]，投影航向与 Euler yaw 的差为 atan2(−sinθ sinφ,cosφ)，前提是水平投影非零。roll/pitch共同倾斜时存在物理量差异；商业融合 Euler yaw 仅作离线诊断。共同时间key也不能消除该差异，不可据此对与新V3完整姿态状态作相同物理量、相同输入的性能排名。

源码对纯竖直非零基线目前会因 atan2(0,0) 返回90°，该水平航向在物理上未定义。这是已证明的未覆盖输入合同角落；本批源码冻结，尚未应用源 guard。全部九实际保存 HEADING 的水平范数及精确零计数将另列逐行机器审计，以确认本批是否受影响；不据审计选择剔除历元或修改成绩。后续拒绝 guard 需要独立版本与边界测试，不能将本批冒称已使用该修复。

## 最终封存已完成

已完成九native终态/source/config/input前后pin与成功openat在线reference0审计，然后三offline child各reference1次。341项独立复算最大RMSE差2.8422e−14°；自身/450共同支持、新旧27同法行、三图与全9水平基线非零证据均在v2_fix。源vertical guard尚未使用，实际9100有效输出最小水平范数0.0198182443m；当前未触发不等于源合同已关闭。
