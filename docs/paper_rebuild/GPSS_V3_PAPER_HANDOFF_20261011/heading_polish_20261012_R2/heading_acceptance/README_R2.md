# 图 5：R2 颜色、分组图例与高清精修

本轮仅修改视图。全部旧候选、已经锁定的 ratio ≥ 3 接受状态、原始评价误差、共同支持和输出分母均未改变；没有重新运行接受筛选或求解器。

图例左侧明确为 **Our direction observations**：

- **Ours: selected direction**：更醒目的蓝色 `#2563EB` 粗实线。
- **Ours: input before selection**：深灰蓝 `#64748B` 细虚线，表示同一观测链在原生选择前的方向输入。

右侧 **Baselines**：

- RTKLIB 默认：珊瑚橙 `#E76F51` 方形标记。
- C-LAMBDA：青色 `#009E9A` 圆形标记。
- C-WLS：紫色 `#8B5CF6` 叉形标记。
- DD-KF：深灰色 `#4B5563` 点划线。

C-LAMBDA/C-WLS 原始结果提高了可见度，仍使用细点/虚线；此前独立完成的 ratio 筛选结果使用空心圆/叉号及实线，图底直接解释。所有原始数值保留，没有把原始候选和筛选结果混成一个方法名称。

174 × 192 mm，最小字号 8 pt；600 dpi PNG 为 4110 × 4535，高清预览为 2740 × 3023。PDF/SVG 文字与曲线可编辑。

`R2_VALIDATION.json` 验证六个封存输入逐字节相同，全部方向路线指标表逐值相同。完整时序局部放大仍为既定 80–100 s 转弯，完整尾部仍到 180°。本轮只改变颜色、线宽和图例显示名称。

实际彩色/灰度检查完成，对齐与最小字号通过，PDF 碰撞检查 0 fail / 0 warn。预览：[F05](preview/F05_heading_error_comparison.png)。完整原理和双语图注见 `CAPTIONS_ZH_EN.md`；接受层原始说明见 `AUDIT_REPORT_ZH.md`。
