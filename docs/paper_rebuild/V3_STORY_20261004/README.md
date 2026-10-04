# LegSA-GINS：原 V3 全量实验故事

本目录解释已经完成的原V3全部6,468个任务；不更改、不纠错、不重跑原矩阵。正式论文方法名为LegSA-GINS，内部配置编号只供证据追溯。原科学freeze7d43b9af…与执行binary96ae436d…保持；2026-10-04其他实验身份分开列述。

首先阅读 [完整任务与指标总览](01_FULL_TASK_LEDGER.md)。全量账本 [tasks](TASK_LEDGER.csv.gz)、[metrics](METRIC_LEDGER.csv.gz)、[native actions](NATIVE_ACTION_LEDGER.csv.gz)采用逐字节无损gzip；[校验与便捷读取](read_ledger.py)支持`--verify`、选列和全行输出。原配置模型、案例、方法映射和53项文件来源见总览。

- [全量注册/数值/配置核对](REGISTRY_VALIDATION_RECEIPT.json)、[无损封装](LOSSLESS_LEDGER_PACKING_RECEIPT.json)。
- [真实阅读声明](READ_COVERAGE.csv)：完整机器核对、实际语义阅读和同blob继承分开记录。
- [可审查读取器](build_story_ledger.py)：参数化的同一读取逻辑，仅读取已有记录与配置，生成本目录派生账本。此次实际执行的外部helper/hash另在封装收据中保留；参数化副本没有冒充此次执行源码。

后续配置→方法→实验结论和横向公平性故事将按独立小块追加。本目录的自然/控制故障数值相对商用融合参考，不将其称为独立ground truth，不将失败/未调用槽置零。
