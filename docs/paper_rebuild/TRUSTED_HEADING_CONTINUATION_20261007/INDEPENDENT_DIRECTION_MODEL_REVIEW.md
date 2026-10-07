# 侧向投影单因素试验：独立静态审查

日期：2026-10-07。审查者为独立子代理。基点 HEAD 8cd93b2；审查对象为主代理拟登记的 direction_model_trial.py 和 MODEL_TRIAL_PLAN.json/md。最终核读 runner SHA256=e33d580c16ee51eb42c99aab930518be6ae1cfdf5300fb53475e822ba1ab84a1。

结论：在下述单次注册、单输出目录及失败停止合同内，未发现阻止这组三窗单因素试验的剩余问题。此结论是静态审查，不是 loader/native/evaluator 通过或性能结论。审查者未 import runner、执行算法、测试、loader、native、evaluator 或 comparison，未读原始/参考 payload，未修改 runner/计划或 Git。

## 已发现并由主代理修复的问题

初版 prepare 只要求输出在任意新 scratch 目录，而每次预算账本仅位于该目录。同一登记可通过改 stage 路径重复三次科学调用。主代理已增加唯一 new_stage：<SCRATCH_ROOT>/TRUSTED_HEADING_CONTINUATION_20261007/DIRECTION_MODEL_ATTEMPT01；独立核读 prepare 第98行、checked_plan 第161行均校验其解析路径，compare 第361行只允许该 stage/COMPARISON，创建均禁止覆盖。修复没有改算法、数据、窗口或采用门。

## 审查链和依据

- runner 第38–48行绑定注册状态、三固定身份/窗口/预算、提交中 runner/plan 的原字节及 source pins。第65–84行核旧阶段 PLAN/PREPARED/native seal/evaluation seal、六旧身份、旧binary/checker/evaluator/V3 lock。旧native source不冒称当前C++。
- 第102–128行只克隆旧 PVT_CONTROL；要求其模型=euler_yaw、来源策略=pvt_priority_control、research runtime、7列/500Hz IMU和原窗。仅允许六个元数据/输出字段及 dual_yaw_prediction_model 改变；除此全部行字节、解析科学字段、五provider与旁路carrier路径相同。配置是逐行文本克隆，不经YAML往返写出。
- 复核旧登记 3c81e5b 的 gi_engine.cpp 第1129–1153行：显式 lateral_projection 同时切换实际机体左侧轴的水平投影 h 与对应三分量 H；近竖直抛出明确失败。显式 euler_yaw 不依赖新stage名选择旧legacy特例。因此控制/作用差异为一个完整量测模型选项；不是新AR或foot clone。
- loader 使用已封存 checker，0编译；第50–59行 reservation 先于各次调用并持久化，无自动重试。native 目录已存在即拒绝。三个native在完整读取审核、有限/时间支持检查及失败分类后才输出 ALL_NATIVE_SEALED；技术异常写FAILED并停止，旧运行不重做。
- evaluator 第244–247行要求三身份输出完整封存并核文件哈希，之后才走既有 protocol_v3/evaluation_process.py。该传输只在冻结评价子进程读取reference，核一次只读打开/哈希/进程身份；父进程仅使用已锁元数据。发散行不调用评价，指标NA。
- 比较复核 compare_clone_window_navigation.load_run/coverage_row/paired_effects 与 compare_full_window_navigation.common_errors：核NAV/评价文件在seal内、实际唯一时间键和物理评价点；V3旧误差序列核hash和实际键。common来自精确键交集，不插值、不从summary伪造；完整支持与共同支持分别报告。缺失不给零分，覆盖减少不能通过原门。
- 已确认原A门、H/V/yaw九指标非退化容差、最大值和事件报告未移；模型采用还需匹配Euler的完整/common正增量。B、整数正确率、风险和独立速度仍NA。原manifest计数缺陷保留，由原生heading事件另派生计数，PVT_CONTROL要求carrier尝试/接纳为0。

## 不能由本试验推出的结论

旧HV保持不变，其中原有整窗插值航向依赖没有消除；本试验不是整链因果化、GNSS/腿输入独立化或风险校准。共享GNSS商业reference只能给相对该参考的一致性证据。仅模型切换的数值改善不能被写成AR、腿约束或新载波贡献。所有主分支采用仍需用户审核。

覆盖：读取runner、MODEL_TRIAL_PLAN json/md、full_window_navigation transport、两个comparator、runtime/frozen相关解析与支持函数、evaluation_process传输，以及旧登记的h/H源码。没有全仓穷尽证明或新执行验证。运行时仍须由主控确认登记提交、各预算与实际回执。
