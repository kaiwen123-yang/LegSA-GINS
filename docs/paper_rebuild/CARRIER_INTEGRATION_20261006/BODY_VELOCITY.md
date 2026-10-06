# 因果机体系足式速度实验输入

BY2 的原始高层日志在本机 WSL 内解析，得到 66–340 秒 56,643 条有效记录。专用 provider 只读取当前消息的 stamp、velocity、error_code；不读取 GNSS、参考轨迹或姿态，不插值。输入三维速度必须完整有限，但仅输出 FRD x/y 两维，FLU→FRD 的 y 轴取反不涉及航向估计。

本数据的 frame 依据是已完成的原始日志内部检验（HV_FRAME_AUDIT.md §2）：BY2 运动段 56,624 个样本的 velocity 与 position 差分方向中位夹角 99.1245°；使用 SDK rpy 旋转后为 1.1047°。BY2H/O 也支持本批日志的 body-FLU 假设。position 与 velocity 可能来自同一内部估计，这只支持分量语义，不证明精度。

Unitree 官方 read_motion_state.cpp 的注释称 velocity 为 odometry frame，和本批记录的内部证据不一致。因此不能把此转换推广到所有型号、固件或其他数据；未来新序列需检查其 frame。官方源：https://github.com/unitreerobotics/unitree_ros2/blob/master/example/src/src/read_motion_state.cpp

本轮共同固定 scale=1、σx=σy=0.20 m/s。该标准差是实验工程权重，不从当前导航误差拟合，也不是经过验证的统计协方差；此前 V3 的 GNSS/PVT 回归标度没有移植。时间相关性、内部估计和惯导的相关性仍存在。SDK 速度物理点与 INS 机体系原点暂采用零杆臂假设，尚无独立外参标定。

新的 native 接口在滤波状态上计算二维 body velocity 预测及姿态 Jacobian；由 .20 秒周期、IMU 时刻触发，最多使用已到达且不超过 .08 秒的源样本。独立载波事件不重复触发足式观测。缺失、异常和过期速度不生成有效更新。所有四个 body-HV 对照臂共享这组参数。
