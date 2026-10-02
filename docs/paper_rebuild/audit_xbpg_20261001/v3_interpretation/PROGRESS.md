# 进度

起点 `d9763ea40fd19963a71321c2a6ca930a022c159d`；授权分支 `audit/code-xbpg-20260105-20261001`。原结果和大索引保持原样。

## 已完成并保存的小项

- M01：explain formal methods and frozen metric definitions；`258b58c99246988b20419be3d6d45d603f76f61f`；PUSHED_VERIFIED。
- N01a：interpret all eleven BY2 natural configurations；`3439053691a1de0624dc371243412bb64180228d`；PUSHED_VERIFIED。
- S00：freeze retained series validation scope and tolerance；`0593770b2b3837012d155254cfc73448d76990b2`；PUSHED_VERIFIED。
- N01b：verify BY2 retained errors and matched trajectory；`ba44f33bad7dafd16c0ac74457fca3cd3f7d9e2f`；PUSHED_VERIFIED。
- N02：interpret and verify all BY2H natural configurations；`f9d298aadba10c5710d42ccaf3a1882a3c93e85e`；PUSHED_VERIFIED。
- N03：interpret BY2O full and all fixed segments with retained checks；`1fae06e5063c99c48a0c2c310b6c82526c45b227`；PUSHED_VERIFIED。
- C01：explain complete GNSS outage family and retained time support；`a544cc5d2d3be0c5cb6475358b738d9a5317e59d`；PUSHED_VERIFIED。
- C02：explain sampling and dropout cases across all methods；`3d17be52f0401b44e136eaa22d235f48850a72b3`；PUSHED_VERIFIED。
- C03：explain position_value results and retained time support；`6e85c769b015bf3a97f557fda4ba202408d66c08`；PUSHED_VERIFIED。
- C04：explain position_std_status results and retained time support；`142b0325cd6a176566c5bd74e9aaf1ff97257e0c`；PUSHED_VERIFIED。
- C05：explain scalar heading faults and bounded series checks；`66be30984e14895e36111f3f4f48e69b6c8830eb`；PUSHED_VERIFIED。
- C06：explain velocity_raw_doppler results and retained time support；`c12d1fd8d889c25a0405893bfd0307bef43d8677`；PUSHED_VERIFIED。
- C07：explain go2_prior_metadata results and retained time support；`0079eba42046be26391d86943e4e17188f5b5eef`；PUSHED_VERIFIED。
- C08：explain mixed faults and reconcile all CORE failures；`331eecac3a10e740ab8c91098866805559764485`；PUSHED_VERIFIED。
- A11：explain A1_10s across all eleven configurations；`d479558ab205c0a0d8b8a8a53deebca11c90c7ad`；PUSHED_VERIFIED。
- A12：explain A1_20s across all eleven configurations；`0e9a36cc5e1c5ce282ade302e0d6ebf47d143221`；PUSHED_VERIFIED。
- A13：explain A1_30s across all eleven configurations；`36547a906cd9c2b3dd9b9da058a561c5663c7523`；PUSHED_VERIFIED。
- A21：explain A2_10s across all eleven configurations；`2996f399a1133035f26c98c83a36daee562d7bc1`；PUSHED_VERIFIED。

## 本次小项

A22：explain A2_20s across all eleven configurations。

A2 20 s：11配置九种子99native/198评价均完成，396原UA格MATCH。全窗H/yaw/up及每方法尾部已解释；F04-F03和F04-A06水平9例均低，上向各6例更高。全文读最后198误差，32652 MATCH/18 NULL/1782不可复算/0差异；至此2308error+1matched各主扫描一次。A2_30 NOT_REGISTERED，未补跑；所有窗口算术标validation，实际HV触发仍未知。

本项提交身份由 Git 给出；push/远端核验回执在下一项更新到 COMMITS.csv，最后一项的完整 SHA 在终端交付。

## 下一项

整理既有配对/不确定度解释，再逐项提交外部旧协议、候选和实际图像说明。

## 调用边界

solver/provider/original evaluator/controller 新调用均为 0；bootstrap/原始reference读取为0。本轮计数、配对及保留时序复算均标为新 validation calculation；历史零统计回执不改写。未用误差重建 NAV/STD。
