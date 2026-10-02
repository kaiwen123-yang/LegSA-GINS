# 已取得的横向结果

既有横向结果读取已完成：CLEAN4/CLEAN7，以及 HX02、HX02E、HX03/R2、HX05、HX07/R 的全部登记方法、运行和评价记录均按原版本保留。下面是阅读入口；结果表全文读取与大载荷仅定位严格分开。

先读 [EXT01/EXT02 结果与诊断说明](existing_clean/EXT01_EXT02_EVIDENCE.md)，再打开 [完整源字段索引](existing_clean/EXT01_EXT02_INDEX.csv) 和 [小型原表副本](existing_clean/ext01_ext02_sources/)。本批完整解析 14 JSON、22 CSV（32,191 数据行）、3 份报告，另外 3 份大型诊断仅确认原位存在。每方法全部 1,509 个原生历元和全部失败均保留，不把历元数说成进程数。

EXT01 R2 返回 1,077 个带搜索证书的整数候选、432 个无结果；EXT02 返回 1,057 个 wrapped 解、452 个失败。证书及算法返回不等于正确固定率。原 trace 航向 RMSE 约 120°，两份旧诊断时间支持不同，不能直接作为共同支持比较。旧 `UNSUPPORTED` / `PASS_*APPLICABILITY_RESULT` 原词保留，但不借名称宣布本轮已查明大误差原因。

历史 fractional-DD 诊断不能单独证明硬件偏差：后续已存在的 `docs/paper_rebuild/hext/DG01R/DG01R_REPORT.md` 记录了接收机时钟/卫星时刻建模影响。该离线诊断使用的成品位置不作为本轮算法输入。本轮将在三方法的原始码/载波功能模型中核查对应项，不从参考拟合偏差。

旧 V3 的 `UNAVAILABLE` 只代表当时版本；不能替代后来 HX02/HX05/HX07R 的记录。HX02/HX07R 首批全表已取得，其余阶段按原版本追加，而非挑最好值覆盖旧表。

物理入口：`<CLEAN_ROOT>/stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON`。具体源路径、字段、读取深度和 recorded hash 属性见索引；绝对路径在 ignored 根配置与 `<EXT_REPRO_ROOT>/existing_clean.local.csv`。本批无 native、provider、evaluator 调用，无新增性能计算。

## HX02 与 HX07R 全方法/变体首批

[读取说明与四变体三序列数字](existing_hx/HX02_HX07R_FIRST_READ.md) 已交付；[完整字段索引](existing_hx/HX02_HX07R_FIRST_INDEX.csv) 包含 629 条表/运行/评价记录。HX02 主表 480 行、24 原生运行，HX07R 12 次原生运行和 13 份评价（包含 V0-convbin 额外评价），各自失败及低覆盖保留。实际根分别是 `<CLEAN_ROOT>/stages/CLEAN9_EXTERNAL_COMPARISON/HX02_FIVE_CATEGORY` 与 `.../HX07R`，是可直接打开的归档目录，不需要解压 ZIP。

HX07R 的 V0/V0E/V1/V2 独立保留，不按最小 RMSE 选真值。HX02 原生 `COMPLETED` 与内部 `UNSUPPORTED_*` 两层状态也同时保留。`.pos` 和 heading 载荷本批仅核位置，评价结果 JSON 已完整读取。更多分段和补表由随后总收集补齐。

## 完整横向阶段入口

- [CLEAN4/CLEAN7](existing_clean/CLEAN4_CLEAN7_OVERVIEW.md)：完整已读83 CSV、168 JSON、21正文；CLEAN7 14个新native身份、28个最终评价槽，包含1个发散和不同评价处置。源表与小型副本见 [索引](existing_clean/CLEAN4_CLEAN7_INDEX.csv)。EXT01/02首批另计，不能将重复视图行数加成运行数。
- [EXT03旧实现全模式](existing_clean/EXT03_EVIDENCE.md)：10个旧模式、15090原生历元及7968失败均已读；主模式GPS/BDS、0.010m长度伪观测为609/1509有效、105 ratio-fixed。旧PASS不代表解决了输入模型问题。
- [HX七阶段](existing_hx/EXISTING_HX_README.md)：674个RUN目录（含复用与仅评价身份）、1040评价或资格门、83已全文读取源表。直接读 [运行视图](existing_hx/EXISTING_HX_RUNS.csv) 与 [结果索引](existing_hx/EXISTING_HX_INDEX.csv)。HX03R2保留36原生发散，360有限；R1的审计不可用不替代R2。
- [精确归档成员](existing_clean/LINKED_ARCHIVE_INDEX.csv)：三个被来源明确引用的handoff包只读12个小成员；CLEAN4绘图ZIP只读catalog。归档目录、ZIP成员和全文读取不是一个状态。
- [后续完整输入入口](existing_hx/INPUT_LOCATIONS.csv)：BY2/BY2H/BY2O完整原始配对1509/1483/2231。BY2H旧1423compact不能冒充完整历史，后续新缓存从保留的完整UBX构造。

实际原结果根仍为上述CLEAN4/CLEAN7及 `<CLEAN_ROOT>/stages/CLEAN9_EXTERNAL_COMPARISON/<阶段>`。本地真实路径索引在 `<EXT_REPRO_ROOT>/existing_hx.local.csv`、`existing_clean.local.csv`。完整工作转录在 `existing_hx_full/` 和 `collection_detail/existing_clean/`，公开索引保留全部运行/评价及源入口，避免上传大量重复控制JSON和逐历元副本。未发现所选主结果元数据缺失；未读大载荷、释放或失败未生成仍按各原记录说明，不能外推成所有历史文件均已验证。

本收集阶段没有任何新科学运行或性能重算。下一项是已授权的三篇方法实现与真实运行，不需要重复本库存。
