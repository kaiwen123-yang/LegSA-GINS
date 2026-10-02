# 已取得的横向结果

当前批次已完成 CLEAN4 的 EXT01 R2 与 EXT02 原生及 proxy 关联恢复版本。其余 CLEAN4/CLEAN7/HX 阶段正在沿已有入口读取；未在本页交付前不计作取得。

先读 [EXT01/EXT02 结果与诊断说明](existing_clean/EXT01_EXT02_EVIDENCE.md)，再打开 [完整源字段索引](existing_clean/EXT01_EXT02_INDEX.csv) 和 [小型原表副本](existing_clean/ext01_ext02_sources/)。本批完整解析 14 JSON、22 CSV（32,191 数据行）、3 份报告，另外 3 份大型诊断仅确认原位存在。每方法全部 1,509 个原生历元和全部失败均保留，不把历元数说成进程数。

EXT01 R2 返回 1,077 个带搜索证书的整数候选、432 个无结果；EXT02 返回 1,057 个 wrapped 解、452 个失败。证书及算法返回不等于正确固定率。原 trace 航向 RMSE 约 120°，两份旧诊断时间支持不同，不能直接作为共同支持比较。旧 `UNSUPPORTED` / `PASS_*APPLICABILITY_RESULT` 原词保留，但不借名称宣布本轮已查明大误差原因。

历史 fractional-DD 诊断不能单独证明硬件偏差：后续已存在的 `docs/paper_rebuild/hext/DG01R/DG01R_REPORT.md` 记录了接收机时钟/卫星时刻建模影响。该离线诊断使用的成品位置不作为本轮算法输入。本轮将在三方法的原始码/载波功能模型中核查对应项，不从参考拟合偏差。

旧 V3 的 `UNAVAILABLE` 只代表当时版本；不能替代后来 HX02/HX05/HX07R 的记录。HX02/HX07R 首批全表已取得，其余阶段按原版本追加，而非挑最好值覆盖旧表。

物理入口：`<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON`。具体源路径、字段、读取深度和 recorded hash 属性见索引；绝对路径在 ignored 根配置与 `<EXT_REPRO_ROOT>/existing_clean.local.csv`。本批无 native、provider、evaluator 调用，无新增性能计算。

## HX02 与 HX07R 全方法/变体首批

[读取说明与四变体三序列数字](existing_hx/HX02_HX07R_FIRST_READ.md) 已交付；[完整字段索引](existing_hx/HX02_HX07R_FIRST_INDEX.csv) 包含 629 条表/运行/评价记录。HX02 主表 480 行、24 原生运行，HX07R 12 次原生运行和 13 份评价（包含 V0-convbin 额外评价），各自失败及低覆盖保留。实际根分别是 `<CLEAN_ROOT>/stages/CLEAN9_EXTERNAL_COMPARISON/HX02_FIVE_CATEGORY` 与 `.../HX07R`，是可直接打开的归档目录，不需要解压 ZIP。

HX07R 的 V0/V0E/V1/V2 独立保留，不按最小 RMSE 选真值。HX02 原生 `COMPLETED` 与内部 `UNSUPPORTED_*` 两层状态也同时保留。`.pos` 和 heading 载荷本批仅核位置，评价结果 JSON 已完整读取。更多分段和补表由随后总收集补齐。
