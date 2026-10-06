# 原生 21+3 attitude clone：局部实现验证

状态：16 个独立合成案例首轮全部通过。仅局部数学与接口资格，不是实测性能、SDK 物理标定或完整性证明。

- 构建：CMake 配置 1 次、research static library/demo 构建 1 次、合成 harness 编译 1 次；全部成功，无修复或重编译。
- 执行：pytest 1 次、16 个测试实例；内部 harness 28 次，其中 6 次为预期非法输入拒绝。
- 真实 foot provider / raw / reference / 导航 / 评价 / AR 搜索调用均为 0。
- 持久日志：<TRUSTED_HEADING_SCRATCH>/NATIVE_ATTITUDE_CLONE_LOCAL_ATTEMPT01/{01_CONFIGURE,02_BUILD,03_HARNESS_COMPILE,04_TESTS}.log；全部命令、返回码、持续时间及内部调用保存在同目录 JSON/JSONL。

| 核验范围 | 结果 |
|---|---|
| 确定性 clone、current 过程与 cross 运输 | 独立 latent Gaussian / 矩阵 congruence 一致 |
| H21 补零后的完整 joint gain/均值/协方差 | NumPy latent QR 后验一致，clone 确有非零修正 |
| full reset、NED/ECEF connection、非零残差 pair H/gauge | SciPy 独立旋转有限差分及完整 GPGᵀ 一致 |
| marginal 退休 | 保留 current marginal，明确不同于 Schur 条件协方差差异 |
| full Sigma6、frame、非法 PSD/SO3 | 完整 cross 传播正确，非法域拒绝 |
| Young unknown-cross bound、固定 W、SKIP | 已知非零 cross 合成模型不突破工作上界；SKIP 原 mean/P 精确保留 |
| 大创新 | NULL/PAIR 同样拒绝、正常退休、无状态/P更新 |
| exact source、同刻 GNSS 在前、ID 单次、旧辅助隔离 | 事件时刻/计数一致；脚事件不触发 RD/RP/HV/SA |
| 零 scale、首末 IMU 支持、timer RETIRE | 冻结块保持零；无未来传播；无 source 的 timer 可解析 |

默认 off 测试核了默认值、禁止足输入、旧 current21 输出形状、同一路径确定性与非法配置；未运行旧二进制差分，因此不声明新旧 binary 字节 parity。NULL 与 PAIR 的共同 full reset 本来就区别于 legacy no-reset；后续真实结果必须与共同调度/共同 reset 对照归因。

新 demo SHA-256：f29010e5ba2d000276b6ac0b2be0dd33b4c3a0f2fa4d8884c25b6ca110bd24aa。

独立只读源码审查由 planner 完成；测试源的进一步静态 oracle 审查若有问题应另记录，不改写本次首轮日志。下一步真实 loader-only、6 条导航或评价仍须单独登记。
