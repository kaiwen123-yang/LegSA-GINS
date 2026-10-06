# READY 02：原 BY2 轨迹与三序列三轴姿态误差

本块 4 张图均为原 V3 已有保存载荷的独立重画，300 dpi PNG + PDF + SVG。没有运行估计器/评价器，没有打开原始参考文件或修改原数组。

`R03_BY2_original_trajectory` 用原 RUN_00004 保存的 MATCHED_TRAJECTORY.csv.gz，56642/56642 个匹配/自身输出历元。WGS84 ECEF 后固定 East/North 显示，锚点仅取首个保存参考 LLH；不旋转拟合轨迹，不移估计去对齐参考。估计与参考均沿原声明双天线中点，保留全部正式窗行。共享 GNSS 的商业融合参考不称独立真值；green/orange 标记首末实际保存点。

`R04_BY2_attitude_errors`、`R04_BY2H_attitude_errors`、`R04_BY2O_attitude_errors` 把 roll/pitch/yaw 分成三个大面板，完整保留原 frozen evaluator v3 误差和不利尖峰。B/H/O 分母56642/58580/76548；只是一一匹配的实际输出行，不是名义500Hz全时覆盖。超过0.1s的时间间隔断线，不平滑或补齐数据。

本轮已确认 H/O 原 V3 的 native NAV 和匹配轨迹数组未保留，不能用当前 IMU 诊断或 FGO 新轨迹冒充原全矩阵结果。本块仅提供可以合法重画的原 BY2 轨迹；H/O 现有连续误差仍完整可用。后续 FGO 的 H/O 轨迹如展示，将明确另立身份。

输入/解压/副本/所有导出 hash、BY2 固定显示锚点在 BUILD_RECEIPT.json；小型列副本在 data/，保留原 decimal tokens 和全部行。脚本依赖上一层 `plot_utils.py`，utilities SHA已绑定。最终4PNG均实际查看，标题、全轴、支持分母和页脚完整；PDF/SVG同Figure导出，本块没有另外渲染PDF。
