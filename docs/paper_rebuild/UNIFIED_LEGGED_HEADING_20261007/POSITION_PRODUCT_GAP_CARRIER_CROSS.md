# 位置产品缺口：载波到共同位置的直接交叉更新

仅读取已封存原生日志，完整保留源定义的30个gap partial和四臂。没有读取NAV/reference，没有运行求解器或评价器。

## 当前实现中的精确线性更新

external模型的H只有Hφ=[h]×，位置、速度、clone及公共杆臂列均为0。观测与R在nominal位置旋到NED，代码未加入该坐标旋转对位置误差的导数。以下是实际实现的重建，不把该省略补成另一物理模型。

`S = [h]× Pφφ [h]×ᵀ + (qa_scale · sa_scale) R`

`δμp = Ppφ [h]×ᵀ S⁻¹ innovation`。innovation已是dz−Hμ；不能再减一次。拒绝/未尝试实际增量为0。pose clone联合更新使用同一公式；H的其余列为0，故所记录当前边缘足够，不用补造clone交叉块。

GIEngine位置反馈为p←p−DRi(p)μp；对应NED反馈切向量为−δμp。这里没有P_vφ，因此不声称重建精确速度增量。

| arm | 源分母 | 尝试/接受 | 单次位置H修正 median / p95 / max，含实际0（mm） |
|---|---:|---:|---:|
| SDK_GAP_FULL_ONLY | 30 | 0/0 | 0.000000 / 0.000000 / 0.000000 |
| SDK_GAP_PARTIAL | 30 | 30/27 | 0.318131 / 0.770822 / 1.006790 |
| FOOT_GAP_FULL_ONLY | 30 | 0/0 | 0.000000 / 0.000000 / 0.000000 |
| FOOT_GAP_PARTIAL | 30 | 30/27 | 0.491392 / 1.220743 / 1.764993 |

## 真实cross参与及有限作用

两个partial背景都尝试30、接受27，3个拒绝时刻也逐一相同；未尝试/拒绝记实际0，不删除这些分母。local-full-only每臂对应30个源点全部实际0，缺失prior不以另一臂值填补。60个真实partial事件的prior姿态误差均值和位置误差均值实际均为0；公式仍使用已记录innovation，没有把零均值当普遍前提。

SDK / FOOT的Ppφ Frobenius中位分别为6.99963e−5 / 1.16523e−4 m·rad；已接受观测的Kp水平块Frobenius中位为0.0131353 / 0.0220445。包含实际0的均次水平修正RMS是0.417220 / 0.689994 mm，accepted-only median为0.360299 / 0.566341 mm。由此可确认：同一个足端替代SDK背景改变了共同交叉协方差，并增加了部分方向更新对位置的直接作用幅度；它不是heading-only展示或纯评价杆臂项。

这种作用仍小：单次Ppp水平trace缩减比例中位SDK3.40883e−6、FOOT1.03977e−5；FOOT最大6.64541e−5（0.00665%）。这说明当前共同Gaussian模型中，每条carrier对位置直接边缘信息的作用有限，不意味着真实位置精度提高了该比例。持续可用的速度源、支撑更新和后续传播决定最终结果；本读出不替代四臂轨迹/评价交互。

内部重建核对：innovation = dz−Hμφ 最大差0；原hard NIS最大绝对差6.8923e−13；乘积qa×sa×R的trace与真实SA日志最大差4.8154e−11（日志舍入）。没有使用先验Ppp/姿态对角值猜测K，没有重写载波模型或增加观测。

## 限定

上述每观测修正不等于最终p差，更不等于真实误差或相对参考RMSE收益。不能把逐次RMS求和当累计位置误差；后续SDK、foot、PVT velocity、Doppler、恢复position和传播还会改变同一状态。
SDK/FOOT对照的cross差属于两种完整历史和SDK替代政策的结果，不单独证明foot带来独立信息；Ppp收缩也不是精度认证。完整所有30行、未尝试/拒绝及conditional mean统计均保留。

机器结果：`/home/kaiwen/research/LegSA-GINS-SCRATCH/UNIFIED_LEGGED_HEADING_20261007/POSITION_PRODUCT_GAP_BY2O_01/CARRIER_CROSS_READOUT/SUMMARY.json`；完整源行：`POSITION_PRODUCT_GAP_CARRIER_CROSS.csv`。
公式重建与实际hard NIS、scaled R trace的数值核对见RECONSTRUCTION_CHECKS.csv，仅核对已保存量，不新增测试或native。
