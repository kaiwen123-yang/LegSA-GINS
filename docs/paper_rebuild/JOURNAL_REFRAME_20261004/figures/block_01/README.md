# READY 01：原 V3 全窗连续曲线与完整自然消融

4 张图均提供 300 dpi PNG、PDF、可编辑标签 SVG。暂用读者标签 **Proposed**，不改正式方法名称或历史结果。所有科学内容取已经保存的评价 CSV；没有运行求解器、评价器，没有读取原始参考载荷，没有平滑、拟合、评分或补齐缺口。

|图|单一科学问题|推荐位置|
|---|---|---|
|R01_BY2_full_window|BY2 全窗位置和航向误差，保留两接收机 IEKF 的局部不利时段|主结果|
|R01_BY2H_full_window|BY2H 全窗误差；IEKF 的几何审计 FAIL 必须与曲线一起读|主结果|
|R01_BY2O_full_window|BY2O 全窗误差与两段已有遮挡窗，保留遮挡前后全部尖峰|主结果|
|R02_natural_all_11_configurations|原 11 配置在三条自然序列上的全部 RMSE，保留小幅与非单调变化|消融/附录|

前三图将位置和航向分成上下两个大面板，每个序列独立占页。图例分数为**匹配历元/自身实际输出历元**；不是名义 500 Hz 网格、物理时间全覆盖率，也不是共同支持或独立样本数。原 F04 分母 B/H/O 为 56642/58580/76548，LC01 为 58014/59934/78441；各自支持表在 `data/curve_support.csv`。原始 V3 的旧 IMU 积分/缺口行为保持历史身份，图不证明当前诊断代码正确或完整连续输入。

LC01 起点 B/O 为 FILE_START，H 为 CONTRACT_START；H 几何审计失败仍显式写入页脚，不把数值当合同合格的优势证据。位置评价沿旧 evaluator v3 声明双天线中点；参考是共享 GNSS 的商业融合结果，不称独立真值。BY2O 灰带是原有 3369.94–3411.95 和 3495.94–3508.94 s 窗，图中改用从正式窗起点起算的 elapsed time。

消融图第一条为 Proposed，随后四条是分别关闭 raw Doppler、source weighting、roll/pitch prior、body-velocity prior；组合关闭与基础配置由横线分开。33 个自然运行均完成，原匹配/输出分母与状态在 `data/natural_all_33.csv` 保留。F01 初始化也用共同双航向，不能称全流程纯单天线。F02/F03 的 receiver velocity 不同，不把五配置梯当严格单模块递增。自然窗差异不能单独证明任一模块普遍必要。

`build_core_figures.py` 是独立作图脚本，只用 csv/gzip/hash、NumPy/Pandas、Matplotlib，不导入 pipeline。6 个小型 gz 曲线副本仅取绘图列、保留所有正式窗行与原 decimal tokens；没有降采样。`BUILD_RECEIPT.json` 保留原源/解压载荷/图副本哈希、原 uncertainty pin 索引、绘图方法和全部导出哈希。输入读取后字节不变。每条曲线在实际时间间隔超过 0.1 s 处断开，不跨缺口画连线；所有保存样本仍绘制。

最终 4 个 PNG 已逐一实际打开核查：标题、图例、轴、页脚与全部不利数据均可见；消融页脚曾与横轴标签挤在一起，正式 READY 版已调整下边距。PDF/SVG 是同一 Figure 的另格式导出，本块未另外渲染 PDF，不扩大视觉审核范围。无图片/照片 AI 编辑。
