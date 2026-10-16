# 图4：同一运动记录在七种初始全局朝向下的估计结果

**中文图注。** 同一接触辅助InEKF在七种初始全局朝向下的运动估计。各次运行使用相同IMU、足位代理与接触输入，初始朝向为−150°、−100°、−50°、0°、50°、100°、150°，世界坐标中的初始状态与协方差按同一旋转变换。(a)各自全局朝向下的轨迹；(b)消除已知初始旋转后的共同相对轨迹；(c)相对0°运行的位置差。最大差约1.89×10⁻⁷m表示数值等变性。0°复用主运行，其余六条来自已有回放。彩色突出三种代表朝向，灰色显示另外四种。

**English caption.** Motion estimates from one contact-aided InEKF under seven initial global orientations. All runs use identical IMU, foot-position-proxy and contact inputs, with initial yaw angles of −150°, −100°, −50°, 0°, 50°, 100° and 150°. World-expressed initial states and covariances are rotated consistently. (a) Trajectories in their respective global frames. (b) Relative trajectories after removing the known initial rotations. (c) Positional differences from the zero-yaw run, with a maximum of approximately 1.89 × 10⁻⁷ m measuring numerical equivariance. The zero-yaw result reuses the primary run; the other six are existing replays. Three orientations are highlighted in color and the remaining four in gray.
