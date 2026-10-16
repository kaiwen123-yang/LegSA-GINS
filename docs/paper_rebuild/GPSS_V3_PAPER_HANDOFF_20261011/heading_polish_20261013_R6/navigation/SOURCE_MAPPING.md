# 图 3 数据索引

本轮复用既有已核验坐标和共同航向时序，不复制旧数据集。

| 内容 | 源路径 |
|---|---|
| Truth / 本文 / 四种 IEKF / TC-FGO / GNC-FGO 坐标 | `G:/LegSA-GINS-project/V3正文精修_20261012_R3/navigation/data/{scene}__{method}.csv.gz` |
| 重新初始化 OiSAM 的 POI 坐标 | `G:/LegSA-GINS-project/V3正文精修_20261013_R4/navigation/data/{scene}__OISAM_RESTART_POI.csv.gz` |
| 六方法共同航向时序 | `G:/LegSA-GINS-project/V3正文精修_20261012_R3/navigation_comparison/data/{scene}_COMMON_HEADING.csv.gz` |
| OiSAM POI 转换证据 | `G:/LegSA-GINS-project/V3正文精修_20261013_R4/navigation/data/OISAM_POI_TRANSFORM_CHECKS.json` |
| 全部 52 条坐标身份去向 | `G:/LegSA-GINS-project/V3正文精修_20261013_R4/navigation/data/ALL_METHOD_DESTINATIONS.csv` |
| 全部 36 条登记身份与原始记录 | `G:/LegSA-GINS-project/V3正文精修_20261013_R4/navigation/data/ALL_REGISTERED_METHOD_DESTINATIONS.csv` |
| GNSS1 定位误差与覆盖摘要 | `G:/LegSA-GINS-project/V3正文精修_20261012_R3/navigation_comparison/METHOD_POSITION_TABLE.csv` |
| GINav 部分轨迹 / 相对方法补图 | `G:/LegSA-GINS-project/V3正文精修_20261012_R3/navigation/preview/S11_GINav_partial_trajectories.png`；`S11_native_relative_trajectories.png` |
| 遮挡参考运动与 SDK 低速记录核验 | `G:/LegSA-GINS-project/V3正文精修_20261013_R4/navigation/OBSTRUCTION_DIAGNOSIS.json`；`OBSTRUCTION_SDK_CORROBORATION.md` |

`scene` 为 BY2、BY2H、BY2O。`method` 为 REFERENCE_POI、F04、LC01、LC01-S、EXT05C、EXT05C-S、WEN_TC 或 GNC。图内使用论文场景名和方法名，不暴露这些内部编号。

空间窗沿用 R4 的时间选择，原点取参考在 90 / 90 / 230.5 s 的位置；所有方法扣除同一原点并以 cm 表示。固定近景框可以裁去框外轨迹，但没有移除原始数据或改写支持；全路线显示各方法完整的原生有效输出。TC/GNC 的 GNSS1 点不混入 POI 近景。航向时序保留实际共同支持，不补造缺失航向。
