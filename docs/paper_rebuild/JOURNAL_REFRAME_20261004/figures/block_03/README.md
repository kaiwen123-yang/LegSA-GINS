# READY 03：完整原 CORE/ADD、尾部与同输入消融

4 张宽图区图均 300dpi PNG/PDF/SVG；数值取原保存 CSV，不执行求解、评价、bootstrap 或显著性重算。

- `R05_CORE_all_11_error_tails`：原 11 配置每个 541 注册案例，完整已保存 median/p95/maximum 与 finite/541。两面板水平/航向 RMSE，log 轴保留全尾部端点。跨案例 RMSE 的 p95 不写成单次运行内误差 p95。
- `R06_CORE_single_module_paired_contrasts`：原四项严格 one-toggle 对比的全部共同有限逐案例 delta，Δ=Proposed−对应关闭模块，负值为 Proposed 较低。每项518/513/519/519，共同有限原分母541；橙菱形是原保存 paired median。不删正向 adverse cases，不拟合分布；仅竖向确定性微偏移便于看点。对称log轴保留大小量级，未删极端值。没有重新计算CI/p。
- `R07_CORE_all_5951_outcomes`：原全部5951条 CORE 按权威 `failure_classification` 计数：5668完成、193发散、90无有效航向输入；每个配置541。汇总表 status 中 `NOT_RUN_ALGORITHM_FAILURE` 是失败后未评价状态，图保留原明确失败分类，不把它当数值零或新分类。全部 run_id、matched/output 保留在列副本中。
- `R08_ADD_all_45_conditions`：原495条ADD，45条件×11配置。D61为10/20/30s×九放置，D62为10/20s×九放置，全部个体值均画出。左右面板严格区别原provider定义的全断与航向保留；不混后来135个修正诊断。均为whole-window指标，不虚称outage-only厘米精度。495原运行全部完成，不等于误差小。

科学主线：自然窗小幅变化不能单独证明模块普遍必要；原全矩阵共同支持和不利个例、长尾与失败都必须一起讨论。多个放置/半合成案例不是独立自然场地实验。common dual-heading初始化及原评价物理点边界保持。

data/ 保存原decimal列副本和全部支持/状态；BUILD_RECEIPT绑定每个原源/解压/副本/12导出hash及独立脚本。读取后原源字节不变。图分别用于**完整尾部**、**配对模块作用**、**全部失败分母**、**故障信息保留边界**四个科学问题，避免把它们挤成一张小图。最终4PNG均实际打开核查；PDF/SVG同Figure另导出，未另外渲染PDF。
