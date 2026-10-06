# Selected-observation likelihood：独立只读代码审查

审查对象：`carrier_phase/selected_likelihood.py` 与
`scripts/paper_rebuild/carrier_phase/integration_frontend.py` 的新入口。
审查期间冻结源码未修改；没有调用求解、验收、导航或参考评估。

结论：当前入口没有发现阻断。该模型明确是一套减少观测行的新似然，
不是原似然中未选整数的等价消元。以下事实由源码确认：

1. 先调用原 `preselect_partial_labels`，仅使用原 selection 窗的
   A/B/Q、标签和元数据规则；随后才构造 reduced y。保留所有 code 与
   对未选整数列严格为零的 phase 行；不根据观测残差或未来支持选行。
2. 协方差取保留行的 principal submatrix，保留交叉项；没有换成
   条件 Schur 协方差、对角近似或错误的独立频率假设。原 row/column
   对应关系另存，selected 列顺序固定，缺失/重置标签拒绝。
3. baseline 每历元仍独立，完整时间模型由原 `assemble_epochs` 构造。
   原 full-rank GLS 和跨历元 Q 支持范围检查仍由求解器执行；较小
   整数维数不能被解释成更强可辨识性或正确固定保证。
4. 求解前后的 fingerprint 覆盖实际 reduced times/lengths/y/A/B/Q、
   labels、选择时刻和 source-row 身份。freeze 检查 wrapper 的
   likelihood kind / plan fingerprint，并把两者写入候选 source_id。
5. frontend 的 selected-support 分支只允许 partial mode，保存
   likelihood、support 和 fingerprint。它冻结新模型的候选后，才读取
   原始五个 future models，使用原 admission、GLRT 和 measurement
   qualification。没有拿 reduced selection 模型替代未来观测。
6. sphere backend 是另一独立开关，INPUT_CONTRACT 保存请求的库哈希；
   `verify_solver_backend` 核对实际证书中的 backend / library SHA。
   本轮 selected-support 计划仍用 Python，不把两个变体混作单因素。

解释边界：内层 TemporalCertificate 的名称仍为
`two_best_selected_integer_classes`。其目标范围必须结合记录中的
`likelihood=selected-support`、plan fingerprint 和候选 source_id 说明；
不能据内层通用字符串将它包装为原 full-row likelihood 的证书。
wrapper 已提供明确的 selected-observation certificate scope。

未发现额外实测授权需求；以上是代码级检查，不替代新模型的整数真值、
弱几何、异常观测、实测准入与整链时间效果验证。
