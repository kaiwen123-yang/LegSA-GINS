## F03_100s_routes_with_spatial_detail

100秒事件路线、真实空间局部差距与同窗航向误差。三行依次为常规行走、大幅机身运动记录和遮挡记录。左列显示100秒完整片段，中列按固定参考中心展示1m或0.4m真实空间方框，坐标单位厘米；不同方法没有相对平移或误差倍率。方框来源分别为固定88–92秒和199.945–209.945秒数据，视窗外按空间轴裁剪。右列为同100秒航向误差，灰色仅标记实际登记遮挡。局部窗口由原参考事件和固定时长确定。

100-s event trajectories, physical spatial details and heading errors. Rows correspond to nominal walking, large-body-motion and obstruction records. Left: the entire100-s segment. Middle: a fixed1-m or0.4-m spatial square centred on the reference event position, with centimetre axes and no method-dependent shift or error magnification. Original samples from fixed88–92s or199.945–209.945s intervals are clipped only by the stated spatial viewport. Right: heading errors over the same100s; gray shading indicates the registered obstruction. All windows follow fixed reference-event rules.

## F11_full_trajectory_comparison

全部自然评价窗中的导航轨迹，按真实评价点分列。左列在POI中点显示本文、单/双位置IEKF文献与标定参数，以及单次初始化OiSAM的全部有效轨迹；右列在GNSS1天线点显示按记录缺口重新初始化的OiSAM、TC-FGO和GNC-FGO。参考线使用同一评价点；缺测和重新初始化块边界断线。OiSAM圆圈为首个动态输出，叉号为最后动态输出，左列文字保留输出分母。小窗围绕固定参考事件位置显示真实局部坐标差，没有拟合旋转/平移或人为放大误差。所有原生有效点均保留；零动态输出的方法不虚构轨迹。GINav原生IMU部分输出和相对里程计另页展示。 米尺度轨迹高度重合是实际结果，精度差应结合左列局部和误差配图读取，不将不同方法人为错位。

Navigation trajectories across the complete natural evaluation windows, separated by physical point. Left: LegSA-GINS, the literature/calibrated single- and dual-position IEKFs, and single-initialization OiSAM at the POI midpoint. Right: recorded-gap-reinitialized OiSAM, TC-FGO and GNC-FGO at GNSS1. Each reference uses the same point. Curves break across output gaps and initialization-block boundaries. Circles and crosses identify OiSAM first and last dynamic outputs; the left panels retain output counts over the full nominal windows. Insets show true spatial differences around fixed reference-defined event locations, without fitted rotations, translations or error magnification. All finite native outputs are retained; no trajectory is invented for zero dynamic support. Native GINav partial outputs and relative-only estimators are shown separately. Metre-scale overlap is expected; inspect the POI insets and companion errors for precision differences. No method-dependent offsets are applied.

## S11_GINav_partial_trajectories

GINav原生INS/IMU点的部分输出。圆圈标首个输出，叉号标最后输出，全部有限点保留，超过1.5秒间隔断线。三条记录分别仅77/275、2/271、5/378个输出；常规与遮挡记录触发原速度界限失败。淡灰POI参考路线只作地理背景，评价点不同，不用于计算本图位置误差。图中没有把部分输出称作完整运行。

Partial GINav outputs at the native INS/IMU point. Circles and crosses identify first and last emitted outputs; all finite points are retained and gaps exceeding1.5s break the curves. Output support is77/275,2/271 and5/378; nominal and obstruction runs triggered the original speed-bound failure. The faint POI reference route provides geographic context only because the physical point differs; it is not used to score these plots.

## S11_native_relative_trajectories

相对状态估计方法的原生局部轨迹。各行对应三条场景记录，各列为官方接触InEKF文献参数、示例参数、接触运动学积分。各方法保留自身局部坐标和初始方向，不额外拟合到地理参考，因此本图是完整输出形状与范围展示，而非同一绝对坐标中的精度比较。圆圈和叉号分别为评价窗内首末状态；相关一次10秒对齐的误差评价在既有相对运动表中保留。

Native local trajectories of the relative-motion estimators. Rows denote the three recordings; columns show the official contact InEKF with literature and default settings and contact-kinematic integration. Every method retains its own native local gauge, without a new fit to the geographic reference. These panels show complete output shape and extent rather than absolute-position accuracy in one shared frame. Circles and crosses mark the first and last in-window states. The previously evaluated one-time10-s alignment errors remain in the companion relative-motion results.
