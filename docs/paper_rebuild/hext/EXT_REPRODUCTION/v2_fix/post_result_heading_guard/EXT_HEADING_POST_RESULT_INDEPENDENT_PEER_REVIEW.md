# EXT后置航向保护：独立交叉审查

结论：本轮数值保护和失败有效性修正通过，无阻断缺陷。它是旧9组横向复现和135组回放完成、独立验收并释放源码冻结之后的单独源码修正；没有改写旧输出或把新源码回贴为旧执行身份。本次不运行真实solver/evaluator，不读取raw reference，不改源码。

## 数学及失败合同

当前ext01_clambda.py:994–1024使用先按最大分量缩放后的rho²=(bN²+bE²)/||b||²，与长度单位无关，拒绝零向量和rho²≤1e−12的近垂直方向。跨1e−150、0.01、1、1e100倍比例的边界测试证明该门不会变成米平方阈值。它是明确的数值投影支持策略，不能据此宣称实际航向精度或噪声门限已标定。有效投影仍保留旧符号及固定+90°合同；非零滚转/俯仰下，投影基线航向一般不等于Euler yaw。

reproduction_runner.py:110–124在转换失败时显式回退valid=false、solution_state=INVALID、body_yaw_deg=null，保留已得到的candidate/certificate/3D baseline作为求解证据，不产生仍valid但缺少航向的假结果。EXT03通过ext03_yang2024.py:954–963调用同一数值门；既有reproduction_ext03.py:283–352在process_epoch异常未返回时保持state_updated=false、空航向和原先成功状态，runner:270据此判无效。内部进度仍是UNKNOWN，不虚构已经完成的KF/MLAMBDA状态。

## 独立实际检查

- 本审查者在Ubuntu-22.04独立执行现有19项小测试，19 passed in0.33s、0skip；保存EXT_HEADING_GUARD_INDEPENDENT_PEER.xml。作者执行的75项bounded测试及红版11失败/8通过保留在独立身份收据；本审查没有把它们写成自己另执行75项。
- 独立读取旧9组全部HEADING和EPOCH记录：15,669条、9,100有效、6,569无当次published baseline的无效记录；另1,786个EXT03已发布float/fixed姿态。用独立math公式核验，不调用项目转换函数作为oracle。有效/内部已发布向量新门触发0，最大角度差5.684341886080802e−14°。所有无效记录空航向，不推断它们未暴露的内部求解向量。
- 旧9个RUN、保存源码、HEADING及EPOCH载荷封存hash前后相同；旧135的PREREGISTRATION/ALL_NATIVE_SEALED/CORRECTED_RESULTS和全部928保存源码snapshot继续匹配原pin。当前3个合法源码变化属于新身份，不能判成旧结果漂移。928是身份覆盖，不是逐行语义审核或实际执行范围。
- 75项回归和non-trigger是有限边界证据，未重跑旧9或135，不证明新solver全路径的反事实结果、作者全部实验、标定后的实用航向精度或独立绝对精度。

## 后续交付文案

完整只读最新finalize_root_delivery.py:1–160，SHAf3558afd1ee0c5a5046ce6c6f52fdf08096a9489b7ed94d48e3bd059b147b999；D61均值、135验收、928保存身份、1改善44更差及fault dispatch限制转录准确，三个旧needle exact1 gate闭合。新增guard精确数量门与稿件最终binding receipt转录保持submission_ready=false及材料/标定/参考/Word缺口。本审查未执行writer。ROOT后来实际渲染两页PDF的增补单独归属ROOT，本审查旧PDF_NOT_RENDERED收据保持真实。

证据为同目录EXT_HEADING_POST_RESULT_INDEPENDENT_PEER_REVIEW.json、两个独立saved-output/internal JSON、独立测试XML及read coverage CSV。人工FULL仅限覆盖CSV明确标注的文件；载荷和928源码hash遍历不冒充逐字人工审核。
