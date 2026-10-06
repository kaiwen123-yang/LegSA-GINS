# 2026-10-01 全代码科学审查与 XBPG 探索：基线

本轮只做代码科学审查和 2026-01-05 四段 XBPG 数据适配/初步实测。用户已授权独立 worktree、原生测试、满足物理条件的探索运行、按科学工作单元 commit/push。旧阶段 XB 禁令不适用于本轮。RTKLIB 动基线已有实现；目标三篇文献完整复现和公平横向比较仍未完成，本轮不补做，不启动历史矩阵，不写三篇稿件。

- 基线：`stage/clean3-math-repair@eb3cbed314693358c7c38442b6fbbb7afcf0342e`。
- remote：`git@github.com:kaiwen123-yang/LegSA-GINS.git`；开始时本地 upstream ahead/behind 为 0/0。推送后另核远端。
- 审查分支：`audit/code-xbpg-20260105-20261001`，从核实基线建立，未带入原 worktree 未跟踪文件。
- 原 worktree 跟踪文件无修改；29 个未跟踪文件保留，其中28个代码/配置列入覆盖清单，1个文档保留。不将它们纳入提交。
- 路径仅由 ignored `configs/paper_rebuild/DATA_PATHS.AUDIT_XBPG.local.yaml` 解析。`<AUDIT_ROOT>`=`<CLEAN_ROOT>/stages/AUDIT_XBPG_20260105_20261001`；`<AUDIT_SCRATCH>` 为独立 ext4 构建/计算目录。raw、冻结配置/二进制、历史结果不写。
- 已核实真实 G: 挂载、四指定 GNSS session 和 xb1..4 存在。开始时 G: 可用约35 GB、ext4约866 GB、内存约22 GiB available。编译最多4线程、数值库1线程、数据流式处理。

`ACTIVE_CONTEXT.md` 在本基线首行标为 SUPERSEDED。AGENTS 中 v2.1 正文与后附 v3 记录并存；本轮以实际冻结配置/二进制/运行记录确认身份，不修改旧记录。v3 使用 raw HPPOSECEF 标量航向，并未将 B3 作为正式 F04。新源码含 B3 候选，不能用同名 target 推定等同冻结二进制。

## 覆盖口径

基线全部跟踪的源文件、脚本、测试、可执行配置和模板，另含原工作树未跟踪代码/配置。脚本读取内容计算行数和 AST 仅用于枚举，深度仍为 `UNREAD`。JSON 配置/schema 纳入；JSON运行结果不冒充代码。外部 gitlink 单列，不声称逐行审第三方库/编译器。

初始清单为 3,057 个跟踪文件 + 28 个未跟踪代码/配置，552,271 行；自动枚举18,630个 Python函数/类。语义审查数此时为0。清单不会以 `legacy` 标签排除其他自有代码；剩余队列将明确保留。

复现：`python3 scripts/paper_rebuild/audit_xbpg/inventory.py --local configs/paper_rebuild/DATA_PATHS.AUDIT_XBPG.local.yaml`。该命令重新生成基线清单（会清除后续手工深度标记），只用于重建初始状态；动态函数目录和重复 blob 组保存在 `<AUDIT_ROOT>`。

## 边界与执行

仅本轮 `docs/paper_rebuild/audit_xbpg_20261001/`、专用 `scripts/paper_rebuild/audit_xbpg/`、`src/legsa_gins/paper_rebuild/audit_xbpg/` 和 `tests/paper_rebuild/audit_xbpg/` 新文件可提交；正式求解器不改，候选只留独立补丁。输出留独立存储根，不建ZIP、不清理旧资产、不合并、不打tag、不force push。

全代码覆盖和科学身份未闭合前不称全仓完成；测试失败、不可执行组合和参考未知均保留。首次参考性能评价前冻结探索协议并提交。审查、修复、试跑和论文有效性四种完成状态分开。
