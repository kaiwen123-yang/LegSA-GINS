# 完整导航输入复用映射

工程元数据清单；权威输入为 AR_V3_RESEARCH_20261006/V3_BASELINE_LOCK.json。
机器路径仅在忽略的 <NAV_INPUT_MAP_LOCAL>/LOCAL_PATHS.json。
没有执行 solver、evaluator、构建或测试，没有打开参考、原始测量正文或解析 provider 数值行。

**核查纠偏：V3_SCRATCH 并未整根释放。三份原运行配置、三个原 GNSS18、十二个 IMU/RD/RP/HV provider、原二进制和冻结 evaluator 均在原登记路径。无需重建 PVT 或找替代副本。** 已释放的是本次对应检查的三组原 NAV/STD；error_series 压缩文件仍在。

| 序列 | 原正式运行 | 完整窗口 / s | base_time |
|---|---|---|---|
| BY2 | RUN_00004 | 66–340 | 1772784000 |
| BY2H | SEQUENCE_BY2H_F04 | 413–683 | 1772784000 |
| BY2O | SEQUENCE_BY2O_F04 | 3186–3563 | 1772780400 |

## 输入身份

配置分别为 <V3_ROOT>/03_NATIVE/RUN_00004/V3_RUNTIME_CONFIG.yaml、
<V3_ROOT>/03_NATIVE/V3R_CONTINUATION/SEQUENCE_BY2H_F04/V3_RUNTIME_CONFIG.yaml、
<V3_ROOT>/03_NATIVE/V3R_CONTINUATION/SEQUENCE_BY2O_F04/V3_RUNTIME_CONFIG.yaml。
三份配置及三个 GNSS18 当前 SHA 均与 V3 lock 相符；十二个大 provider 只核存在和大小，沿用原 SHA，未宣称重新全量校验。

每序列初始化及全部 provider 精确 alias 路径/SHA 见同名 JSON。
GNSS18 在 <V3_SCRATCH>/02_PROVIDERS/CASES/ 下；
RP/HV 在 <CLEAN_ROOT>/stages/CLEAN6_SENSOR_MODEL_V21/02_BASE_PROVIDERS/ 下；
IMU/RD 在 <CLEAN_ROOT>/stages/CLEAN5_CALIBRATED_SENSOR_MODEL/02_CALIBRATED_PROVIDERS/ 下。
V3_PROVIDER_SOURCE_INDEX.json 的 base_gnss 是 heading lift 前来源，不能替换已锁正式 GNSS18。

原配置是 **7 列、500 Hz IMU**。现有 navigation_trial.py 以 stage_07 的 BY2 IMU8 研究输入起步，
不能把它的配置直接作为三窗原 V3。后续从原配置派生新身份并登记改动；
保留原 dual-yaw 初始化也不能被解释为纯载波自主冷启动。

## 二进制和构建

原 V3 科学冻结为 7d43b9af26120ed5dde21f53e515386361072ba6；
<FROZEN_CODE_ROOT>/build/p13_v21_cpp/legsa_v23_port_core_demo 当前 SHA
96ae436d82ba8922c68382bd73fc42c8bf4bcb22d72a43a8bd05f506043a9c1c 相符。

研究接口现存于 <CARRIER_NAV_SCRATCH>/BUILD_BODY_HV/：
legsa_v23_port_core_demo 的 SHA 为 e715d7405fbeff4e9e2b86aa3797b4ae8ea076b6fc4e34d7f88fc48e3b7a9462；
config_check 的 SHA 为 f5b2e4cbd2c1af51742e4050c82857bf1e31ef02b7d0ee209629eeb3b2511a97。
两者在本次只读盘点时 SHA 匹配旧 PLAN，彼时58个 C++源文件与其登记身份相同；随后新增的 PVT/carrier fallback 尚未包含在这两个旧二进制中，新试验必须使用另行封存的新构建。
它含 external-carrier 向量/完整协方差及 body-FRD HV 研究接口，**不是原 V3 二进制**。
尚未加载新三窗配置，也未执行关闭新功能的兼容运行。

实际 CMake 入口是 <CODE_ROOT>/cpp/CMakeLists.txt。如后续确需新构建，保留旧 binary：

~~~text
cmake -S <CODE_ROOT>/cpp -B <NEW_BUILD_ROOT> -DCMAKE_BUILD_TYPE=Release
cmake --build <NEW_BUILD_ROOT> --target legsa_v23_port_core_demo -j2
~~~

现有缓存为 C++17、Release、-O3 -DNDEBUG。本次未构建；
新构建必须另记源码/工具链/实际二进制 SHA。

## 冻结评价

入口文件位于 <CLEAN_ROOT>/16_FINAL_V23_ARCHIVE_RECOVERY/ARCHIVE_45953164c53e/selected/MAIN/KF-GINS/bin/evaluate_nav_trace_kfgins_v2.py，
当前 SHA aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da 相符。
使用 protocol_v3/evaluation_process.py::evaluate、各序列 base_time/full window、
--yaw_truth_mode enu、canonical_v2_wgs84_full_support 和被动访问审计。
参考只在新输出封存后由 evaluator 子进程读取。

物理点沿用 clean5_parity/evaluation.py::transform_nav/write_transformed_nav：
IMU 点加 body FRD 杆臂 [0.03, 0.03−median/2, −0.30]，依 NAV 姿态转 NED/ECEF 后回到 LLH；
评价点是天线中点。三窗已锁 median 依次为
**0.356191491865984、0.35418777593777223、0.35013463864843675 m**，
不能用 AR 名义长度 0.35 m 替代。仅改 NAV 零基列 2/3/4，其余 token 不变。
STD 同次原样保留，点位协方差未传播，因此不能据此宣称完整 NEES/保护水平。

clean5_parity.evaluation._metrics 内含 BY2 固定计数窗，不能直接用于 BY2H/O。
新封装应复用 protocol_v3/runtime.py::evaluate_native 的序列合同/指标路径；
已有 BY2 运行包装仅作接线参考，不能冒用其运行身份。

## 复用策略与缺失边界

默认复用原 V3 封存指标/评价记录，不重跑矩阵。
原 NAV/STD 历史 SHA 仍可作为每序列至多一次兼容检查的目标；
新输出全文件 SHA 同值才构成该输出字节一致证据，不同则保留新身份并独立评价，不能借用原数字。
原载荷在 summary 指向的 scratch 和 archive 均缺失，不重建它们补证据。

三条 error_series.csv.gz 仍在。共同时间支持只能在新输出封存后按实际键求交；
本次未打开压缩内容或派生统计。依赖缺失 NAV/完整协方差的指标记 NA，
不能由首末时刻和行数假造支持。

原 HV 含 A1/GNSS 航向旋转依赖，保留它只能称原输入复用，不能称独立速度。
载波臂如何移除/保留 PVT yaw 及处理共享信息，须在新运行合同明确。
原 D61/D62 等 provider 层故障不等于 raw phase/slip 故障，本轮没有复建任何退化输入。

核查量：10 个小运行对象当前 SHA 匹配、58 个研究 C++ 源身份匹配；
12 个大 provider 和 1 个注册表仅存在/大小核查，6 个旧 NAV/STD 确认缺失。
没有全盘搜索或大规模重复 hash。下一步缺的是新三窗配置、侧车和运行登记，不是原 V3 PVT 输入。
