# 分段诊断 native 检查点（2026-10-04）

这是独立工程缺测诊断，不替代严格一次初始化主表，不宣称连续全窗复现。冻结提交 `9d80ef33b3a40914cfa92f41835419d62152fa88`；源码身份包含实际 872 项 Python 与 FGO C/C++，是依赖身份超集，不表示全部文件执行。

3 个新 OiSAM native：BY2 单连续块控制、BY2H 全 3 个真实连续块、BY2O 全 7 个真实连续块。固定预登记全部区段均尝试；块内数值失败不得再初始化，下一独立区段只由预先确定的真实输入缺口触发。另复用 6 个 Wen/GNC 已封存完整批处理 native；没有人为按 IMU 缺口停掉它们。

全部新 native 在 2026-10-04T10:35:24.220316Z 封存，新增和复用 native 在线参考均 0。BY2 全 285 行数值、状态、全部旧事件字段 exact 相同。BY2H 的 414 秒单节点只有先验初始化，没有动态传播/QR解；主评价排除所有先验输出，次级评价明确保留。BY2O 3484 秒真实初始化角速度不满足合同，等待至 3485 秒；该行保留 invalid。3286 秒 Ceres 仍为可用但未收敛的有限迭代终态，不称已经修好。

`COPY_INDEX.json` 逐文件绑定原 stage 路径、字节数与 SHA256。此块仅保存轻量 native 检查点；完整状态、事件、SOURCE_SNAPSHOT.zip、strace 和目标 normal NPZ 均保留在原 stage。离线评价与独立结果复算将另交付，不在此块混入尚未封存时的结果声明。

原 stage：`/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/FGO_SEGMENTED_DIAGNOSTIC_20261004T100449Z`。
