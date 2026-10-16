# Image生成记录与科学校正

日期：2026-10-11。工具：Codex内置 `image_gen.imagegen`。工具没有返回底层模型的可核验版本号，因此不自行填写模型型号。

## 原始素材与用途

- 作者的原始实机安装照片：`references/platform_original.jpg`，仅作为平台外形和安装组件的可核查来源；原始照片保留不改。
- 作者所给PADP论文截图：仅作为简洁技术线稿、图形图标、低饱和颜色和箭头组织的风格参考，不复制其机械臂/控制算法；截图本身保留在本地，不随仓库公开。
- 冻结V3方法信息流：原D01图及其technical_notes。共同状态、15活动误差维、历史方向/倾角构造HV和GNSS事件调度由已有源说明约束。

## 图1生成brief

Two-panel scientific technical illustration on a white background. Use the real author platform photograph to depict the gray compact quadruped, four articulated legs, blue top-mounted sensor assembly and the visible antenna/support layout. Use the provided example only for restrained academic illustration style. Panel(a) Platform illustration; panel(b) Lateral baseline. In the top view the front points up, GNSS2 is body-left, GNSS1 body-right, the nominal separation is0.35m, b=p2-p1 points left, x_b forward and y_b left. Do not invent a manipulator, wheels, additional antennas, measured IMU lever arms or unseen dimensions. Short labels in Arial/Helvetica; no decorative radio waves or photographic street background. This is a source-based technical illustration, not a documentary photograph.

第一稿生成文件ID：`exec-af368690-65db-4f24-92b9-083b3583bb3b`。检查后发现Body MEMS IMU引线落在机身按钮处，会暗示未确认的精确IMU位置；第二次调用要求去掉引线和点，只保留`MEMS IMU (onboard)`文字。最终生成文件ID：`exec-5f1b1928-b9b9-41f1-9988-566d054b2e95`，交付`Fig01_platform_image.png`。

## 图2生成brief

Original scientific GNSS/INS overview. Left input groups contain Body MEMS IMU, Dual-antenna GNSS, and Robot motion observations. One central shared state x=(R,p,v,bg,ba),P. IMU connects to inertial propagation; GNSS connects to observation update. Roll/pitch connects directly to the same observation update; body velocity passes through Frame rotation informed by Existing heading + tilt. State propagation and observation correction maintain the same state and covariance. Source quality and innovation inflate each observation covariance Rs=λsR0,s with1≤λs≤λmax,s; an innovation arrow leads from update to quality, and Rs returns to the update. Auxiliary updates occur at valid GNSS events. The shared state provides Attitude,Velocity,Position output. No contact/FK factor, integer ambiguity solver or independent second estimator. Crisp original line icons, restrained pale blue/green/gray/peach blocks, clear orthogonal arrows, no crossing of text.

生成与校正顺序：

1. `exec-b52ef180-e386-497e-986c-0e414ad15691`：视觉首稿，GNSS/IMU连线和P/Rs标签需修正，未作为最终图。
2. `exec-267e8c1c-3577-4904-86a5-d89998662d90`：调整输入顺序，正确的IMU→传播、GNSS→观测更新和Rs反馈；仍有多余roll/pitch→速度旋转连线。
3. `exec-86852238-d8e5-4992-93e4-e5ef72f0f08a`：删除多余旋转输入与拥挤的长虚线；roll/pitch直接更新箭头被生成工具一并删除，需补回。
4. `exec-2daa3e1d-4269-446d-9a6e-e3f0181f5667`：仅补回绿色机身观测框到Observation update的直接箭头；保留body velocity→Frame rotation。最终交付`Fig02_method_image.png`。

最终关系已按源方法逐项目视核对：IMU传播、GNSS更新、RP直接更新、HV预处理旋转、创新与Rs反馈、同一状态输出。生成图内图形图标不承担新的机械参数或数值证据。

## 原生分辨率与投稿制版

工具返回平台图1774×887、方法图约1815×866像素。高分辨率请求没有改变工具的原生输出尺寸；本目录保留原生PNG，不用上采样伪装新增分辨率。这两张是已完成科学关系检查的视觉讨论稿，174mm通栏下约260dpi，尚需最后高分辨率/可编辑制版。其余定量图已经具有174mm矢量PDF/SVG和600dpi位图。

AI使用将在最终图注/声明中说明；来源、用途和人工核验按官方政策保留：https://www.springernature.com/gp/policies/editorial-policies/ai-manuscript-preparation 。
