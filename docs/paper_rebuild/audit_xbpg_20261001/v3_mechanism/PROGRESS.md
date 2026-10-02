# 进度

起点 `b0fdb81f103a5f0e7c7432e5247a9341524c7fa6`；授权分支 `audit/code-xbpg-20260105-20261001`。原结果和大索引保持原样。

## 已完成并保存的小项

- D01：correct V3 display precision denominators and reproduction wording；`a62bd637303341a92b5016aaa7666e30994c4424`；PUSHED_VERIFIED。
- E01：document actual V3 fault exposure against evaluation support；`6d326c9fa3c2279d6bfd5fbbc46d467d4523b44f`；PUSHED_VERIFIED。
- E02：补充核对 D39 seed00 的两个窗内区间及窗外空集；`dff215f5d11ba35097dbcfbef290fe0a2cf6667f`；PUSHED_VERIFIED。
- P01：预登记11个机制对象的原输入身份与22槽诊断协议；`b221e3244ed61f84b0c8278245ff23f85d780f0e`；PUSHED_VERIFIED。
- I01：封存观察插桩与合成无干扰门；`4194177cc5c769a4bd8a3cc8dd0a9f88ad91c939`；PUSHED_VERIFIED。
- C01：闭合C00三方法历史身份与调度创新权重证据；`982258d9cf16292bd1ff9ce0b596966d081c6fc5`；PUSHED_VERIFIED。

## 本次小项

A1：闭合A1中断的RP入口阻断与HV候选边界。

固定20 s seed00三方法6次真实native全部历史与观察版字节一致。中断内A04/F04各100个RP候选合格但入口未调度，HV原匹配候选0；F03辅助关闭。F04 N12影子R差876次、N16差1265次，未改变滤波器或新评价；两种窗口时轴分别保留。只读复核PASS。

本项提交身份由 Git 给出；push/远端核验回执在下一项更新到 COMMITS.csv，最后一项的完整 SHA 在终端交付。

## 下一项

A2：固定20 s seed00三方法，核实保留heading后的实际HV/RP接受与RD不可用。

## 调用边界

真实诊断调用以 REPLAY_MANIFEST.csv 及本项说明为准，上限11身份×原版/观察版=22次native。provider生成/旧controller/bootstrap不调用。所有新中间量为replay_observed，历史零调用回执不改写。原数据只读，保留新NAV/STD，不用误差重建旧NAV。
