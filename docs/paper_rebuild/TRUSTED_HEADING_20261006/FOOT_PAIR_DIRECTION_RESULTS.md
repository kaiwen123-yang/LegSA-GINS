# 脚对方向内核：局部数学结果

已实现独立 foot_pair_direction.py；没有接入 native/provider 或 24 维滤波。Ubuntu-22.04 WSL 中 16 个唯一局部测试最终通过；实际 pytest 两次，首轮15通过/1失败，次轮仅重跑失败项1通过，总测试执行17次。所有日志及源码/测试SHA保留于相邻receipt。没有读取raw/reference，没有CILS/native/导航/evaluator调用。

## 实现前数学修订

原准备式 world residual 的解析H正确，但非零residual处不保持共同世界旋转null。root解析审查后，首次执行前改为历史body0相对残差 d0−C0ᵀC1d1。旧准备源码/计划留scratch，未执行，不能写成运行失败。

最终H的current/clone两块为相反的同一矩阵 −/+ C0ᵀskew(C1d1)。非零姿态残差的独立有限差分、有限共同world旋转不变性、联合rank2和轴向null均通过。两时刻C只代表filter-state linearization；没有新增独立姿态观测。

## 验证范围与真实失败记录

物理oracle从两只固定世界接触足、分别转动/平移的机体原点和非零IMU杆臂出发生成足位置，未使用production残差反造输入；确认平移和共同杆臂取消。还覆盖显式安装SO3、FLU/FRD、足序/反向足对、四点稠密Sigma、共同误差PSD完全取消，以及零足距、断episode、连续性未知、迟到、重复端点和非法SO3/协方差。

NED误差映射包含E/K位置项，clone增广包括−K/E。正号左乘reset J_l(a) 经独立SciPy exp/log有限差分，覆盖零、小角、一般角及接近pi；没有实现或检验联合滤波传播/更新/reset后的统计性能。

唯一首轮失败是clone位置映射FD中理论零元素得到8.3267e−17，略超过测试8e−17绝对容差。保留失败日志后，将该零元素的浮点容差改为8×machine epsilon；生产源码和数学未修改，仅该项重跑通过。首次pytest打印的负耗时属于报告计时异常，不作性能证据；receipt保存外层monotonic墙钟时间。

## 接口边界与采用判断

四点Sigma顺序固定[p0_i,p0_j,p1_i,p1_j]，按各端原FLU/FRD轴，包含全部跨时/跨足项；结果保留退化协方差，不floor、不求逆、不输出准入。SDK来源ID与position_gnss_input_used的bool/None声明分开，默认不证明GNSS-free；IMU统计独立、无滑移、绝对yaw、导航准入均为false。

端点一次使用检查仅覆盖调用者提供的consumed-ID集合，不是全局ledger。调用者仍须保证foot source时间、attitude状态时刻、available时间、episode和安装轴一致。当前无joint24状态实现，也未处理SDK误差与滤波状态相关性。

局部结论：该工程条件内核可进入root独立审查及下一项联合状态数学设计；不能据此称可信航向、独立速度、垂向问题已解决或真实导航改善。

root 与 comparisons 最终只读审查均无阻断；未追加数值运行。冻结仅限本条件数学内核，不代表联合滤波或实测已获准入。
