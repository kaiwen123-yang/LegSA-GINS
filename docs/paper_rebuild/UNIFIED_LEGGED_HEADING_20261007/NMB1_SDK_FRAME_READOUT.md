# NMB1 的 SDK 速度坐标：同源内部核对

2026-10-07。原始数据实际核对支持本记录中的 body-FLU 速度解释；没有改变在线输入或外参。不能仅凭官方示例的 Odometry-frame 注释将本记录改成世界坐标，也不能将这一内部核对称为独立真值标定。

使用与既有 BY 审计相同的 direction_diagnostics，比较 raw velocity 与 SDK position 时间导数，以及先用同条 SDK RPY 旋转 velocity 后的方向差。在两者水平速度均≥0.3 m/s的69,648个样本上，未经旋转的方向差中位数92.119828°，旋转后1.124320°；raw velocity相对机体前向的方向差中位3.361356°。未拟合安装角、时移或尺度。此结果排除了目前最粗的“把世界速度误当机体速度”解释，但不验证幅值、延迟、SDK或足点谁更准确。

一次原始文件读取同时保存完整足点、足速、足力、SDK位姿/速度及gyro，供后续源内诊断复用。cache为80,295条；原native窗口内80,271条字段完整。唯一不完整记录位于原native结束之后（40972.571833428 s，source_row 93267），保留在faults中，不把它描述为窗内掉数。全文件SHA为01d20699dff81fa0f8f13ee8b5d8956d30e1cd64ed59176a4bb65bfc768ec157。

脚本：scripts/paper_rebuild/unified_legged_heading_20261007/nmb1_sdk_internal_frame.py。
结果：UNIFIED_LEGGED_HEADING_20261007/NMB1_SDK_INTERNAL_FRAME_01/{PLAN.json,READOUT.json,NMB1_FULL_SOURCE_MOTION.npz}。整数native_ns保留原纳秒时间，映射使用既定base=1767571200和offset=-1100000000 ns，不重新校时。无GNSS、NAV或参考读取，无native/evaluator调用，无导航provider变更。

复现命令需显式提供`--source`和`--output`；source采用PLAN记录的原始文件。完成运行后仅将固定机器路径改为CLI参数，解析/坐标核对/缓存数学未变，未为此重读原始数据。
