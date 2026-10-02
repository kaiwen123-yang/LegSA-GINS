# V3 展示更正与最小机制取证

接续 `b0fdb81f103a5f0e7c7432e5247a9341524c7fa6`，本目录按独立小项交付。当前授权包含展示更正、既有小型元数据的暴露核对、11 个指定身份的冻结原版及观察版诊断重放；不改变正式算法、有效性、参数、输入或故障。前两轮的零调用回执仍是其各自阶段的历史记录。

- `DISPLAY_CORRECTIONS.csv` / `DISPLAY_CORRECTIONS.md`：旧展示、原始完整精度源与维护稿更正。
- `FAULT_EXPOSURE_NOTES.csv` / `FAULT_EXPOSURE.md`：注册区间与评价支持的交集，不改变注册分母。
- `MECHANISM_PROTOCOL.md` / `REPLAY_MANIFEST.csv`：首次真实调用前冻结的队列、输入、判据及每次实际调用。
- `FINAL_MECHANISM_FINDINGS.md`：历史身份、重放事件、权重影响与尚未测试的闭环影响分别裁定。
- `PROGRESS.md` / `COMMITS.csv`：小项进度、完整 SHA、push/远端核对状态。最后一项自身 SHA 由 Git 和终端交付，不递归提交。

原 V3 NAV/STD 已按历史策略释放。新生成文件一律是新的重放输出，中间量为 `replay_observed`，不称“找回的历史日志”。大载荷仅放隔离输出根，实际本机根通过 ignored local config 解析；共享文件使用路径别名。不会重复扫描既有全部误差文件或调用旧矩阵控制器。
