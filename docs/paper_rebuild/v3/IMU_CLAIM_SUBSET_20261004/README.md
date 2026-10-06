# STEP2：V3 修正后 45 案例 × 3 方法复验结果审查

本次固定的135组原生运行与135次离线评价全部完成，135接纳、0不可用。每组原始分母、实际NAV和匹配评价均为56,642，未重建缺失运动、未拼接中断运行、未挑选placement。新结果支持“保留A1航向时，冻结SDK水平速度输入在这些D62受控位置/速度缺测窗中降低水平误差”的条件结论；不支持“完整GNSS不可用仍持续获得RD/RP/HV辅助”“RD稳定改善航向”或“所有故障条件保持厘米级”。独立540个全窗指标、810自身域、2520配对指标和280组汇总已全部复算通过，独立实现最大差3.907985046680551e-14；独立最终交付与实际两PNG验收已闭合：IMU_CLAIM_135_FINAL_DELIVERY_RECEIPT.json SHA9120b27ef47cf5a97fceba439287eca8c78774062024c21ea10957d10f8b5669。

## 1. 身份、存储与执行闭合

- 实际新根：`/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/IMU_V3_CLAIM_SUBSET_20261004T064538Z`。PUBLICATION是唯一此次数值/图入口；G为实际存储，代码/编译仍在WSL，未伪称全部储存在E。
- protocol：`V3_CLAIM_SUBSET_EXPLICIT_IMU_DURATION`；stage_id：`IMU_V3_TIME_CONTRACT_FIX_20261004`；运行前缀：`IMUFIX_CLAIM_`；native role：`imu_v3_corrected_controlled_replay_solver`。
- 数据身份：`data_mode=semisynthetic`、`semisynthetic_data_used=true`、`synthetic_data_used=false`。旧ADDENDUM源registry为受控语义，但旧native transport曾未正确传递case/data_mode/semisynthetic；新身份明确纠正，不能据此把新子集改称纯自然数据。
- HEAD `0625cea2c137859d1319c2e1011178cea19af10a`仅标识修改基点。实际科学身份为928项源码/配置/observer快照与新二进制hash，不声称当前修改等同该旧HEAD。928是依赖身份超集，不是“928文件逐字已读/执行”的覆盖证明。
- 当前二进制SHA256：`7ca1568ea75f11dad63aec5f16966c28f3ce6596207eb234c1b0f878b95fbe42`；构建收据：`/home/kaiwen/research/LegSA-GINS-SCRATCH/IMU_V3_FIX_20261004/BUILD_IDENTITY_20261004T063702Z.json`。
- PREREGISTRATION SHA256：`50674d262162968a06640c2870b80e28b64af57def0f950d27abc35bb3e4505b`。保留原435个provider/config pins；新IMU8/135子配置独立pin并前后重核。新IMU8 SHA：`0078814bb29b3c42cea74dda2e92b0372d5eade5105ac7b0643b7c359cad4f46`；56,643条观测、56,642个输出时刻，66.001035–339.997056秒，无gap/重初始化。
- 全135原生封存于2026-10-04T07:36:24.552870Z，之后才启动离线；native seal：`1f041d1180032b6552af8d43d1f0eb3b9256ad3f11c64a1e98fdf7cebaade60b`。`CONTROLLER_COMPLETE.json`于07:54:04.737952Z确认135/135；`CORRECTED_RESULTS.json` SHA：`a0f004962971f9ca22926e503f7c51f7eebf11857727c2dc60eacc9e665d9576`。
- 全135 online成功trace open=0；离线每组锁定trace句柄open/hash各1，共135。归约程序不读取GT、也不调用solver/evaluator。源、原输入、新IMU8/config、控制器、评价文件和aggregate均在归约前后重核。
- `REDUCTION_RECEIPT.json` SHA：`8fe4f7321202600c1befd68416ad64e9806f24a7a789f4a7439f4ed56001bc26`；本归约540个自身全窗指标独立重算与存档指标最大差0。保留810个自身支持域行、2520配对域/指标行、280个placement组汇总以及全部有利/不利结果。
- 13项新native解析/分析回归、全部135真实native loader接纳与14负向合同拒绝、14项外部归约边界/身份测试均有收据。135是实际求解/评价，不是只运行模块单测。`CONFIG_CHANGE_LEDGER_ADDENDUM.json`另闭合110自然+135子集配置的245个gap-policy append记录，科学配置字节未由该补充台账改写。

## 2. 固定队列与公平配对

队列在新修正成绩产生前固定：BY2 ADDENDUM中D61的10/20/30秒×seed00–08，共27；D62的10/20秒×seed00–08，共18，合计45。九个原placement锚点跨duration/family重复使用；它们不是45个独立随机实验。保留全部九个placement、全部seed和所有故障窗，没有按新指标选择案例、调参或重新生成故障/运动。

| 配对 | 唯一方法变量 | 保留的共同信息 |
|---|---|---|
| F04–A03 | A03只关闭raw Doppler（AB0111） | RV仍开启，provider、初始化、其他数值模型及RP/HV相同 |
| F04–A06 | A06只关闭SDK HV（AB1110） | RD、RV、RP、provider、初始化及其他数值模型相同 |

F04为完整AB1111（合法算法标签LegSA_Paper_V1或AB1111）；不使用F04–F02等多变量差异来估计RD/HV分量作用。90组配对均有事前字节/字段复核与独立审查。已有旧provider/config/raw血缘保留，只按授权更换显式IMU8、修正native源码、新stage/protocol/case身份、endtime/output/gap-policy等传输字段；首次初始化不变、没有新增IMU干预/合成运动。多个native缺陷一起修正，因此不能把新旧成绩差异归因于单一IMU时长或单一yaw Jacobian错误。

## 3. 指标定义与原分母

所有误差均相对锁定的commercial融合reference，仍存在shared-GNSS/参考物理点/姿态量/不确定度输运边界；不是独立绝对精度或Kalman统计一致性证明。

自身支持和配对共同支持分列。原始IMU微秒键定义每个域分母，缺测不改分母、无跨gap插值。此次全部56,642/56,642，所有配对域均保留原分母。

- `full`：全窗66–340秒。
- `fault`：半开故障窗[start,end)。
- `outage_end`：最后一个严格处于故障窗内的原始IMU时刻，必须两方法在该确切键都有输出；不存在则UNAVAILABLE，不回退到更早时刻、不插值。H/3D为非负位置误差，V/yaw为该时刻绝对误差，不能叫末端RMSE。
- `recovery_0_5`：(end,end+5]；`recovery_5_10`：(end+5,end+10]；`recovery_10_30`：(end+10,end+30]；`all_post_outage`：t>end。
- 各组mean是九个placement各自RMSE或末端误差之差的平均，不是把九个重复锚点当独立样本池化RMSE；无独立trial p值。差值统一F04减ablation，负值表示F04诊断误差较低。

## 4. 全窗结果：九个固定placement的自身RMSE均值

这些数值是九个RMSE的算术平均；全部单案例值见`FULL_135_RESULTS.csv`。D61全GNSS有效字段遮蔽时，位置误差随故障时长显著增大，不能被小幅分量差值掩盖。

| 故障 | 方法 | H / V / 3D（m） | yaw（deg） |
|---|---|---|---|
| D61 10s | F04 | 1.762729 / 0.301429 / 1.793708 | 1.907128 |
| D61 10s | A03 | 1.772570 / 0.303874 / 1.803803 | 1.906587 |
| D61 10s | A06 | 1.763987 / 0.301501 / 1.794970 | 1.907886 |
| D61 20s | F04 | 10.693422 / 0.950272 / 10.783047 | 1.937454 |
| D61 20s | A03 | 10.727455 / 0.951122 / 10.817119 | 1.936893 |
| D61 20s | A06 | 10.705759 / 0.949610 / 10.795258 | 1.938444 |
| D61 30s | F04 | 30.795521 / 2.778528 / 31.125140 | 1.956869 |
| D61 30s | A03 | 30.791395 / 2.788264 / 31.123218 | 1.955784 |
| D61 30s | A06 | 30.821253 / 2.776363 / 31.150421 | 1.957583 |
| D62 10s | F04 | 0.129049 / 0.328448 / 0.354607 | 1.901778 |
| D62 10s | A03 | 0.129107 / 0.331241 / 0.357225 | 1.901230 |
| D62 10s | A06 | 1.543061 / 0.307969 / 1.578844 | 1.902459 |
| D62 20s | F04 | 0.251598 / 1.025199 / 1.073224 | 1.900267 |
| D62 20s | A03 | 0.251434 / 1.029595 / 1.075397 | 1.899637 |
| D62 20s | A06 | 8.213691 / 0.980201 / 8.314221 | 1.900791 |

## 5. 配对故障窗与精确末端H结果

每行保留九个placement；表中“改善/更差”按故障窗H RMSE计数，无tie或不可用。全部V/3D/yaw及恢复域，不利案例与range见`PLACEMENT_BLOCK_SUMMARY.csv`及2520行配对表，不用本紧凑表代替完整结果。

| 故障 | 差值F04− | fault H均差（m） | 精确末端H均差（m） | fault改善/更差 |
|---|---|---:|---:|---|
| D61 10s | A03 | −0.053877 | −0.098249 | 7/2 |
| D61 20s | A03 | −0.134924 | −0.250639 | 6/3 |
| D61 30s | A03 | +0.009531 | +0.003463 | 6/3 |
| D62 10s | A03 | +0.000691 | +0.000780 | 4/5 |
| D62 20s | A03 | +0.000896 | +0.000807 | 4/5 |
| D61 10s | A06 | −0.006993 | −0.014376 | 5/4 |
| D61 20s | A06 | −0.048618 | −0.098182 | 6/3 |
| D61 30s | A06 | −0.084341 | −0.185658 | 5/4 |
| D62 10s | A06 | −7.439890 | −16.577577 | 9/0 |
| D62 20s | A06 | −29.614411 | −64.637496 | 9/0 |

RD增量：全45案例的全窗yaw只有1例改善、44例更差；五组yaw均差为+0.000541、+0.000561、+0.001085、+0.000548、+0.000630度。不能写“Doppler稳定提升航向”。全窗H 30改善/15更差，fault H 27/18，3D full/fault均32/13；收益和负例混合、幅度依赖条件，不能称统一独立信息增益。D61_30s的mean H变差，即使6/9个例改善仍须报告总体均差与最大不利值（fault +0.529112m、末端+0.961709m）。D62的H差在毫米尺度并且fault两组各5/9更差。

SDK HV增量：D62两组各9/9 H/3D故障窗与末端改善，提供明确条件配置收益；同时D62 fault V分别7/9、6/9更差，V均差+0.108238/+0.188896m，不能把水平增益扩写成每个轴普遍改善。全45 fault H为34改善/11更差，full yaw为41/4；yaw差通常很小，D62_20s全窗仍4例更差。恢复域全部预先分桶保留；未以某个最有利恢复时段替代完整域。

## 6. 故障有效信息与物理边界

(1) D61所有27个故障窗中的冻结HV有效provider行数为0；D62保留A1航向时HV仍有1,727–4,550个有效行。事前`HV_AVAILABILITY_ALL_45_CASES.csv`证明输入事实。D61和D62之间不能说“只差yaw”：有效HV信息也改变。F04–A06在D61的差异是故障前状态/协方差与恢复过程影响，不是故障窗中SDK HV持续桥接。

(2) 当前native只在有效GNSS事件内执行RD/HV/RP。`cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp:355–357`先拒绝invalidGNSS；RD/HV/RP在422–432，GNSS是否有效由P/RV/yaw字段决定。D61完全无有效字段时，不能宣称原始Doppler或RP在故障中独立持续调度。独立invalidGNSS辅助调度在前轮N09已裁定为可选能力扩展，不是冻结V3合同违约，本轮未扩大调度或新增案例。

(3) 独立保存source-aware trace账本按共享update_index对应的GNSS事件时刻分类，全部135接受总数与native manifest一致：D61故障窗内所有source evaluated=0；D62的P/RV/RD accepted=0，F04 HV与RP各有50–100次实际accepted更新。见`IMU_CLAIM_ACCEPTED_FAULT_SOURCE_COUNTS.json/csv`。因此D62也不能被当作RD在RV缺测中持续桥接的实验；F04–A03故障域差异可能来自此前状态/协方差及恢复/窗外作用。本135闭合的是这些冻结case/config的事实，不关闭“独立RD在RV失效且raw Doppler仍合法可用时的能力”验证缺口。

(4) SA trace的Go2时间是被选provider行时间（gi_engine.cpp:1297上下文），不是实际更新派发时刻；±0.02秒匹配可跨故障边界。provider时间域计数不可冒充实际故障域持续更新计数。独立账本已确认六条原RP sample-time靠近fault end的记录对应实际恢复期GNSS事件；未用它们宣称故障窗内RP更新。

(5) 当前冻结HV真实构造来自`src/legsa_gins/paper_rebuild/clean6_sensor_v21/providers.py:157–194`，SHA `86002aba39c524887264d7b65a707bc1824dc5c0d266ead3cfd45acb25c87a4d`：FLU→FRD符号M=diag(1,−1,−1)，取水平选择S_H，并用Ĉ=Rz(A1基线投影+90deg) Ry(−SDKpitch) Rx(SDKroll)，乘K_HV=1/0.962142，固定std=0.132838m/s。valid为SDK source_valid且A1插值支持（内侧A1间隔>1.2s无效，142–154）。Ĉ是冻结工程旋转，不等于独立标定的true姿态；非零roll/pitch时基线投影+90不自动等于Euler ψ。新native N01修正预测/Jacobian没有反向重写旧HV provider。旧clean5校准metadata文字不能替代此真实负pitch实现。

(6) 保持BY2训练/标定选择边界、独立真值/杆臂/时轴实测及reference物理点/不确定度输运未闭合。本子集不能将这些未验证项关闭，也不能用每组P门/全部支持证明实用准确性或独立统计一致性。实际保存边界Pactive15 PSD与冻结scale块精确0已检查；不冒称所有传播/更新时刻完整P都独立检查。

## 7. 图、阅读与后续论文范围

`ALL45_PAIRED_HEATMAP.png/.pdf`保留全部45×2配对的faultH、精确末端H、faultyaw、末端绝对yaw；`PLACEMENT_BLOCK_DIFFERENCES.png/.pdf`保留全部九个placement点及其均值，无裁剪/逐案例选择。已实际显示并检查两个完整PNG，标签/单位/负值较好规则/所有不利数值保留；工具对显示分辨率做了缩放。PDF已生成/哈希，未另行render。Matplotlib的Axes3D不可用警告与此次2D绘图无关，未改图或隐藏警告。见`VISUAL_REVIEW.json`。

本子集为修正后、已存在冻结输入/参数下的45个claim-bearing受控案例复验；不是重新验证全6468矩阵、全部20类HV对照、完整Go2/RP关闭组、全部三序列受控案例或作者原实验矩阵。历史主张如需要这些全范围证据，仍须标历史supplementary/未重验边界，不能以135替代6468。V3、动基线、RTKLIB、LC01的旧结果没有被本子集重跑或覆盖。

本轮实际读了完整外部prepare/loader/controller/reducer/tests/plot/协议文本、135行关键指标与280组mean/range/improved/worsened等字段及真实图；2520行全字段与原始误差大表由机器逐值独立复算，不改称人工逐字阅读。全部928项hash遍历也不是逐字审查。准确范围见`CLAIM_SUBSET_READ_COVERAGE.csv`，全仓覆盖由root总表统一管理。

独立最终表格复算/source928前后/真实图像验收已经闭合，源码冻结于08:09:46.142211 UTC正式释放。随后单独修复EXT纯竖直航向guard。该后置源码修复必须使用新身份/新测试/现有15,669payload与9,100有效输出非触发证明，不能回贴到上述135或旧EXT九组的执行源码身份。

## 本目录可审查资产

- [完整135结果](FULL_135_RESULTS.csv)、[自身810域](OWN_SUPPORT_DOMAINS.csv)、[90配对2520指标](PAIRED_ALL_90_CASES_DOMAINS.csv)、[280条件汇总](PLACEMENT_BLOCK_SUMMARY.csv)。
- [参考访问](REFERENCE_ACCESS_AUDIT.csv)、[原生摘要](NATIVE_RUN_SUMMARY.csv)、[自身重算](INDEPENDENT_RECOMPUTATION.csv)。
- [45案例热图](ALL45_PAIRED_HEATMAP.png)、[全部九锚点散点](PLACEMENT_BLOCK_DIFFERENCES.png)，PDF保留但未另render。
- [独立最终验收](IMU_CLAIM_135_INDEPENDENT_FINAL_REVIEW.md)、[交付/冻结释放](IMU_CLAIM_135_FINAL_DELIVERY_RECEIPT.json)、[实际接受事件域账本](IMU_CLAIM_ACCEPTED_FAULT_SOURCE_COUNTS.csv)、[归约封存](REDUCTION_RECEIPT.json)。
- [复制/存储血缘](SMALL_PUBLICATION_COPY_RECEIPT.json)。本目录仅小型审查资产；完整native/error/source-snapshot仍在上述实际stage。未发布GitHub、未commit/push。外部helper绑定原stage身份，未来新运行须建立新身份，不可重用已封存输出目录。
