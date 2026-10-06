# 单例冻结 v3 评价入口

本目录只准备显式选择的一次离线评价，不启动 solver、Context、历史 controller、整队列或自动重试。`EVAL_MANIFEST.csv` 有 7 个既有基线身份及 10 个候选组合；准备时均为 `PLANNED_NOT_INVOKED`。真实调用由 supervisor 在本目录提交后逐项执行。

```bash
python3 -B docs/paper_rebuild/audit_xbpg_20261001/v3_definition_validation/evaluation/evaluate_one.py \
  --candidate-id BASELINE --run-id RUN_00004 --preparation-commit <FULL_COMMIT_SHA>
```

候选把 `BASELINE` 换成队列中该运行的 `N12_ONLY`、`N16_ONLY` 或 `N09_RP_ONLY`。无 `--all`。指定提交必须逐字包含当前脚本、源 pin、旧结果期望、队列和定义说明，候选还绑定所选候选的 `READY.json`。脚本只允许队列身份；整个新评价根用非阻塞单例锁，创建任何槽输出之前核全 17 槽集合及身份、本槽 `PLANNED_NOT_INVOKED`/attempts 0/child 0。同一槽的外部或共享输出已存在就拒绝，不覆盖或继续执行旧槽。

路径从 ignored `configs/paper_rebuild/V3_DEFINITION_ROOTS.local.json` 解析。基线使用 `<MECHANISM_ROOT>/replays/<run_id>/original/` 的既有 NAV/STD；候选使用 `<VALIDATION_ROOT>/candidates/<candidate_id>/<run_id>/`。原生回执必须为指定成功终态、一次实际 native、访问门通过、原配置 hash 对上，NAV/STD 另与其回执 hash 核对。基线原 binary pin 固定为 `96ae436d82ba8922c68382bd73fc42c8bf4bcb22d72a43a8bd05f506043a9c1c`；候选原生回执的 binary/READY hash 必须与已提交 READY 相同，99 项固定 data-role 比对必须逐项 present/same。`COMPLETED_REVIEW_REQUIRED` 不进入评价。

新大载荷留在 `<VALIDATION_ROOT>/evaluations/<candidate-id>/<run-id>/`，包括转换 NAV、完整 evaluator 输出和误差序列。小型数值/计数/对照回执写入本目录 `results/<candidate-id>/<run-id>/`。误差 source_path 按冻结 reader 的 plain CSV 优先、否则 gzip 规则登记实际入口；两份新派生均保留。父进程只 stat 参考；参考正文仅由冻结 evaluator 子进程以原句柄读取和核 hash。错误、非零退出、未启动或计数未知均保留；`evaluator_invocation_attempts`、实际 Python evaluator `execve` 数和参考读取数分列。`STARTED.json`、`BEFORE_EVALUATOR_CALL.json` 保留各自原状态，终态另写。

科学身份由 `FROZEN_PINS.json` 指定，当前含 13 个仓库小文件及 1 个外部 evaluator。8 个核心文件为本 worker 新哈希对 supervisor 提供的冻结 pin；另外 5 个辅助模块为本地新 pin，冻结来源沿 supervisor 已核对的集合登记。没有把尚未逐项列入的模块算成完整 16 项闭包。执行时重新核这 14 个小文件，不以当前 HEAD 代替 evaluator 科学身份。原科学来源提交是 `7d43b9af26120ed5dde21f53e515386361072ba6`。

固定评价口径：

- 原窗 `[66,340]`、base time `1772784000`、`canonical_v2_wgs84_full_support`、yaw truth mode `enu`。
- 用冻结 `transform_nav` 从原始 native NAV 转换一次位置到 POI，FRD lever 为 `[0.03,-0.148095745932992,-0.30]` m；不读取 native `EVAL_NAV.csv` 当输入。基线转换后 NAV hash 必须先等于旧记录才启动 evaluator。
- STD 原样传入，标 `UNTRANSPORTED_STD_DIAGNOSTIC_ONLY`。参考仍非独立真值；不计算无参考支持的速度 RMSE。
- 显式核 audit、子进程参考单次读取及同句柄 hash、原列选择、无额外 raw/bag/fpl、写范围、D12 固定 0.01 m/deg 门、无时移、资源回执。D12 不是本轮逐指标容差。
- `BASELINE_EXPECTATIONS.json` 原字面值来自 7 份旧 `EVALUATION_RESULT.json` 及其 capture；旧源 metadata SHA 在新调用前再核。每身份比较 128 项误差统计、14 项支持字段和 cleaned-reference count，共 143 项。一般数值固定 `1e-10+1e-10*abs(old)`，时间绝对 `1e-9`，整数/布尔/状态精确；缺失不当零。原字面值、来源 JSON pointer、新值、差值、容差和状态并列保留。
- 候选只有在对应基线终态、全部原口径比较及实际子进程计数均闭合后产生直接对比。先核精确时间支撑；相同支撑才给全窗差值。支撑不同保留双方完整指标及 exact-timestamp 共同计数，差值留空，标 `COMPLETED_DIFFERENT_SUPPORT_REQUIRES_COMMON_METRICS`；共同子集指标可另立只读小项计算，不偷偷删历元、插值或换分母。
- 每个新 NAV/STD 的所有列登记 count/finite/nonfinite/首末/范围；非有限输入保留诊断后停止，不筛除。NAV 速度仅为自身状态诊断。
- A1/A2 从本次新误差计算固定半开中断 `[196.2,216.2)`，前段 `[66,196.2)` 和后段 `[216.2,340]`；均标本轮 validation calculation。分段参考 count 为 unknown，不额外读参考。C00/D15 不造局部故障窗，不使用 evaluator outage 参数。

准备与测试：`prepare_contract.py` 仅执行过一次小元数据读取，生成 17 个未调用槽。`test_evaluate_one.py` 第一次为 57/57 PASS，原回执完整保留在 `test_history/`；审查加强门后第二次 74/74 PASS，累计 2 次 helper 测试进程、0 次失败。新增反例覆盖完整槽集合、已启动槽、固定 binary/READY、99 项角色门，原容差、缺失、独占输出、symlink、D12、实际 exec 计数和半开窗检查保持。两次均未调用 `run_one`、冻结指标函数、mock evaluator、真实 evaluator 或 native，未读取任何真实 NAV/STD/参考正文。此测试不冒充整条科学评价链已经通过；两份首基线仍需正式单例调用后闭合。
