# 135 组纠正受控回放：独立最终验收

**独立数值与身份检查全部通过。** 实际135 native和135 offline均完成，135评价被准入、0不可用；原案例完整45×F04/A03/A06，没有结果筛选。全部135运行各自实际输出、匹配与原观测记录分母均为56642；这不是名义500Hz格点或物理连续时间覆盖声明。

主机器收据：[IMU_CLAIM_135_INDEPENDENT_FINAL_NUMERICAL_REVIEW.json](G:/LegSA-GINS-project/修复_20261004/IMU_CLAIM_135_INDEPENDENT_FINAL_NUMERICAL_REVIEW.json)。独立审查器没有导入publisher函数或项目solver/evaluator，没有打开原始GT/reference、bag/fpl，也没有运行新科学计算或改科学输入。

## 精确验收身份及范围

- stage：`G:/LegSA-GINS-project/clean_rebuild_202607/stages/IMU_V3_CLAIM_SUBSET_20261004T064538Z`。
- PREREGISTRATION SHA256：`50674d262162968a06640c2870b80e28b64af57def0f950d27abc35bb3e4505b`。
- binary SHA256：`7ca1568ea75f11dad63aec5f16966c28f3ce6596207eb234c1b0f878b95fbe42`。
- ALL_NATIVE_SEALED SHA256：`1f041d1180032b6552af8d43d1f0eb3b9256ad3f11c64a1e98fdf7cebaade60b`，135 native在2026-10-04 07:36:24.552870 UTC的前离线收据中已封存。
- CORRECTED_RESULTS SHA256：`a0f004962971f9ca22926e503f7c51f7eebf11857727c2dc60eacc9e665d9576`。
- REDUCTION_RECEIPT SHA256：`8fe4f7321202600c1befd68416ad64e9806f24a7a789f4a7439f4ed56001bc26`。
- 独立完整复算完成时刻：2026-10-04 07:59:27.208813 UTC（北京时间15:59:27），后续只读accepted-source账本、图片核查及交付身份单独记录。

事前独立合同、外部配置账本和四门修订收据分别保持；本轮原native独立审查已核全部2160封存成员、928源码身份、实际LAUNCH/config/IMU8、strace及输出支持。最终复算再次核全部928实际工作源码前后与保存snapshot相同、435原provider/config、控制器/prepare/loader及receipt、新IMU8+135配置、全部evaluation result/error和7个publication CSV身份前后相同。没有把旧baseHEAD当作修改后的完整源码身份。

## 独立重算的结果

| 检查对象 | 完整核查数 | 结果 |
|---|---:|---|
| 全窗 H/V/3D/yaw RMSE | 540 | 与正式结果一致，最大绝对差3.907985046680551×10⁻¹⁴ |
| 自身支持域 | 810行（135×6） | 数值、原观察分母、匹配/缺失及状态一致 |
| 两个单因素配对的7域×4指标 | 2520行（45×2×7×4） | 所有full/ablation/delta、共同支持/缺失、单位/状态一致 |
| 九重复放置锚点的条件汇总 | 280行 | 9case、mean/median/range、改善/平局/不利/不可用计数一致 |
| 所有完整/配对访问与native摘要 | 135+135行 | actual native/access/covariance/runtime身份及标志一致 |

四份独立重算明细：

- [全窗540指标](G:/LegSA-GINS-project/修复_20261004/IMU_CLAIM_135_FULL_RMSE_INDEPENDENT.csv)
- [810自身支持域](G:/LegSA-GINS-project/修复_20261004/IMU_CLAIM_135_OWN_DOMAINS_INDEPENDENT.csv)
- [2520配对指标](G:/LegSA-GINS-project/修复_20261004/IMU_CLAIM_90_PAIR_DOMAINS_INDEPENDENT.csv)
- [280条件/锚点汇总](G:/LegSA-GINS-project/修复_20261004/IMU_CLAIM_PLACEMENT_SUMMARY_INDEPENDENT.csv)

故障域为[start,end)；恢复域为(end,end+5]、(end+5,end+10]、(end+10,end+30]及所有t>end。故障末端取原观测IMU输出记录中严格在窗口内的最后key，两方法必须都在该精确key有保存误差；没有nearest fallback、插值、替代时刻或缺失记0。每个配对域均按保存时间微秒key取精确交集，原分母保持。135×4 full算术用独立dot/sqrt，配对交集/endpoint/统计独立实现，不调用publisher作为oracle。

## 结果能支持的主张及反例

以下为F04减消融的fault域H差异计数，负为F04较低；九锚点重复，不把27/18条条件记录作独立实测推广：

| 配对 | D61 H改善/不利 | D62 H改善/不利 |
|---|---:|---:|
| F04–A03：只关闭RD，RV保留 | 19/8 | 8/10 |
| F04–A06：只关闭SDK HV | 16/11 | 18/0 |

yaw fault同样有不利项：F04–A03 D61为15好12差、D62为10好8差；F04–A06 D61为20好7差、D62为12好6差。没有平局或不可用。不应将某一子集位置改善改写为所有情况、所有指标均改善。完整7域4指标和全部不利记录随表保留。

D61同时禁止P/RV/RD/yaw，其HV provider继承A1航向有效性，故障中没有有效HV；RP虽有有效provider，当前调用调度仍依赖GNSS可用。D62保留A1航向条件与HV。D61与D62之间不能视作只换yaw而其余即时信息相同；案例内部F04/A03/A06 provider及其余科学配置仍完全相同。D61窗口内两方法差异可能来自此前状态/协方差和之后恢复，不证明窗口内新HV或独立RP持续桥接。

独立读取全部135保存source-aware trace，接受总数逐source与native manifest更新计数一致；故障域账本按共享update_index所对应GNSS事件时刻分类，见IMU_CLAIM_ACCEPTED_FAULT_SOURCE_COUNTS.json/csv。trace.time是各provider自己的sample时间，不能直接当统一state update time。例如D61 seed00某RP sample216.1970806122 s，对应GNSS事件216.2000000480 s（fault end216.2 s），故该RP发生于恢复事件。原source-sample直接分窗诊断保留，没有据此杜撰窗口内RP更新、物理未来泄漏或修复收益。

## 图像与仍保留的边界

已用original分辨率实际独立查看两个PNG：45案例热图和五条件各九锚点散点图。全45/90配对及所有不利值保留，负值较好含义、单位和图例清楚；没有颜色/纵轴clip、未见遮挡。图只显示H/yaw的fault/末端四固定面板，完整28域×指标应随全表提供。两个PDF仅核身份，**本审查没有单独render PDF，不称已完成PDF版面验收**。

共享GNSS商业融合参考仍是agreement/diagnostic reference；数学复算不证明独立绝对精度。物理点/协方差运输仍未闭合，原STD未运输；保存P的PSD只覆盖recorded active15边界、scale被冻结，不证明全21物理估计或噪声校准。九锚点是同底轨迹上的重复放置，探索性回放不能宣称45独立试验或确认性p值。多项native数学修复同时改变，未隔离单项修复因果收益；没有重跑旧6468矩阵或全部HV方法。

**验收身份只针对上述封存stage。本轮最终交付后可释放源928冻结，后续源码变更须建立新身份；不影响已绑定保存snapshot的本次验收。**
