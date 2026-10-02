# 进度

起点 `334f5a64a8a1193bde25113ac84a5ddff1211cc7`；授权分支 `audit/code-xbpg-20260105-20261001`。原结果和大索引保持原样。

## 已完成并保存的小项

- DEF：固定V3顺序创新有效维度与RP事件候选定义；`bf561d56838d405a323077d29ad8be9173012545`；PUSHED_VERIFIED。
- P_OBS：加入候选完整协方差只读诊断与原生负对照；`6979459bb69154d70b6e88220e3dff29e3356568`；PUSHED_VERIFIED。
- N09_CODE：isolate N09 RP scheduling and validate original branch controls；`a66bc41fa7b8a1d5aefb00d0b43c17919c4da9de`；PUSHED_VERIFIED。
- N12_CODE：isolate conditional innovation and test same-event covariance contract；`bb6d4e015fef5cecee1532b2d67617679afe06bf`；PUSHED_VERIFIED。
- N16_CODE：exclude disabled HV dimension from quality statistics with native controls；`35817c5077212c8e02d8f5881902b438055a037c`；PUSHED_VERIFIED。
- RUN_ENTRY：gate ten single-slot candidate calls with immutable input and access checks；`17aba05b15cf8a80bc43dfece7c7be963b063839`；PUSHED_VERIFIED。
- N12_NATIVE：record two completed N12 closed-loop calls and changed acceptance；`633db7fd8d2f92e78eb9a3a0e0e60328621e6f5c`；PUSHED_VERIFIED。
- N16_NATIVE：record independent N16 closed-loop calls without combining N12；`5b0353f7bad7b4cd475ca06511c8a39f93e119ca`；PUSHED_VERIFIED。
- EVAL_ENTRY：bind frozen singleton evaluation and baseline reproduction gates；`af74931169deb1f94576277f35df2b976a4286dc`；PUSHED_VERIFIED。
- N09_C00_NATIVE：verify N09 normal-GNSS controls reproduce ten scientific outputs；`556b8d0a8df4ae6ab5a150ac009eeed1b32edbbf`；PUSHED_VERIFIED。

## 本次小项

BASELINE_C00_D15_EVAL：reproduce C00 and D15 frozen evaluation with exact recorded values。

复用两原版新重放NAV，无native新增。各转点NAV hash一致；143/143原指标及支持字段差值全0，17项evaluator门通过，NAV/STD全部列有限。实际evaluator2/参考child打开2，parent参考0，失败重试0。此前57项helper历史回执一并保留。

本项提交身份由 Git 给出；push/远端核验回执在下一项更新到 COMMITS.csv，最后一项的完整 SHA 在终端交付。

## 下一项

N12两候选离线评价并逐项提交；N09 A1真实调用；候选事件/P核对。

## 调用边界

真实候选调用以 RUN_MANIFEST.csv 及本项说明为准，限定10个计划candidate组合，基线复用。真实native、原生fixture、离线evaluator分别登记，技术失败/重试不隐藏。provider生成/旧controller/bootstrap不调用；原数据只读，新NAV/STD/事件原位保留。
