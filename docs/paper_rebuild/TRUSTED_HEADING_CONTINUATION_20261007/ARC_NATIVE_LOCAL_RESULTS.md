# ARC 原生联合姿态日志：局部资格结果

24个独立合成用例均已有通过证据：首次登记dcce5bb实际23通过、1失败；登记b87ff784修复测试夹具后，只复验受影响的第4、第6项，2项通过。共26次测试执行、55次合成harness调用，绝非“首次24项全部通过”。原始失败及其输入、输出、Junit、调用与访问日志完整保留。

首轮configure/build/两个harness编译成功。失败来自合成夹具直接构造PortOptions遗漏diagnostic enable；真实loader已自动使能。生产代码无需修复，原噪声和调度未变。修复只补夹具标志，并加强case6实际HV接受断言。补验四次harness各有GNSS/RP/HV=3，三条BODY更新全部接受；同刻GNSS/辅助/HV更新及feedback先于ARC端点记录、NULL与TELEMETRY的NAV/STD/IMUERR/heading/body/ARC共有输出逐字节相同。

已覆盖严格事件schema和精确double时间、空端模型保留、IMU增量拆分守恒、同刻顺序、实际joint update/reset及P24到P6的坐标映射、未覆盖/错序/重复处理、模式互斥和冻结尺度。旧16项原生clone回归通过。测试直接驱动GIEngine；真实YAML loader的ARC字段还需下一阶段3次loader-only验证。

本阶段共1 configure、1生产build、3 harness compile、2 pytest；真实完整窗native=0、evaluator=0。首轮访问审计见ARC_NATIVE_LOCAL_ATTEMPT01_AUDIT，修复审计见ARC_NATIVE_LOCAL_REPAIR_AUDIT。访问结论限实际跟踪的openat/execve。

这只证明实现的局部合同及空模型两臂一致性，不证明协方差已校准、物理到达时间已知、状态与相位独立或真实航向/导航受益。已冻结demo/library可用于下一登记，但不自动授权读入相位值或做导航更新。

下一步先准备全921块1842端点的来源时间表，明确精确时间映射、缺失fingerprint与全分母；用新库编译loader checker并验证3份共用config。之后才进行拟定6次同算术的空相位两臂诊断。源相位数据不进native，不进行评价或信息增益数值读出。
