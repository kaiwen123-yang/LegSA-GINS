# EXT 后结果修复：未定义投影航向与有效标志

已修复纯竖直/数值近竖直基线产生90度假航向，以及独立runner在转换失败后留下valid=true的真实错误。此修复发生在旧EXT九组与135 V3子集最终独立封存之后，使用新的后结果源码身份，没有再运行旧九组或135估计器/评价器，也没有重写它们的源pin、成绩或输出。

## 数学与输出合同

当前输出仍为固定横向基线的水平投影角加90度，保持原角度返回约定与合理倾斜投影；不是一般非零roll/pitch时的Euler yaw。β=atan2(b_E,b_N)在b_N=b_E=0时数学上未定义，不能将atan2(0,0)的程序默认值当成可测航向。

新共同转换函数使用无量纲ρ²=(b_N²+b_E²)/||b||²；先按向量最大绝对分量缩放再计算比例，避免平方溢出/下溢，任意非零尺度不改变准入。零长度与ρ²≤1e−12拒绝，错误码BASELINE_HEADING_UNDEFINED。阈值不是m²的绝对水平长度门，而是数值近奇异门；不代表独立标定的实用精度/噪声门。有限projection、双fixed或STD也不能证明实际航向准确。

- `src/legsa_gins/paper_rebuild/horizontal_literature/ext01_clambda.py:994`起新增typed错误、无量纲门及共同bearing函数；body_yaw函数保持原wrap(β+90)。
- `ext03_yang2024.py:954`起复用共同bearing门，翻译为已有Yang2024Error类型/稳定错误码。原baseline长度、pitch计算与正常角度约定保持；现有adapter异常路径继续返回invalid、null yaw、不hold上次输出。
- `reproduction_runner.py:110–122`先保存已有3D baseline证据，再转换heading；捕获数值/物理输入错误时强制valid=false、solution_state=INVALID、body_yaw=null。保留candidate/certificate、solver诊断和已经计算的3D baseline，不能把heading失效误称无候选或无3D解。

## 真实回归与非触发证据

新增可重用测试位于repo `tests/paper_rebuild/test_ext_projected_heading_guard.py`，G同名85行源副本保留，SHA256 f17003ace668400c4ab5cdcd8e8cd3407436b011d0fe06c1d39cb4b53299b1bd。19例覆盖零长度、正负竖直、数值近竖直、shape/nonfinite、1e−150至1e100跨尺度、正常倾斜及旧角度约定、EXT01/02转换失败后invalid/null yaw与候选/3D证据保留。

原源码下19例有11失败/8通过；修复后19/19通过。连同既有C-LAMBDA、Yang2024和reproduction runner回归共75通过、0skip。使用原冻结RTKLIB library进行合成oracle回归；没有启动真实raw序列solver/eval。JUnit为EXT_HEADING_GUARD_RED.xml、EXT_HEADING_GUARD_GREEN.xml、EXT_HEADING_BOUNDED_REGRESSION.xml，旧失败结果没有删除或覆盖。

兼容审计独立只读遍历旧九组EPOCH_EVIDENCE的全部15,669条，逐件重新核RUN/saved-source/HEADING/EPOCH原hash前后相同：

| 对象 | 完整数 | 结果 |
|---|---:|---|
| 原payload记录 | 15,669 | 全部按epoch_index与manifest计数枚举 |
| 已发表有效最终基线 | 9,100 | 新纯转换门0触发，与保存heading最大差0 |
| 额外EXT03 float/fixed态度 | 1,786 | 原heading/body_yaw/pitch逐值完全相同 |
| 原invalid记录 | 6,569 | 全部没有当次published baseline，保存yaw为null |

已发表最终基线最小水平长度0.01981824432371024m、最小ρ²=0.0032062270046879547，远大于固定1e−12数值门。此证据证明已发表有效输出不受该后置转换门影响；不声称6,569次失败内部未记录的counterfactual求解过程在新代码重跑后一定相同。没有为方便形成一致数字重跑、拼接或改写旧失败行。

主收据`EXT_HEADING_POST_RESULT_REPAIR_RECEIPT.json` SHA256 cc7c70dccfbd454ada1d51efec26b9630613c6a470da0cc093a30002cafe27d3，all_checks_passed=true，另保留九组CSV、exact post-V2-only diff与三个before源码副本。审计helper SHA068780951e5580df836a2858060cf9244c4c14a51db43a75ac603c2886c673cc。这是SAVED_SELECTED_PAYLOAD_MACHINE_AUDIT，不是逐字人工审读15,669条结果，也不是raw数据全文语义阅读。

## 新旧身份

新后结果源码SHA256：

- ext01_clambda.py：d28604a587655623537bdf9125afc24a929388b218696829fe42c9ffd2192ede。
- ext03_yang2024.py：4d4ef06794fe9d0f51417de2162b21bead31f171908619ae0cb8acbeb465d3a4。
- reproduction_runner.py：1a2e6e5876b80ece568e18733809a7786cea32387c233c83b14df97988200095。

旧9实际执行源码与SOURCE_SNAPSHOT仍为原hash，未回贴新源。135的旧928快照逐件仍精确；相对于旧prereg928清单，current仅上述3个hext Python源有明确后结果差异，新测试不属于该928清单。最终135独立冻结释放收据9120b27e…在08:09:46.142211 UTC生效，后置修改不代表旧运行在执行过程中漂移。

只完成源码/合同边界错误修复、有效旧payload非触发证明与真实小型回归；实用近竖直噪声/不确定度门、非水平安装下的true Euler姿态与独立物理点/标定仍待验证，不能以此次门通过将它们关闭。后续新科学运行必须建立新的源码/输入/运行身份；无commit/push。
## 独立终验与可复用入口

独立peer已于2026-10-04 08:28:43.976493 UTC接受，无阻断项：`EXT_HEADING_POST_RESULT_INDEPENDENT_PEER_REVIEW.json` SHA256 4a945f84e699385ab0353de819e22089cb90ac3ca38b051348089e3efe5e51b6。peer独立执行19边界测试，并再次遍历全部15,669 saved HEADING/EPOCH记录及1,786内部态度、核验旧135的928保存快照；没有启动科学solver/eval，也没有读取raw GT。peer重新按数学式计算最大差5.68434e−14度属于浮点舍入，不改变自身纯函数与保存角度差0的原收据。

可复用repo测试及G副本位置/共同hash由独立小收据`EXT_HEADING_POST_RESULT_TEST_LOCATION_RECEIPT.json`补充绑定；没有修改已peer绑定的主修复收据。代码与测试实际位置、声明阅读范围见`EXT_HEADING_POST_RESULT_READ_COVERAGE.csv`；所有payload兼容检查明确是machine audit。新文档入口为repo `docs/paper_rebuild/hext/EXT_REPRODUCTION/v2_fix/post_result_heading_guard/README.md`。

## 可核验文件

- [主修复收据](EXT_HEADING_POST_RESULT_REPAIR_RECEIPT.json)、[独立peer验收](EXT_HEADING_POST_RESULT_INDEPENDENT_PEER_REVIEW.md)、[peer收据](EXT_HEADING_POST_RESULT_INDEPENDENT_PEER_REVIEW.json)。
- [九组非触发摘要](EXT_HEADING_POST_RESULT_PAYLOAD_COMPATIBILITY.csv)、[确切后结果diff](EXT_HEADING_POST_RESULT_ONLY.diff)、[新旧源身份](EXT_HEADING_POST_RESULT_SOURCE_CHANGE.json)。
- [可复用测试](test_ext_projected_heading_guard.py)、[测试实际位置](EXT_HEADING_POST_RESULT_TEST_LOCATION_RECEIPT.json)、[精确阅读声明](EXT_HEADING_POST_RESULT_READ_COVERAGE.csv)。
- 本目录仅后结果代码保护与审查资产；上层V2表/图仍来自原guardless执行，不以新源重绑成绩。完整before/after字节及machine audit helper保留在G修复目录；[本包复制身份](SMALL_DOCUMENT_COPY_RECEIPT.json)。
