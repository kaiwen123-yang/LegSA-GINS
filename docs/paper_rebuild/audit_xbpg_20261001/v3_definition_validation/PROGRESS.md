# 进度

起点 `334f5a64a8a1193bde25113ac84a5ddff1211cc7`；授权分支 `audit/code-xbpg-20260105-20261001`。原结果和大索引保持原样。

## 已完成并保存的小项

- DEF：固定V3顺序创新有效维度与RP事件候选定义；`bf561d56838d405a323077d29ad8be9173012545`；PUSHED_VERIFIED。
- P_OBS：加入候选完整协方差只读诊断与原生负对照；`6979459bb69154d70b6e88220e3dff29e3356568`；PUSHED_VERIFIED。
- N09_CODE：isolate N09 RP scheduling and validate original branch controls；`a66bc41fa7b8a1d5aefb00d0b43c17919c4da9de`；PUSHED_VERIFIED。
- N12_CODE：isolate conditional innovation and test same-event covariance contract；`bb6d4e015fef5cecee1532b2d67617679afe06bf`；PUSHED_VERIFIED。
- N16_CODE：exclude disabled HV dimension from quality statistics with native controls；`35817c5077212c8e02d8f5881902b438055a037c`；PUSHED_VERIFIED。

## 本次小项

RUN_ENTRY：gate ten single-slot candidate calls with immutable input and access checks。

三个候选代码门已完成。入口静态审查建议已落实：统一READY身份字段、已提交依赖门、固定manifest身份/禁止布尔/窗口参数、成功open完整解析与相对路径待审。py_compile通过，真实调用仍0。下一步先check-only再限定调用。

本项提交身份由 Git 给出；push/远端核验回执在下一项更新到 COMMITS.csv，最后一项的完整 SHA 在终端交付。

## 下一项

N12 C00与D15真实候选、基线同口径离线评价和事件核对。

## 调用边界

真实候选调用以 RUN_MANIFEST.csv 及本项说明为准，限定10个计划candidate组合，基线复用。真实native、原生fixture、离线evaluator分别登记，技术失败/重试不隐藏。provider生成/旧controller/bootstrap不调用；原数据只读，新NAV/STD/事件原位保留。
