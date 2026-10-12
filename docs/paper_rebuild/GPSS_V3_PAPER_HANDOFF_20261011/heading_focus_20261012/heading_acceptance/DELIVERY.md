# 本轮方向接受层与图 5 交付

正文图：`F05_heading_error_comparison.pdf` / `.svg` / `.png` / `.tiff`。
直接预览：`preview/F05_heading_error_comparison.png`。

- `AUDIT_REPORT_ZH.md`：原文要求、已实现部分、工程补充和结果。
- `CAPTIONS_ZH_EN.md`：双语图注、子图读法、正文结论边界。
- `PLAN_LOCK.json`：GitHub 提交 6a1e536 后才执行的固定方案。
- `acceptance.py` / `test_acceptance.py`：参考无关的接受层，21 单测通过。
- `run_acceptance.py`：先全部生成 mask 并封存，再连接保存误差的两阶段执行器。
- `ACCEPTANCE_FULL_HISTORY.csv`：10446 条完整历史，2484 接受、4988 ratio 拒绝、2974 原生无效。
- `ACCEPTANCE_SEAL.json`：生成全部 mask 后、读取保存误差前的封存。
- `ACCEPTED_ERROR_SERIES.csv`：9210 条评价窗记录，原估计和新增筛选后估计同时保留。
- `ACCEPTANCE_SUMMARY.csv`：六组原始/筛选后共 12 项摘要。
- `COMMON_SUPPORT_COMPARISON.csv`：78 行按精确时间 key 的两两共同支持，包括全部 RTKLIB 变体与 DD-KF。
- `ALL_DIRECTION_ROUTE_METRICS.csv`：本文方向、RTKLIB 四配置、C-LAMBDA / C-WLS 原始与筛选后、DD-KF 固定输出的完整配表。
- `WINDOW_DECISION_COUNTS.csv`：按序列/方法的完整评价窗状态计数。
- `qa/`：最终对齐通过、最小字号 8 pt、PDF 碰撞 0 fail / 0 warn。源审计两个 WARN 已核实：静态解析把 `174/25.4` 误读为 174 英寸，实际 PDF 宽为 174 mm；`dropna` 只在评分时排除无参考值，前后输出数/评分数分别保留在完整配表。实际成图逐面板检查完成。

正文展示的 RTKLIB 为预先确定的默认 V0，没有按参考表现从四配置中选最佳。其余三配置进入完整配表。失败状态不占正文大幅面；全部分母和失败保留配表。本轮没有重新运行原始载波/导航求解器，没有修改冻结 V3。

GitHub 归档时排除 `*.pdf.txt`（本地原文提取全文）和 `__pycache__/`。不复制原生 EPOCH_EVIDENCE 大载荷；其路径、身份和 SHA256 已在封存记录中保存。

最终图实际检查：所有小窗/全窗的时间窗有明确含义；主时序局部放大采用相邻独立轴，未覆盖输入大异常；ECDF 精度主轴到 15°，完整尾部由内嵌图保留到 180°；同色 C-LAMBDA / C-WLS 以淡虚线与实线区分原始和新筛选，原始值未删除。内嵌 ECDF 是同一个完整分布的尺度切换，纵轴同为 0–1。
