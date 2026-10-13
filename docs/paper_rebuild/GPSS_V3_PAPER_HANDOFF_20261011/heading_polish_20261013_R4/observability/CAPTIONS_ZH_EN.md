# 图4修订图注：图面保留，来源与职责说清楚

**同一接触辅助InEKF的全局朝向变换检查。** 对同一段IMU、足端位置代理和接触数据，以七种已知初始全局朝向运行同一个估计器；0°结果复用H5冻结主运行，六种非零设置在H6阶段分别逐历元回放。初始世界表达状态及协方差同步变换。(a)原始坐标表达的路径；(b)消除已知初始旋转后的共同相对路径；(c)相对0°运行的逆旋转后数值差。该图检查预期的等变性质，七条曲线不是七种方法或七次独立采集，残差不是相对真实位置的定位误差。

**Global-yaw equivariance of one contact-aided InEKF implementation.** The same recorded IMU, foot-position-proxy and contact inputs are processed using seven known initial global orientations, with the world-expressed initial state and covariance transformed consistently. The zero-yaw result reuses the frozen H5 primary run; the six nonzero settings are separate H6 native replays. (a) Trajectories in the respective initial global frames. (b) Relative paths after removing the known initial rotations. (c) Numerical position differences from the zero-yaw run after inverse rotation. This illustrates the expected equivariance property, not seven competing algorithms or independent field trials. The residual is not geographical positioning error.

图面PDF/SVG/PNG/TIFF与已批准R3保持相同。原始身份、代码与日志证据见[七条曲线来源审查](../observability_audit/README.md)。
