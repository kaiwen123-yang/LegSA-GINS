# V3 展示更正与最小机制取证

接续 `b0fdb81f103a5f0e7c7432e5247a9341524c7fa6`，本目录按独立小项交付。当前授权包含展示更正、既有小型元数据的暴露核对、11 个指定身份的冻结原版及观察版诊断重放；不改变正式算法、有效性、参数、输入或故障。前两轮的零调用回执仍是其各自阶段的历史记录。

- [展示更正](DISPLAY_CORRECTIONS.md) / [逐项来源表](DISPLAY_CORRECTIONS.csv)：旧展示、原始完整精度源与维护稿更正。
- [机制措辞更正](MECHANISM_WORDING_CORRECTIONS.md)：把已观察的GNSS入口、dz诊断、禁用维元数据和HV归因限制同步到维护稿，数字和原显示方程不变。
- [故障暴露](FAULT_EXPOSURE.md) / [交集表](FAULT_EXPOSURE_NOTES.csv)：注册区间与评价支持的交集，不改变注册分母；[D39 指定22文件补充读取](exposure/D39_WINDOW_VALIDATION.md) 单独保存新窗口算术。
- [机制协议](MECHANISM_PROTOCOL.md) / [逐次调用](REPLAY_MANIFEST.csv)：首次真实调用前冻结的队列、输入、判据；[输入生成与继承链](INPUT_LINEAGE.md) 分开hash匹配和语义资格。
- [观察版与合成门](observer/IMPLEMENTATION.md) / [字段](observer/SCHEMA.md)：完整源码patch与固定构建pin，合成无干扰不代替真实对象身份核对。
- [C00 三方法](groups/C00/README.md)：历史字节关系、实际更新和N12/N16同快照权重；[A1 20 s、seed_00](groups/A1/README.md)：区分RP入口阻断、HV候选不可用与恢复边界。
- [A2 20 s、seed_00](groups/A2/README.md)：保留heading后的实际HV/RP接受、RD资格拒绝与影子权重边界。
- [D15 seed_00](groups/D15/README.md)：位置噪声下NIS差异的双向权重变化、cap遮蔽及999哨兵的实际作用范围。
- [最终裁定](FINAL_MECHANISM_FINDINGS.md)：11身份、22次真实native已完成，逐项区分历史身份、重放事件、影子权重与尚未测试的闭环影响；[问题—结果—表图映射](RESULT_CLAIM_SCOPE.md) / [16条来源记录](RESULT_CLAIM_SCOPE.csv) 保留旧状态与新证据。
- [最终核对回执](FINAL_CHECKS.json) / [独立只读审阅](FINAL_REVIEW.md)：55项历史输出hash、55项观察版输出hash、调用/事件和新证据保留范围；通过的是身份与范围账，不是科学正确性。
- [进度](PROGRESS.md) / [提交记录](COMMITS.csv)：小项进度、完整 SHA、push/远端核对状态。最后一项自身 SHA 由 Git 和终端交付，不递归提交。

原 V3 NAV/STD 已按历史策略释放。新生成文件一律是新的重放输出，中间量为 `replay_observed`，不称“找回的历史日志”。大载荷仅放隔离输出根，实际本机根通过 ignored local config 解析；共享文件使用路径别名。不会重复扫描既有全部误差文件或调用旧矩阵控制器。

本阶段已经完成，后续修补候选、因果干预和扩大重放均未执行。M01 首次 push 失败后的一次限定重试已成功，详见 [完整失败与恢复回执](M01_PUSH_RECOVERY.json)。
