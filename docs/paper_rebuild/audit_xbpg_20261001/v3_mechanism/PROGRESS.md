# 进度

起点 `b0fdb81f103a5f0e7c7432e5247a9341524c7fa6`；授权分支 `audit/code-xbpg-20260105-20261001`。原结果和大索引保持原样。

## 已完成并保存的小项

- D01：correct V3 display precision denominators and reproduction wording；`a62bd637303341a92b5016aaa7666e30994c4424`；PUSHED_VERIFIED。

## 本次小项

E01：document actual V3 fault exposure against evaluation support。

读取既有小型元数据540案例657组件及11880评价终态，显式216区间中192故障与18恢复窗内、5窗后、1窗前。D22 seed00/06为EMPTY_INTERSECTION；D39 seed00仅前两段各2s在窗内，第三段3s窗外。另列同类D39 seed01/06窗外与窗前条目，无区间不补零，不改变540/541注册分母。11个解析端点断言通过；本项零payload、零性能核算、零科学调用。

本项提交身份由 Git 给出；push/远端核验回执在下一项更新到 COMMITS.csv，最后一项的完整 SHA 在终端交付。

## 下一项

只补充读取D39_seed00的22个已登记误差文件补两段统计；并完成11对象输入资格/科学协议的独立提交，之后才真实重放。

## 调用边界

真实诊断调用以 REPLAY_MANIFEST.csv 及本项说明为准，上限11身份×原版/观察版=22次native。provider生成/旧controller/bootstrap不调用。所有新中间量为replay_observed，历史零调用回执不改写。原数据只读，保留新NAV/STD，不用误差重建旧NAV。
