# 图1与图2：实物图和可编辑方法图

## 图1

![图1](preview/F01_platform.png)

按作者确认的方案移除整机AI插画，三面板为实物平台、同一照片中的传感器安装局部、矢量短基线几何。原图1706×1279像素，未改变亮度/对比度、未修补或生成硬件细节。仅使用两个登记的视窗裁切，坐标记录在qa/F01_SOURCE_AND_LAYOUT.json。两照片面板明确来自同一张照片。

右侧取消类似机器人外形的灰色装饰，采用简洁天线点、基线矢量与机体坐标轴。p1/p2移至天线符号下方，名义长度置于独立尺寸线之上。几何是定义图，不从照片推断哪个器件对应某个接收机编号，也不标未测量的IMU杆臂。

屏幕版2560×1147，600dpi出版PNG4110×1842，几何和文字保留矢量。安装局部的源视窗只有345×295像素，PNG尺寸增加并不会产生新的实物细节；若最终实物面板需要更多清晰细节，应换更高分辨率的原始近景。

English caption: Experimental platform and short-baseline geometry. (a) The quadruped with the installed sensor assembly. (b) A detail from the same original photograph. (c) Schematic position-pair baseline, nominal separation and body axes. The images are viewport crops without retouching. The geometry defines notation and does not represent surveyed lever arms or receiver identities inferred from the photograph.

## 图2与编辑方式

![图2](preview/F02_method.png)

本轮完全重建为矢量文字、框和连接线；不再用位图封装冒充可编辑图。Frame rotation的输入/输出端点共用y=107.5mm，历史heading+tilt从下方进入，roll/pitch沿独立支路进入有效GNSS事件门。

- [draw.io编辑文件](editable/F02_method.drawio)：在diagrams.net或draw.io桌面版选择打开文件。框、文字、连线是独立对象；主要连线附着于源/目标节点，支持拖动节点后继续调整。
- [可编辑SVG](figures/F02_method.svg)：可在Inkscape/Illustrator等矢量编辑器中修改。文字保留为text；数学公式可能由多个可编辑字符组成。
- [矢量PDF](figures/F02_method.pdf)：用于论文排版和清晰预览。
- [场景定义](editable/F02_scene.json)与build_schematics.py：用于一致重绘。

draw.io文件与论文SVG来自同一几何定义，字体度量可能因编辑器发生细微变化。PDF/PNG为已目视确认的论文输出。draw.io已检查XML结构与节点连接，不将它的第三方编辑器渲染结果视为已经逐像素验证。

English caption: Editable information-path diagram of the frozen shared-state estimator. IMU propagation and observation updates act on the common attitude, position, velocity, bias and covariance state. The position-pair branch constructs and selects heading; tilt and pre-rotated body velocity enter the update through the registered valid-GNSS-event gate. Historical heading and tilt support preprocessing only. Source quality and innovation govern bounded covariance inflation. The diagram changes presentation, not the estimator.

## 检查

两图PDF碰撞审计0 fail/0 warn，实际彩色图已查看。图1普通字体最小8pt、数学下标6.3pt；图2普通字体最小8pt、数学下标5.6pt。单个复合画布按非可比图轴记录，未声称具有数据轴的三等分网格。静态源码审计0FAIL；物理尺寸用真实PDF页面与记录核验。图1不含AI图像资产，图2不含任何图片资产。
