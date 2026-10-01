# 另外两套自有原生实现：完整语义审查

本报告审查 `cpp/src`、`cpp/include`、`cpp/apps`、`cpp/legsa_v23_core` 中全部 **90 个 C++ 文件、5,624 行**。每个文件均读完并完成下列函数/连续语句组语义说明；不是按编译、文件名或函数枚举自动提升深度。源码基线 `eb3cbed314693358c7c38442b6fbbb7afcf0342e`，每文件身份见 `NATIVE_OTHER_COVERAGE.csv`。与 `NATIVE_COVERAGE.csv` 的 57 文件、11,556 行不重叠，合计 147 文件、17,180 行（含 CMake 81 行）。这只闭合已列出的原生实现，不代表全仓 Python、测试、配置等全部完成。

正式算法、当前 B3 候选和历史二进制的身份见 `NATIVE_REVIEW.md`。`cpp/CMakeLists.txt:9–24` 将 `cpp/src` 链接为 `legsa_gins`；26–52 将 `legsa_v23_core/src` 链接为静态库和 `legsa_v23_core_demo`；54–81 才是正式 `legsa_v23_port_core_demo`。三者没有互相链接，`GINSOptions`、`INSMechanization`、`Rotation` 等相同名字不能跨 namespace 当成同一实现。下述 O 类问题不会仅凭静态相似性被归到正式 port core，也不能拿这些旧模块代替 XB 主方法。

## 1. 主要结论与本轮新增证据

- `legsa_gins` 是明确标为 toy 的 21 项对角协方差基础实现；预测不传播 P，不含重力/地球率机械编排，advanced factor 只是 registry。它不支持“完整 21 维 ESKF”主张。原生测试确认一次预测后 P 逐元素不变（O01）。
- 该 target 的 CSV 初始化搜索整份 receiver 列表；`LegSAFilter::process` 又把 IMU 终点以后的记录继续更新到终点状态。原生 IMU 时间 [0,1]、GNSS 速度时间 2 s 的反例最终 time 仍为 1 s，北速已成为 9.900990099 m/s（O02）。
- 该 target 的 history 全部配最终一份 STD；bias/scale STD 输出列写 dph/mGal/ppm 却未从内部单位换算，不能作为逐历元置信区间（O03）。
- `legsa_v23_core` 的 F 不是 nominal mechanization 的线性化：`F_vφ` 使用 body 增量负 skew，省略 Cbn 且符号与自身反馈定义不一致；零输入时 scale 导数仍是 ±C 常数。实际原生矩阵对左扰动 FD 的最大绝对差为 **20.018660218 m/s²/rad**，步长 1e−6 rad；零输入的两块 scale 导数 Frobenius 范数均为 √3，应为 0（O06）。
- 该 target 的比力旋转一阶项使用上一段 dtheta，当前段开始转动时漏掉主要项。当前 θz=0.02 rad、Δvx=1 m/s、前段零转动时，解析东向增量 0.009999666671 m/s，原生输出 0（O07）。这不是用 reference 选择的符号。
- GNSS 排队每个 IMU 区间只消费一条，旧样本后来按左端时刻更新；[0,2] s 内 3 条 GNSS 只消费 2 条，剩余留队列而 runtime 已结束（O09）。
- 此 target 配置入口不设置 measurement/state feedback 实现开关；真正 update 只在专门 toy 构造函数启用。配置时窗/IMU 长度也没有进入裁剪，最终仅写一行输出，不是全轨迹（O10）。

新增 `native_other.cpp` 直接链接已构建生产对象与 `liblegsa_v23_core.a`，没有复制/改写被测 C++ 函数，没有改正式源码。编译和 counterexample 各 1 次、exit 0；这是观测器执行完成，不是“发现均通过”。`NATIVE_OTHER_RESULTS.json` 保存数值、源码/二进制哈希和耗时；大收据在 `<AUDIT_ROOT>/native/native_other/`。此次是审查后新增的 post-hoc 合成软件实验，不是四段实测、算法比较或期刊有效性验证。

## 2. `legsa_gins` 的逐文件、逐函数说明

以下头文件缩写 `include/` 指 `cpp/include/legsa_gins/`；实现缩写 `src/` 指 `cpp/src/`。声明与定义合并解释，构造、普通 getter、转发可合并，关键状态修改/索引/单位单列。

### 2.1 类型、数学与坐标

|文件/行/函数组|读入、计算、状态与边界|
|---|---|
|`include/math/constants.hpp:8–16`|PI/deg↔rad 与 WGS84 a/f/e²；仅常数，无硬件安装或高程转换。|
|`include/math/vec3.hpp:10–44`|x/y/z 结构与逐分量加减/标量乘除、dot、cross、norm、finite；不携带 frame，单位由调用方保证；平方和 norm 无缩放保护。|
|`include/math/angle.hpp:12–42`|rad/deg wrap 都用 fmod，有界完成；[-π,π)、[0,2π)及degree对应；Inf 产生 NaN，而非 port 的 while 不返回。不得用 port 的 timeout 测试给此函数记失败。|
|`include/math/quaternion.hpp:13–18;22–65`|wxyz；normalize 检查 norm 有限且正，multiply 是原始 Hamilton 积、不自动单位化；inverse 除 norm²；rotvec 小角近似；rotate 先 normalize 再 qvq⁻¹。巨大有限值平方溢出被 normalize 拒绝；并非 port 的返回零四元数行为。|
|`include/math/rotation.hpp:8–12`;`src/math/rotation.cpp:13–44`|ZYX RPY→qbn、qbn→RPY；先规范化，pitch 用 clamp 后 asin，yaw 转 [0,2π)。没有 port 的提前阈值奇异分支；真正奇异的 Euler 表示不唯一。|
|`include/math/earth.hpp:9–18`;`src/math/earth.cpp:13–48`|WGS84 meridian/prime radii；DR/DRi 把 NED 米与 BLH(rad,rad,m)相互转换，D 与 height 符号相反；经度使用 abs(cos) 下限 1e−8；gravity 为纬高函数，但本 target mechanization 没有调用。极点夹限只是数值近似。|
|`include/types/filter_types.hpp:14–67`|21 项顺序 p/v/φ/bg/ba/sg/sa；PVA 保存 qbn 与 Euler、BLH rad/m、NED m/s；bias rad/s、m/s²、scale fraction；P 仅 21 个对角值，dx 21项。Receiver flags 默认 false，std 正默认，不能从字段存在推断有效。|
|`include/types/imu_types.hpp:11–18`|LegSAImuSample 的 tow、dt、dtheta rad、dvel m/s、body frame/source role；这是增量，不是角速度/加速度。|
|`include/types/nav_types.hpp:12–71`|输出 NavState 用 degree/NED；StdState 列名规定 m、m/s、deg、dph、mGal、ppm；另有 skeleton 的 ImuSample/GnssMeasurement，与 filter increment 类型不是同一接口。|

### 2.2 配置、因子 registry 与入口

|文件/行/函数组|行为和真实作用|
|---|---|
|`include/config/runtime_config.hpp:10–32`;`src/config/runtime_config.cpp:10–14`|配置容器含 receiver/advanced enable、IMU模式、heading offset 字符串。`loadRuntimeConfigPlaceholder(path)` 明确忽略 path 并返回默认，不是 YAML parser。不能给此 target 传正式 runtime 后认为参数生效。|
|`include/factors/factor_base.hpp:11–29`;`include/factors/factor_registry.hpp:12–24`;`src/factors/factor_registry.cpp:10–53`|枚举9槽位、factorName switch、默认3 receiver enable、集合 enable/disable/isEnabled/getEnabled；没有 residual/H/R 或优化计算。FactorBase 仅抽象 kind/name。|
|`include/engine/legsa_engine.hpp:17–51`|持有 config、registry、两个 skeleton buffer、NAV/STD/writers；声明 dry toy、filter toy、CSV 三个不同入口，不能把 skeleton `processNext` 当 LegSAFilter。|
|`cpp/apps/legsa_gins.cpp:23–91`|CLI 逐token识别输出/imu/receiver路径、max epochs及三种mode；值缺失/未知报错。`stoull` 在 later try 外，错误 max-epochs 可能绕过统一失败前缀。|
|`cpp/apps/legsa_gins.cpp:93–130`|检查 mode 排他及必要路径，调用 engine 对应入口；主体 std::exception 转exit1。注释 dry-only 不应覆盖实际存在的 CSV入口；本轮没有运行历史 CSV/性能。|
|`src/engine/legsa_engine.cpp:484–523 applyRuntimeConfigToFactors`|仅改 registry 开关；`LegSAFilter::update` 不读 registry，因此 receiver disable 不能沿该入口关闭对应更新。advanced enable 也不产生实现（O04）。|

### 2.3 对角滤波器、预测与观测

|文件/行/函数组|公式、状态和异常|
|---|---|
|`include/filter/diag_covariance.hpp:9–14`;`src/filter/diag_covariance.cpp:10–24`|默认 Pp=(25,25,36)，Pv=(1,1,1)，φ=(.05²,.05²,.1²)，其余1；不是根据真实硬件校准初始化。|
|`diag_covariance.cpp:26–47`|ensure 遍历21项 finite且>0；scalarGain=P/(P+R)，posterior=(1−K)P，reset全dx=0。单变量近似不保持交叉协方差；极小R/大P可能舍入为0使下次检查失败。|
|`include/mechanization/ins_mechanization.hpp:10–21`;`src/mechanization/ins_mechanization.cpp:15–31`|compensateDelta=(increment−bias·dt)/max(1e−9,1+scale)；负/零scale分母被裁剪，不等于合法物理校准。|
|`ins_mechanization.cpp:33–39`|`compensateImuError` 返回 state 原样，是边界占位；真正增量校正在 propagate 49–58。不能见函数名就记已校正。|
|`ins_mechanization.cpp:41–77 propagate`|dt 优先输入正dt，否则非负实际差；旧姿态旋转补偿dvel加速度，**没有 g/Coriolis/导航率**；用新速度一阶积分BLH；qbn右乘增量q，再更新Euler/tow。适用于声明的toy，而不能直接接真实比力做完整INS。P在此不存在。|
|`include/filter/legsa_filter.hpp:14–40`;`src/filter/legsa_filter.cpp:18–40`|initialize 检查P、清dx/history并记录初值；predict 只更新 nominal，不修改P、不使用Q/F/Phi（O01原生证明）。|
|`legsa_filter.cpp:42–81`|按 position→velocity→heading立即更新/反馈，每类只看measurement flag；process 初值时先消费≤首IMU，随后每条IMU后消费≤当前时间的所有消息，没有精确插值；最后78–80消费全部未来记录，状态time不随其变（O02）。初始history另push一次，重复首时刻不是两个独立历元。|
|`legsa_filter.cpp:84–134`|getter按值复制state/P，history返回const引用；NAV转degree；STD角度转degree，其余bias/scale未转却标dph/mGal/ppm（O03）。没有每次更新的P history。|
|`include/updates/receiver_position_update.hpp:9–14`;`src/updates/receiver_position_update.cpp:20–59`|flag false返回；DR把 nominal−obs BLH差转NED残差；逐轴K以−K残差修正nominal，P按scalarposterior减少，dx清零；没有天线杆臂、姿态交叉项。|
|`include/updates/receiver_velocity_update.hpp:9–14`;`src/updates/receiver_velocity_update.cpp:20–54`|同样逐轴处理vnom−vobs，三轴P独立；未处理旋转杆臂、时间异步或源相关。|
|`include/updates/receiver_heading_update.hpp:9–14`;`src/updates/receiver_heading_update.cpp:12–35`|wrap Euler yaw差，标量K减残差、重建q；仅yaw方差变，不是正式port的左扰动观测/反馈。std平方与finite/P检查拒绝范围必须从此实现判断。|

### 2.4 CSV解析与初始化

|文件/行/函数组|输入、缺失/时间策略和调用者|
|---|---|
|`include/readers/standard_imu_increment_reader.hpp:11–17`;`src/readers/standard_imu_increment_reader.cpp:18–106`|必需10列；split按逗号、去CR，非RFC引号CSV；header/fieldcount/非空检查；stod不检查全部消费或finite。readRows把数据加载vector，不是流式估计。|
|`standard_imu_increment_reader.cpp:108–155`|time优先algo_time否则timestamp；要求FRD，dt≤0拒绝，时间只拒绝严格倒序，duplicate接受；dt与相邻time差未交叉核对，NaN dt不满足≤0而漏检。source_role要求header但未作为单位/设备真实性核查（O05）。|
|`include/readers/standard_receiver_measurement_reader.hpp:10–15`;`src/readers/standard_receiver_measurement_reader.cpp:18–127`|同类简单CSV助手；time优先algo_time、否则tow；必需10列与source_name，不自动解GNSS raw。|
|`standard_receiver_measurement_reader.cpp:129–157`|BLH degree→rad；水平std复制到N/E，has_velocity强制false；heading flag读取但yaw std仍使用默认1rad；lower time拒绝、equal接受。设备accuracy能否当单轴std未由reader证明。|
|`include/readers/toy_csv_reader.hpp:10–16`;`src/readers/toy_csv_reader.cpp:16–89`|简单CSV header/行数检查、required字段、stod/三种true文本；有重复实现而非共享parser；没有标准CSV引用语法。|
|`toy_csv_reader.cpp:91–142`|IMU/receiver逐字段填toy容器；degree转rad；只检查非倒序，IMU不校验FRD、dt>0/实际dt；属于toy fixture，不可当新数据适配。|
|`src/engine/legsa_engine.cpp:27–117`|CSV splitter、16列trial header、fieldcount/required、stod、time优先algo_time、bool；原始bytes/YAML无法经此接口安全解码。|
|`legsa_engine.cpp:119–157`|专用receiver trial decoder，所有numeric字段即使相应flag false也要求存在；只拒绝倒序不拒equal。|
|`legsa_engine.cpp:159–208`|navFromFilterState转换输出；makeInitialState首IMU time，却遍历全部receiver拿第一position/第一heading，二者可不同time甚至未来；roll/pitch固定0，再建q。未找到position抛错；未找到heading可用默认0。O02初始化部分静态证实，本轮动态只复现末尾future更新。|

### 2.5 Engine三个入口及写出

|文件/行/函数组|实际执行含义|
|---|---|
|`legsa_engine.cpp:210–257`|By2 trial manifest JSON，主要forbidden值硬编码；说明event-normalized/no clock sync/no numerical performance，但没有文件访问监测。路径/string未完整JSON转义（O14）。|
|`legsa_engine.cpp:259–277`|constructor设registry；initialize开NAV/STD/eval/manifest，构建的是skeleton输出，不创建LegSAFilter。|
|`legsa_engine.cpp:279–322`|buffer push；processNext无GNSS时仅推进time，有GNSS直接把GNSS BLH/v/yaw复制输出并丢首元素；这是明示skeleton。vector erase(begin)为线性搬移，不能以此证明正式端实时性。|
|`legsa_engine.cpp:324–339`|状态/registry getter，writeCurrentEpoch转交3writer，无滤波或轨迹校正。|
|`legsa_engine.cpp:341–378 runDryRunToy`|两条toy GNSS配人工IMU跑上述skeleton；输出不能当解算精度。|
|`legsa_engine.cpp:380–441 runFilterToy`|五IMU/三receiver构造后新建LegSAFilter、process；取最终STD一次并仅改time复用到全部history（O03）。|
|`legsa_engine.cpp:443–482 runFilterCsvTrial`|standard IMU＋trial receiver→未来可见初始化→process全部记录→history输出；max_epochs控制读取IMU/写出行，却不限制已读receiver未来更新；同样final STD复用。|
|`include/io/nav_writer.hpp:12–28`;`src/io/nav_writer.cpp:13–49`|创建目录、open检查、header、单调非降time检查、按列写，允许equal；状态文本不作CSV完整引号处理。close/flush后未检查写满磁盘等错误。|
|`include/io/eval_nav_writer_bridge.hpp:12–27`;`src/io/eval_nav_writer_bridge.cpp:13–49`|NAV字段转同一评价CSV；不读reference、不改坐标点、不做杆臂；开头open检查及非降time同NAV。|
|`include/io/std_writer.hpp:12–27`;`src/io/std_writer.cpp:13–57`|固定common-unit header、21std写出、非降time检查；writer不能弥补上层STD单位与历史P错误。|
|`include/io/run_manifest_writer.hpp:11–22`;`src/io/run_manifest_writer.cpp:14–110`|jsonEscape只处理反斜线与引号；writePlaceholder和writeToy记录config/registry、claim boundary；registry enabled并非该因子被执行；forbidden=false是声明，不是访问审计。|

## 3. `legsa_v23_core` 的逐文件、逐函数说明

本节头/源路径相对于 `cpp/legsa_v23_core/`。外观更接近正式 port，但其 F、机械编排、runtime、loader、yaw residual均不同。只使用其实际代码与本轮合成测试判断，未使用旧实验指标。

### 3.1 基础合同、旋转与地球

|文件/行/函数组|语义|
|---|---|
|`include/legsa_v23_core/common/constants.hpp:10–39`|21状态、18噪声索引/单位常数/WGS84/cov floor；P/V/φ/BG/BA/SG/SA顺序及noise六组三轴。|
|`common/math_types.hpp:11–106`|Vector/Quaternion/std::array固定矩阵；zero/identity/diagonal构造；`matrix3At/matrix21At/matrix21x18At/noiseAt`直接row*cols+col索引，无任何二维/flatten边界。错列可跨行、真正超界为未定义行为；本轮只静态审查，port Matrix补丁不覆盖它（O11）。|
|`common/time_status.hpp:5–10`|Before/Inside/After枚举，仅声明；engine实际用int 0/1/2/3，不能据此枚举推断调度实现。|
|`state/nav_state.hpp:7–18`;`state/filter_state.hpp:8–14`;`state/imu_types.hpp:7–13`;`state/gnss_types.hpp:7–20`|nominal以Euler保存，BLH rad/m，NED m/s，bias/scale internal；Filter保存current/previous、21dx/P；IMU增量无compensated标志；GNSS time/BLH/std/vel/yaw(deg)以及三flag。|
|`common/rotation.hpp:12–45`;`src/common/rotation.cpp:11–88`|skew，rotvec→wxyz，normalize后q→matrix，按trace/最大diag分支matrix→q；没有矩阵正交性输入检验。|
|`rotation.cpp:90–134`|ZYX matrix→Euler uses asin clamp及两个atan2；Euler→matrix/q；q→rotvec不统一q和−q最短表示，返回角可能>π。此分支与port近奇异特殊处理不同。|
|`rotation.cpp:136–173`|wrap rad/deg while loops对±Inf不返回，对很大有限数可能减法无变化；multiply后无条件normalize；normalize的平方和可能溢出，极小norm返回identity，NaN传播（O11静态）。|
|`common/earth.hpp:12–36`;`src/common/earth.cpp:11–56`|gravity=[0,0,g]，radii，RN，DR/DRi；DRi夹cos到1e−12，DR不用该夹限，近极点二者不严格互逆。|
|`earth.cpp:59–94`|qne这里表示 **ECEF→NED**，port同名qne为NED→ECEF；blh由rotation求lat/lon；iewn及enwn按BLH/NED求。enwn第三项额外 `/cos_lat*cos_lat`代数相消、极点仍有tan不稳定，不是另一物理修正。|

### 3.2 配置及文件输入

|文件/行/函数组|行为和实际生效项|
|---|---|
|`config/gins_options.hpp:11–58`|factor flags默认false；init position/v/att std默认0，IMU噪声字段默认0；measurement/state-feedback/mechanization“implemented”flags及单独position/vel/yaw声明。不是全套运行开关。|
|`config/config_loader.hpp:10–14`;`src/config/config_loader.cpp:17–69`|trim/lower/stripQuotes；parseVector3先去括号用流提取3double，恰好3个数但尾随文字可被忽略；degree转换；非标准YAML。|
|`config_loader.cpp:71–138`|逐行先截#再去引号，优先冒号否则等号；无分隔行改provenance=evidence_missing；任何key含trace/final_v23_output就拒绝，包含false值也拒绝。解析path、time、imu格式、initPVA/std、杆臂和provenance，未知key静默忽略；不解析任何implemented flag和噪声；duplicate覆盖。O05/O10。|
|`io/imu_file_loader.hpp:10–15`;`src/io/imu_file_loader.cpp:12–65`|trimDataLine处理#和空白；load严格需要至少7个数，错误带line号抛出，不像port静默跳行；额外尾列未拒绝；dt用相邻time差且必须>0，首条0；一口气存vector。有效性只到格式/顺序，不证明原始sportmodestate或FLU→FRD已正确。|
|`io/gnss_file_loader.hpp:10–15`;`src/io/gnss_file_loader.cpp:14–71`|至少15数，否则抛row错误；degree→rad，时间严格递增；所有读到的行统一has_velocity/has_yaw/isvalid=true，没有18列细分missing mask；extra列无效。它解高层state文本，不解RAWX/SFRBX，不是raw Doppler backend。|

### 3.3 机械编排和误差传播

|文件/行/函数组|公式、状态和科学差异|
|---|---|
|`mechanization/ins_mechanization.hpp:12–22`;`src/mechanization/ins_mechanization.cpp:13–36`|cross/add/scale/matVec固定3算术；输入含两个IMU增量，无hidden单位转换。|
|`ins_mechanization.cpp:41–47`|copy前PVA，按velocity→position→attitude更新；正时间但不合法小/负dt会被各函数max(dt,1e−6)替代，没有报错。|
|`ins_mechanization.cpp:50–67`|body比力增量=Δv₂+0.5(Δθ₁×Δv₂)+(Δv₁×Δθ₂+Δθ₁×Δv₂)/12；主要0.5项应由当前角增量而非上一段控制。旋转旧Cbn后加重力−Coriolis，没有导航系半步旋转；O07反例单独隔离0.5项。|
|`ins_mechanization.cpp:71–81`|前/新速度均值×dt，再前位置DRi转换BLH；与toy target新速度Euler积分不同；midpoint曲率近似未迭代。|
|`ins_mechanization.cpp:85–98`|current dtheta+previous×current/12，左乘负导航率qnn、右乘bodyqbb；每步重新Euler而非持续四元数nominal。地球/运输率在前时刻求。|
|`filter/error_state_matrices.hpp:10–19`;`src/filter/error_state_matrices.cpp:15–84`|setBlock/setNoiseBlock逐3×3写索引；Phi=I+Fdt；GQcGt、ABAT用四层循环；checkFinite全441项，仅保证有限不保证物理正确/PSD。|
|`error_state_matrices.cpp:90–130`|options完全未用；cbn由nominalEuler，skew_force却是**body dvel**；Fpp=−1e−8I、Fvp=1e−7[v]×、Fφp=1e−9I、Fφv=1e−6I均非从Earth导数得出；Fvφ=−[Δv_body]×/dt、Fvba=−Cbn、Fvsa=−Cbn；Fφbg=−Cbn但Fφsg同样−Cbn而缺diag(ω)。GM均固定−1e−5I。O06。|
|`error_state_matrices.cpp:132–159`|G的V/VRW、φ/ARW为C，四组误差噪声I；Qraw=GQcGᵀdt，Qd=(PhiQrawPhiᵀ+Qraw)/2，有限检查。此离散化正dt且QcPSD时PSD，但不修复错误F。|
|`filter/ekf_predictor.hpp:7–8`;`src/filter/ekf_predictor.cpp:10–41`|multiply21未被该文件使用；multiplyABAT四层循环，O(21⁴)而非两次立方乘法；不从外观直接宣称实时失败。|
|`ekf_predictor.cpp:46–81`|P←PhiPPhiᵀ+Qd、dx←Phidx、P显式对称；只检测diag finite/负值，[-1e−12,0)裁到0，不检查dx/non-diagonal有限或整体PSD。上层另checkCov仍不等于Cholesky（O12）。|

**O06 独立导数依据。** 此实现 position/velocity residual=nominal−observation，反馈减dx；姿态反馈左乘Exp(φ)，因此真姿态定义为 `C_true=Exp(φ) C_nom`，速度误差为 `δv=v_nom−v_true`。比力项有 `δv_dot≈[C_nom f_body]×φ + C_nom δba + C_nom diag(f_body) δsa`，不能使用负的body-frame skew。测试调用原生Rotation作左扰动，用实际生产 `buildErrorStateMatrices` 输出比较；不是仅重写一个Python函数。bias/scale符号需同时遵循误差定义，不能照搬参考名词。Fφsg在零angular rate必须为0，本实现不是。全部旧模型块需独立重推，不能靠修改一个符号就宣称等价KF-GINS。

**O07 解析输入。** 当前段固定角速度绕z转θ、body恒定比力使Δv=(1,0,0)，导航平面精确积分为 `[sinθ/θ,(1−cosθ)/θ]`；previous零增量时，本实现北向1、东向0，缺掉θ/2项。该输入是已知合成量，不依赖商业参考、安装推测或真实RMSE。导航系小转动和Earth项不会产生本例量级的0.01m/s，原生测试初速度0隔离Coriolis。

### 3.4 观测、Joseph和反馈

|文件/行/函数组|残差/导数/有效性/状态|
|---|---|
|`updates/measurement_update.hpp:13–46`;`src/updates/measurement_update.cpp:16–58`|MeasurementBlock存rows、dynamic residual/H/R；makeBlock零初始化；mat3Vec；varianceWithFloor= max(abs(std),floor)²，将负std作为正数接受；H/R访问flatten无边界，EKF入口另校验shape。|
|`measurement_update.cpp:63–92`|预测天线=BLH+DRi Cbnlever，残差DR(pred−obs)，Hp=I、Hφ=[Clever]×，R每轴std²至少1e−6m²；与其减位置、加姿态反馈相容。没建双天线向量，也没有source metadata。|
|`measurement_update.cpp:97–107`|速度nom−receiver，Hv=I、Rstd²≥1e−6；明确没有杆臂速度，不可称raw Doppler。|
|`measurement_update.cpp:111–126`|yaw residual=obs−pred（度wrap后rad），Hφz=+1；这和其正左姿态反馈在水平姿态下方向正确，与port的pred−obs/H−1符号不同但不是仅凭异号判错。pitch不零仍遗漏完整Euler导数；schemeC接受后建R。|
|`updates/yaw_scheme_c.hpp:9–31`;`src/updates/yaw_scheme_c.cpp:9–19`|soft≤6°原std、≤15°std乘2.5（R乘6.25）、否则拒绝；std下限1e−3deg，不是NIS检验；NaN residual落reject，NaN std可进入R。门限是角度，不是自由度概率。|
|`filter/ekf_update.hpp:8–10`;`src/filter/ekf_update.cpp:16–91`|小矩阵access、Gauss-Jordan partial pivot固定绝对门限1e−18；非finite无预检查；末端checkStateFinite查dx、所有P元素及diag负值，不查PSD。NaN S最终通常使结果抛错，不能把它描述成安全而稳定的矩阵求解。|
|`ekf_update.cpp:97–158`|检rows/shape，算HP、S=HPHᵀ+R、PHᵀ、K；实际innovation=residual−Hdx，序贯块共享dx时公式正确。没有通用NIS或源相关联合R。|
|`ekf_update.cpp:162–206`|Joseph=(I−KH)P(I−KH)ᵀ+KRKᵀ，对称赋值后finite检查；S明式求逆，R非负/对称输入未验证。|
|`filter/state_feedback.hpp:7–9`;`src/filter/state_feedback.cpp:12–55`|mat3Vec；pos−DRiδp、vel−δv、q←Exp(φ)q、bias/scale+=dx，清dx但P不作扰动重置。和port相同的reset近似争议需量化，非一见未调用就判致命（O12）。|

### 3.5 Engine调度、补偿及参数

|文件/行/函数组|实际执行|
|---|---|
|`runtime/legsa_v23_engine.hpp:21–94`;`src/runtime/legsa_v23_engine.cpp:18–42`|constructor存options；initialize initPVA、zero dx、P bias/scale默认1e−4，PVA用std平方；Qc固定ARW1e−8/VRW1e−6/bias1e−12,1e−10/scale1e−14，与未解析imu_noise无联系。time=start_time但不自动把PVA传播到首IMU。|
|`legsa_v23_engine.cpp:45–65`|IMU在队尾严格递增，可选提前compensate后入队；GNSSinvalid不入队，有效严格递增。advance后未保持全局last GNSS monotonic约束；入口只是队列比较，不是跨运行时间安全锁。|
|`legsa_v23_engine.cpp:69–124`|每对IMU只看GNSS front；res1先更新再传播，res2先传播再更新，res3分两段传播夹更新；每次pop一GNSS、一IMU。GNSS多于一条/IMU区间会排队延时，窗口末有剩余时直接失去更新（O09）。|
|`legsa_v23_engine.cpp:127–150`|getter按值；isToUpdate eps1e−10，所有早于左端的数据也res1，无最大staleness；future右侧res0。不是port的1ms边界，不共享其future容差反例。|
|`legsa_v23_engine.cpp:154–174`|interval≤0或timestamp不在内部时直接mid=imu2；合法内部按时间比例切当前增量，原减mid保证总量守恒，dt分别两段。常角速度/比力假设，不能还原区间真实动作。|
|`legsa_v23_engine.cpp:177–185`|compensate写成 raw/(1+scale)−bias·dt；若raw=(1+s)true+b·dt，正确是(raw−b·dt)/(1+s)，现式多出−b·dt·s/(1+s)。b=.2、s=.5、dt=.5、raw=.1时应0而得−.0333333；此点静态计算，未另原生调用。且runFromConfig addImu不启用compensate，toy一次性预入队会使用尚未更新bias（O08/O10）。|
|`legsa_v23_engine.cpp:188–205`|insPropagation将previous=current再机械编排、time=currentIMU；buildFGPhiQd用**已传播后**PVA，非函数名pvapre意义；EKFPredict wrapper确实总执行，mechanization_predict_implemented=false不会关闭（O10）。|
|`legsa_v23_engine.cpp:209–254`|measurement_update_implemented总闸；其下position总建，velocity/yaw看GNSS flags而不看position/velocity/yaw_implemented声明；yawGate为计数再build重复计算，值相同；source-aware/RD/RP/HV不存在。|
|`legsa_v23_engine.cpp:258–284`|逐pending块Joseph，最后清队列；stateFeedback wrapper；checkCov查diag有限非负、上三角有限/对称差≤1e−8，不查PSD。下三角NaN与abs比较可漏检但上游EKF通常会捕捉；调用隔离时仍是防护缺口（O12）。|

### 3.6 Runtime、输出与异常链

|文件/行/函数组|输入/输出、时窗和声明|
|---|---|
|`runtime/legsa_v23_runtime.hpp:12–30`;`src/runtime/legsa_v23_runtime.cpp:20–65`|outputPath用filesystem；runDryToy建两IMU、一GNSS，default测量闸false却进行propagation；写单末状态，不能当完整滤波验证。|
|`legsa_v23_runtime.cpp:68–107`|runDryPropagationToy 200次IMU传播，用固定gravity9.80665而非当地精确平衡；flags称prediction，loop使用可选compensate；只写终点。|
|`legsa_v23_runtime.cpp:110–168`|runDryUpdateToy启用measurement/feedback，六IMU/三个yaw人工跨soft/hard门限，全部IMU先入队；原生code分支存在，但本轮OTHER未运行此toy，不将coreport的toy结果迁移到这里。|
|`legsa_v23_runtime.cpp:171–190`|runFromConfig加载全部IMU/GNSS并要求至少2IMU；所有GNSS预队列，逐IMUadd不补偿，测量闸仍false；start/end/imu length未用于裁剪；末写一次。O10静态闭合。|
|`legsa_v23_runtime.cpp:194–204`|目录、NAV/STD/eval开文件并写同一末时刻、manifest；没有逐历元输出，没有输出完整率/elapsed原生日志。|
|`src/legsa_v23_core_demo.cpp:18–68`|CLI未知/缺参抛runtime_error统一catch返回1；多mode并存按dry→prop→update→config优先，未排他，可能运行与调用者预期不同的mode；无模式返回2。|
|`writers/nav_writer.hpp:10–21`;`src/writers/nav_writer.cpp:11–24`|open失败抛错；10列空格NAV，BLH/姿态转degree；无finite、time monotonic、flush-finalcheck。|
|`writers/eval_nav_writer.hpp:10–21`;`src/writers/eval_nav_writer.cpp:11–24`|同状态写10列CSV，仅格式桥接；没有POI变换或reference访问。|
|`writers/std_writer.hpp:10–21`;`src/writers/std_writer.cpp:13–38`|21列std0…std20，diag nonfinite或<−1e−15抛错，极小负夹0；φ转deg，bias/scale保留内部单位，未像另一target错标common-unit。φ分量仍不是一般姿态下的Euler std（O13）。|
|`writers/run_manifest_writer.hpp:9–14`;`src/writers/run_manifest_writer.cpp:11–61`|boolText、写options flags/yaw计数和固定full_ekf_math_closed=false；JSON string直接拼接无escape，provenance/phase含quote会损坏；forbiddenflag是配置声明，未打开输入的计数不可从此倒推（O14）。|

## 4. 对正式链的意义、修正顺序与复现

这些模块是项目自有代码，所以全部语义审查，并保留可复现缺陷；它们的旧标签不构成当前性能证据。针对正式 port 的数学/调度/数值结论仍以 `NATIVE_REVIEW.md` 的实际实现为准。尤其不能把本节 F 错误直接写成正式 port 的 F 同样错误：正式 port 是另外一组近似与缺项，已单独审查。也不能把该 target 的 yaw H=+1 与 port H=−1直接对比判错，两者 residual 符号不同。

若未来恢复旧 target，优先明确toy合同或重做完整模型，再修时窗/时标和参数生效；不能只把manifest“implemented”改true即宣称闭合。O02/O03/O06/O07/O09/O10 足以阻止将这些现有实现当正式完整算法。这里没有建议重跑旧历史矩阵；如旧材料用过这些target，先按实际二进制、命令、输出行数追身份，再决定具体旧主张是否需要撤回/重评。

复现新增原生测试（既有对象在本轮scratch；脚本拒绝覆盖输出目录）：

```bash
python3 scripts/paper_rebuild/audit_xbpg/native_other_tests.py --local-config <ignored-local-config>
```

初次用 `python` 启动因本机无该命令退出127，尚未创建运行目录；改用 `python3` 后编译/执行退出0。没有为改变结果调参或重复既有测试。测试本身5组证据：旧P、旧未来更新、新F/scale、当前比力转动积分、新队列；不把打印项数作为独立实验数。F FD 单正常姿态/步长尚未做全姿态统计；sculling只隔离一个漏项，其他高阶项/地球近似未动态量化；其它静态问题在CSV明确 `STATIC_ONLY/NOT_RUN`。两target各自全部代码已经语义审查，但还没有建立它们完整运动、无噪声、known-noise Monte Carlo或全入口回归；本轮不以这些历史toy替代正式要求的验证。
