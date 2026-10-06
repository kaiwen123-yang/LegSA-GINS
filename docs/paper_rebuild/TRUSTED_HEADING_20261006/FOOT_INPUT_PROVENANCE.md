# 足端输入与机体—IMU 外参来源记录

日期：2026-10-06。性质：工程来源审计；不含新的算法、实测或性能结论。

## 结论与使用边界

现有 BY2 输入按 Go2 **SportModeState** 的 `foot_position_body` / `foot_speed_body` 字段解析。已保存的官方接口定义和订阅示例支持“机器人报告的机体系足端状态”这一描述；它们没有闭合实机内部 FK 生成链、原始关节来源、采集版本或与 IMU 的统计关系。不得将其改称已确认的旧式 `HighState.footPositionInBody`，也不得将字段名称本身作为纯编码器 FK 的证明。

本次覆盖内没有找到已完成物理对应和标定的 **SDK body-origin→机器人 IMU 敏感中心** 外参。旧 GNSS 测量杆臂不是这个量；公开 URDF 的不同模型表示也不能任选一个替代实机对应。

因此，新有限区间足端位移内核目前是条件工程模型。它不能直接升级为“已验证、GNSS 无关且精确的当前速度”。内核输出是有限区间位移；来源的 GNSS-free 声明不证明其与 EKF IMU 统计独立。显式旋转、杆臂、协方差及交叉相关接口不得以零杆臂或独立噪声默认值补齐缺失证据。

## 已证实、工作约定与未证实事项

|事项|已证实或已声明|尚不能推出|
|---|---|---|
|足端字段|项目直接提取两个足端数组；官方 SportModeState 声明 float32[12]，公开订阅示例称其相对于 body|实机内部使用哪套 FK、关节/编码器输入、几何版本、滤波或状态补偿|
|实际消息身份|项目按 SportModeState 字段结构处理；公开示例订阅 sportmodestate / lf/sportmodestate|历史记录由哪个确切 collector、topic、firmware/build 生成；文本字段不能独立识别完整采集链|
|坐标与单位|项目维护 FLU、足序、传感器到机体安装旋转等合同|SDK body 精确物理原点、实机敏感中心、轴向与安装误差已测量|
|Hartley 适配|明确采用高层 FK-like translation proxy，raw_joint_encoder_urdf_fk=false|原始编码器 FK 已取得；代理等价于作者原始传感器输入|
|时间|解析外层 stamp.sec/nanosec，脚本采用因果源时间处理|外层时间就是芯片采样时刻；通信可用时刻、内部延迟或时钟关系已标定|
|统计关系|新内核允许调用者给出完整工作协方差及交叉项|足端字段与 IMU 独立，或必然依赖 IMU；两种结论当前均无充分证据|
|body→IMU 杆臂|新内核明确要求该输入；历史模型存在其他点位/杆臂声明|已取得该实机外参；不能自动填零|
|公开 URDF|已有来源审计记录两种命名/建模表示|任一模型原点已对应到当前 SDK body 原点和实机 IMU 中心|

## 可审计直接来源

路径别名仅为缩短显示：
- `<CODE_ROOT>` = `/home/kaiwen/research/LegSA-GINS-WORKTREES/audit-code-xbpg-20261001`
- `<EXTERNAL_ROOT>` = `/home/kaiwen/research/LegSA-GINS-EXTERNAL`

1. **项目实际字段读取，不执行 FK。**  
   `<CODE_ROOT>/src/legsa_gins/datasets/by2/go2_body_state_parser.py:198–215`：从外层 stamp 和各数组读取记录；`:254–268`：项目填入单位、FLU/body-relative 等语义标签；`:270–273`：逐元素输出足端数组。该路径没有从关节编码器计算足端位置。标签属于软件合同，不是原始消息携带的完整物理标定。

2. **已保存的官方消息定义与接收示例。**  
   `<EXTERNAL_ROOT>/hartley/unitree_ros2/cyclonedds_ws/src/unitree/unitree_go/msg/SportModeState.msg:1–3,13–15`：stamp、error_code、imu_state，以及足力/足端数组的声明。没有 FK 生成公式、协方差或精确 body 原点。  
   `<EXTERNAL_ROOT>/hartley/unitree_ros2/example/src/src/read_motion_state.cpp:16–28`：订阅 sportmodestate 或 lf/sportmodestate，类型为 SportModeState；`:50–58`：直接复制足端字段并说明相对于 body；`:36–37`：机器人整体 position/velocity 另称 Odometry frame。不能把不同字段的坐标说明相互套用，也不能把公开示例当作实际 collector 的证明。

3. **历史适配明确为高层代理。**  
   `<CODE_ROOT>/configs/paper_rebuild/horizontal_literature/hartley/stage_payload/04_METHOD_CONTRACTS/BY2_FK_PROXY_CONTRACT.yaml:10–20`：source_field=foot_position_body、source_role=GO2_HIGH_LEVEL_FK_LIKE_TRANSLATION_PROXY、raw_joint_encoder_urdf_fk=false。  
   同目录 `HARTLEY_STATE_AND_FRAME_CONTRACT.yaml:63–90` 是项目 frame/安装旋转映射合同；`:25–27` 的论文运动学变量定义不证明当前代理字段的生成来源。

4. **旧杆臂不可复用为 body→IMU。**  
   同目录 `H7_EVALUATION_CONTRACT.yaml:65–86`：模型将状态点称为 GO2_BODY_IMU_ORIGIN_USED_BY_REPRODUCED_INEKF；这只是模型点位声明。`:85–86` 明确 [0.03,0.03,-0.30] m 的角色为 SOLVER_GNSS_MEASUREMENT_LEVER_ARM_NOT_EVALUATOR_POINT_TRANSFORM。  
   同目录 `H7C_SOURCE_RECOVERY_CONTRACT.yaml:233–243` 要求两端点、方向、约定及适用配置等证据，并明确没有端点/方向证明时该历史杆臂不可准入。以上不是 SDK 足端 body 原点与 IMU 中心重合的物理证据。

5. **已有官方接口、作者事实与几何证据限制。**  
   `<CODE_ROOT>/docs/paper_rebuild/TIM_EVIDENCE_20261005/sdk_and_metrology/OFFICIAL_INTERFACE_AND_AUTHOR_FACTS.md:9–11`：作者同安装 CAD 等事实与缺失的采集/标定记录分开；`:17–28`：固定公开 SDK 提交、字段语义及实际采集身份边界。  
   `:32` 记录官方 `unitree_ros@5994d4faef0a9cadd3287f8de0199a67eeb2a259` 的两种表示：`robots/go2_description/urdf/go2_description.urdf:735–739` 的 base→imu 为 [−0.02557,0,0.04232] m、零 rpy；`robots/go2_description/xacro/robot.xacro:68–71` 的 trunk→imu_link 位于原点。本次复用已保存核查，没有重新打开网页或据模型猜实机点位。不同命名/建模表示尚未与 SDK body、实际敏感中心建立对应，不能据此选值。  
   同目录 `INPUT_UNCERTAINTY_BUDGET.csv:12–15` 将基线、历史 IMU-to-antenna 杆臂、robot-to-FP 安装及 POI 分列；U12 明确配置声明不是物理测量，相关不确定度未估计。

## 实际只读覆盖与命令记录

本轮只读收口使用 PowerShell 调用 `wsl -d Ubuntu-22.04 -- bash -lc '…'`。成功命令在 WSL 内用 `nl -ba` 配合 `head` / `sed -n` 查看以下内容；路径以以上别名规范化，选取范围与实际命令一致：

- BY2_FK_PROXY_CONTRACT.yaml：`nl -ba … | head -n 125`
- HARTLEY_STATE_AND_FRAME_CONTRACT.yaml：`nl -ba … | head -n 120`
- H7_EVALUATION_CONTRACT.yaml：`nl -ba … | sed -n "65,100p"`
- H7C_SOURCE_RECOVERY_CONTRACT.yaml：`nl -ba … | sed -n "225,251p"`
- OFFICIAL_INTERFACE_AND_AUTHOR_FACTS.md：`nl -ba … | head -n 44`
- 官方 SportModeState.msg：`nl -ba …`，文件共 17 行
- 官方 read_motion_state.cpp：`nl -ba … | head -n 82`
- go2_body_state_parser.py：`nl -ba … | sed -n "198,220p;247,275p"`
- INPUT_UNCERTAINTY_BUDGET.csv：`nl -ba … | sed -n "10,16p"`

首个尝试用 shell 循环读取两个 YAML 时，跨 PowerShell/Bash 的变量展开使文件名为空，返回两条 `nl: '': No such file or directory`；未成功读取或修改文件。随后改为上列显式路径只读命令。这是工具调用失败，与算法/数据执行无关。另一次组装本记录的工具调用在调用 shell 前因 JavaScript 环境无 btoa 而失败，没有读取或写入文件；随后使用 WSL Python 直接写入本记录。

覆盖限定为现有项目解析器、已保存官方 ROS2 接口/接收示例、已有方法与计量来源账本。没有全仓库/全外部源码穷尽证明，没有读取新原始数据或评价参考，没有查更多网页/URDF，没有运行算法、分析脚本或测试，没有测量实机外参。本次唯一新增产物是本工程记录，不改写历史数据、合同或结果。

## 对下一阶段的直接约束

可继续评审显式条件下的 pose-clone 数学与软件实现，但真实接入身份必须保留“SDK 派生足端代理、物理原点映射待确认、工作协方差、未证明 IMU 统计独立”。缺失来源不能由效果、轨迹拟合、零杆臂或扩大噪声替代。

单足给定相对旋转可构造有限位移，但不能检测滑移；共同滑移仍可能不可观。这些已在位移内核局部测试中作为模型边界保留，本记录没有增加或重跑测试，也不据来源审计提升其真实性能资格。

