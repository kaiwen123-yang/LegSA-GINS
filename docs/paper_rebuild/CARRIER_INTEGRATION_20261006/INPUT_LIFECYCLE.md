# 真实输入生命周期与本轮融合范围

本次只读源码、输入注册表、小型 RAWX 配对时间缓存及已保存 provider/IMU 元数据；没有重扫 ZIP、重新哈希整套 raw、运行载波搜索或读取参考轨迹。另完成新准备入口的因果校验与隔离单测。

## 可立即使用的序列

|序列|已登记 RAWX 精确配对数|完整 RAWX 相对时间 s|原导航窗 s|已保存 IMU8 连续支持|
|---|---:|---|---|---|
|BY2|1509|55.998–357.598|66–340|56643 行，66.001035–339.997056，无缺口|
|BY2H|1483|401.198–697.598|413–683|2 段；414.905067→415.081079 有未记录运动|
|BY2O|2231|3143.398–3589.398|3186–3563|7 段、6 个未记录运动缺口|

配对数/时间来源：<EXT_REPRO_ROOT>/inputs/{BY2,BY2H,BY2O}/INPUT.json 与其中登记的 cache/paired_epochs.npy；本轮仅读取小型时间/身份记录。时间采用 GPS epoch + week/tow − 各记录 leap seconds − base_time。BY2/H 的 base_time=1772784000，BY2O=1772780400，不能直接拼接两种相对时间。

IMU 来源：<SCRATCH>/IMU_V3_FIX_20261004/stage_07/PREREGISTRATION.json 的 sequences。IMU8 增量/真实积分时长保持原 token，缺口不是补零/保持角速度。BY2 最适合首轮完整融合，避免同时引入断流重启模型。

Jan5 XB/NMB 的8段是旧R5同一数据。[既有审查](../HEADING_REASSESSMENT_20261006/02_DATA_AND_FIX_AUDIT.md) 记录 RAWX 精确 week/tow 配对为零、双机约7–8 ms偏时。当前 exact-pair 前端不能直接把近邻观测改写成同步；这些数据不纳入本轮同步AR。主三窗为2026-03-06，Jan5为另一个采集日期，不是新增加的独立留出集。

## 星历因果性与修复

此前 real_trial.prepare 默认加载全文件NAV；显式override只核文件hash，缺少 cutoff<=start 入口校验。历史记录原样保留，该事实不能重写成当时已具备实时接收因果证据。

当前准备入口强制显式NAVIGATION_MANIFEST.json，要求有限causal_cutoff_relative_s、old_full_history_navigation_loaded=false，且cutoff不晚于requested start或实际最早处理RAWX。显式prefix被使用时不再打开、哈希或加载旧全历史NAV。14个隔离测试覆盖未来prefix、缺失/非有限cutoff、full-history flag、实际首历元、hash改变以及不存在旧NAV的完整mock prepare。

可复用<CARRIER_SCRATCH>/GAL_NAV_QUALIFICATION_V2/NAVIGATION_MANIFEST.json：cutoff=100 s，两机最后保留RAWX=99.9979999065 s。保存PAGE_QUALIFICATION显示首批完整Galileo E1星历availability bound为99.198 s，部分99.398 s。不能把该prefix用于66 s。本轮前端100–340 s，融合66–340 s，100 s前没有carrier输入。

星历TOE/age/health校验不能替代消息接收可用时刻；prefix制作只把cutoff前已接收消息交给转换器。完整扫描用于来源审计，不等于未来消息可用于当前解算。

## 信息来源与坐标基

- 当期GNSS1 code-only cold SPP ECEF位置可建立本历元ECEF↔ENU/NED坐标基；它不使用reference，也不提供机器人yaw。接收机自身有效位置也可作坐标基，需保留timestamp/源身份。
- Go2 gyro/accelerometer是唯一传播IMU；receiver IMU不替代本体。Go2 roll/pitch是机器人内部状态弱先验，不是独立真值。高层日志含脚位置/速度/脚力，但尚不能称为独立FK足式里程计。
- 旧clean6_sensor_v21/providers.py:142–194使用A1 yaw的np.interp前后插值，把SDK FLU velocity转为NED；它依赖GNSS航向并可能包含下一航向时刻。本轮四链统一关闭HV，不把旧world-frame HV作为解耦或实时先验。
- 研究runtime的RP/RD应past-only、每源最多一次；新增carrier更新不得重放同一辅助源。新native实现与测试核验这一点，历史legacy结果不修改。
- 已导出NAV/STATE_COVARIANCE是算法结果，不是另一个前端的外部独立航向真值。在线自身预测态可以是条件先验，但须取本次更新前状态并保留相关性，不能把post-update平滑或未来插值回灌。
- BY2初始化沿用final_v23_static_contract_a906c3a2：yaw=0.688505°，roll/pitch/velocity=0；已声明dual-yaw初始化。四臂相同。本比较不是无初始航向AR冷启动，不能据此声称覆盖XB初始化失败。

## C1已有双位置差侧车

[DUAL_PVT_INPUT_AUDIT.json](DUAL_PVT_INPUT_AUDIT.json) 记录小文件核验。复用<CLEAN_ROOT>/stages/CLEAN7_T5BC_V3_CANDIDATE_PILOT/03_PROVIDER_TABLES/BY2/B3/baseline3d.csv：1510行、55.8–357.6 s、主窗1371行、valid均1。逐行time token、b_n/b_e/b_d、pAcc1/2、valid与PREPARED_RAW_MANIFEST一致；pinned R5 GNSS18 SHA与当前共同GNSS18完全相同。

向量由两机NAV-HPPOSECEF位置差GNSS2−GNSS1，经首个55.8 s GNSS1位置建立固定NED框架；不是RAWX载波AR，不取C2/C3或reference。pAcc单位m；native工作协方差为k_b²(pAcc1²+pAcc2²)I，本轮固定k_b=1，不重用历史拟合k_b。该独立各向同性模型没有两机交叉协方差；固定NED近似与随位置变化的实时NED不是严格相同，保留接口来源说明。raw SHA继承自登记，本轮没有再读大文件。

## 本轮可执行链

四臂共同AB1110（RD/source-aware/RP开、HV关）、同IMU8、GNSS18位置/速度、初始化、噪声及原窗口：C0 scalar lateral projection；C1 dual-PVT vector；C2 full-current-class carrier vector；C3 selection-only preselected partial-class carrier vector。因此C0是本轮共同条件基线，不是未经改变的完整V3 F04。

navigation_trial.py分prepare/native/evaluate：准备核身份、复制已有侧车与两个carrier15列输入、保持其余配置token并做实际loader检查；native固定4次、独立进程组超时、I/O审计、全输出封存；随后固定4次冻结evaluator。要求四臂相同NAV/匹配评价time keys；保留66–340整体、66–100无carrier、100–340前端支持三个预声明区间，不按结果挑窗口。

Carrier measurement_time必须等于decision_available_time，不能把最后验证历元输出回填到选整数时刻。invalid保持显式，0个接纳不是运输失败。参考不进入frame、起点、整数、协方差或门限选择；接收机派生reference只由封存后的evaluator子进程读取。
