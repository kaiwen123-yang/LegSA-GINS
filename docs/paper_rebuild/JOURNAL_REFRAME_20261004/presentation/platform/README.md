# 实际安装照片的学术图版

`Platform_photograph_and_detail.png` 为两面板照片：(a) Unitree Go2 实际装置；(b) 同一原图顶部装置局部放大。正文或图注可说明 GNSS、机体 IMU 与参考的实际测量链，照片本身不代替安装标定。

原 JPEG 逐字节保留为 `Original_installation.jpg`；SHA256 为 a5aac11a5cde1e99bd31d0342b5e3351d428e92ae5f74ef5547f9a35508cb64b。主图只用原始像素的显示裁剪、等比例排版、英文面板标题；无物体移动、去物体、补画、锐化或坐标/尺寸推测。左裁剪 left=.355,top=.28,right=.14,bottom=.12；右裁剪 .51,.28,.28,.53。矩形宽高按裁剪后的源像素比例设置。

通过 `@oai/artifact-tool` 的 native image crop 及 text 元素生成；脚本留存。脚本默认使用本任务 Windows 原始路径与私有渲染目录，重新使用时修改 root/src 为本机路径，并使用已有 Node runtime 和 artifact-tool。最终 PNG 2560×1320；实际打开检查设备比例、面板与文字。原照片尺寸不足以恢复不可见细节，放大区域保留原照片清晰度。

尝试过生成式透明背景处理，但为保留设备外观证据，本主图与完整报告采用原图裁剪版本；生成处理不进入科学证据图。此处未从照片确认天线1/2编号、相位中心、安装转角或杆臂尺寸。
