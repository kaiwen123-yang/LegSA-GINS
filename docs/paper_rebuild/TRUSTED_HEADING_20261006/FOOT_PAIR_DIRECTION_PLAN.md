# 脚对方向独立内核：局部数学执行计划

范围：实现 foot_pair_direction.py 与最多 16 项独立物理/有限差分单元测试；不接 24 维滤波、不改 native，不读取 raw/reference/provider，不做真实航向评价。全部编辑与测试在 Ubuntu-22.04 WSL，Git 由 root 维护。本文件是执行计划，不是论文材料。

## 输入和数学合同

同连续支撑 episode 的预先指定有序足对 (i,j)，以 FootPositionEpoch 传两端足位置/足ID/接触token/时间/可用时间；保留两个独立端点ID及调用者已消费ID集合。断弧、未知连续性、重复端点或未到达输入拒绝，不自动选别的足。

两个姿态是相应时刻 body→ECEF 的 filter-state linearization，不能被标成另一个独立传感器。显式输入足端FRD→该姿态body轴的静态SO3与来源。四点Sigma的固定顺序为 [p0_i,p0_j,p1_i,p1_j]，每块按对应FootPositionEpoch的原FLU/FRD轴，保留全部跨时/跨足相关项。PSD允许退化，不floor、不求逆、不生成创新准入。

d0=p0_i−p0_j，d1=p1_i−p1_j，u1=C1d1；使用历史body0坐标的相对残差 h=d0−C0ᵀC1d1。按正号左乘feedback且h_new≈h−Hdx，有世界角H=[−C0ᵀskew(u1),+C0ᵀskew(u1)]，列顺序current/clone。它在非零残差时也保留共同世界旋转null；不把原ECEF残差的非零残差rank3带入本内核。

NED helper 显式接收 E=cne、K=vee(dE DRi Eᵀ)：当前位置H=C0ᵀskew(u1)K、当前姿态H=−C0ᵀskew(u1)E、clone姿态H=C0ᵀskew(u1)。clone增广J的P块=−K、PHI块=E。此阶段不把Earth机械编排复制进Python；E/K的来源和同一误差约定由调用者负责。

单非零足对的每端及联合旋转灵敏度rank2，非零残差时亦如此；不补绕足对方向的缺失自由度。零/数值退化足距拒绝。共同平移和共同杆臂精确消去，但不证明无滑移或绝对yaw可观。

reset helper 仅给实际正号左乘姿态retraction的局部Jacobian J_l(a)，含稳定小角分支。通过独立SciPy旋转exp/log中心差分核符号，非线性后验精确性不作声明。

## 来源与重复信息

position_source_id、covariance_source_id、frame安装来源必填；position_gnss_input_used必须显式提供bool或None（未知），不默认GNSS-free。IMU统计独立、无滑移、导航准入、绝对航向观测字段固定false。单次纯函数只能检查调用者提供的consumed集合，不能冒充全局一次使用ledger。四点共享误差由Sigma表达，不意味着与EKF状态相关噪声已解决。

## 固定检查上限

最多16项pytest：世界固定足/动态姿态/非零杆臂物理oracle；共同平移消除；双姿态H有限差分；当前NED误差完整H；clone增广；四点稠密Sigma与独立FD；共同误差PSD取消；FLU/FRD及足序；反向足对；rank2/null方向及非零残差的有限共同世界旋转不变性；退化；接触域；时间/重复；输入域与不可变结果；reset一般FD；reset零角/小角/近pi/非法域。

持久日志逐次保留。若失败，保留首日志与原因，修改后只重跑受影响检查；已通过套件不为补日志重跑。最终记录源码/测试哈希和实际调用，不扩展真实实验。全部结果仅证明局部工作模型的实现，不证明来源独立、可信航向或导航收益。
\n准备阶段修订（0测试/0数据调用）：root解析审查指出world residual在非零残差时的共同旋转gauge缺陷，首次执行前改为上述body0相对残差。旧准备源码和计划留scratch/FOOT_PAIR_DIRECTION/PREPARATION_WORLD_RESIDUAL_NOT_EXECUTED；未执行旧形式，没有覆盖运行结果。\n