# 固定 1191 窗口的物理弧支持审计

授权：新可信航向目标阶段 A；本次是保存输入的分类诊断，不是 AR/准入/导航试验。原始字节、阈值、N、Q、观测和既有结果不修改。

## 固定输入与范围

别名 `<CARRIER_INTEGRATION>` 指现有 CARRIER_INTEGRATION_20261006 scratch 根；`<TRUSTED_HEADING>` 指本目标的新 scratch 根，机器路径由命令行参数提供。

- `<CARRIER_INTEGRATION>/DENSE_SELECTED_FRONTEND/INPUT_CONTRACT.json`
- 同目录 `SUMMARY_0001.json` 和其登记的全部 `cases/partial_0100.00.json ... partial_0338.00.json`（窗口实际每 0.2 s，共 1191，不省略中间项）。
- `<CARRIER_INTEGRATION>/REAL_100_340_V2/PLAN.json` 中 1200 个原时键，固定 family=GPS_GAL_BDS_DUAL。
- 同目录的 `ARC_EVENTS.json`（既有接收机/信号/弧资格和原因），以及 PLAN 指定 1200 份该 family 模型 NPZ。

序列仍为 BY2 100–340 s 的开发输入，不是原 V3 三全窗效果。固定机会 start=100+i/5，i=0..1190；每窗仍是原五个选择历元加原五个未来槽，不缩短到 0.2 s。从登记 case 只采用 subset_selection 的身份、时键和 selected_labels；不以 case 的候选/准入/测量/精度状态选择窗口。

JSON 整体反序列化可能读入文件内包含的候选整数、残差与既有判定；这些字段不参与分类或统计决策。NPZ 只请求 A/B/Q，文件容器包含 y；不据此宣称 y 字节从未进入操作系统缓存。禁止打开评价参考、误差序列、NAV/STD；不调用 CILS、求解器、准入、GLRT、native 或 evaluator。

## 分类及支持上界

逐窗重现原 exact-DD-label 首次缺失。另用两个接收机的原 SD arc token、eligible 和 temporal_link_qualified 检查物理持续性；一个原节点首次失效后，本窗口内永久移除，不因同 token 后来出现而复活。

首失败原因同时保留互斥主类和多原因 flags：
1. 原物理节点均持续，且全部仍在当前模型，只是 pivot 坐标改变；
2. 原物理节点均持续，但某节点未进入当前模型资格；
3. 原 pivot 物理失弧；
4. 原 target 物理失弧；
5. pivot/target 同时失弧；
6. 缺模型/未知资格等明确未决。metadata、TDCP 和 model qualification 原因另外保留，不能把 metadata 异常断言为物理 cycle slip。

对每个原连通分量，先保留其差分关系再移除失效节点。幸存并进入当前模型的原节点可在分量内重新选规范 pivot；由当前 DD 行相减建立它们的 phase 设计行，即使当前模型 pivot 不是原已知节点也允许代数相消。不能跨原分量或新 arc 建整数关系。该步骤只计算整数关系的拓扑可识别性，不需要读取任何候选整数。

保留当前全部 code 行；phase 采用上述独立差分基。相应 U 作用于 B 和完整 Q：B'=UB、Q'=UQUᵀ。计算 phase 行数、rank、固定 N 条件下自由 baseline Cb=(B'ᵀQ'⁻¹B')⁻¹，以及相对“当前全部整数都已知”的完整几何协方差 trace/最大特征值比。后者是乐观几何参考，不是真可用算法；Cb 不是投影角误差界。若 rank 不足，指标 NA，不能伪造有限精度。

主要计数：全部 1191 窗口首失败分类；全五槽均满足 phase≥4、rank=3 的条件支持窗口数；原标签失败但条件剩余几何仍满足的窗口数；过去选择及最后未来槽的组分布。此数是理论支持上界，**不是重新准入率、正确固定率、可融合测量数或导航改善**。不根据结果重新选择 N/子集/窗口。

## 输出与执行边界

只运行一遍审计脚本；保存每个窗口，包括失败，原文件不覆盖。
- tracked：ARC_SUPPORT_AUDIT_RESULTS.csv、ARC_SUPPORT_AUDIT_SUMMARY.json、ARC_SUPPORT_AUDIT_REPORT.md。
- scratch：原输入身份/机器路径、逐窗口五槽详情 JSONL.gz、状态与错误记录。
- 记录 script SHA、当前 commit、输入合同/PLAN 身份；不重新 hash raw。
- 本次搜索/准入/GLRT/native/evaluator/reference 调用预算均为 0。
- 审计完成与有效支持的事实分开；技术异常单列，不能当原算法失败。
