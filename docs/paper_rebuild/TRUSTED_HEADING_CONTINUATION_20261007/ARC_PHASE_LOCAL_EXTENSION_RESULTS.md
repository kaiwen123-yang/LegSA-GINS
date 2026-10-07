# 局部内核后续扩展资格：31 项

本文件单独记录 geometry-only 与未知跨时相关条件界扩展。
首次原 26 项证据仍以 ARC_PHASE_LOCAL_ATTEMPT_01.* 为准，不被本轮替代。

扩展源单次运行结果：原 26 项回归 + 新增 5 项，共 31/31 通过；
0 失败、0 修复重试，pytest 0.54 s、进程 0.713 s。
源/test SHA、命令、时间和 JUnit 见 ARC_PHASE_LOCAL_ATTEMPT_02.*。

新增检查覆盖显式未知 actual availability 的 geometry-only 输出、
原完整 factor 对 None 拒绝、空支持仍保留未知状态，以及用正/负/一般 PSD
cross 验证未知相关条件二阶矩界。极端正相关时差分噪声可为 0，
极端负相关时可为 4Q，不能把零 cross 当成事实。
每个新增实例的名称和实测属性见同名 JSON。

这是合成观测代数资格。条件界仅在两端工作矩阵实际能上界误差二阶矩时成立，
没有验证 RAWX 工作 Q 的该前提；也没有建立各块独立、方向可信或导航改善。
