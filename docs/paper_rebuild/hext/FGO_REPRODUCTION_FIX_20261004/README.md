# FGO修正阶段：实际9身份与失败支持

2026-10-04修正后的选定算法独立实现已经完成9个真实方法×序列身份、全部native封存后3次离线评价、指标独立复算和三图。**OiSAM BY2H正式窗0/271，BY2O55/378；九次尝试完成不等于九格全窗有效解，也不等于三篇作者完整原实验全部复现。**

| 序列 | 方法 | H / V / 3D RMSE(m) | yaw RMSE(°) | 匹配/原期望 | 求解+适配(s) |
|---|---|---|---|---|---|
| BY2 | OISAM | 0.105788 / 0.043647 / 0.114439 | 4.652921 | 275/275 | 48.727977 |
| BY2 | WEN_TC | 7.692119 / 11.281932 / 13.654694 | NA | 274/275 | 39.213737 |
| BY2 | GNC | 2.173503 / 4.543968 / 5.037039 | NA | 274/275 | 0.579792 |
| BY2H | OISAM | NA / NA / NA | NA | 0/271 | 36.642451 |
| BY2H | WEN_TC | 7.672239 / 12.139729 / 14.360929 | NA | 270/271 | 38.796025 |
| BY2H | GNC | 2.134279 / 4.212907 / 4.722683 | NA | 270/271 | 0.499028 |
| BY2O | OISAM | 0.040439 / 0.039280 / 0.056376 | 0.979876 | 55/378 | 59.316959 |
| BY2O | WEN_TC | 9.583724 / 16.424586 / 19.016172 | NA | 377/378 | 58.543607 |
| BY2O | GNC | 2.724164 / 2.945937 / 4.012433 | NA | 377/378 | 0.567325 |

RMSE仅对各自有效支持；NA无成绩。Wen/GNC无估计姿态。共同三方法支持274/0/54。OiSAM严格一次A1、无连续heading，H从408s前导seed缺IMU起停，O3241s缺IMU后停；不填补、不再次初始化，原275/271/378分母保留。

OiSAM使用固定作者OB_GINS Earth预积分实际编译模型及真实Givens/A-JSWR/Ceres；Wen右端bias联系与AHRS合同；GNC Eq21平方GM及原Algorithm1降theta停止都已实现/真实运行。作者Oi完整程序、Wen原XSens AHRS和GNC原作者数值设置未取得，差异见[详细报告](REPRODUCTION_NOTES.md)。独立作者连续600s/601节点Oi诊断完成601/601并单列，不冒充原论文全实验。

- [新方法自身/共同支持表](METRICS.csv)、[完整应用对照表](COMPARISON_TABLE.csv)、[9运行账本](RUNS.csv)。
- [BY2图](figures/FGO_BY2.png)、[BY2H图](figures/FGO_BY2H.png)、[BY2O图](figures/FGO_BY2O.png)，PDF/SVG同名。图Truth表示共享商业融合评价参考，独立绝对truth未成立；历史缺NAV显式注明。
- [原文差异/失败/身份/回归](REPRODUCTION_NOTES.md)、[复跑入口](RUN_REPRODUCE.md)。旧FGO_COMPARISON保存14次历史结果，不能与此严格协议混用。

科学stage：`/home/kaiwen/research/LegSA-GINS-SCRATCH/FGO_REPRODUCTION_FIX_20261004/FGO_REPRODUCTION_FINAL_20261004T054410Z`。Windows小报告/源和图：`G:\LegSA-GINS-project\修复_20261004\FGO_FINAL`。22份实际源aggregate SHA `1ae538d65e116028f90d80f0a721619b23ff514f0c11159a908cf303b6e009bd`；执行含本地未提交overlay，不能仅写HEAD0625。69条冻结源码回归通过、9native在线参考0、封存后3offline各参考open1。没有commit/push或覆盖旧结果；wall time含输入/求解/适配，不能在线时延排名。
