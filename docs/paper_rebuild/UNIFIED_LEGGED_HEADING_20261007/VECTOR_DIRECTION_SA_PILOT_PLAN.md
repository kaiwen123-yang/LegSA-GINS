# 统一支撑/方向状态中的向量信息消费修正

2026-10-07，执行前计划；起点72af566。本轮解决已有完整三维方向协方差被scalar yaw metadata重复惩罚的问题，不引入新独立导航器。

## 实证问题及所选修正

原三窗rolling实际接受partial共302条，其中281条LSIM×6、17条×2、4条×1；638条完整carrier均×1。旧metadata用sqrt(R_NN)/0.35伪装yaw标准差，同一物理R与向量共同绕D轴旋转90°后，23/302条LSIM档位改变。弱方向已在完整R中弱化，旧scalar门又全向缩掉强方向的信息。两种有物理意义但不等价的scalar读法（atan2传播方差、固定其他姿态的局部yaw信息）不能选其中小值替代。完整证据由DIRECTION_VECTOR_LSIM_AUDIT.md保存。

最小修正：metadata增加scalar_yaw_std_available，默认true保留原scalar/正式V3语义，external 3D carrier置false；日志写NOT_APPLICABLE。只跳过LSIM中依赖scalar yaw std的规则，保留原观测vector、各向异性R、valid/time/quality、hard3DOF NIS、OIM、source cap及完整R/v/p/IMU bias/pose clone cross。没有缩小原测量噪声或改变阈值，没有从参考调权。支撑失效的原whole-engine replay会重建这同一策略历史。

集中实际C++ policy fixture验证坐标旋转反例、新vector规则等变、原scalar门及vector其他质量/创新逻辑仍执行；不扩大旧测试矩阵。

## 唯一匹配pilot

- 使用既有BY2O完整[3186,3563]秒、原REPLACE_SUPPORT+ROLLING配置和provider。该配置在相同后验真实使用足端XY、body速度、完整/部分carrier；不是heading-only输出对比。
- 原footXY本轮不改为XYZ；噪声、端点、SDK替换、初值、全部source provider与原source masks保持。明确SDK discrepancy=off、support observed axes=body0_xy，均为原默认。
- LEGACY使用已冻结c42f1609… binary；VECTOR使用本轮仅3份生产文件改动后的binary，两个binary独立复制。旧BY2O 4f79输出可以保留作历史身份参照，不假装它与新后端bitwise相同。
- 两次native、各一次原冻结evaluator，共2+2；每臂一个子PLAN并在运行前封存输入/二进制。没有更多参数或片段搜索。reference仅在native全部完成后由冻结评价子进程读取。
- FULL.csv和ROLLING.csv的原valid差定义partial供给，不能以本轮接受结果反过来挑partial样本。

## 如何判断

先检验修正的机制是否成立：实际SA记录中external scalar yaw std为不适用；旧伪std导致的×2/×6不再存在，原R与方向信息不变；保留OIM及真实接受/拒绝变化，并追踪足端/SDK后续接受及共用状态反馈。

完整报告原full/rotation/support transition/heading unavailable等所有固定输入分段，yaw/H/Up/p99/coverage与原生R/v/p/bias差、评价杆臂项分别记录。全窗相对参考yaw至少5%改善才称明显的相对航向信号；即使满足，也不等于独立真值认证或总体收益成立。若位置作用仍只亚毫米级或其他分量退化，必须保留该结论，不用几何PASS或更小创新替代导航净收益。

此pilot只改变信息消费的一处；可靠PVT策略不在本轮动作中改变（沿用原configured实验身份），足端观测/依赖撤销仍在同一个导航器。不会借本轮好指标追认NMB1足端共同平移模型，也不把已核参考退化当免除负结果的理由。总goal仍ACTIVE。
