# P01：11 个对象的输入资格与生成链语义

逐运行身份见 [DIAGNOSTIC_QUEUE.csv](DIAGNOSTIC_QUEUE.csv)，55个输入引用见 [INPUT_USES.csv](INPUT_USES.csv)。实际只有11个不同直接输入文件，均已全文读取并各核实一次SHA256，55/55与正式`V3_NATIVE_SUMMARY.json#provider_hashes`匹配；11份原配置与正式pin相同，冻结binary匹配`96ae436d…c1c`。这是现存载荷对正式记录的身份闭合，不声称重新执行raw生成链。原NAV/STD只取得历史OUTPUT_SEAL的pin，载荷释放状态见 [HISTORICAL_OUTPUT_HASHES.csv](HISTORICAL_OUTPUT_HASHES.csv)。

原求解源为ca73cb1f，runner为7d43b9af；原base BY2 bundle记录生成code为d01f2be8fb0ef1633d4871ec57b0e6d4e9de44a7，目标fault bundle为521901f0347e367281abed23b46686b84df86055。不能把它们统一写成同一个code_commit。原manifest还保留移植来源5a4471…字面值，外层协议另登记实际源。

## 真正输入与有效位

|输入|本轮读到的正文|实际有效/依赖|
|---|---|---|
|IMU I001|63,277行，44.889051..350.091049 s，7列|已经过固定预处理/标定的Go2 body输入；不把配置500Hz当实测采样率|
|GNSS I002/I006/I009/I011|各1,510行，55.799999952..357.599999905 s，18列|C00/D15三valid均1510；A1三个valid各100条为0；A2仅position/velocity各100条为0，yaw全1510有效|
|RD I003/I007/I010|各1,248行，56..357.6 s|C00/D15全valid；A1/A2各100条valid=0，另1148条valid=1；原值和行仍存在|
|RP I004|63,278行，44.8870780468..350.091049432755 s|原body roll及取负后的pitch弱先验；active不等于实际接受|
|基础HV I005|63,278行，update_flag/valid有效60,867，无效2,411|C00/A2/D15共用同一文件；std_vd全部999，实际水平二维路径另核|
|A1 HV I008|63,278行，update_flag/valid有效57,024，无效6,254|上游旧status heading中断收缩准备支持，不能与调度入口阻断合并|

本轮导出的 [INPUT_FIELD_QUALITY.csv](INPUT_FIELD_QUALITY.csv) 全部必需字段不存在缺列/缺值、非有限、非法数值；无畸形行、相邻重复或逆序时标。结论仅限11个读取文件，不能由此关闭N15的全部代码风险。真实到达时间未提供，保持UNKNOWN；`source_time`与`time`也不互换。

原运行配置完整范围为66..340 s；保持全部原文件及原初始化，运行器按冻结读取/跳过逻辑处理此前行。没有把故障窗裁成新的求解起点。A1/A2的case_meta和components都为anchor206.2、区间[196.2,216.2)，这两个指定case的边界相同；有效样本支撑还受采样格、准备插值、匹配与调度限制。

## 主航向与HV准备航向的两条链

V3 `src/legsa_gins/paper_rebuild/protocol_v3/providers.py::lift_heading`（7d43b9af）只替换GNSS18零基13 yaw与17 yaw_valid，其余token/空白有原byte gate。`t5a_provider.py::raw_yaw_from_ned`使用raw HPPOSECEF的GNSS2−GNSS1，通过固定ECEF→NED和安装变换；exact iTOW配对，R5要求两NAV-PVT carrSoln均为2。缺raw/PVT不插值、不开B3、不按离线误差选角。

HV使用`clean6_sensor_v21/providers.py::correct_hv`（521901f）：Go2 FLU体速度、Go2 roll/pitch和注入后的**旧status双天线航向**旋转到NED后保留水平，k=1/0.962142，σN/E=0.132838m/s。status时间减base_time1772784000后按毫秒关联；准备航向unwrap后线性插值，首末闭区间，gap>1.2s时剔除内部开区间。valid/update_flag是Go2源有效与准备航向有效的合取，V3不拿raw主航向重新旋转HV。

RP由同源`correct_rp`继承roll、pitch取负，行时间差<1e-9s核对，std1.6°转rad。RD来自hash锁定GNSS1 RAWX/SFRBX的既有RTKLIB Doppler速度，非接收机NAV-PVT速度；本轮没有重新运行该生成器或打开原raw来做第二次转换。IMU/RD标定链为明确继承，不把已读provider值称原始独立传感器真值。

## 故障实现的实际继承关系

`canonical541/provider_generator.py::_outage`按[start,end)改有效位/update_flag及相应status，保留原行和值；`place_interval`按anchor居中。该文件与521901f的相关冻结来源相同。bundle的`components`/`semantics`是生成过程历史回执；本轮正文验证有效位分布，不把回执存在升级为重新执行过生成器。

- C00：V3 raw heading替换；IMU/RD/RP/HV继承各原pin。
- D15_seed_00：在既有GNSS位置注入N/E σ3m、Up σ5m高斯噪声，std/status及其余通道保持。HV/RD/RP/IMU继承base；不从变差曲线反推注入。
- A1：position/RV/RD和旧dual yaw同时中断，随后由受影响准备航向生成HV支持；V3主raw heading也按冻结故障时格失效。bundle记录旧yaw有效281、HV有效57024，本轮HV正文计数对应。
- A2：position/RV/RD中断，旧yaw保留；HV与base字节身份相同。bundle旧yaw有效301、HV有效60867，本轮HV正文对应。

这些只是输入/准备层事实。正式`gnss_file_loader.cpp`读取18列三valid，`GIEngine::addGnssData`根据enable后的有效位形成事件；辅助尝试在GNSS事件入口之后。RP loader以source_status=active计可用；HV loader使用source_status/update_flag/diagnostic_only/truthclaim，不另由a1_heading_valid列重建插值。A2有heading也不保证HV接受，必须继续读取实际事件。

## 证据强度与下一门

已有SOURCE_AWARE/PORT日志字段范围见 [EXISTING_LOG_SCOPE.csv](EXISTING_LOG_SCOPE.csv)。原SA记录有NIS和scale，没有同状态H/dx/P/baseR矩阵；原循环记录不足以解释每个辅助源的未调用原因。观察性新重放因此必要。Frozen source154成员见 [SOURCE_MEMBERS.csv](SOURCE_MEMBERS.csv)，仅隔离副本可增加观察输出。

资格满足的是直接输入、配置和二进制的现存pin关系，并包含已读源码定义与bundle继承说明。没有声称独立重新证明raw观测真实性、安装几何、参考独立性，或在此处证明任何源已接受。后续首次真实调用受 [MECHANISM_PROTOCOL.md](MECHANISM_PROTOCOL.md)固定判据约束。
