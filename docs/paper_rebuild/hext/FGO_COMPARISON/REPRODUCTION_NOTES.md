# FGO 实现与评价约定

三篇身份和输入边界见 [FGO_SELECTION.md](FGO_SELECTION.md)。实现均独立编写，未声称作者代码逐字复现；真实参数在 `configs/paper_rebuild/fgo_comparison/` 首次主运行前固定。真实数据与合成计算测试分开；合成结果不进入性能表。

## 原文—函数—配置

| 方法/环节 | 原文 | 函数 | 固定配置与差异 |
|---|---|---|---|
| 原始未差分GNSS | Wen2021 Eq10/13–16；GNC2022 Eq4–13 | `raw_inputs.prepare / solve_code_wls / doppler_wls / code_sigma` | GNSS1 GPS L1CA/BDS B1I，广播钟差/相对论、Klobuchar、Saastamoinen、TGD与一次地球自转；单星座观测不分配另一钟偏。码STD用作者实现的cofactor平方根，明确解决Wen2021 Eq15/16权重命名矛盾。 |
| GNC伪距/Doppler图 | Eq5/13 | `gnc._Graph.residual_jacobian` | ECEF位置、每历元实际观测系统的米制钟偏；不分配自由速度。Doppler从原始频率解算，图STD 0.6m/s沿作者factor实际分母，保存WLS实际协方差诊断。 |
| GNC鲁棒机制 | Eq17–21、Algorithm1 | `gnc.gm_loss / gnc_weight / solve` | cGM=2，theta初值max(1,3max(r²)/c²)，每轮/1.4至1；按Eq21驻点用平方权重，Eq22印刷矛盾明示。完整批处理使用未来观测；无滑窗边缘化。 |
| GNC数值求解与缺测 | Eq23，未公开数值项 | `gnc._fixed_weight_solve / _prepare_graph` | 稀疏GN/回溯；固定收敛容差与足够预算见GNC_2022.json。WLS初值，缺初值仅在有锚分量内Doppler传播；无先验补秩。缺Doppler切断边；秩亏/不收敛分量主输出NaN，全部节点/观测分母仍保留。 |
| Wen TC状态与码/运动因子 | Eq21–23、30、32 | `wen_tc.TCProblem / solve` | ECEF p/v、体坐标加计偏置、实际观测星座钟偏；运动0.3m、偏置差0.01m/s²、INS联系0.15m/s。全批LM，无姿态状态/额外Doppler因子。缺末INS时未约束末速度不进入求解、输出NaN；其余图消元判秩，无阻尼冒充先验。 |
| Wen外部AHRS/INS速度联系 | Eq3、25–27 | `wen_ahrs.prepare_ahrs / wen_tc` | Go2 quaternion经既有FLU/FRD安装关系、一次A1初始全球定向；校准比力积分加正常重力及杆臂速度差。原始stamp重建精确增量dt；缺口不填。区间内以左端偏置积分，为原文逐点右端加速度偏置式的固定离散适配。 |

`raw_inputs` 复用既有RAWX缓存和广播库，不调用动基线求解器。缓存内容校验绑定前轮独立登记的INPUT身份；两接收机历元数与配对数均为1509/1483/2231且无配对失败，不因配对裁掉本次GNSS1历元。1Hz按距离整秒最近的实际RAWX时刻（容差0.05s）选取，保留实际时刻，不改写成整秒；原始/选中/名义缺失/各级筛选数量登记。传输与大气更正在原始码SPP近似位置计算，不借用任何完整导航轨迹。

## 初始化与缺测的事前处置

OiSAM与Wen AHRS只使用合法传感器初始化。BY2H体IMU在407.017–413.041s有真实缺口，BY2O亦有短缺口，已在主运行前从provider时间确认。OiSAM不跨缺口填IMU：保留失败节点，下一段连续IMU及合法GNSS位置/A1 yaw支持时独立重新初始化；每段一次初始yaw登记次数/来源，不形成连续航向因子。Wen保留码/运动/偏置图，仅缺失的INS速度边不可用。所有规则三序列相同。

## 输出与评价

OiSAM提供位置/速度/自身姿态，当前节点输出不回填历史；Wen TC输出位置/速度/偏置/钟偏，AHRS姿态只作输入；GNC仅GNSS定位，姿态字段不存在。Wen和GNC完整批处理使用未来观测；总离线时间不能解释为在线最坏延迟。

沿用每序列base_time及66–340、413–683、3186–3563s闭窗。1Hz名义窗口分母为275/271/378，另报告实际原生节点、有限节点、匹配节点与参考历元数，边界附近RAWX实际时刻不强制移入窗口。参考仅在独立离线评价进程读取，使用既有固定WGS84、参考插值和wrap角误差，不插值方法输出。GNSS-only输出点为GNSS1；reference中点按固定[0,b/2,0]FRD及reference自身姿态转到GNSS1。OiSAM使用既有IMU→POI转换。共同时间支持单列，不能消除不同输入/评价物理点的应用比较边界。
