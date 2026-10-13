# 图 3 数据来源与物理点

实际绘图源的逐场景、逐方法路径及完整有效点数见 [MAIN_TRAJECTORY_SOURCE_MAPPING.csv](data/MAIN_TRAJECTORY_SOURCE_MAPPING.csv)。本轮直接读取 R3/R4 已核验坐标，不复制大数据、不重跑求解。

| 用途 | 已核验来源 |
|---|---|
| 本文、四个 IEKF 配置、TC/GNC、参考轨迹 | `G:/LegSA-GINS-project/V3正文精修_20261012_R3/navigation/data/{scene}__{method}.csv.gz` |
| 重新初始化 OiSAM 的 POI 轨迹 | `G:/LegSA-GINS-project/V3正文精修_20261013_R4/navigation/data/{scene}__OISAM_RESTART_POI.csv.gz` |
| OiSAM 自身姿态 / 杆臂变换核验 | `G:/LegSA-GINS-project/V3正文精修_20261013_R4/navigation/data/OISAM_POI_TRANSFORM_CHECKS.json` 和同目录 `prepare_oisam_poi.py` |
| 全部 52 条坐标身份原始出处、支持与去向 | `G:/LegSA-GINS-project/V3正文精修_20261013_R4/navigation/data/ALL_METHOD_DESTINATIONS.csv`；本目录保存轻量去向索引 |
| 全部 36 条方法登记、执行与原文证据 | `G:/LegSA-GINS-project/V3正文精修_20261013_R4/navigation/data/ALL_REGISTERED_METHOD_DESTINATIONS.csv`；本目录保存轻量去向索引 |
| 49 个原始坐标来源及恢复校验 | `G:/LegSA-GINS-project/V3正文精修_20261012_R3/navigation/data/COORDINATE_SOURCES_READ.csv`、`COORDINATE_PARITY_CHECKS.csv`、`COORDINATE_PROTOCOL.json` |
| 原 GNSS1 三方法、三场景定位摘要 | `G:/LegSA-GINS-project/V3正文精修_20261012_R3/navigation_comparison/METHOD_POSITION_TABLE.csv` 与同名 `.md`；完整 36 条结果在其 `data/FGO_GNSS1_ALL36_RESULTS.csv` |
| 原 GINav 部分输出补图 | `G:/LegSA-GINS-project/V3正文精修_20261012_R3/navigation/preview/S11_GINav_partial_trajectories.png` |
| 原相对方法原生坐标补图 | `G:/LegSA-GINS-project/V3正文精修_20261012_R3/navigation/preview/S11_native_relative_trajectories.png` |
| 原图 11，现留补充 / 历史来源 | `G:/LegSA-GINS-project/V3正文精修_20261012_R3/navigation/preview/F11_full_trajectory_comparison.png` |
| 遮挡近静止与恢复运动诊断 | `G:/LegSA-GINS-project/V3正文精修_20261013_R4/navigation/OBSTRUCTION_REFERENCE_MOTION.csv`、`OBSTRUCTION_DIAGNOSIS.json` |
| 同时间 SDK 低速旁证 | `G:/LegSA-GINS-project/V3正文精修_20261013_R4/navigation/OBSTRUCTION_SDK_CORROBORATION.md`、同名 `.json` / `.csv` |

`scene` 为 `BY2`（常规）、`BY2H`（大幅机身运动）、`BY2O`（遮挡）。`method` 为 `REFERENCE_POI`、`F04`、`LC01`、`LC01-S`、`EXT05C`、`EXT05C-S`、`WEN_TC` 或 `GNC`。这些内部身份只用于追溯，不用作图内场景名。

POI 局部的各方法共用一个参考位置原点。原点取固定局部时间窗中点：90 s、90 s 和 230.5 s；仅扣除同一个二维地理原点并将 m 转成 cm。前两条局部 88–92 s，第三条 228–233 s，沿用 R4 已登记窗口。全路线保留各自原生支持，TC/GNC 为 GNSS1 点，其他主方法与 Truth 为 POI。

100 s 背景段中的圆 / 方标记为落在规定窗口内的首 / 末有效参考样本，而非新的起停事件。局部矩形是右侧真实空间视窗在全路线中的投影。全部窗口、实际源点包络和最终视窗范围见 [LOCAL_EXTENTS_AND_WINDOWS.csv](data/LOCAL_EXTENTS_AND_WINDOWS.csv)；每个实际绘图层的源点数见 [SOURCE_POINT_COUNTS.csv](data/SOURCE_POINT_COUNTS.csv)。
