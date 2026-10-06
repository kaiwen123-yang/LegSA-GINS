# 足对事件 provider：全窗工程输入登记

状态REGISTERED_READY：独立源代码审查与6项纯合成检查已完成，首次全通过；登记时尚未读取新的实测body。原V3三窗完整保留，共4605个固定0.2s机会。仅一次三条body前缀到窗末的读取，沿用锁中的raw身份与size检查，不重哈希raw，不调用GNSS/NAV/reference/AR/评价。

每个机会仅检查其后第一个实际body sample，若晚于机会0.05s、不足两个合格足、来源异常或已有区间，则保留该机会的失败原因。按FR/FL/RR/RL既有顺序取前两个合格足。START只用当前与过去资格；不得先看END是否成功再回选START。END为START后首个至少0.1s、至多0.15s的真实sample，全程必须同两个support episode。缺帧0.05s/区间超时以因果timer退休；source异常或token变更退休。端点一次使用，不换脚挽救失败。

足端body FLU经diag(1,-1,-1)成为body FRD。继承软件body轴约定，配置再显式给body FRD到engine body FRD的单位旋转及来源标签；不重复施加已用于IMU安装的Rx(-1°)。这不是独立实机外参标定。

仅使用timestamp、error_code、foot force/position；复用旧H5解析器会校验原始gyro/accel字段，但数值不用作观测。不读SDK rpy/velocity或foot speed，也不把SDK派生足点包装成原始编码器FK。

单档工作不确定度为每足点各轴sigma=0.01m。若四个点各自零均值二阶矩确实不超过sigma²I，无论四点之间如何相关，其joint covariance受4sigma²I12上界，两个足差向量联合受8sigma²I6上界。END导出这个上界，未声称端点独立；物理假设未校准，偏置/滑移/内部滤波尾部不被自动覆盖。不会根据后续更新次数或误差修改sigma。

50列EVENTS.csv为START/END/RETIRE，完整机会和坏输入另列。事件带原source时刻及离线可用时刻；原NAV最后IMU之外的末端事件不得触发外推：native仅在实际最后状态边缘清理clone，单列未消费的末端cleanup/超支持端点，保留覆盖限制。

真实输入执行前，root须审本地合成结果，冻结最终source pins并提交REGISTERED_READY计划；只允许本次输入生产，不自动触发native或评价。
