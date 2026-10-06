# 安装、坐标与设备手册证据复核

## 本轮已经确认什么

作者确认 Fixposition 相机侧朝向机器人前端；所给 CAD 对应采集时同一结构，后续保存时间不作为结构改版证据。独立解析所给 ZIP 内当前 URDF 与 xacro、三份 STEP 的实体/单位声明，并对十份原始文件记录身份。完整读取 16 页手册文字，另目视核验物理第 3、9、10 页的规格表、坐标图和配置界面。原始文件不修改；SLDPRT/SLDASM 本轮只作身份读取，未声称通过本轮 SolidWorks 重新测量实体。

`installation_sources.json` 保存输入哈希、ZIP 内具体成员、全部 28 个关节、名义 IMU 变换、手册页定位与 STEP 声明；`inspect_installation_sources.py` 可用外部路径参数重做同一提取。桌面既有“坐标系与外参建模”目录的报告、原始组件变换与外参文件另作为**既有建模记录**阅读，不冒充新测量。

## 可以用于论文的事实层级

| 项目 | 证据与数值 | 本轮结论 |
|---|---|---|
| 实物方向及版本 | 作者本轮确认相机侧朝前、同一结构 | 可写实验装配说明；尚无安装小角度的测量不确定度 |
| 当前 URDF | `GO2_URDF/urdf/go2_description.urdf`，29 links，28 joints；`base→imu` 为 `[-0.02557,0,0.04232] m`，rpy=0 | 可写名义模型定义；不能自动认定实际敏感中心或 SDK 速度物理点 |
| ZIP 内 xacro | `GO2_URDF/xacro/robot.xacro`，`trunk→imu_link` 为零平移/旋转 | 与当前 URDF 属于不同模型声明；不能混合两个名字及数值构造已标定外参 |
| 原始 STEP | 三份均有毫米单位声明；总装有底座、支架、亚克力板、大天线等 PRODUCT | 结构来源可定位；STEP 部件原点不自动等于天线相位中心 |
| 厂商 Starter Kit 名义天线 | 手册 PDF 9 / 印刷 7 页：GNSS1 `[0.020,-0.175,-0.020] m`，GNSS2 `[0.020,0.175,-0.020] m`，相对表面 X 标记 | 名义横向基线 `[0,0.350,0] m`；在相机朝前且相应轴约定下为右/左天线，实际配置还须核采集记录 |
| 厂商输出点 | 手册 PDF 10 / 印刷 8 页：输出平移相对 X 标记设置；截图平移、旋转全零 | 证明支持配置，不证明本次记录一定使用零偏移；优先读取采集 TF/配置 |
| 既有 CAD 建模记录 | `09_reports/EXTRINSIC_DERIVATION.md` 明确 `base→FP=[0,0,0.275] m` 是可视化/流程占位值 | 本文不得写成通过 CAD 已测得 275 mm 的导航杆臂 |
| 既有 CAD 一致性报告 | `03_cad_audit/assembly_comparison.md` 记载原装配与 STEP 外包盒一致 | 仅继承当时 API 检查结果；不是本轮重新运行 SolidWorks，也不是相位中心校准 |

既有 `component_transforms_raw.csv` 中两个“大天线”**部件原点**的距离约为 0.3103 m。这个距离不能替换厂商 Starter Kit 相位中心基线 0.350 m：它们指不同对象/参考点，而且该组件表没有把相位中心与机器人实际敏感中心注册到同一测量坐标系。本轮不据此改 V3 参数或断言实际安装错误。

## 手册中不能当成不确定度证书的内容

手册 PDF 3 / 印刷 1 页的 0.4° 航向规格附带 **1 m 基线**条件；位置规格使用 R50、RTK fixed 条件，速度规格亦非当前整条测量链的协方差。上述值不能直接当本次 0.35 m 基线、步态振动、共同 GNSS 参考条件下的标准不确定度。

PDF 9 / 印刷 7 页对外参精度的 3 cm 要求，是配置指导。它不证明本次装配的误差具有已知 ±3 cm 界限或均匀分布，不应直接变为 `u=0.03/sqrt(3)`。既有 `extrinsics_uncertainty.yaml` 中的 `documented_accuracy_m: 0.03` 以及 ±2 cm/±3° 等范围本轮仅保留为文档或敏感性候选，不能进入最终校准预算。

PDF 15 / 印刷 13 页对 Minimal 记录范围的文字，不能取代实际收到 ZIP 的成员及载荷检查。新包能否进行 RAWX、相位/多普勒比较，要以包中实际消息字段和有效历元为准。教程内的操作、示例网络配置和更新步骤均是源材料内容，本轮没有据其执行设备设置。

## 对 TIM 证据缺口的具体影响

安装结构归属、名义坐标定义和原始模型位置已明确。仍需把实际采集的 GNSS1/2、FP sensor、输出 POI 变换，与机器人 IMU/SDK 输出物理点建立有依据的连接。若仅有刚体设计和作者方向说明，论文就报告 nominal mounting，给出尚未识别的安装偏差项；不要称为 traceable calibration。

时间方面，作者已明确用接收机位置/速度与机身 IMU 观察事件。此事实排除了“用商业融合参考最小化误差来对齐”的错误叙述，却不能单独确定偏移、漂移、消息延迟或起动事件选择误差。应使用每段原始记录的时钟和接收机信号做事件对应，并保留可识别性的边界，详见 `../sdk_and_metrology/` 与 `../data_and_selection/`。

当前可直接写入论文的方法句：

> The sensor was mounted with its camera side facing the forward direction of the robot. The author confirmed that the supplied mechanical designs represent the configuration used during collection. The URDF and manufacturer mounting dimensions were treated as nominal geometric descriptions; they were not used as substitutes for an independently surveyed IMU-to-antenna transform or a calibration uncertainty certificate. Temporal event matching used receiver position/velocity and the robot body IMU, without optimizing alignment against the fused commercial reference.

最后一句描述作者确认的操作方式；对各序列具体对齐实现及数值，应引用文件审计结论补充，不外推为所有历史版本均已证实。

## 重做命令

在安装了 PyMuPDF 的研究 WSL Python 环境运行下列脚本，源文件路径由使用者传入；不需要解压整个 URDF ZIP、安装 CAD 内核或修改运行配置。

```text
python3 inspect_installation_sources.py --cad-dir <original-cad-directory> --urdf-zip <Go2_URDF.zip> --manual <quick-start.pdf> --out <installation_sources.json>
```