# 新窗口交接：先画图，再写论文

更新：2026-10-05。交接前研究版本：`2a739b3574c437a2ccf8936c4a68f7dd5da3172e`。

## 当前决定

作者准备换窗口，把工作分成两个连续阶段：先专心完成论文图，再围绕确定的图写论文。本次只整理交接说明，没有新增实验、修改算法或制作图片。沿用现有数据，不要求补采；原V3主结果继续保留。

绘图窗口应先看数据和图源，做出1–2张有代表性的成图供作者讨论风格，再推广到其余图。不要一开始批量导出几十张相似图。写作窗口接收最后选定的图、图注、来源表和现有中文初稿。

## 新窗口可以直接使用的任务说明

> 本窗口专心制作 LegSA-GINS 项目的论文图，完成后再转入论文写作。请先阅读本交接文件及所列数据入口。论文方向是 GPS Solutions 和 IEEE TIM，先围绕短基线航向与机器人运动信息融合组织图件，TIM补充测量链、时间关系和不确定度。使用现有原V3及明确标识的附加结果，不需要重跑全量矩阵。先做少量代表图，做到论文栏宽下清晰、版式简洁、每幅图回答一个科学问题，再逐图完善。F03/F04等只保留在内部来源映射，图中使用清楚的方法名称，具体论文命名可再讨论。每完成一小部分就提交并推送GitHub。详细来源见下表。

## 优先入口

以下路径均相对于当前研究仓库；先读本表，不必重新通读全部历史日志。

| 目的 | 路径 | 如何使用 |
| --- | --- | --- |
| 当前中文、英文初稿 | `docs/paper_rebuild/EXISTING_DATA_R5_20261005/manuscript/` | 中文 R5 是后续写作底稿；英文 GPS Solutions R5 对应相同结果。当前稿的图组织仍需重做。 |
| 原V3方法、选型及结果 | `docs/paper_rebuild/V3_STORY_20261004/CURRENT_STORY_INDEX.md` | 主结果入口，含源码解释、自然序列表和完整矩阵账本。 |
| 原V3自然序列指标 | `docs/paper_rebuild/V3_STORY_20261004/NATURAL_METHOD_RESULTS.csv` | 明确选择原V3、对应方法及评价合同；不要从旧图片抄数字。 |
| 已有32个图源 | `docs/paper_rebuild/JOURNAL_REFRAME_20261004/figures/FIGURE_CATALOG.csv` | 复用数据定位和脚本线索，旧图风格无需沿用。 |
| 横向对比 | `docs/paper_rebuild/TIM_EVIDENCE_20261005/comparisons/README.md` | 总表、方法含义与运行来源；同目录 `RUN_EVALUATION_INDEX.csv` 定位真实输出和误差文件。 |
| 失锁过程 | `docs/paper_rebuild/EXISTING_DATA_R5_20261005/existing_results/DIAGNOSTIC135_PAPER_RESULTS.md` | 已整理故障期间、末端、恢复期结果；属于单列的诊断版本。 |
| IMU中断附近与共同支持 | `docs/paper_rebuild/EXISTING_DATA_R5_20261005/existing_results/GAP22_PAPER_RESULTS.md` | 已有22成员/7处中断的结果，不替换原V3。 |
| 新NMB/XB数据 | `docs/paper_rebuild/EXISTING_DATA_R5_20261005/new_data/RESULTS_AND_USE.md` | 最终采用 T03 / ATTEMPT_03、统一0.15秒参考插值；同目录 `RESULTS.csv` 为最终表。 |
| TIM分析 | `docs/paper_rebuild/EXISTING_DATA_R5_20261005/manuscript/TIM_measurement_analysis_zh.md` | 测量链、时间关系、误差传播与参考相关性。 |
| 实物/CAD/URDF | `docs/paper_rebuild/TIM_EVIDENCE_20261005/installation/INSTALLATION_EVIDENCE_REVIEW.md` | 实物标注与几何示意的来源；相机朝前、采集时同一结构已由作者确认。 |
| 早期详细绘图交接 | `docs/paper_rebuild/TIM_EVIDENCE_20261005/DRAWING_HANDOFF.md` | 仍可用的数据和安装说明；其中 r3 文稿入口由本文件的 R5 替代，八图计划只作参考。 |

## 图件怎么组织

优先考虑六组内容，主文/补充的归属随成图效果再定，不预先锁死数量：

1. **实物平台与安装关系**：处理真实照片的裁切、背景和标注，结合CAD/URDF做准确的点位/坐标示意。照片保留真实装配关系，示意与实拍分开表达。
2. **方法图**：让读者看懂短基线航向、接收机速度、原始Doppler和机器人姿态/速度如何进入估计，以及它们之间的依赖。
3. **三个主序列**：轨迹、航向/位置误差和关键环境过程，选代表性对照；全部方法的数值另用表格或补充图承载。
4. **模块贡献与失锁过程**：配对消融解释谁起作用；时间曲线解释何时有效、失锁和恢复发生了什么。
5. **横向比较**：把比较方法、输入、误差和有效输出联系起来。严格OiSAM与分段OiSAM有各自结果；无自行估计姿态的方法不画成有航向成绩。
6. **TIM与新记录补充**：输入时间关系、测量链及已有不确定度证据；NMB长缺测、XB初始化结果可用于展示实际适用条件。

每张图交付可编辑矢量PDF/SVG、预览PNG、绘图脚本和简洁图注，来源索引记录数据表与方法映射。图内只放读者需要的科学信息；日志、提交号、绝对路径放在图外索引。按最终栏宽实际查看可读性。

## 新窗口需要保留的几个事实

- BY2用于参数开发；BY2H/BY2O沿用数值参数。原V3矩阵不因这次画图而改动。
- 当前研究实现融合接收机位置形成的短基线航向，并未提出新的整数模糊度固定算法。GPS主线可讨论航向可用条件与运动辅助效果。
- 新数据中4段NMB已完成最终8次运行，长GNSS缺测伴随很大位置漂移；4段XB依照现有规则无合法初始双固定航向。它们有实际用途，但不是新的良好精度验证。
- NMB长缺测期间辅助更新的调度依赖是已发现的解释线索，尚未完成受控因果验证；这次换窗口没有启动修复实验。
- FGO、RTKLIB、动基线、LC01等按最新运行索引取数，误差较大也按实际展示。不要把输入层次不同的成绩直接写成同输入求解器排名。
- 方法名称尚可讨论；当前文稿标题为“融合短基线航向与机身运动信息的四足机器人GNSS/INS组合导航”。图例以读者能理解的名称为准，内部编号留在来源映射。

## 画图完成后如何交给写作窗口

提供最终图目录、每幅图的一句话结论与图注、对应结果表、主图/补充图选择，以及中文R5底稿。写作时围绕这些图重写引言、结果和讨论，使每项贡献都有直接证据；GPS Solutions先形成完整主稿，TIM另围绕测量证据组织。

原始数据、科学输出与大图文件留在现有数据盘；绘图脚本、图注和简短索引按小块提交GitHub即可。本次没有创建新的压缩包，也没有开始其他窗口。

## 已核验的直接曲线源

以下数据路径本次已核实存在。`<G_PROJECT>`指本机项目数据根；Windows为G盘项目目录，WSL为其/mnt/g挂载。

原V3三个主序列的逐历元误差根：`<G_PROJECT>/clean_rebuild_202607/stages/CLEAN8_PROTOCOL_V3/04_EVALUATION/`。

- BY2：`RUN_00004/v3/FROZEN_EVALUATOR/error_series.csv.gz`
- BY2H：`V3R_CONTINUATION/SEQUENCE_BY2H_F04/v3/FROZEN_EVALUATOR/error_series.csv.gz`
- BY2O：`V3R_CONTINUATION/SEQUENCE_BY2O_F04/v3/FROZEN_EVALUATOR/error_series.csv.gz`

三者均含time、N/E/U误差、水平/三维误差、roll/pitch/yaw误差及3σ字段。含3σ字段并不自动证明不确定度已校准，使用时按实际量解释。

仓库 `docs/paper_rebuild/JOURNAL_REFRAME_20261004/figures/` 下已有可复用的数值副本：

| 子目录 | 已存内容 |
| --- | --- |
| `block_01/data/` | 原V3/LC01三序列曲线、`natural_all_33.csv`与`curve_support.csv`。 |
| `block_04/data/` | RTKLIB V0/V0E/V1/V2三序列逐历元航向和12条件指标。 |
| `block_06/data/` | 最终EXT V2九组合指标及三序列全窗逐历元结果。 |
| `block_07/data/` | 分段FGO的36行指标、九组主要误差，另有旧严格OiSAM身份表。 |
| `block_08/data/` | 分段FGO九份GNSS1轨迹及OiSAM自行估计航向/状态。 |

这些目录用于取数和复用脚本。严格OiSAM与分段结果分开，FGO轨迹点与原V3轨迹点按各自定义表达。
