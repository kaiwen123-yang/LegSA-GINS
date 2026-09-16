# H-EXT-02 执行记录

状态：HUMAN_AUTHORIZED_PREREGISTRATION；本提交冻结 D1–D6、适配、评估、聚合与绘图代码。授权来源：`H-EXT-02 prompt 2026-09-16`。只新增外部对比行，协议 v2.1 保持冻结。

## 冻结前验证

起点 `736862d5df4403c9b7fd0946e5fe11b746340b6c`，分支 `stage/clean3-math-repair`。三序列 D4 检查全部通过。每序列 22 文件进行 size/metadata 检查，其中 21 个非 trace 文件进行 SHA-256 检查；trace 内容只在后续评估器子进程唯一读取句柄内核验。

测试：78 passed，0 failed。两个冻结文件 `ext05_pavlasek.py`、`phase5_runner.py` 的 git diff 为空。只读代码复核通过。

新增 H02 路径、FILE_START、文献参数的 BY2 身份复验：

| 方法 | SHA-256 | 原文件逐字节 |
| --- | --- | --- |
| LC01 | ccd25c2e1309ba2870e57e2208f476a6b48eaba69f0d038f26be2f168bb2c695 | PASS |
| EXT05C | 915192d6fcefaf7bef33c4028b571d1b723f7e0759063e2955aebd3d1ee7ace8 | PASS |

身份复验 2 native / 0 evaluator / 0 trace，单列验证预算，不入比较表。比较运行预算 14 native / 28 evaluator；尚未执行。原 28 图及 pinned RENDER_MANIFEST 已逐文件建立前置哈希快照。

## 预注册定义

D1 按原始相邻 IMU dt 判定，整个无效区间不传播；GNSS 更新保持原始事件时刻；无效端点样本不成为保持样本；下一有效原始区间使用自身 dt 及最后保留的前一有效样本，之后恢复原方法的前一样本保持方式。无插值、无协方差膨胀。D2 FILE_START 主行；BY2H CONTRACT_START 为诊断；静态失败时按合约替换槽位。全部数值参数与选择规则见授权合约。

输出根 `<CLEAN_ROOT>/stages/CLEAN7_HEXT_EXTERNAL_SEQUENCES/`，ext4 暂存 `<HEXT_SCRATCH>/H_EXT_02/`。原始路径统一经 local YAML 和序列 registry 解析。

## 簿记裁定

1. 22 文件身份检查与 trace 仅评估器读取规则并存：21 payload SHA + 1 trace declared SHA/size，后者由评估器 capture 校验，绝不称为预运行完成了 22 payload SHA。
2. 必需的 BY2 身份复验 2 次单列于 14 条新比较行之外；零评估、不入性能表。
3. 静态失败在 native 前分类，CONTRACT_START 替换槽位；BY2H 已有诊断槽位去重，不超预算。
4. P-07 无对应 v2 横向表；BY2 v2 文献行复用已 pin 的 CLEAN5 parity 冻结标量汇总，保留真实来源，不重新评估。
5. 原测试要求审计文件必定 dirty，已改为显式 clean/dirty 两状态测试；未触碰冻结运行实现。
6. 冻结 v2.1 A04/F04 全速 NAV 已不在保留目录；09 项整项 UNAVAILABLE，不用 NAV_10HZ 或 P06 替代。内部体坐标偏差缺少全速证据时同样保留 UNAVAILABLE。
7. ZIP 内含 commit 2 与 commit 2 内含最终 ZIP SHA 会形成自引用。结果提交登记最终 receipt 路径；提交后打包并嵌入两个 commit hash，外部 receipt 记录真实 ZIP SHA、字节数、成员 SHA 与 CRC。包哈希不伪写进自身提交。

## 待执行

冻结提交的实际哈希写入运行侧 `03_PREREG/CODE_FREEZE.json`。此后至结果提交之间不改科学代码；任何簿记改动追加在本节。结果、图、审计计数与最终包 receipt 在任务完成时更新。
