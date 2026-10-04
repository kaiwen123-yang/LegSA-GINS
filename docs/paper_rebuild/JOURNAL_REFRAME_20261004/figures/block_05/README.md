# READY 05：原接收机速度作用与真实航向接受状态

三个R11分别画原F02/F03的全部水平误差和yaw误差曲线。对三个序列逐行比对封存runtime配置，除run身份/标签/输出路径及ablation记录外，唯一数值功能开关为 `enable_receiver_velocity: false/true`；逐行差异存CONFIG_DIFF_EVIDENCE。两配置均保留共同dual-heading初始化。图中RMSE只转录原汇总，不重算原评价。BY2/BY2H略有改善、BY2O航向变差也保留，不能称速度对所有场景普遍改善。各曲线matched/output分母明确，仅表示原观察到的输出历元。

R12把原BY2 Proposed完整yaw误差和全部1369条真实native GNSS事件的航向状态同轴显示：NORMAL1225、DOWNWEIGHT123、REJECT21。它是算法接受状态，不能当参考精度好坏的标签，也不能把同图变化当因果修复收益。原trace的yaw residual字段全空，因此没有伪造创新曲线或重新推门限。

四图均白底宽图，300dpi PNG/PDF/SVG。完整saved样本均保留，时间间隔大于0.1s的线断开，不平滑/拟合/重跑。不读取rawreference或启动science。data/保存原decimal列副本，BUILD_RECEIPT绑定原源、每段配置、列副本、绘图代码与输出hash。最终4张PNG实际打开查看，坐标、图例、脚注与全部数据范围可读；PDF/SVG同Figure导出，没有独立渲染PDF。
