# V3 论文当前入口

最新作者轮次：2026-10-13正文精修R4。

- [正文十图与本轮解释](docs/paper_rebuild/GPSS_V3_PAPER_HANDOFF_20261011/heading_polish_20261013_R4/FIGURE_READERS_ZH.md)
- [状态与高清图2入口](docs/paper_rebuild/GPSS_V3_PAPER_HANDOFF_20261011/heading_polish_20261013_R4/README.md)
- [图4七条运行的原始来源审查](docs/paper_rebuild/GPSS_V3_PAPER_HANDOFF_20261011/heading_polish_20261013_R4/observability_audit/README.md)

原图11与图3合成完整路线、POI空间细节、100s航向误差一组。图1/4/5/6/7/9/10图面保持通过版；图2保留原构图，提供7680px及矢量放大阅读。图8不再堆三例，而解释同一退化回放中的输入不一致、来源协方差调整与航向结果，同时保留位置代价和全部总体结果。

必须继承的纠正：图4是一种接触辅助InEKF、一次记录、七种初始全局朝向（H5主运行+六H6原生回放）；不是七算法或七次实测，逆旋转后重合是预期性质。图8支持条件性稳健收益，不支持普遍提升典型航向精度。遮挡原局部是参考近静止，与SDK低速读数一致；不将弱辅助当独立运动真值。

科学问题仍以紧凑四足平台的短基线方向与机身观测互补为核心，主打航向精度。冻结V3为7d43b9af26120ed5dde21f53e515386361072ba6。本轮无新原生求解、provider或冻结评价器执行。下一步先讨论新图3/8，再决定正文最终篇幅。
