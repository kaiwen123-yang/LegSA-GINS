# PAPER10G Legged Observability Theory Summary

结论：IMU + 足式接触/运动学/高层状态只能提供相对运动和 motion context，不能观测全局平移，也不能观测绕重力方向的全局 yaw。重力可以帮助 roll/pitch，但不能定义 heading。LegSA-GINS 因此需要短横向双天线 GNSS yaw 作为绝对航向源，同时用 source-aware/QM 处理短基线和 poor GNSS 可靠性。
