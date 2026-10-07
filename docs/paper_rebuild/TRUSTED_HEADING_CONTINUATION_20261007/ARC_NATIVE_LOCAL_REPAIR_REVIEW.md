# ARC 局部资格首轮失败与受影响项修复登记

首轮 dcce5bb 的配置、生产构建及两个 harness 编译成功；pytest 24项实际23通过1失败，旧16全通过、新8中7通过。日志与源码登记完整保留，不称首次全部通过。失败 case4 在ordering_mid断言HV应为3，实际为0；case6首轮虽通过，但同样没有执行HV，因此纳入修复范围。

根代理与fusion独立核对：GIEngine setter 以 enable_go2_velocity_prior_diagnostic 重算 solver_enabled；直接构造PortOptions的合成夹具遗漏此标志。正式loader已有 horizontal=>diagnostic 自动使能。首轮ordering_mid和两identity的BODY日志均三行 provider_unavailable。生产调度/噪声/准入无需更改。

仅测试harness补一行使能，case6新增两臂GNSS/RP/HV各3及三行BODY均接受的断言。case4原要求及byte identity保留。heading静态复核新runner/plan，根代理加入pytest实际加载的tests/conftest.py、pyproject.toml来源哈希。全部生产源码和旧库不变。

本次严格限定新stage中一次harness编译（链接首轮库）、一次pytest只选case4及case6，预期四次合成harness；不重建、不重复旧16项、不执行真实导航/评价，不自动重试。成功路径核前后pins；失败仍保留首次日志，若失败则需单独补核，不能预称已完成后验核对。

局部通过仅支持实现和空模型两臂一致性，不证明真实载波信息增量、物理协方差/时间资格或可信航向。
