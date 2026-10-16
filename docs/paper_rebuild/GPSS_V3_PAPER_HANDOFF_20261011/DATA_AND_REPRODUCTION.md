# 数据、图件与再生成依赖

## Git 中已保存

全部 15 组图的彩色预览与 PDF、双语图注、逐图读法、结果组织、82 项目录化结果/诊断表、比较与方法索引、源文件来源元数据，以及已有绘图脚本。可在 GitHub 直接阅读，不依赖本地磁盘才能看图。

`figures/` 和 `records/` 保存本轮已有文件的副本。CSV、JSON、PDF、PNG、Python 文件保持源文件字节；本目录的 .gitattributes 对证据快照关闭换行转换，保留嵌入日志/配置的空白；Markdown 仅转换阅读链接并添加当前/历史状态说明。`FIGURE_INDEX.csv` 和 `TABLES.md` 提供可移植入口，原 `FIGURE_CATALOG.csv`、`TABLE_CATALOG.csv` 保留当时的来源路径。

## 本地完整资产

- 当前全套图：`G:/LegSA-GINS-project/V3五问题论文组图_20261011`。
- 结果恢复：`G:/LegSA-GINS-project/V3研究记录梳理_20261011`。
- M1/M4 的初始两组图与原绘图输入：`G:/LegSA-GINS-project/V3论文组图_20261008/focused_20261011`。
- 早期组图及样式来源：`G:/LegSA-GINS-project/V3论文组图_20261008/redesign_20261009`，以及原 Git 工作区 `docs/paper_rebuild/GPSS_V3_FIGURES_20261008/redesign_20261009`。
- 科学结果根：`G:/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN8_PROTOCOL_V3`，具体留存范围及原始身份见 [V3 总账](../V3_STORY_20261004/CURRENT_STORY_INDEX.md)。

600 dpi PNG、SVG、灰度预览、大时序 `.csv.gz` 及本地 HTML 图册继续留在这些目录，Git 中不重复存放。逐文件去向见 [ARTIFACT_STORAGE.csv](ARTIFACT_STORAGE.csv)。这份交接支持检查和继续论文工作；仅克隆本分支不等于下载了全部科学数据，也不保证每张图无需外部路径即可重新生成。

## 用户指定的参考映射

- by1（论文中的单侧天线遮挡，内部 BY2O）：`G:/LegSA-GINS-project/data/raw/BY2_BY3/2026-03-06/fixption数据/2026.3.6/by1/vrtk2_a87c6e_2026-03-06-07-52-22_minimal/trace_vrtk2_a87c6e_2026-03-06-07-52-22_minimal.csv`。
- by3（论文中的大幅机身运动，内部 BY2H）：`G:/LegSA-GINS-project/data/raw/BY2_BY3/2026-03-06/fixption数据/2026.3.6/by3/vrtk2_a87c6e_2026-03-06-08-06-39_minimal/trace_vrtk2_a87c6e_2026-03-06-08-06-39_minimal.csv`。

这两个是作者指定的参考文件；Fixposition 来源及共享 GNSS 相关性仍需在评价方法中解释。原始参考数据保持在本地，不作为导航算法输入。

## 绘图代码

本次保存的 Python 是原生成过程的代码快照，没有执行科学链，也没有为了归档重新计算指标。`figures/robot`、`heading`、`navigation`、`aiding/plot_code` 中有各组绘图代码；复用 M1/M4 的脚本和样式另放在 `plot_sources/`。部分脚本仍含原 WSL/G 盘绝对路径及图形检查工具依赖，再生成前需按存储清单配置数据路径与依赖。

原环境是 Ubuntu-22.04 WSL，使用 Python、NumPy、pandas、Matplotlib、PyMuPDF 等。图中局部放大使用原生 `Axes.inset_axes`；旧环境混装的 `axes_grid1` 曾不兼容。交接没有将环境快照冒称为一键复现实验包。

## 版本和工作区

原有研究工作区：`/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001`，采集时 HEAD `76807b652c85326e66d301a30429d9f7cd614285`，另有未提交研究改动。

本次文档独立工作区：`/home/kaiwen/research/LegSA-GINS-WORKTREES/v3-paper-handoff-20261011`；分支 `docs/v3-paper-handoff-20261011`，从 GitHub `main` 的 `077fb725612730d743ff1dd3ba698c43499b4fcb` 建立。它只提交论文交接，不携带研究分支额外提交或其他工作区修改。
