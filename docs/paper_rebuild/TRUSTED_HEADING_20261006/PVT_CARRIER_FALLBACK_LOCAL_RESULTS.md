# PVT 优先、载波补缺：局部工程结果

实现完成，尚未进行任何真实导航或性能评价。8 个唯一局部测试首轮全部通过（6.28 s）；随后第 8 项补充原 PVT 辅助触发边界，两次单项复测分别通过（3.74 s、3.83 s）。累计 10 个测试实例、0 测试失败。首次通过后的二进制、日志与后续局部复测均保留。源码 pins、每次命令、原始 JUnit、harness 调用及预期负例退出由 [receipt](PVT_CARRIER_FALLBACK_LOCAL_RECEIPT.json) 绑定。

## 配置入口

保持原 V3 三份配置全部非航向输入、7 列 IMU 格式、初始化、P/RV/HV/RD/RP/SA 参数及标量预测公式；只为新研究 case 显式设定：

    runtime_contract: research_experiment
    heading_source_policy: pvt_priority_control  # 实验臂用 pvt_priority_fallback
    dual_antenna_measurement_model: baseline3d
    baseline3d_source: external_carrier
    external_carrier_baseline_path: <已登记的当前时刻 carrier15 文件>
    baseline3d_body_vector_m: [0, -0.35, 0]
    dual_yaw_prediction_model: <原配置实际公式：euler_yaw 或 lateral_projection>

新模式拒绝隐含 legacy 标量预测选择，避免更换 stage 字符串后悄然改变公式；具体值必须从原 V3 配置的实际路由确定，不能将全部输入统一改成另一公式。原 configured 默认路径不改变，也不新增强制 fallback。basic-only 方法不在本轮新模式范围内；原 F03/F04 科学身份不重写，新 case 使用研究身份。

固定时间常量：最近已到达 PVT 状态新鲜度 0.21 s；已接受的跨来源航向更新近时互斥 0.01 s（包含端点，浮点比较容差 1e-12 s）。未知、过旧或有效 PVT 状态都禁止尝试载波；PVT 自身被残差/SA 拒绝仍然是源有效，不切换到载波。同刻有效 PVT 优先。载波拒绝不占用互斥；载波已接受后 +2 ms 的 PVT 航向受抑制，但源状态仍立即更新为有效，下一 0.2 s 周期正常处理。反向近时互斥也生效。

## 验证内容

- 默认外部载波 replacement 仍不读取商业 yaw tokens；新 opt-in 才保留 GNSS18 的原 scalar yaw/std/validity，并严格检查源身份与显式 validity。
- 原 stage 的投影标量公式与显式选择保持一致；新 control 分别使用 Euler / lateral projection，与相应原 scalar exact-event 路径的状态和协方差精确相等。
- 全有效 PVT 的 control、fallback、无载波三个合成流，状态、协方差、传播次数精确相等；已启用 RD、RP、旧 NED HV 与 SA 的计数相同。载波受抑制时不调用 QA/readiness/辅助更新，不拆分 IMU。
- 现有 B3 NIS 拒绝后，+2 ms PVT 恢复可正常接受；载波接受后近时 PVT 仅航向被抑制，P/V 和原有辅助触发保持。
- 全无效 PVT 的同刻载波不能新增原来没有的辅助触发；相反，原 yaw-valid、P/V-invalid 的 PVT 航向受抑制时，原辅助触发仍保留。这是两次限定复测覆盖的边界。
- 无效 carrier-only 行与缺席观测的状态、协方差、传播计数精确相同；所有源行保留在 HEADING_SOURCE_EVENTS.csv，不是按结果删除。

BASELINE3D_DIAGNOSTICS.csv 记录实际 B3 尝试的测量/NIS；新 HEADING_SOURCE_EVENTS.csv 列出完整 PVT/载波联合事件的源时间、状态、资格原因、尝试和接受。RUN_MANIFEST 新增分来源尝试/接受/抑制计数及时间合同。PVT 与载波都通过已有 heading slot、但每次至多选一类；不将相同接收机信息作为独立双观测。

## 可执行产物与后续界限

二进制：<SCRATCH>/TRUSTED_HEADING_20261006/PVT_CARRIER_FALLBACK_LOCAL_ATTEMPT01/BUILD/legsa_v23_port_core_demo。它已编译但从未用真实配置执行。本轮只有局部 harness 调用；真实 raw、参考、整数搜索、导航和评价调用均为 0。

后续计划为原 V3 三全窗共同 exact-event PVT 对照 + 三 fallback。新研究 exact-event IMU 拆分、RD/RP past-only/每源一次与旧调度有差异，必须通过共同对照单独说明；不能拿旧 AB1110/IMU8 cropped runner 直接替代原 V3。旧非航向 provider 的历史插值/时序假设并未在本实现中被重新修正。

10 ms 只是已知近时错位的工程去重，不证明接收机周期关联、跨历元独立或整数完整性。当前 fixed-N covariance 仍是条件工作协方差，未包含共享 GNSS/IMU、选择和时序相关；本模块不把候选资格升级为可信 FIX，也不保证导航改善。必须由后续登记的完整窗结果检验。
