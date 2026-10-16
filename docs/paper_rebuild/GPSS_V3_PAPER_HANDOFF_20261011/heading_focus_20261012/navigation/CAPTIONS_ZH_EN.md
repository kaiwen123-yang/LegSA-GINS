## F03_event_routes_and_heading

三种场景中与实际运动事件对应的轨迹及航向误差。左列在米尺度展示事件期间参考与本文的局部轨迹，等长箭头为机身航向，小窗定位完整路线；右列上方展示本文与两种双位置IEKF的航向误差，下方给出同一事件的位置误差。前两行使用仅由参考姿态确认的首个20秒转弯；第三行展示首个登记遮挡及前后各10秒，灰色表示实际遮挡。空间误差很小时轨迹重合是预期现象，右列以角度和厘米直接量化。误差保留各方法冻结评价契约，局部窗口不用于重新定义全窗排名。

Event-aligned routes and navigation errors. The left column shows metre-scale local reference and LegSA-GINS trajectories with body-heading arrows and a small full-route locator. The right panels show heading and horizontal-position errors for LegSA-GINS and both dual-position IEKF parameter settings during the same event. The first two events are the first reference-confirmed 20-s turns; the third spans the first registered antenna obstruction with 10 s of context on each side. Gray shading denotes the registered obstruction. Equal-length arrows encode body direction, not speed. Frozen evaluation contracts are retained; event selection does not use estimator errors.

## F09_heading_comparison

航向精度的解级滤波与因子图比较。（a–f）三条自然记录中，本文、双位置和单位置IEKF的文献/标定参数，以及按既定IMU数据段重新初始化的OiSAM，在全部方法共同支持的名义时刻上的有符号航向误差与绝对误差累积分布。误差定义均为机体NED航向相对参考的环绕角差；不混合位置参考点。灰带表示登记遮挡，缺少动态输出处断线。自然比较使用原登记起点，大幅运动的双位置IEKF几何审查例外在完整表保留。（g）首个登记20秒位置中断中的航向过程，金色点划线为保留基线IEKF；本文保留可用方向和机身辅助。（h）全部18个中断布置的整窗航向RMSE，每点一个案例，短黑线为中位数。自然与中断两类实验使用各自既定输入协议；无误差优化选窗。

Heading accuracy across solution-level filtering and factor-graph methods. (a–f) Signed heading errors and absolute-error ECDFs at common nominal dynamic epochs for LegSA-GINS, the literature/calibrated dual- and single-position IEKFs, and OiSAM reinitialized on predeclared recorded-IMU blocks. Curves break where dynamic output is unavailable; gray spans denote registered antenna obstruction. Native initialization conventions and the large-motion geometric-audit exception are retained in the full companion table. (g) The first registered 20-s position interruption, including the baseline-retaining IEKF in gold; LegSA-GINS retains available direction and body-motion aids. (h) Whole-run heading RMSE for all 18 registered interruptions; each point is a case and black ticks are medians. Natural and interrupted conditions retain their respective input protocols.
