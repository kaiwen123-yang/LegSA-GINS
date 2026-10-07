# BY2O 位置产品反事实：源驱动的最小可归因方案

状态：2026-10-07 源驱动方案定稿，本审阅未生成故障 provider/config，native=0、evaluator=0。真实载波前 prior 读出已完成：117条完整，41个双分量域的远弧均被当前先验明确排除（必要转角最小85.3313°，全117的99.9%外包半径最大1.93075°；远弧log质量上界最大−16763.7885），41个双域没有两弧同时被排除。另2个单弧与prior不相容，原生NIS已拒绝，不能隐去。此为当前Gaussian先验条件的几何界，不是后验模态概率或真实姿态风险认证；足以停止本批多分支工程。根任务据此选择下面4臂下一阶段，负责冻结provider、runner、binary与执行时点。

## 唯一主要干预及选窗

现有 FULL.csv 中，两端有 FULL valid 恢复、内部有真实 ROLLING partial 的最长 FULL 断弧是 **3278.598000049591–3310.3980000019073 s（31.8 s）**。完全由原 carrier 供给定义，不看 NAV、参考或输出误差选窗。保持原 BY2O [3186,3563] s 完整运行窗、初始化及前后历史。

只将严格开区间内 GNSS18 **第16列 position_validity** 从1改0，共159行；不删除行，时间和其余17列保持。两端 FULL 载波仍原样消费。最近保留的位置源时刻为3278.400000095、3310.400000095 s，所以实际位置源相邻间隔是32.0 s。边界定义先于运行，不能按状态响应伸缩。

保留 PVT velocity、raw Doppler、RP、IMU、SDK body velocity、carrier及它们原 validity/噪声/时间。窗口内 PVT position/velocity/yaw 三列原 validity 均159/159；raw Doppler available/valid均159/159。配置继续原 configured 研究身份，不改PVT优先策略、不把这个位置产品反事实写成真实失锁或自然GNSS中断。GnssFileLoader::loadExternalCarrier（gnss_file_loader.cpp:189–221）独立读取position/velocity有效性，位置失效不能偷偷改velocity有效性。

## 原源足式与运动分母

| 原源量，严格区间内 | 数值 |
|---|---:|
| carrier槽 / FULL valid / ROLLING partial | 158 / 0 / 30 |
| 支撑 START / END / RETIRE | 143 / 75 / 68 |
| END 起止均在区间内 | 75 |
| END 足对 FR–RL / FL–RR | 33 / 42 |
| SDK body有效行 | 6593 / 6593 |
| ≥2个支撑proxy源行 | 6143 / 6593 |
| SDK水平速度 median [p10,p90] | 1.086760 [1.022365,1.182012] m/s |
| 原gyro模长 median [p10,p90] | 24.433964 [14.495250,43.958030] deg/s |

END区间时长min/median/max为0.100001/0.102013/0.109479 s；并非长静止或全足端无效窗口。这里是来源读数，SDK速度与支撑proxy不能认证真速度或无滑移。68个RETIRE中67个来源/支撑无效、1个source gap/timeout，只结束未来作用并保留有效历史；原源REVOKE=0，不能冒称撤销故障已经暴露。

## 最少比较及可宣称问题

冻结为局部 partial 消融：四臂的载波共同背景均是完整原 MOTION.csv。GAP_PARTIAL 保留全部原行；GAP_FULL_ONLY 仅把严格缺口内30条 partial 换成同历元 FULL.csv 的无效行。缺口外另外87条 partial、两端 FULL 和所有其他行完全相同。这样每个足式背景下，两载波臂在第一个受影响 partial（3279.99799990654 s）之前应有完全相同的状态历史，不能把缺口前已有不同航向作为缺口内30条 partial 的作用。该名称只指局部缺口，不是整窗 FULL-only 算法。

| 共同导航背景 | 缺口内只用 FULL | 缺口内保留 partial |
|---|---|---|
| SDK_NULL：SDK按原周期使用，足端NULL | SDK_GAP_FULL_ONLY | SDK_GAP_PARTIAL |
| REPLACE_SUPPORT：原footXY替代其支撑区间SDK | FOOT_GAP_FULL_ONLY | FOOT_GAP_PARTIAL |

四臂均应用同一位置validity反事实、同一当前向量SA语义；固定原foot XY、point sigma=.01、SDK discrepancy=off、全部噪声/阈值/杆臂/初值。foot维度代表**足端替代SDK区间的部署方案**，不是独立叠加foot的纯效应；如果换为REPLACE_NULL，则在控制臂同时删除SDK和foot，改变了要回答的实际部署问题。不要据结果增添第五臂或重扫尺度。

比较两个背景内的GAP_PARTIAL−GAP_FULL_ONLY作用，再报告两种作用之差；先看真实共同R/v/p、来源接受与foot统计，随后才看原冻结参考下H/Up/yaw/尾部与杆臂项。RMSE差中差是描述性交互，不是可加因果分解，也不能称独立真值精度。四臂若执行，需4 native＋4原冻结评价，现有无mask旧结果不冒充匹配控制。位置产品以外的强速度源可能使增益仍小；这是真实保留来源下的结果，不再删掉它们制造收益。

本次主要干预只设位置validity，不再叠加晚到几何fault。原support生命周期、依赖标记与whole-engine重放能力继续保留；正常RETIRE的历史保持和REVOKE=0完整报告。已有真实失配撤销的集成证据仍有效，但此次若无REVOKE，不能新增撤销成功主张。将来只有新的明确撤销科学问题才设计其暴露，避免在这次交互中混第二干预。

## 完整固定读出与数据身份

执行前冻结为4 native＋4评价。完整[3186,3563]窗口和原场景mask保持，新增主要读出为full、严格gap开区间、recovery [t1,t1+20]及其余完整补集（后三者不重复覆盖），保留缺口前状态身份和首次分歧时间；不按误差删恢复点。在线参考仍为0，原冻结评价仅离线。若收益微小或某分量变坏，照报，不称整体goal完成。

本次仅解析既有 FULL/MOTION、support provider、SDK velocity provider、GNSS18、Doppler和原body缓存，未读NAV/reference、未扫raw。完整源SHA与计数：`/home/kaiwen/research/LegSA-GINS-SCRATCH/UNIFIED_LEGGED_HEADING_20261007/BY2O_POSITION_PRODUCT_PROTOCOL_01/SOURCE_INPUT_COUNTS.json`。原源输入未变。

## 原源路径与可复现选择器

- FULL：`/home/kaiwen/research/LegSA-GINS-SCRATCH/CONTINUOUS_HEADING_20261007/PARTIAL_FULL_WINDOW_01/BY2O/FULL.csv`
- ROLLING：同目录 `MOTION.csv`。
- 四臂模板/输入身份：`/home/kaiwen/research/LegSA-GINS-SCRATCH/UNIFIED_LEGGED_HEADING_20261007/SUPPORT_POSE_NATIVE_BY2O_01/PLAN.json`；配置子目录 `CONFIGS/BY2O__SDK_NULL.yaml`、`CONFIGS/BY2O__REPLACE_SUPPORT.yaml`。
- GNSS18：`/home/kaiwen/research/LegSA-GINS-SCRATCH/CLEAN8_PROTOCOL_V3/02_PROVIDERS/CASES/BY2O__C00_clean_normal__c5212cf72d07afd6d3ae0407fee87f841f2e0d909dfb8c1416bd7f38b0248bb4/GNSS18.gnss`
- 原足端事件：`/home/kaiwen/research/LegSA-GINS-SCRATCH/UNIFIED_LEGGED_HEADING_20261007/SUPPORT_POSE_PROVIDER_BY2O_01/SUPPORT_POSE_EVENTS.csv`
- SDK body-FRD速度：`/home/kaiwen/research/LegSA-GINS-SCRATCH/UNIFIED_LEGGED_HEADING_20261007/FIRST_SHARED_STATE_PILOT/BODY_PROVIDER/BODY_VELOCITY.csv`
- 本次运动读数缓存：`/home/kaiwen/research/LegSA-GINS-SCRATCH/CONTINUOUS_HEADING_20261007/BODY_CACHE/BY2O_body_motion.npz`。
- RP、IMU、raw Doppler 的原路径和SHA直接沿用模板PLAN的 `runs[].providers`，不能重新扫描raw或重建不同版本。

以下只选择窗口，不生成修改后数据；full与rolling必须是已封存原版本。第16列的唯一修改由后续runner另存新provider执行，原输入文件不动。

```python
import csv
from pathlib import Path
base = Path('/home/kaiwen/research/LegSA-GINS-SCRATCH/CONTINUOUS_HEADING_20261007/PARTIAL_FULL_WINDOW_01/BY2O')
def read_csv(p):
    with p.open() as f:
        return list(csv.DictReader(f))
full, rolling = read_csv(base/'FULL.csv'), read_csv(base/'MOTION.csv')
t = [float(r['measurement_time']) for r in full]
assert t == [float(r['measurement_time']) for r in rolling]
f = [r['valid'] == '1' for r in full]
r = [x['valid'] == '1' for x in rolling]
anchors = [i for i, ok in enumerate(f) if ok]
arcs = [(t[b]-t[a], t[a], t[b], a, b)
        for a, b in zip(anchors[:-1], anchors[1:])
        if b > a+1 and any(r[a+1:b])]
# Longest source-defined bounded FULL loss; an exact tie uses earliest start.
_, t0, t1, ia, ib = max(arcs, key=lambda x: (x[0], -x[1]))
assert (t0, t1) == (3278.598000049591, 3310.3980000019073)
assert sum(r[ia+1:ib]) == 30 and ib-ia-1 == 158
# For original GNSS18 tokens: change tokens[15] only where t0 < float(tokens[0]) < t1.
# Expected source rows: 159. Do not change velocity validity tokens[16] or yaw tokens[17].
```

## 半合成身份与元数据许可

本研究是 real source 上人为屏蔽定位产品的受控反事实，配置与 PLAN 均明确 `data_mode=semisynthetic`、`semisynthetic_data_used=true`、`synthetic_data_used=false`，在线 reference=false。研究 stage/protocol 分别为 `UNIFIED_POSITION_PRODUCT_GAP_20261007` / `POSITION_PRODUCT_GAP_PARTIAL_SUPPORT_INTERACTION_V1`。不能沿用 real_clean 或 false 标签让它通过旧配置检查。

当前 research_experiment 合同仍沿用了 formal 的半合成禁止项；本轮仅让显式 research_experiment + semisynthetic 数据身份的配置通过这一元数据检查。正式模式、原始数据、观测数值、时间、噪声、算法与其他 forbidden flags 不变。这是记录真实数据身份所需的最小配置许可，不是新估计算法。新 binary 单独编译，四臂共同使用；不覆盖已验证诊断 binary。
