# CLEAN5 IMU parity：P-03 审计、运行与分解记录

**COMPLETED_WITH_P02_V2E_UNAVAILABLE**。P-03 六次求解与十二次评估均完成；原P-02 V2e失败引用保留UNAVAILABLE。本记录列示A/B审计、全部v2/v3指标、体坐标偏差与37行分解，不作性能解读。

| 字段 | 状态 |
|---|---|
| input_audits | INPUT_AUDITS_COMPLETE |
| runtime | 6/6 COMPLETED，exit=0，retry=0 |
| evaluation | 12/12新增调用COMPLETED |
| metrics | 每版本18可用+1原P-02 UNAVAILABLE |
| decomposition | 37行；原22行保持，新增15行 |
| input-audit provider file generations / solver invocations / evaluator invocations | 0 / 0 / 0 |

审计基点：`8d47753d612eee3ab5c205b537cc7224c4e49829`。数据为锁定真实 Go2 raw；synthetic/semisynthetic=false；trace_used_online=false。源码审计和内存计算的精确 source hashes 见 [A_IMU_PREPROCESSING_COMPARISON.json](%3CCLEAN_ROOT%3E/stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/10_IMU_PROCESSING/00_AUDITS/A_IMU_PREPROCESSING_COMPARISON.json) 与 [B_INPUT_AUDIT.json](%3CCLEAN_ROOT%3E/stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/10_IMU_PROCESSING/00_AUDITS/B_INPUT_AUDIT.json)。本文中的输出链接采用 `<CLEAN_ROOT>` 别名；原始输入位于 `<RAW_ROOT>`。

## A. IMU 预处理逐项对照

EXT05C 与 LC01（EXT05A）共享冻结 native 摘要中的一个 provider/calibration。当前维护源码 `phase5_runner.py:434–456,612–624` 将同一 cache_root 传入同一 `_run_filter_sequence`，通过 two_receiver True/False 选择 dual/single。

| 项目 | 相同/不同 | 冻结 V2 | EXT05C / LC01 共同链 | 当前源码位置 |
|---|---|---|---|---|
| 原始IMU来源 | 相同 | Go2 by2.txt；不是接收机IMU | 共同Go2 by2.txt，63278帧 | `src/legsa_gins/input_generation/imu_txt_builder.py:29-48`；`src/legsa_gins/paper_rebuild/horizontal_literature/ext05_provider.py:261-277,338-354` |
| 时间戳字段 | 相同 | stamp.sec + stamp.nanosec*1e-9 | 相同Unix timestamp构造 | `src/legsa_gins/input_generation/imu_txt_builder.py:43-45,109`；`src/legsa_gins/paper_rebuild/horizontal_literature/ext05_provider.py:277,300-305` |
| 时间表达及序列化 | 不同 | 减1772784000为相对秒；中间所有列.12g读回，最终时间.6f/六个增量.8f | absolute float64保存在共同cache | `src/legsa_gins/paper_rebuild/horizontal_literature/phase5_runner.py:337`；`src/legsa_gins/paper_rebuild/final_v23_clean_input.py:429-469`；`src/legsa_gins/input_generation/process_data_compat.py:186-190` |
| dt来源 | 相同：测量差分 | 相邻消息时间差；载入器以已序列化相邻time差分 | IMU/GNSS事件时间差，不用标称采样周期 | `src/legsa_gins/input_generation/imu_txt_builder.py:118-124`；`cpp/legsa_v23_port_core/src/fileio/imu_file_loader.cpp:30-36`；`src/legsa_gins/paper_rebuild/horizontal_literature/phase5_runner.py:480-493` |
| 积分采样端点 | 不同（当前维护源码） | 当前样本current的gyro去偏与原始比力乘区间dt | previous样本ZOH，事件后才切换样本 | `src/legsa_gins/input_generation/imu_txt_builder.py:125-135`；`src/legsa_gins/paper_rebuild/horizontal_literature/phase5_runner.py:465-470,488-498` |
| FLU→FRD与安装角 | 相同 | [x,-y,-z]后RzRyRx，安装角[-1,0,0]deg | 相同固定顺序和角度 | `src/legsa_gins/input_generation/imu_txt_builder.py:64-76,96-106`；`src/legsa_gins/paper_rebuild/horizontal_literature/ext05_provider.py:327-335,345-353` |
| 输入重力处理 | 相同 | 保留含重力原始比力，不在输入阶段减重力；直接force*dt | 保留原始比力；不从accel减静态meanforce | `src/legsa_gins/input_generation/imu_txt_builder.py:126,133-145`；`src/legsa_gins/paper_rebuild/horizontal_literature/ext05_provider.py:352-353`；`src/legsa_gins/paper_rebuild/horizontal_literature/phase5_runner.py:470,497` |
| 传播器重力处理 | 均内部加入重力；算法不同 | NED INS mechanization含重力/Coriolis等 | C Exp(omega*dt/2) f + g的SE_2(3)传播 | `cpp/legsa_v23_port_core/src/kf_gins/insmech.cpp:26-51`；`src/legsa_gins/paper_rebuild/horizontal_literature/ext05_pavlasek.py:340-348` |
| 重力模型 | 不同 | Earth按当前latitude多项式及height计算 | 静态校准初始化位置使用Somigliana surface减3.086e-6*h，冻结g=9.801554418645956 | `cpp/legsa_v23_port_core/src/common/earth.cpp:24-32`；`src/legsa_gins/paper_rebuild/horizontal_literature/ext05_provider.py:384-390` |
| 前N帧陀螺零偏估计 | 不同 | 前min(1000,N)=1000帧FRD gyro算术均值后在输入去偏 | 首个输入-only合格5s静态窗；本次为最初1031样本 | `src/legsa_gins/input_generation/imu_txt_builder.py:114-115,125`；`src/legsa_gins/paper_rebuild/horizontal_literature/ext05_provider.py:407-474` |
| 输入加速度零偏/标度估计 | 相同：没有 | 不估计输入加速度零偏或scale，不归一化比力 | meanforce用于初始姿态；不做输入accel bias/scale校准 | `src/legsa_gins/input_generation/imu_txt_builder.py:125-135`；`src/legsa_gins/paper_rebuild/horizontal_literature/ext05_provider.py:461-469`；`configs/paper_rebuild/horizontal_literature/PHASE5_EXT05_PAVLASEK_CONTRACT_V1.yaml:103-105` |
| 加速度零偏/标度状态与先验 | 不同 | 21误差状态含BG/BA/SG/SA；初始bias/scale全0；abstd与initbastd=77.8mGal；asstd及其初始fallback为0 | 9维extended pose误差状态，无bias/scale随机状态或相应先验 | `src/legsa_gins/paper_rebuild/horizontal_literature/ext05_pavlasek.py:139-167,294-318`；`cpp/legsa_v23_port_core/include/legsa_v23_port_core/types.hpp:38-50`；`cpp/legsa_v23_port_core/src/config/port_config_loader.cpp:559-581`；`cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp:761-782` |
| IMU速率假设及间隔筛选 | 测量时标相同；标称字段/校验不同 | imudatarate=500为解析/报告字段；输入实际measured dt；丢弃dt<=0或dt>0.1；BY2丢弃0 | 63278消息measured dt，传播器限制dt<=0.1；没有按500Hz重采样 | `src/legsa_gins/input_generation/imu_txt_builder.py:118-124`；`src/legsa_gins/paper_rebuild/horizontal_literature/ext05_provider.py:355-369`；`src/legsa_gins/paper_rebuild/horizontal_literature/ext05_pavlasek.py:334-335`；`cpp/legsa_v23_port_core/src/config/port_config_loader.cpp:587`；`cpp/legsa_v23_port_core/src/fileio/imu_file_loader.cpp:30-36` |
| 初始姿态 | 不同 | 冻结initatt=[0,0,0.688505]deg与共同静态初值 | gravity-derived roll/pitch加首个GNSS2−GNSS1基线yaw，EXT05C同样使用双接收机初始化 | `src/legsa_gins/paper_rebuild/horizontal_literature/phase5_runner.py:434-456`；`src/legsa_gins/paper_rebuild/horizontal_literature/ext05_provider.py:477-508` |
| GNSS事件拆分/插值 | 不同 | C++按时间对齐情况及lambda拆分IMU增量 | 当前维护runner在min(next_imu,next_solution)事件处分段ZOH传播 | `src/legsa_gins/paper_rebuild/horizontal_literature/phase5_runner.py:480-498`；`cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp:278-294` |

### A.1 冻结输入内存重现

锁定 raw 共63278帧；有效增量63277行；dt筛除0。前1000帧 FRD gyro 均值为 `[-0.0076475324789062145, -0.0027141998420126146, -0.0011917145728981486]` rad/s。

序列化为原始 `.12g` 中间写出、float读回，再最终时间 `.6f` 与六个增量 `.8f`。省略中间读回产生15行差异；首差异第12676行的时间token为直接 `102.165045`、冻结 `102.165046`，其余六token相同。

最终直接导入已修复 `serialize_baseline` 的内存核验为 **PASS**：5091513 bytes，与 P02 V2 IMU 逐字节相同，SHA-256=`a46fe2b50a5a99d550392f42e3952c871a7562c6d5625ea1b377691009ab643b`。未写出 provider 文件。

### A.2 外部五秒输入校准

当前低层校准按锁定 raw 只读重算，各字段与冻结 native provider calibration 完全相等。

| 字段 | 冻结值与重现值 |
|---|---|
| acceleration_norm_median_mps2 | `9.507909327281775` |
| end_time_unix_seconds | `1772784049.887078` |
| gyro_bias_frd_radps | `[-0.0076655634452167005, -0.0026948138158392793, -0.0011093268712426007]` |
| gyro_norm_median_radps | `0.015289418986737115` |
| local_gravity_mps2 | `9.801554418645956` |
| max_internal_gap_seconds | `0.014250040054321289` |
| mean_specific_force_frd_mps2 | `[-0.13180068738317743, -0.14941227642414154, -9.506078096349812]` |
| sample_count | `1031` |
| start_time_unix_seconds | `1772784044.887078` |
| used_preregistered_initial_interval | `True` |

外部重力初始化位置（lat°, lon°, h m）：`[39.98482985253808, 116.34312812098969, 41.77999215293676]`。静态窗规则为首个连续5 s、gap≤max(0.1 s,5×median dt)、median gyro norm<0.05 rad/s、|median accel norm−g|≤0.5 m/s²；本次选择最初窗口。

### A.3 来源可用性边界

精确原始 `phase5_runner.py` 文本为 **UNAVAILABLE**。冻结记录SHA=`f3ef9ecd2f509c4785ab9d4b384204a782ecacded580d0222d3e013772ff09b1`，当前维护SHA=`9ca29e1e5d679c56ac1a68f70f4f917c484dbc5be11f76f903a9df8b014138db`。

previous-sample ZOH、事件拆分、cache时标表达和外部初始化执行路径属于当前维护源码证据。校准字典全部相等不构成原始runner逐字节证明。输入干预不等于复现外部传播器、状态维度、初值和GNSS事件调度。

完整15项与 source hashes：[A_IMU_PREPROCESSING_COMPARISON.json](%3CCLEAN_ROOT%3E/stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/10_IMU_PROCESSING/00_AUDITS/A_IMU_PREPROCESSING_COMPARISON.json)；审计说明：[A_IMU_PREPROCESSING_COMPARISON.md](%3CCLEAN_ROOT%3E/stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/10_IMU_PROCESSING/00_AUDITS/A_IMU_PREPROCESSING_COMPARISON.md)。

## B. 输入侧与先验审计

### B.1 消息时间间隔与等效速度增量量级

时间差使用原始整数纳秒 `stamp.sec×10⁹+stamp.nanosec` 相邻差，未以标称采样率代替；保留所有非负间隔。标准差为总体标准差。

| 序列 | 帧数 | dt数 | dt≤0数 | abs(dt−median)>1 ms数 | 比例 |
|---|---:|---:|---:|---:|---:|
| BY2 | 63278 | 63277 | 0 | 33462 | 0.528817737883 |
| BY2H | 63222 | 63221 | 0 | 31047 | 0.491086822417 |
| BY2O | 95860 | 95859 | 0 | 51857 | 0.540971635423 |

| dt，单位s | n | 均值 | 总体标准差 | 中位数 | 最小 | P05 | P95 | 最大 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BY2 | 63277 | 0.00482330027106 | 0.0018184701075 | 0.004011771 | 9.3331e-05 | 0.0019996814 | 0.008002543 | 0.091676082 |
| BY2H | 63221 | 0.00471324471128 | 0.0192616939155 | 0.004005938 | 0.000107914 | 0.00199874 | 0.007986793 | 4.740005874 |
| BY2O | 95859 | 0.00491640836168 | 0.00249861121826 | 0.004016021 | 0.000101498 | 0.002000198 | 0.008001959 | 0.345998617 |

明确公式：`δdt_i=dt_i−median(dt)`；`δv_equiv_i=g_local×δdt_i`。这是时间戳抖动的等效增量量级，**不是独立物理传感器噪声**。三序列使用本次冻结位置得到的同一 `g_local=9.801554354839126 m/s²`。

| 有符号等效δv，m/s | n | 均值 | 总体标准差 | 中位数 | 最小 | P05 | P95 | 最大 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BY2 | 63277 | 0.00795424826086 | 0.0178238336013 | 0 | -0.0384068026462 | -0.0197216055812 | 0.0391157686758 | 0.859246509246 |
| BY2H | 63221 | 0.00693270517618 | 0.188794539879 | 0 | -0.0382066941125 | -0.0196736602979 | 0.0390185666612 | 46.4201607972 |
| BY2O | 95859 | 0.00882519566589 | 0.0244902736674 | 0 | -0.0383684099578 | -0.0197581987042 | 0.039068387962 | 3.3519610031 |

| 绝对值等效δv，m/s | n | 均值 | 总体标准差 | 中位数 | 最小 | P05 | P95 | 最大 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BY2 | 63277 | 0.0128816621754 | 0.0146636246966 | 0.0177595441526 | 0 | 4.57340526197e-05 | 0.0391157686758 | 0.859246509246 |
| BY2H | 63221 | 0.0123606047525 | 0.188516991646 | 0.00485124012171 | 0 | 2.28670263098e-05 | 0.0390185666612 | 46.4201607972 |
| BY2O | 95859 | 0.0132699102124 | 0.0223956930189 | 0.0190059392091 | 0 | 7.02379385068e-05 | 0.039068387962 | 3.3519610031 |

| 序列 | 等效δv RMS，m/s |
|---|---:|
| BY2 | 0.0195181738296 |
| BY2H | 0.18892178458 |
| BY2O | 0.0260318570764 |

BY2H最大原始间隔为4.740005874 s；以上统计保留该间隔。未按大小删选数据。

来源：[B_INPUT_AUDIT.json](%3CCLEAN_ROOT%3E/stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/10_IMU_PROCESSING/00_AUDITS/B_INPUT_AUDIT.json) → `sequences.<sequence>.B1`。

### B.2 全程模长、温度与10秒滑窗

温度由已存在的 raw parser 的 `imu_state.temperature` 取得；与 `parse_sportmodestate_text` 全序列 timestamp/accel/gyro 逐帧精确断言通过。三序列没有不完整消息。未改变维护parser。温度为原始报告单位，未作单位转换。

| 全程加速度计模长，m/s² | n | 均值 | 总体标准差 | 中位数 | 最小 | P05 | P95 | 最大 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BY2 | 63278 | 9.82473088808 | 3.38403024372 | 9.35902190226 | 0.23534831899 | 5.95877699696 | 16.6508641802 | 30.9569231154 |
| BY2H | 63222 | 9.84465046749 | 3.45952289239 | 9.291033852 | 0.732930807965 | 5.92009430974 | 17.0328459562 | 31.3293134737 |
| BY2O | 95860 | 9.73256329468 | 2.78664924204 | 9.50195051975 | 0.466576114223 | 6.27315046665 | 15.0935021015 | 31.7737593452 |

| 原始温度字段 | n | 均值 | 总体标准差 | 中位数 | 最小 | P05 | P95 | 最大 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BY2 | 63278 | 79 | 0 | 79 | 79 | 79 | 79 | 79 |
| BY2H | 63222 | 79 | 0 | 79 | 79 | 79 | 79 | 79 |
| BY2O | 95860 | 79 | 0 | 79 | 79 | 79 | 79 | 79 |

三序列温度均为常量79，温度−模长 Pearson 相关系数均为 **UNAVAILABLE_CONSTANT_OR_MISSING**。全程运动模长变化只报告 observed variation，不能仅据此归因于scale或温度。

滑窗从首帧相对时刻0开始，宽10 s、步长1 s，区间 `[start,start+10)`。完整窗与末端部分窗分别保留；不作结果导向静态筛选。以下摘要覆盖所有窗，逐窗值见原CSV。

| 序列 | 完整窗数 | 部分末端窗数 | 完整窗起点范围s | 部分窗起点范围s | 完整窗样本数范围 | 部分窗样本数范围 |
|---|---:|---:|---|---|---|---|
| BY2 | 296 | 10 | 0–295 | 296–305 | 1631–2340 | 44–1910 |
| BY2H | 288 | 10 | 0–287 | 288–297 | 721–2303 | 191–1970 |
| BY2O | 462 | 10 | 0–461 | 462–471 | 1710–2250 | 64–2049 |

完整滑窗摘要：以下每行统计对象为指定scope下全部窗口的相应逐窗统计量；不将重叠窗口当成独立样本。单位m/s²。

| 序列/scope/逐窗统计量 | 窗数 | 均值 | 总体标准差 | 中位数 | 最小 | P05 | P95 | 最大 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BY2/FULL/mean | 296 | 9.83071110086 | 0.080095079277 | 9.8471396521 | 9.5038562006 | 9.66678439882 | 9.90854079115 | 9.94444062213 |
| BY2/FULL/std_population | 296 | 3.34833442656 | 0.68889423718 | 3.50148065843 | 0.0331404806399 | 2.4660968984 | 3.62951479778 | 3.72561275123 |
| BY2/FULL/median | 296 | 9.21405237047 | 0.10269767354 | 9.2087664466 | 8.99401926772 | 9.07432298104 | 9.4983610707 | 9.50697118776 |
| BY2/FULL/min | 296 | 2.64409047291 | 1.72471163623 | 2.57586224574 | 0.23534831899 | 0.375944952852 | 4.36146093555 | 9.38319666637 |
| BY2/FULL/max | 296 | 28.0576548364 | 3.57851681936 | 28.5918652901 | 9.60670626309 | 26.8036992517 | 30.7691207681 | 30.9569231154 |
| BY2/PARTIAL_TERMINAL/mean | 10 | 9.73650539869 | 0.0768277000432 | 9.77235898024 | 9.5677537496 | 9.59847985709 | 9.80181588903 | 9.80367032295 |
| BY2/PARTIAL_TERMINAL/std_population | 10 | 2.75303160061 | 0.641638625472 | 3.02580991623 | 1.02939619288 | 1.54766132397 | 3.17172766722 | 3.18936762927 |
| BY2/PARTIAL_TERMINAL/median | 10 | 9.32818743697 | 0.0972963763639 | 9.30964679649 | 9.22677400037 | 9.23410992806 | 9.51102834949 | 9.54108667097 |
| BY2/PARTIAL_TERMINAL/min | 10 | 3.40225594451 | 1.23122778039 | 3.35056645853 | 1.61677103784 | 2.04590708739 | 5.21140360331 | 6.73390672177 |
| BY2/PARTIAL_TERMINAL/max | 10 | 24.2968467756 | 4.33198255653 | 25.9257386167 | 11.6995265246 | 16.6598235052 | 26.4241907149 | 26.4241907149 |
| BY2H/FULL/mean | 288 | 9.84747293945 | 0.0763199302845 | 9.85496251503 | 9.49610611183 | 9.78966212294 | 9.92929184234 | 9.96408077747 |
| BY2H/FULL/std_population | 288 | 3.41529517245 | 0.624444397135 | 3.54187715984 | 0.0309370007923 | 3.33358103359 | 3.62715934 | 3.69065935887 |
| BY2H/FULL/median | 288 | 9.20447720519 | 0.0876944279851 | 9.20085372401 | 9.01238842436 | 9.07816008838 | 9.30059626588 | 9.50255688656 |
| BY2H/FULL/min | 288 | 2.68255446722 | 1.43178085107 | 2.63321652714 | 0.732930807965 | 1.09407944074 | 4.24905276145 | 9.38936488446 |
| BY2H/FULL/max | 288 | 28.5419482028 | 3.6156856189 | 28.8406326564 | 9.59906412489 | 27.1597136053 | 31.2629760033 | 31.3293134737 |
| BY2H/PARTIAL_TERMINAL/mean | 10 | 9.7518897785 | 0.0412835030406 | 9.75381609062 | 9.66420313149 | 9.68489057758 | 9.80106785258 | 9.80343354526 |
| BY2H/PARTIAL_TERMINAL/std_population | 10 | 3.24696819442 | 0.138935282113 | 3.27568551595 | 3.04062888517 | 3.06227534322 | 3.44070322515 | 3.4791075932 |
| BY2H/PARTIAL_TERMINAL/median | 10 | 9.32922672898 | 0.0791181404689 | 9.28859271363 | 9.2674848686 | 9.26817050334 | 9.47832670325 | 9.49185256882 |
| BY2H/PARTIAL_TERMINAL/min | 10 | 2.16247088365 | 0.38646333896 | 2.34163922187 | 1.39463994319 | 1.39463994319 | 2.39279680947 | 2.39279680947 |
| BY2H/PARTIAL_TERMINAL/max | 10 | 27.2661965779 | 0.199658990416 | 27.1996435811 | 27.1996435811 | 27.1996435811 | 27.5656850636 | 27.8651735492 |
| BY2O/FULL/mean | 462 | 9.73335491102 | 0.172421970338 | 9.82249523547 | 9.48297934992 | 9.51113933741 | 9.93066127733 | 9.98138310986 |
| BY2O/FULL/std_population | 462 | 2.29324954044 | 1.57502328397 | 3.42929082954 | 0.0308251721465 | 0.0313743179441 | 3.61167516307 | 3.73064794454 |
| BY2O/FULL/median | 462 | 9.33556625092 | 0.15641063361 | 9.2948303814 | 9.00591344875 | 9.10845907519 | 9.51712953902 | 9.51981148609 |
| BY2O/FULL/min | 462 | 4.54584886476 | 3.06098290049 | 3.28868790558 | 0.466576114223 | 0.897667586318 | 9.42445420458 | 9.42640626944 |
| BY2O/FULL/max | 462 | 22.9728198262 | 8.7553395588 | 28.1552324277 | 9.60806326815 | 9.62422564666 | 31.5958005343 | 31.7737593452 |
| BY2O/PARTIAL_TERMINAL/mean | 10 | 9.51460802432 | 0.0238734750992 | 9.50906186446 | 9.46919885623 | 9.48312341864 | 9.55435129868 | 9.55971224224 |
| BY2O/PARTIAL_TERMINAL/std_population | 10 | 0.910014242505 | 0.900221016005 | 0.683102219701 | 0.0321046572122 | 0.0327828772383 | 2.17563849566 | 2.23182714132 |
| BY2O/PARTIAL_TERMINAL/median | 10 | 9.50615305036 | 0.00380404591262 | 9.50681445187 | 9.49961717736 | 9.50015833425 | 9.51097554274 | 9.51201643712 |
| BY2O/PARTIAL_TERMINAL/min | 10 | 5.62435383417 | 3.58801600309 | 5.17992217324 | 2.05015359429 | 2.05015359429 | 9.43659190967 | 9.44474278488 |
| BY2O/PARTIAL_TERMINAL/max | 10 | 18.3980347927 | 8.5939028104 | 18.8114107787 | 9.59028606993 | 9.59449096322 | 26.9869624334 | 26.9869624334 |

所有完整/部分窗的温度均值、中位数、最小、最大、P05、P95均为79，温度标准差均为0；temperature unavailable_n均为0。

| 序列 | 全量逐帧CSV | 温度CSV | 全部10s窗口CSV | 单序列审计JSON |
|---|---|---|---|---|
| BY2 | [B_BY2_FRAMES.csv](%3CCLEAN_ROOT%3E/stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/10_IMU_PROCESSING/00_AUDITS/B_BY2_FRAMES.csv) | [B_BY2_TEMPERATURE.csv](%3CCLEAN_ROOT%3E/stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/10_IMU_PROCESSING/00_AUDITS/B_BY2_TEMPERATURE.csv) | [B_BY2_WINDOWS_10S.csv](%3CCLEAN_ROOT%3E/stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/10_IMU_PROCESSING/00_AUDITS/B_BY2_WINDOWS_10S.csv) | [B_BY2_AUDIT.json](%3CCLEAN_ROOT%3E/stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/10_IMU_PROCESSING/00_AUDITS/B_BY2_AUDIT.json) |
| BY2H | [B_BY2H_FRAMES.csv](%3CCLEAN_ROOT%3E/stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/10_IMU_PROCESSING/00_AUDITS/B_BY2H_FRAMES.csv) | [B_BY2H_TEMPERATURE.csv](%3CCLEAN_ROOT%3E/stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/10_IMU_PROCESSING/00_AUDITS/B_BY2H_TEMPERATURE.csv) | [B_BY2H_WINDOWS_10S.csv](%3CCLEAN_ROOT%3E/stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/10_IMU_PROCESSING/00_AUDITS/B_BY2H_WINDOWS_10S.csv) | [B_BY2H_AUDIT.json](%3CCLEAN_ROOT%3E/stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/10_IMU_PROCESSING/00_AUDITS/B_BY2H_AUDIT.json) |
| BY2O | [B_BY2O_FRAMES.csv](%3CCLEAN_ROOT%3E/stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/10_IMU_PROCESSING/00_AUDITS/B_BY2O_FRAMES.csv) | [B_BY2O_TEMPERATURE.csv](%3CCLEAN_ROOT%3E/stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/10_IMU_PROCESSING/00_AUDITS/B_BY2O_TEMPERATURE.csv) | [B_BY2O_WINDOWS_10S.csv](%3CCLEAN_ROOT%3E/stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/10_IMU_PROCESSING/00_AUDITS/B_BY2O_WINDOWS_10S.csv) | [B_BY2O_AUDIT.json](%3CCLEAN_ROOT%3E/stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/10_IMU_PROCESSING/00_AUDITS/B_BY2O_AUDIT.json) |

逐帧CSV保留 `timestamp_ns`、`timestamp`、相对 `time`、`norm_mps2`、`imu_state.temperature`、`gyro_norm_radps` 和原消息索引。来源字段为 `B2`，无归因拟合或后续校正。

### B.3 固定前1000帧与局地重力比例

| 前1000帧模长，m/s² | n | 均值 | 总体标准差 | 中位数 | 最小 | P05 | P95 | 最大 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BY2 | 1000 | 9.50831884389 | 0.0343221731154 | 9.5078332743 | 9.4050149707 | 9.44980479975 | 9.56875986696 | 9.60670626309 |
| BY2H | 1000 | 9.50198930959 | 0.0311098931915 | 9.50210355467 | 9.41933062893 | 9.45183899016 | 9.55398975054 | 9.58827092132 |
| BY2O | 1000 | 9.51513125885 | 0.0318041290339 | 9.51531029148 | 9.43298314389 | 9.46212739956 | 9.56834479694 | 9.62080479824 |

冻结初值为 `[39.98482973, 116.34312609, 41.80208107]`（lat°,lon°,椭球高m）。重力公式以NGA WGS84定义参数及AHRS官方公式为来源；未直接下载或核对受注册页面限制的NGA PDF公式。

定义参数来源：[NGA WGS84](https://earth-info.nga.mil/?action=wgs84&dir=wgs84)；公式来源：[AHRS WGS84 normal gravity](https://ahrs.readthedocs.io/en/latest/geodesy/wgs84.html)。

| 常数/派生量 | 值 |
|---|---|
| a_m | `6378137` |
| inverse_flattening | `298.257223563` |
| GM_m3ps2 | `3.986004418e+14` |
| omega_radps | `7.292115e-05` |
| ge_mps2 | `9.7803253359` |
| k | `0.00193185265241` |
| derived_e2 | `0.00669437999014` |
| derived_b_m | `6356752.31425` |
| derived_m | `0.00344978650684` |

```text
f=1/inverse_flattening; e²=f(2−f); b=a(1−f); m=ω²a²b/GM
g0=ge(1+k sin²φ)/sqrt(1−e² sin²φ)
g(h)=g0[1−(2/a)(1+f+m−2f sin²φ)h+3h²/a²]
s=g_local / mean(norm(a_i), i=0..999)
```

椭球表面g0=`9.80168335159263` m/s²；高度修正后 **g_local=`9.801554354839126` m/s²**。BY2固定前1000帧 `mean(norm)= 9.508318843893118` m/s²；**s=`1.0308398903907543`**。定义为 `mean(norm(a))`，不是 `norm(mean(a))`；只使用BY2固定前1000帧，未用结果挑选区间。

来源与精确hash：[B_SCALE_FACTOR.json](%3CCLEAN_ROOT%3E/stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/10_IMU_PROCESSING/00_AUDITS/B_SCALE_FACTOR.json)；g常数与来源同存 `gravity_spec`。

### B.4 冻结噪声、单位转换与先验理论

冻结配置原文：

```yaml
arw: [0.985, 0.985, 0.985]
vrw: [0.077, 0.077, 0.077]
gbstd: [9.38, 9.38, 9.38]
abstd: [77.8, 77.8, 77.8]
gsstd: [0, 0, 0]
asstd: [0, 0, 0]
corrtime: 1.0
```

| 参数 | 源码单位转换 | 转换后各轴值 |
|---|---|---|
| arw | deg/sqrt(hour) -> rad/sqrt(s)；乘0.000290888208666 | `[0.00028652488553573575, 0.00028652488553573575, 0.00028652488553573575]` |
| vrw | m/s/sqrt(hour) -> m/s/sqrt(s)；乘0.0166666666667 | `[0.0012833333333333334, 0.0012833333333333334, 0.0012833333333333334]` |
| gbstd | deg/hour -> rad/s；乘4.8481368111e-06 | `[4.547552328807448e-05, 4.547552328807448e-05, 4.547552328807448e-05]` |
| abstd | mGal -> m/s2；乘1e-05 | `[0.000778, 0.000778, 0.000778]` |
| gsstd | ppm -> dimensionless；乘1e-06 | `[0.0, 0.0, 0.0]` |
| asstd | ppm -> dimensionless；乘1e-06 | `[0.0, 0.0, 0.0]` |
| corrtime | hour→second，乘3600 | 3600.0 s |

源码：`cpp/legsa_v23_port_core/src/config/port_config_loader.cpp:564–581`；初始化协方差 `gi_engine.cpp:53–56,766–769`；Qc `gi_engine.cpp:772–782`；F/Phi/Qd `gi_engine.cpp:808–825`。

| 理论量 | 值 |
|---|---|
| ab stationary σ | 0.000778 m/s² |
| 0.3 m/s² / σ | 385.6041131105398 |
| τ | 3600.0 s |
| stationary P_a=σ² | 6.05284e-07 m²/s⁴ |
| Qc_a=2σ²/τ | 3.362688888888889e-10 m²/s⁵ |

```text
db=−b/τ dt+sqrt(2σ²/τ)dW
E[b(T)|b0]=b0 exp(−T/τ)
P(T)=σ²+(P0−σ²)exp(−2T/τ)
δv=0.3T; δp=0.15T²  （自由积分，无滤波/姿态/重力反馈）
```

| T s | 自由δv m/s | 自由δp m | OU均值衰减exp(−T/τ) | P(T), P0=0 | E[b(T)], b0=0.3 m/s² |
|---|---:|---:|---:|---:|---:|
| 1 | 0.3 | 0.15 | 0.999722260799 | 3.3617549816e-10 | 0.29991667824 |
| 10 | 3 | 15 | 0.997226076677 | 3.3533653602e-09 | 0.299167823003 |
| 274 | 82.2 | 11261.4 | 0.926713232702 | 8.54676650569e-08 | 0.278013969811 |

上表精确OU指数为理论先验量；native实现使用 `Phi=I+F·dt` 与梯形Qd，不称其采用精确OU离散。冻结初始scale标准差及scale驱动标准差均为0；该零scale协方差/驱动不吸收scale误差。以上为先验与自由积分理论，不是运行误差指标。

偏置先验标准差不是硬界；`0.3/0.000778=385.6041131105398` 仅表示相对先验尺度，不能据此断言实际滤波吸收了多少持续误差。实际吸收量未由本理论审计推算。

来源：[B_INPUT_AUDIT.json](%3CCLEAN_ROOT%3E/stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/10_IMU_PROCESSING/00_AUDITS/B_INPUT_AUDIT.json) → `B4`；冻结配置SHA-256=`8f2b51509ba7d811e2f42dea6acf199f6206260ca8fbd811bd1d32bb730669c1`。

## C. 预注册与执行结果

代码与合约 v3 提交并推送后，以同一提交的干净 detached 快照执行。P-03 的活动范围由合约 `p03` 块指定；顶层 P-02 八次运行定义仅保留为原注册历史。

| 变体 | F03/A04 次数 | IMU处理 | 其余输入 |
| --- | --- | --- | --- |
| V2i | 1 / 1 | 原外部5s陀螺校准+当前维护源码previous-sample ZOH；原runner文本UNAVAILABLE | 四份V2非IMU provider原路径/原hash |
| V2s | 1 / 1 | 原current-sample，三轴未舍入比力先乘s再乘dt；time/gyro token原样 | 同V2 |
| V2is | 1 / 1 | V2i+s；time/gyro token等于V2i | 同V2 |

固定 `s=1.0308398903907543`；与冻结链前1000帧陀螺去偏同属输入侧标定。所有新IMU均使用原 `.12g → float → time .6f / increment .8f` 序列化，三份各63277行、跳过0个BY2区间；全部时间token等于V2。原IMU内存重建SHA=`a46fe2b50a5a99d550392f42e3952c871a7562c6d5625ea1b377691009ab643b`。

| 变体 | IMU SHA-256 |
| --- | --- |
| V2i | 44bcac046d2af3bcdcb9d5f503dc183ed90a77d661b792d65e18dddf86b5d58d |
| V2s | 74e31747c5b10d46846472a5adb41bd8e75ad3e27a612f45946c4895b976f647 |
| V2is | a8187c9e996271fbeafd8efe684e50790673c38efe5c7df6fb9fe538341cfb28 |

非IMU输入、冻结配置和初始状态均保持。F03/A04 的 frozen_parameter_hash 分别为：

- F03: `9a05481fd5e6cbeec5ef7d029908970fda6e09a3708f6b13316e54268efd0c97`，三变体及P-02 V2均相等。
- A04: `6e2ef3e39c03aea3635c5273506ad5d476b963f3e12f190102f8bb420378689f`，三变体及P-02 V2均相等。

六次串行调用均COMPLETED、exit=0；重跑0次。每run P/RV期望1369、yaw attempt期望273，独立源时序重算与native一致。下表计数来自封存run manifest；yaw列为normal/downweight/reject/accepted，RD列为实际update。

| run | exit | P/RV | yaw attempt | yaw N/D/R/A | RD | RP/HV | 原生终态 | 耗时s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V2i/F03 | 0 | 1369/1369 | 273 | 245/22/6/267 | 0 | 0/0 | COMPLETED | 8.238503857 |
| V2i/A04 | 0 | 1369/1369 | 273 | 245/22/6/267 | 1063 | 1369/1369 | COMPLETED | 10.037949414 |
| V2s/F03 | 0 | 1369/1369 | 273 | 244/23/6/267 | 0 | 0/0 | COMPLETED | 8.399448650 |
| V2s/A04 | 0 | 1369/1369 | 273 | 244/23/6/267 | 1066 | 1369/1369 | COMPLETED | 9.877031204 |
| V2is/F03 | 0 | 1369/1369 | 273 | 244/23/6/267 | 0 | 0/0 | COMPLETED | 8.193041751 |
| V2is/A04 | 0 | 1369/1369 | 273 | 244/23/6/267 | 1063 | 1369/1369 | COMPLETED | 9.794043841 |

A04 的RD按provider时刻选择数均1108，实际update按run分别记录；RP/HV均1369。F03的RD/RP/HV更新均0。source-aware evaluation/weight changed、FGO、nine-factor、QM、QA、contact/FK均0。所有辅助选择明细在 `04_PARITY_SEAL/SCHEDULING/<run>/`。

四次独立raw hash-only检查点均为22文件并PASS；每个检查点允许trace/.bag/.fpl各1次仅作哈希。provider生成仅5次只读打开BY2 body，trace/.bag/.fpl为0/0/0；六个solver均raw/trace/.bag/.fpl打开0，越界写入0。114个封存文件哈希通过独立复核；封存早于首次评估。

## D. v2/v3 指标、体坐标偏差与分解

终态 `COMPLETED_WITH_P02_V2E_UNAVAILABLE`：新增求解6/6完成、实际新增评估12/12完成。每个评估版本19行，其中18行AVAILABLE/COMPLETED、1行P-02 V2e为UNAVAILABLE；原13行的全部数值字段保持。总计36行可用结果、2行原失败引用。

评估器SHA=`aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da`，`base_time=1772784000`，窗口66–340，trace SHA=`ee3ee42dea3ada196dfdbcc78fd07524f91b4ce4fb94d9d6482a3e7d4b34aa4c`。可执行文件SHA=`9c00565c45b654453b2b378f3d5995e5dc21d1271323a9b683acdab75993235f`。

v3仅对新的NAV副本执行既授权变换：`POI_est=p_IMU+C_b^n·[0.03,-0.148095745932992,-0.30]`，`b_med=0.356191491865984 m`，使用每run自己的完整roll/pitch/yaw。原NAV/STD保持，未拟合或进一步修正；v3单列，不替换v2。完整协方差运输为 `UNAVAILABLE_FULL_COVARIANCE_NOT_TRANSPORTED`。

来源缩写：`P03-v2:n` = `<CLEAN_ROOT>/stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/10_IMU_PROCESSING/08_AGGREGATE/UNIQUE_EVALUATION_RESULTS.csv:n`；`P03-v3:n`在同目录的`v3/`；`P02-v2:n`/`P02-v3:n`使用父stage相应表。n包含CSV表头。P-02原来源保存在p02_source_row/frozen_source_row；当前source_row指本P-03表。小数显示9位，完整精度在CSV/JSON。

### evaluator_contract_v2 全部指标

| 行源 | 变体/方法 | H m | 3D m | Up m | yaw deg | matched | time start/end | 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P03-v2:2 | V0-18/A04 | 0.352386387 | 0.890358461 | 0.817656421 | 1.934075656 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v2:3 | V1/F01 | 0.288911147 | 0.866783379 | 0.817217092 | 7.512225616 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v2:4 | V1/F03 | 0.286993916 | 0.866176658 | 0.817249347 | 1.892542426 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v2:5 | V1/A04 | 0.286718204 | 0.865822042 | 0.816970305 | 1.906077412 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v2:6 | V2/F01 | 0.195105249 | 0.528712607 | 0.491396950 | 7.886386458 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v2:7 | V2/F03 | 0.194404836 | 0.528504175 | 0.491450326 | 1.916259723 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v2:8 | V2/A04 | 0.194107267 | 0.528320210 | 0.491370139 | 1.912220730 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v2:9 | V2e/F01 | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE/UNAVAILABLE | UNAVAILABLE |
| P03-v2:10 | V0/F01 | 0.354570400 | 0.891344831 | 0.817786915 | 6.927287766 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v2:11 | V0/F03 | 0.352517110 | 0.890580910 | 0.817842310 | 1.962413317 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v2:12 | V0/A04 | 0.352386387 | 0.890358461 | 0.817656421 | 1.934075656 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v2:13 | LC01 | 0.169139117 | 0.379008961 | 0.339175104 | 2.994827460 | 58014 | 66.0/340.0 | COMPLETED |
| P03-v2:14 | EXT05C | 0.171007693 | 0.381819908 | 0.341383671 | 12.048641738 | 58014 | 66.0/340.0 | COMPLETED |
| P03-v2:15 | V2i/F03 | 0.206411112 | 0.516950120 | 0.473953457 | 1.701268128 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v2:16 | V2i/A04 | 0.206148598 | 0.516827858 | 0.473934374 | 1.719874249 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v2:17 | V2s/F03 | 0.194934612 | 0.480999116 | 0.439727924 | 1.926909839 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v2:18 | V2s/A04 | 0.194634839 | 0.480815258 | 0.439659632 | 1.924220175 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v2:19 | V2is/F03 | 0.207205829 | 0.466091429 | 0.417500856 | 1.701513956 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v2:20 | V2is/A04 | 0.206941611 | 0.465981404 | 0.417509088 | 1.723020812 | 56642 | 66.005054/339.997056 | COMPLETED |

### evaluator_contract_v2 BODY_FRAME_BIAS

使用该run原NAV航向：`F=N*cos(yaw)+E*sin(yaw)`，`R=E*cos(yaw)-N*sin(yaw)`，`U=Up`；下列σ为总体标准差(ddof=0)。均值带符号，未用于拟合。

| CSV行 | 变体/方法 | 前μ m | 前σ m | 右μ m | 右σ m | 上μ m | 上σ m | count | 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | V0-18/A04 | -0.219003239 | 0.146387605 | 0.148759939 | 0.180706660 | -0.412836014 | 0.705782154 | 56642 | AVAILABLE |
| 3 | V1/F01 | 0.047194720 | 0.152170694 | 0.154226888 | 0.185203822 | -0.408513216 | 0.707785792 | 56642 | AVAILABLE |
| 4 | V1/F03 | 0.027059573 | 0.152187719 | 0.160247576 | 0.181088101 | -0.408681072 | 0.707726131 | 56642 | AVAILABLE |
| 5 | V1/A04 | 0.026594205 | 0.151986375 | 0.160230188 | 0.180904685 | -0.408667224 | 0.707411888 | 56642 | AVAILABLE |
| 6 | V2/F01 | 0.039170298 | 0.093526842 | 0.137994231 | 0.093499027 | -0.360040786 | 0.334427264 | 56642 | AVAILABLE |
| 7 | V2/F03 | 0.023634437 | 0.090932892 | 0.144313287 | 0.090219386 | -0.360104417 | 0.334437186 | 56642 | AVAILABLE |
| 8 | V2/A04 | 0.023275408 | 0.090782094 | 0.144168444 | 0.090055305 | -0.360119057 | 0.334303572 | 56642 | AVAILABLE |
| 9 | V2e/F01 | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE |
| 10 | V0/F01 | -0.202374791 | 0.148371518 | 0.165529451 | 0.188017303 | -0.412729128 | 0.705995826 | 56642 | AVAILABLE |
| 11 | V0/F03 | -0.218489306 | 0.146647907 | 0.149150570 | 0.181050366 | -0.412871548 | 0.705976719 | 56642 | AVAILABLE |
| 12 | V0/A04 | -0.219003239 | 0.146387605 | 0.148759939 | 0.180706660 | -0.412836014 | 0.705782154 | 56642 | AVAILABLE |
| 13 | LC01 | 0.015193793 | 0.073160722 | 0.143972769 | 0.047922228 | -0.337142249 | 0.037079043 | 58014 | AVAILABLE |
| 14 | EXT05C | -0.015752772 | 0.078416221 | 0.146577692 | 0.036896581 | -0.338625335 | 0.043309270 | 58014 | AVAILABLE |
| 15 | V2i/F03 | 0.019848461 | 0.090555306 | 0.163589645 | 0.085145466 | -0.381722099 | 0.280927247 | 56642 | AVAILABLE |
| 16 | V2i/A04 | 0.019460057 | 0.090470684 | 0.163418156 | 0.085018305 | -0.381711802 | 0.280909044 | 56642 | AVAILABLE |
| 17 | V2s/F03 | 0.024110128 | 0.091377604 | 0.143876115 | 0.091476783 | -0.308435712 | 0.313413559 | 56642 | AVAILABLE |
| 18 | V2s/A04 | 0.023741305 | 0.091232681 | 0.143729287 | 0.091310246 | -0.308470580 | 0.313283407 | 56642 | AVAILABLE |
| 19 | V2is/F03 | 0.020073975 | 0.090937782 | 0.163639668 | 0.086508208 | -0.330724705 | 0.254809997 | 56642 | AVAILABLE |
| 20 | V2is/A04 | 0.019658535 | 0.090868498 | 0.163460979 | 0.086381694 | -0.330734058 | 0.254811345 | 56642 | AVAILABLE |

来源：`<CLEAN_ROOT>/stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/10_IMU_PROCESSING/08_AGGREGATE/BODY_FRAME_BIAS.csv`；error_series_source逐run保存在该CSV和最终摘要。

### evaluator_contract_v3 全部指标

| 行源 | 变体/方法 | H m | 3D m | Up m | yaw deg | matched | time start/end | 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P03-v3:2 | V0-18/A04 | 0.301330664 | 0.775302238 | 0.714348228 | 1.934075656 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v3:3 | V1/F01 | 0.253589220 | 0.759272996 | 0.715673102 | 7.512225616 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v3:4 | V1/F03 | 0.245556171 | 0.756601924 | 0.715645609 | 1.892542426 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v3:5 | V1/A04 | 0.245180270 | 0.756183178 | 0.715331835 | 1.906077412 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v3:6 | V2/F01 | 0.149833746 | 0.370992990 | 0.339390111 | 7.886386458 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v3:7 | V2/F03 | 0.139507765 | 0.366970756 | 0.339418796 | 1.916259723 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v3:8 | V2/A04 | 0.139145727 | 0.366713395 | 0.339289229 | 1.912220730 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v3:9 | V2e/F01 | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE/UNAVAILABLE | UNAVAILABLE |
| P03-v3:10 | V0/F01 | 0.297583351 | 0.774024700 | 0.714533683 | 6.927287766 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v3:11 | V0/F03 | 0.301355409 | 0.775495351 | 0.714547379 | 1.962413317 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v3:12 | V0/A04 | 0.301330664 | 0.775302238 | 0.714348228 | 1.934075656 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v3:13 | LC01 | 0.097547971 | 0.109920334 | 0.050664318 | 2.994827460 | 58014 | 66.0/340.0 | COMPLETED |
| P03-v3:14 | EXT05C | 0.087750813 | 0.104350662 | 0.056469952 | 12.048641738 | 58014 | 66.0/340.0 | COMPLETED |
| P03-v3:15 | V2i/F03 | 0.136122312 | 0.322081389 | 0.291902616 | 1.701268128 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v3:16 | V2i/A04 | 0.135800117 | 0.321927576 | 0.291883012 | 1.719874249 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v3:17 | V2s/F03 | 0.140758605 | 0.343660298 | 0.313511428 | 1.926909839 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v3:18 | V2s/A04 | 0.140394817 | 0.343392293 | 0.313380858 | 1.924220175 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v3:19 | V2is/F03 | 0.137302487 | 0.290922647 | 0.256483943 | 1.701513956 | 56642 | 66.005054/339.997056 | COMPLETED |
| P03-v3:20 | V2is/A04 | 0.136979691 | 0.290772396 | 0.256486160 | 1.723020812 | 56642 | 66.005054/339.997056 | COMPLETED |

### evaluator_contract_v3 BODY_FRAME_BIAS

使用该run原NAV航向：`F=N*cos(yaw)+E*sin(yaw)`，`R=E*cos(yaw)-N*sin(yaw)`，`U=Up`；下列σ为总体标准差(ddof=0)。均值带符号，未用于拟合。

| CSV行 | 变体/方法 | 前μ m | 前σ m | 右μ m | 右σ m | 上μ m | 上σ m | count | 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | V0-18/A04 | -0.189296784 | 0.147267328 | 0.005696757 | 0.182336989 | -0.110569264 | 0.705739207 | 56642 | AVAILABLE |
| 3 | V1/F01 | 0.076890388 | 0.153205648 | 0.011124403 | 0.186546611 | -0.106263510 | 0.707740105 | 56642 | AVAILABLE |
| 4 | V1/F03 | 0.056825056 | 0.153175860 | 0.017151053 | 0.182515049 | -0.106435942 | 0.707686391 | 56642 | AVAILABLE |
| 5 | V1/A04 | 0.056342529 | 0.152971403 | 0.017156607 | 0.182330153 | -0.106409193 | 0.707373111 | 56642 | AVAILABLE |
| 6 | V2/F01 | 0.068753373 | 0.094116341 | -0.005031340 | 0.094020876 | -0.057738467 | 0.334442696 | 56642 | AVAILABLE |
| 7 | V2/F03 | 0.053290074 | 0.091466188 | 0.001273993 | 0.090856469 | -0.057816103 | 0.334458394 | 56642 | AVAILABLE |
| 8 | V2/A04 | 0.052927069 | 0.091300981 | 0.001113554 | 0.090681584 | -0.057837248 | 0.334323247 | 56642 | AVAILABLE |
| 9 | V2e/F01 | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE |
| 10 | V0/F01 | -0.172720829 | 0.149296656 | 0.022467668 | 0.189549672 | -0.110456618 | 0.705944559 | 56642 | AVAILABLE |
| 11 | V0/F03 | -0.188773521 | 0.147533627 | 0.006081880 | 0.182692309 | -0.110608806 | 0.705934593 | 56642 | AVAILABLE |
| 12 | V0/A04 | -0.189296784 | 0.147267328 | 0.005696757 | 0.182336989 | -0.110569264 | 0.705739207 | 56642 | AVAILABLE |
| 13 | LC01 | 0.044245598 | 0.073720762 | 0.000216921 | 0.046077499 | -0.035167725 | 0.036470595 | 58014 | AVAILABLE |
| 14 | EXT05C | 0.013471659 | 0.078655528 | 0.003411557 | 0.036337154 | -0.036350684 | 0.043214387 | 58014 | AVAILABLE |
| 15 | V2i/F03 | 0.049035367 | 0.091577318 | 0.020777696 | 0.085479230 | -0.079282647 | 0.280929527 | 56642 | AVAILABLE |
| 16 | V2i/A04 | 0.048640707 | 0.091478664 | 0.020590774 | 0.085342998 | -0.079278423 | 0.280910349 | 56642 | AVAILABLE |
| 17 | V2s/F03 | 0.053790676 | 0.091905286 | 0.000804434 | 0.092045204 | -0.006166979 | 0.313450768 | 56642 | AVAILABLE |
| 18 | V2s/A04 | 0.053416821 | 0.091745997 | 0.000642154 | 0.091867337 | -0.006208178 | 0.313319359 | 56642 | AVAILABLE |
| 19 | V2is/F03 | 0.049289198 | 0.091959418 | 0.020800460 | 0.086794897 | -0.028302570 | 0.254917590 | 56642 | AVAILABLE |
| 20 | V2is/A04 | 0.048866301 | 0.091875922 | 0.020606484 | 0.086658573 | -0.028317800 | 0.254918129 | 56642 | AVAILABLE |

来源：`<CLEAN_ROOT>/stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/10_IMU_PROCESSING/08_AGGREGATE/v3/BODY_FRAME_BIAS.csv`；error_series_source逐run保存在该CSV和最终摘要。

### 更新后的完整分解表

37行：前22行保持P-02原值及原来源；追加15行。`imu_handling=V2−V2i`，`accel_scale=V2−V2s`，combined为附加的`V2−V2is`逐项差；F01上界列按请求记`V2 F01−EXT05C`，不作数学上界推论。残差预注册选择V2is A04(v3)，未依据结果择优。各端点采用各自native support，未宣称共同重采样支持。

| CSV行 | 项 | H m | 3D m | Up m | yaw deg | 左来源 | 右来源 | 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | time:F01 | 0.065659254 | 0.024561452 | 0.000569823 | -0.584937850 | P02-v2:10 | P02-v2:3 | AVAILABLE |
| 3 | rate:F01 | 0.093805898 | 0.338070772 | 0.325820142 | -0.374160842 | P02-v2:3 | P02-v2:6 | AVAILABLE |
| 4 | time:F03 | 0.065523194 | 0.024404252 | 0.000592963 | 0.069870891 | P02-v2:11 | P02-v2:4 | AVAILABLE |
| 5 | rate:F03 | 0.092589081 | 0.337672483 | 0.325799021 | -0.023717296 | P02-v2:4 | P02-v2:7 | AVAILABLE |
| 6 | time:A04 | 0.065668184 | 0.024536419 | 0.000686116 | 0.027998244 | P02-v2:12 | P02-v2:5 | AVAILABLE |
| 7 | rate:A04 | 0.092610936 | 0.337501831 | 0.325600166 | -0.006143317 | P02-v2:5 | P02-v2:8 | AVAILABLE |
| 8 | module:V2:A04-F03 | -0.000297568 | -0.000183964 | -0.000080187 | -0.004038993 | P02-v2:8 | P02-v2:7 | AVAILABLE |
| 9 | estimator:V2e-EXT05C | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | P02-v2:9 | P02-v2:14 | UNAVAILABLE |
| 10 | dual_receiver:LC01-EXT05C | -0.001868577 | -0.002810947 | -0.002208566 | -9.053814278 | P02-v2:13 | P02-v2:14 | AVAILABLE |
| 11 | measurement_point:V0-18:A04 | 0.051055724 | 0.115056223 | 0.103308193 | 0.000000000 | P02-v2:2 | P02-v3:2 | AVAILABLE |
| 12 | measurement_point:V1:F01 | 0.035321926 | 0.107510383 | 0.101543989 | 0.000000000 | P02-v2:3 | P02-v3:3 | AVAILABLE |
| 13 | measurement_point:V1:F03 | 0.041437746 | 0.109574734 | 0.101603737 | 0.000000000 | P02-v2:4 | P02-v3:4 | AVAILABLE |
| 14 | measurement_point:V1:A04 | 0.041537934 | 0.109638864 | 0.101638470 | 0.000000000 | P02-v2:5 | P02-v3:5 | AVAILABLE |
| 15 | measurement_point:V2:F01 | 0.045271503 | 0.157719617 | 0.152006839 | 0.000000000 | P02-v2:6 | P02-v3:6 | AVAILABLE |
| 16 | measurement_point:V2:F03 | 0.054897071 | 0.161533419 | 0.152031529 | 0.000000000 | P02-v2:7 | P02-v3:7 | AVAILABLE |
| 17 | measurement_point:V2:A04 | 0.054961540 | 0.161606815 | 0.152080910 | 0.000000000 | P02-v2:8 | P02-v3:8 | AVAILABLE |
| 18 | measurement_point:V2e:F01 | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE | P02-v2:9 | P02-v3:9 | UNAVAILABLE |
| 19 | measurement_point:V0:F01 | 0.056987049 | 0.117320131 | 0.103253232 | 0.000000000 | P02-v2:10 | P02-v3:10 | AVAILABLE |
| 20 | measurement_point:V0:F03 | 0.051161701 | 0.115085559 | 0.103294931 | 0.000000000 | P02-v2:11 | P02-v3:11 | AVAILABLE |
| 21 | measurement_point:V0:A04 | 0.051055724 | 0.115056223 | 0.103308193 | 0.000000000 | P02-v2:12 | P02-v3:12 | AVAILABLE |
| 22 | measurement_point:EXTERNAL:LC01 | 0.071591145 | 0.269088626 | 0.288510786 | 0.000000000 | P02-v2:13 | P02-v3:13 | AVAILABLE |
| 23 | measurement_point:EXTERNAL:EXT05C | 0.083256880 | 0.277469246 | 0.284913718 | 0.000000000 | P02-v2:14 | P02-v3:14 | AVAILABLE |
| 24 | imu_handling:F03:v2 | -0.012006276 | 0.011554055 | 0.017496869 | 0.214991595 | P03-v2:7 | P03-v2:15 | AVAILABLE |
| 25 | accel_scale:F03:v2 | -0.000529776 | 0.047505058 | 0.051722402 | -0.010650116 | P03-v2:7 | P03-v2:17 | AVAILABLE |
| 26 | combined_imu_handling_and_scale:F03:v2 | -0.012800993 | 0.062412745 | 0.073949469 | 0.214745767 | P03-v2:7 | P03-v2:19 | AVAILABLE |
| 27 | imu_handling:A04:v2 | -0.012041330 | 0.011492352 | 0.017435765 | 0.192346480 | P03-v2:8 | P03-v2:16 | AVAILABLE |
| 28 | accel_scale:A04:v2 | -0.000527571 | 0.047504952 | 0.051710507 | -0.011999445 | P03-v2:8 | P03-v2:18 | AVAILABLE |
| 29 | combined_imu_handling_and_scale:A04:v2 | -0.012834344 | 0.062338806 | 0.073861051 | 0.189199918 | P03-v2:8 | P03-v2:20 | AVAILABLE |
| 30 | F01_upper:V2F01-EXT05C:v2 | 0.024097556 | 0.146892699 | 0.150013279 | -4.162255280 | P03-v2:6 | P03-v2:14 | AVAILABLE |
| 31 | imu_handling:F03:v3 | 0.003385453 | 0.044889367 | 0.047516180 | 0.214991595 | P03-v3:7 | P03-v3:15 | AVAILABLE |
| 32 | accel_scale:F03:v3 | -0.001250841 | 0.023310458 | 0.025907368 | -0.010650116 | P03-v3:7 | P03-v3:17 | AVAILABLE |
| 33 | combined_imu_handling_and_scale:F03:v3 | 0.002205278 | 0.076048110 | 0.082934853 | 0.214745767 | P03-v3:7 | P03-v3:19 | AVAILABLE |
| 34 | imu_handling:A04:v3 | 0.003345610 | 0.044785819 | 0.047406217 | 0.192346480 | P03-v3:8 | P03-v3:16 | AVAILABLE |
| 35 | accel_scale:A04:v3 | -0.001249090 | 0.023321102 | 0.025908371 | -0.011999445 | P03-v3:8 | P03-v3:18 | AVAILABLE |
| 36 | combined_imu_handling_and_scale:A04:v3 | 0.002166036 | 0.075940999 | 0.082803068 | 0.189199918 | P03-v3:8 | P03-v3:20 | AVAILABLE |
| 37 | F01_upper:V2F01-EXT05C:v3 | 0.062082933 | 0.266642328 | 0.282920159 | -4.162255280 | P03-v3:6 | P03-v3:14 | AVAILABLE |
| 38 | residual:preregistered_V2isA04-EXT05C:v3 | 0.049228878 | 0.186421734 | 0.200016208 | -10.325620926 | P03-v3:20 | P03-v3:14 | AVAILABLE |

来源：`<CLEAN_ROOT>/stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/10_IMU_PROCESSING/08_AGGREGATE/PARITY_DECOMPOSITION.csv`。P-02 estimator(V2e−EXT05C)与V2e measurement-point项因原生失败保持UNAVAILABLE。

## E. 交付身份

| 项 | 身份/状态 |
| --- | --- |
| 起点 | 8d47753d612eee3ab5c205b537cc7224c4e49829 |
| 合约v3+代码提交 | a95141e9edd4eacd62a50c2bfed6cb78c83791b8 |
| 执行快照 | clean5-imu-parity-a95141e9edd4（与工作树同级）；detached、未修改/构建/提交 |
| 预执行测试 | 38 passed, 1 skipped；单独启用原跳过的exact-evaluator测试后6 passed（5项重叠）；合计39个不同测试通过 |
| P03_TERMINAL SHA-256 | 0b24f681557b049ab72c4e2af7962b3311f8b23e4de0747f31aac1a5efdf6d32 |
| P03最终评估摘要SHA-256 | d82fe2c515b22289fec5a1ac6bd58bb291da9a582e7cfa4fa2dd2761e2970b15 |
| P03输出封存SHA-256 | 7279e7295b2db9b085deeb293b706cc9f6218fb0f03c9a3a68e84ad1ad3f7277 |
| P-02参考摘要SHA-256 | 7ad4294999bdb7b3668bb7cd59869f49a42fb0d840f76b83c94b0704aee64d75 |
| 结果记录提交 | 本文件所属 docs(clean5): IMU parity results and decomposition record 提交；完整提交hash见交付回执P03_DELIVERY.json |

结果根为 `<CLEAN_ROOT>/stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/10_IMU_PROCESSING`。`08_AGGREGATE/` 与其 `v3/` 保留P-02同结构结果表，并各有BODY_FRAME_BIAS.csv；完整A/B逐帧和滑窗证据在00_AUDITS。所有运行产物未加入Git。主证据链、原P-02结果、raw、C++、可执行文件和评估器身份保持。
