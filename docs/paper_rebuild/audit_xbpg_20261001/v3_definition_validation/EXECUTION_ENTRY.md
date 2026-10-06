# 有限闭环入口

`run_candidate.py --roots <ignored local config> --candidate-id <candidate> --run-id <baseline_run_id>` 只消费 CANDIDATE_QUEUE 的一个 PLANNED 槽。`--check-only` 验证输入、已提交协议和二进制身份，不调用 solver，不创建运行槽；没有批量、自动重试或恢复历史矩阵入口。

10个新候选调用，7个去重基线直接用上一阶段 original 输出；基线不默认重跑。原 config 字节不改，原 native manifest 中的 run_id 因此仍是原输入身份；外层 `slot_id=candidate_id__baseline_run_id`、READY 的新 source/binary pin、CANDIDATE_RECEIPT 明确其科学身份是新候选，不能冒充原 V3。方法开关及完整窗口保持，CLI 仅把输出重定向到新的受保护隔离根。

入口要求新定义、队列、候选 READY、旧资格/输入/历史回执及所导入工具均与已提交版本相同；核实新 binary/config hash，复用旧输入 hash 资格并逐项检查现存 size/device/inode/mtime。不再扫描所有 provider 或保留误差。调用前写 STARTED/attempt，退出后以 strace 成功 exec 计真实调用；状态不明、技术异常、算法失败和输出均保留，不自动再次调用。

strace 检查成功打开的完整解析、相对/未知路径、项目输入白名单、reference/raw 禁入和槽外写。成功仍须核对 native manifest 中的数据角色、禁止布尔、实际输入路径、原初始化/窗口/安装关系/开关、SA阈值/cap及辅助源参数；允许闭环更新计数与科学输出变化。未通过进入 COMPLETED_REVIEW_REQUIRED，不能自动宣称同口径性能比较通过。

每次保留五种 full 输出、事件、完整 P 诊断、stdout/stderr、访问记录与回执。五输出 hash 与旧可信 recorded hash 并列：N09 C00/A2是预先固定的字节负对照；N12/N16和N09 A1允许真实分叉，不能用 hash 不同判候选失败，也不能用更低 RMSE 判数学正确。全部新日志是 candidate observed，不是历史创新日志。

本入口不含 evaluator/provider/controller 调用；同口径离线评价另用独立入口和调用账本。大载荷只在 `<VALIDATION_ROOT>/candidates/`，只提交小摘要。旧根没有写操作。
