## 保留航向时的机身速度辅助

机身速度辅助在GNSS中断中的条件作用。（a,b）一处20 s中断及恢复过程的水平误差，灰色为中断区间；（b）插图放大中断期间0–2.5 m误差范围。（c,d）同一实测路线中，每种时长九个中断布置的全窗水平RMSE，细线连接相同布置。两列分别为全部GNSS观测中断与保留航向的平移观测中断。所评价实现中，全部GNSS观测中断同时暂停辅助更新。

Conditional effect of body-velocity aiding during GNSS interruptions. (a,b) Horizontal error around one 20-s interruption; grey shading marks the interruption. The inset in (b) enlarges the 0–2.5 m range during the interruption. (c,d) Whole-run horizontal RMSE for nine interruption placements per duration on the same recorded route. Lines connect identical placements. Columns show complete GNSS loss and interruption of translational observations with heading retained. Complete GNSS loss also pauses auxiliary updates in the evaluated implementation.

## 来源加权的收益与精度代价

来源加权的收益与位置精度代价。（a,b）已保存的GNSS位置加噪案例中的水平和航向误差，水平标准差3 m、竖直5 m。（c）同次运行三个观测来源的实际协方差放大倍数。（d）541个案例的发散次数；两种配置各另有九例缺少有效初始航向。（e）双方均完成的513例的全窗水平RMSE。等值线下方表示完整方法误差更小，插图放大正常误差量级。案例来自同一实测路线的受控观测扰动。

Benefits and costs of source-dependent weighting. (a,b) Horizontal and heading errors in a saved GNSS position-noise case (horizontal standard deviation 3 m, vertical 5 m). (c) Recorded covariance multipliers for three observation sources in the same run. (d) Divergent runs across 541 cases; both configurations additionally have nine cases without valid initial heading. (e) Whole-run horizontal RMSE for the 513 cases completed by both configurations. Points below the identity line favour LegSA-GINS; the inset enlarges the nominal error range. The cases reuse one recorded route with controlled observation perturbations.

## 机载倾角辅助与姿态误差

三条实测序列中机身倾角辅助对横滚、俯仰误差的影响。蓝线为完整方法，橙色虚线为关闭倾角辅助；每列对应一个序列，上下分别为横滚和俯仰。

Roll and pitch errors with and without robot tilt aiding during nominal walking, large body motion and single-antenna obstruction. Each column shows one recording, with roll above and pitch below. The zero-error line represents the reference attitude. All curves use the same fixed parameters and their recorded timestamps.

## 基础GNSS/INS加入双天线航向的作用

基础GNSS/INS、基础配置加入双天线航向更新以及完整LegSA-GINS的航向误差。三列依次为常规行走、大幅机身运动与单侧天线遮挡。（a–c）完整误差时序，灰色区间在（d–f）放大。三种配置共享初始方向；前两种配置用于解释加入双天线航向链的作用，完整方法还包含其他辅助。

Heading errors for basic GNSS/INS, the same basic configuration with dual-antenna heading updates, and LegSA-GINS. Columns correspond to nominal walking, large body motion and single-antenna obstruction. (a–c) Full error histories; shaded intervals are enlarged in (d–f). All three configurations share an initial direction. The first two configurations isolate the addition of the dual-antenna heading chain; LegSA-GINS also includes the other enabled aids.
