# 进度

起点 `d9763ea40fd19963a71321c2a6ca930a022c159d`；授权分支 `audit/code-xbpg-20260105-20261001`。原结果和大索引保持原样。

## 已完成并保存的小项

- M01：explain formal methods and frozen metric definitions；`258b58c99246988b20419be3d6d45d603f76f61f`；PUSHED_VERIFIED。
- N01a：interpret all eleven BY2 natural configurations；`3439053691a1de0624dc371243412bb64180228d`；PUSHED_VERIFIED。
- S00：freeze retained series validation scope and tolerance；`0593770b2b3837012d155254cfc73448d76990b2`；PUSHED_VERIFIED。
- N01b：verify BY2 retained errors and matched trajectory；`ba44f33bad7dafd16c0ac74457fca3cd3f7d9e2f`；PUSHED_VERIFIED。
- N02：interpret and verify all BY2H natural configurations；`f9d298aadba10c5710d42ccaf3a1882a3c93e85e`；PUSHED_VERIFIED。
- N03：interpret BY2O full and all fixed segments with retained checks；`1fae06e5063c99c48a0c2c310b6c82526c45b227`；PUSHED_VERIFIED。

## 本次小项

C01：explain complete GNSS outage family and retained time support。

D01-D07全部63案例×11方法；693native全完成，11088汇总格/6174配对差一致。154保留误差文件全文、25396数值MATCH。D06大误差与真实注册故障窗相符；区分旧event包络。新增局部ignore例外使CORE文档可跟踪；BY2O两段文字末位统一到已有DIFFERENCES原值。

本项提交身份由 Git 给出；push/远端核验回执在下一项更新到 COMMITS.csv，最后一项的完整 SHA 在终端交付。

## 下一项

CORE gnss_sampling：D08-D12全部方法和保留时序。

## 调用边界

solver/provider/original evaluator/controller 新调用均为 0；bootstrap/原始reference读取为0。本轮计数、配对及保留时序复算均标为新 validation calculation；历史零统计回执不改写。未用误差重建 NAV/STD。
