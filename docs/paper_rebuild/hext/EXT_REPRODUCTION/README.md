# EXT01 / EXT02 / EXT03 文献复现与横向结果

本任务接续 `8fdcfd2f0742be00e84bbab2450cbe849b401f1b`，保留原 V3、旧横向运行与全部失败。先取得既有结果，再补足三种文献方法的实现和三序列运行；本页随完成的小项更新，不代表所有队列已完成。

- [既有横向结果入口](EXISTING_COMPARISON_RESULTS.md)：已读的结果、版本和保留边界。
- [既有结果索引](EXISTING_COMPARISON_INDEX.csv)：文件/结果身份；细节进入分组索引。
- [论文与实现依据](REPRODUCTION_NOTES.md)、[输入核对](INPUT_PREPARATION.json)、[运行队列](RUN_QUEUE.csv)。
- [进度](PROGRESS.md)：每批完成范围、调用与提交状态。
- [论文包成员索引](PAPER_PACKAGE_INDEX.csv)：本机 34 个 PDF 成员、29 个字节唯一文件；字节读取与全文阅读分开登记。论文原件不提交。

公共路径使用别名。机器上的 `configs/paper_rebuild/EXT_REPRODUCTION_ROOTS.local.json` 是 ignored 根映射，`<EXT_REPRO_ROOT>/existing_clean.local.csv` 等本机镜像给出可直接打开的真实路径。旧结果主要在 `<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON`、`CLEAN7_HEXT_EXTERNAL_SEQUENCES`、`CLEAN9_EXTERNAL_COMPARISON`。新运行只进入 `<EXT_REPRO_ROOT>`，编译和论文缓存进入 `<EXT_REPRO_BUILD>`。

原 V3 的完整导航、文献方法的基线/航向和其他方法的相对位姿分别解释；未保存或无此输出的指标不填零。参考仅离线评价，固定判定不是已知整数正确性。

执行入口：`PYTHONPATH=src OPENBLAS_NUM_THREADS=1 python3 scripts/paper_rebuild/run_ext_reproduction_batch.py --roots configs/paper_rebuild/EXT_REPRODUCTION_ROOTS.local.json --config configs/paper_rebuild/horizontal_literature/EXT_REPRODUCTION_V1.json --sequence BY2`（另两个序列仅替换sequence）。输出目录存在即拒绝，不自动续跑或覆盖；技术重试需明确独立attempt。单方法模块 `horizontal_literature.reproduction_runner` 供定向复查。所有原始NAV/参考只读，新基线/ambiguity/状态证据在新运行根，不上传raw。
