# 进度

起点 `b0fdb81f103a5f0e7c7432e5247a9341524c7fa6`；授权分支 `audit/code-xbpg-20260105-20261001`。原结果和大索引保持原样。

## 已完成并保存的小项

- D01：correct V3 display precision denominators and reproduction wording；`a62bd637303341a92b5016aaa7666e30994c4424`；PUSHED_VERIFIED。
- E01：document actual V3 fault exposure against evaluation support；`6d326c9fa3c2279d6bfd5fbbc46d467d4523b44f`；PUSHED_VERIFIED。
- E02：补充核对 D39 seed00 的两个窗内区间及窗外空集；`dff215f5d11ba35097dbcfbef290fe0a2cf6667f`；PUSHED_VERIFIED。
- P01：预登记11个机制对象的原输入身份与22槽诊断协议；`b221e3244ed61f84b0c8278245ff23f85d780f0e`；PUSHED_VERIFIED。
- I01：封存观察插桩与合成无干扰门；`4194177cc5c769a4bd8a3cc8dd0a9f88ad91c939`；PUSHED_VERIFIED。
- C01：闭合C00三方法历史身份与调度创新权重证据；`982258d9cf16292bd1ff9ce0b596966d081c6fc5`；PUSHED_VERIFIED。
- A1：闭合A1中断的RP入口阻断与HV候选边界；`33e888287d57444f2fdd485cc8a608790874408c`；PUSHED_VERIFIED。
- A2：确认A2航向保留时的HV和RP实际接受；`761839827027f33f89d327de253b8abdd5b18a85`；PUSHED_VERIFIED。
- D15：核实D15顺序创新与哨兵权重的实际遮蔽；`25ab500ab7bac7b59288f0dbb5b0c0fe66fd6433`；PUSHED_VERIFIED。
- M01：补维护稿的调度创新与HV因果限定；`f6de3c4d6840cd4de416c3c4a478692ac279dafe`；PUSHED_VERIFIED_AFTER_ONE_RETRY。

## 本次小项

FINAL：封存V3最小机制取证裁定与四组来源边界。

已完成11身份、22真实native（无失败/重试），另计3个合成fixture进程。55历史输出hash和55观察版hash一致；71,848个SA快照复核，N12最终影子R不同3472、N16不同4043，均未反馈闭环。16条旧问题/结果映射保留原状态；46收尾检查及独立只读终审通过。独立验证计算已执行，evaluator/provider/controller/bootstrap为0。M01首次SSH失败后唯一限定重试成功，失败与恢复回执保留。

本项提交身份由 Git 给出；push/远端核验回执在下一项更新到 COMMITS.csv，最后一项的完整 SHA 在终端交付。

## 下一项

本阶段完成后停止。最小后续候选见FINAL_MECHANISM_FINDINGS.md；未执行算法修补、闭环干预、扩大重放或科学范围扩展。

## 调用边界

真实诊断调用以 REPLAY_MANIFEST.csv 及本项说明为准，上限11身份×原版/观察版=22次native。provider生成/旧controller/bootstrap不调用。所有新中间量为replay_observed，历史零调用回执不改写。原数据只读，保留新NAV/STD，不用误差重建旧NAV。
