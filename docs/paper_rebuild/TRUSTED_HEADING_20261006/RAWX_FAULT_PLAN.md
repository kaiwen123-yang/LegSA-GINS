# RAWX 观测层半合成：固定三窗执行登记

状态 REGISTERED_READY：root已独立读审overlay、缓存码anchor和两个默认关闭hook；8项不同本地合成/mock场景已通过（初次4失败及4项定向重测保留）。登记时尚未运行真实prepare、前端搜索、导航、评价或读取参考。提交后按两个分开入口执行。历史 FULL_WINDOW_FRONTEND 与 PREPARE 计划/pin 和结果不改。

## 输入、故障和身份

固定原 V3 BY2 [66,340]、BY2H [413,683]、BY2O [3186,3563]，1370/1350/1885 共4605历元。每序列只生成一条半合成流，依次在全窗1/4、1/2、3/4之后首个原配对 RAWX 历元注入下列事件，区间均为 [start,start+1s)：

1. RX2 单完整信号 cpValid=false、locktime=0；故障前五历元双接收机合格且通过原TDCP门的信号中，优先上一输入模型pivot，再按full signal稳定排序。
2. RX2 所有信号同样临时失去载波资格；码、Doppler、时标和接收机时钟位不变。
3. 单信号未宣告 +0.25 cycle 相位脉冲；优先上一输入模型非pivot，仍按相同过去五历元输入规则选择。只改变当前原本合格的相位，不把-0.5/NaN等无效值变成合法数据。

前两类结束后恢复原解码字段；不额外添加整数阶跃，也不声称模拟具体接收机固件内部locktime轨迹。原 ArcTracker 必须因无效区间生成新token。第三类保持原质量位、锁时和Doppler，是相位观测偏置，不冒称整周周跳。事件选择不读取接受结果、NAV或参考；此前已看过该开发记录，不能称留出。

固定事件缺五历元资格/信号或故障后20s输入时，原位保留 NOT_IMPLEMENTABLE，无替换。故障前无owner只令旧源延续项 NOT_EXERCISED，不能倒过来择取成功时段。三事件来自同一序列且顺序相关，不当作独立样本。

这是 RAWX **观测层半合成**：原UBX字节不改，读取后在独立内存对象上overlay，再进入既有 ArcTracker→pivot→多系统/频率组内DD→完整Q。既有NPZ与ARC_EVENTS都不被直接改写。不能称自然故障、硬件故障试验或原整数真值。若未来仅对NPZ相位行做加法，那是另一种模型级半合成。

## 最小实现与复用

- `rawx_fault_overlay.py`：纯观测变换和逐信号修改日志；时间/码/Doppler/clock内容指纹保持。
- `real_trial.prepare(..., epoch_overlay=None, anchor_reuse=None, prepare_families=None)`：默认行为不变；本次仅主 family。变换位于decode之后、ArcTracker之前。
- `rawx_fault_trial.py prepare`：核旧完整seal/PLAN、registry/UBX/source、因果广播schedule；复用同week/tow/time的封存纯码anchor，包括原不可用原因。逐历元同schedule/广播身份，零新SPP、零converter。仍调用既有satpos广播状态后端建模，不是零卫星状态计算。
- `rawx_fault_trial.py frontend`：prepare全部完成并封存后，按本登记固定template派生输入seal，调用同一完整集合前端。`full_window_frontend.run`的supplied_plan/registration_check仅是明确登记入口，默认历史PLAN路径不变。不能用新source hash追改旧登记。

源集合、工作Q、原始n维chi-square成本域、phase Holm .01、五槽同origin、长度与sphere点检查、TTL/单worker/序列化开销限制全部不变。front-end阶段只读新MODELS，不再读RAWX。

## 执行预算和停止

新prepare预算3次，6个已登记接收机UBX载荷各读一次；主family建模最多4605机会。零新SPP/convrnx/AR/NAV/evaluator/reference。建议外层监督900s硬停止并保留stdout/stderr/PID和所有半成品；库内部不是严格墙钟认证。

新frontend三序列一次pass：921固定获取机会；最多921完整域枚举/长度筛选，每次100000 nodes、10000 candidates、30s合作式超时；总处理1200s，GLS/GLRT/geometry各400000、sphere接口9210上限。未执行槽和所有失败保留。此前clean的预算已消费，本登记是独立新身份，禁止补窗/重试/改噪声或门限。

所有原sealed clean结果复用。新增导航/evaluator预算均0，不能从PVT仍有效但carrier被注入故障推断V3同层故障恢复；C-LAMBDA/CWLS原候选器或RTKLIB Q1也不是共同准入对照。若要既定20%恢复收益，须另登记同输入和验收的strict-DD-retire消融，本次不作该结论。

## 结果检查与命令

保留全部4605行和921机会，分别报告物理弧退休、当前临时质量拒绝、单/多类、所有失效及条件研究点。查部分失弧的存活关系；全断后的旧source/pending终止；新token不得继承旧receipt；同数值整数可被新搜索重新提出，但必须新source和满五槽，不能称旧源复活。真实整数正确率/错误固定率仍NA。

恢复计时从固定故障结束到重新满足原资格且持续至少1.0**实际秒**的确认末时刻；5Hz通常需六个点跨满1s，不能把五槽跨度0.8s写成1s。缺测重置稳定确认。20s未恢复者右删失，20仅作受限汇总值；无旧源/信号未实施分列。输出为offline观测事件回放，不是端到端零延迟实时。

Root冻结后分别调度两命令，持久stdout/stderr由外层driver保存；不要串成失败后仍执行的shell命令：

```text
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONPATH=<repo>/src python3 scripts/paper_rebuild/carrier_phase/rawx_fault_trial.py prepare --stage <NEW_STAGE> --registration-commit <FULL_SHA> --roots <existing roots.yaml> --clean-prepared <FULL_WINDOW_PREPARE_ATTEMPT02>
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONPATH=<repo>/src python3 scripts/paper_rebuild/carrier_phase/rawx_fault_trial.py frontend --stage <NEW_STAGE> --registration-commit <FULL_SHA>
```

本地工程验证另见 RAWX_FAULT_LOCAL_PLAN/TEST_RECEIPT：最多8个纯合成/mock场景；其授权不包含上述真实半合成执行。
