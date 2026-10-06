# N12_ONLY：当前顺序条件创新

隔离源码由上阶段已验证的 frozen ca73 + 只读 observer 副本开始。科学差异见 `candidate.patch`；合并公共 P 观察层后的全差异见 `TOTAL_CANDIDATE_AND_OBSERVER.patch`。正式源码/二进制未改。

OIM 的 residual、norm、NIS 与原 fallback 改为当前事件 `nu=dz-H dx_before`。S 使用同一事件当前 P 和 pre-SA R。dof、归一化、阈值、LSIM、cap、先行门、RD SA-off 硬门、历史缓存更新逻辑（缓存统计随 nu 变化）、顺序和 EKF 原 dz 均保持。metadata 的 raw norm 独立保留，不影响 LSIM。没有再次调用 policy.evaluate。

本轮新增两个原生合成进程，各9场景；只使用人工状态，未读真实 provider/reference。独立 NumPy 同快照核算170项均通过：dx=0 与旧式状态/P完全相同；dz=Hdx 时候选NIS为0而旧式大于0；非对角S、连续两次更新P阶段、fallback、实际EKF只扣一次、SA-off、yaw硬门、RD SA-off硬门均覆盖。新计算是 validation calculation，不能冒充旧回执。`TEST_RECEIPT.json` 保存每场景旧/新NIS和实际scale。

失败保留：首次夹具编译误用了私有P接口（退出1）；仅夹具改用 public EKFPredict(Phi=0,Qd=P) 和 getCovariance 后重新编译，候选求解实现未因测试修改。首次 Python 核对遇到配置记录没有 snapshot 的 KeyError；修正schema分支后读取同一批输出，无原生重试。原编译stderr、全部测试输出位于 `<VALIDATION_BUILD_ROOT>/N12_tests_v1`，未清理。

READY绑定实际candidate binary、源码全清单和补丁hash；这只通过代码/原生门，不代表真实性能或全V3通过。下一项只运行注册C00 F04与D15 seed_00 F04，基线复用。
