# FGO 文献比较：固定选文

2026-10-03 用户补充固定以下三篇；不再增选。起点为 `d90bc6965fffb9a408915e414c2e9051c4538ba3`，`audit/code-xbpg-20260105-20261001`，工作区干净且起点远端相同。本轮新证据根 `<FGO_ROOT>`，本机映射在 ignored `configs/paper_rebuild/FGO_ROOTS.local.json`。

## 三篇及实现身份

| 方法 | 原文与包内版本 | 输入、状态和核心 | 选择理由及边界 |
|---|---|---|---|
| OISAM_2025 | Zhichao Yang, Xiangjie Ding, Ying Yang, Qi Wang. **OiSAM-FGO: an efficient factor graph optimization algorithm for GNSS/INS integrated navigation system**. Satellite Navigation 6:23 (2025), [DOI](https://doi.org/10.1186/s43020-025-00173-w). `s43020-025-00173-w.pdf`, 18页, SHA256 `1b3a9c79c0285cdf6f41e95b3c3215218bc202df9978376e6bb453c83d693a6e`. | GNSS位置/标准差、Go2 IMU；位置、四元数、速度、两种偏置；GNSS位置、IMU预积分、边缘化先验；结构化增量Givens及A-JSWR。 | 主要GNSS/INS导航对照；必需输入现存，机制独立。没有找到作者OiSAM代码，按原文独立实现；不能用普通iSAM2替代。 |
| WEN_TC_2021 | Weisong Wen, Tim Pfeifer, Xiwei Bai, Li-Ta Hsu. **Factor graph optimization for GNSS/INS integration: A comparison with the extended Kalman filter**. NAVIGATION 68(2):315–331 (2021), [DOI](https://doi.org/10.1002/navi.421). `Factor graph optimization for GNSSINS integration A comparison with the extended Kalman filter.pdf`, 17页, SHA256 `7b94be96194b77b4d4ddc128f7b0df0729765299c789a747a47a79edb322273f`. | 固定TC支路：ECEF位置、速度、加计偏置、接收机钟偏；原始伪距、运动模型、外部AHRS/加速度的速度联系。 | 普通FGO定位对照；姿态是输入，不是图估计成绩。Go2本地yaw没有全球北向合同，必须通过合法传感器的一次初始定向建立AHRS坐标，披露适配；不能使用参考或V3轨迹。关键输入若无法成立则仅此方法标阻塞。 |
| GNC_2022 | Weisong Wen, Guohao Zhang, Li-Ta Hsu. **GNSS Outlier Mitigation via Graduated Non-Convexity Factor Graph Optimization**. IEEE TVT 71(1):297–310 (2022), [DOI](https://doi.org/10.1109/TVT.2021.3130909). `GNSS_Outlier_Mitigation_via_Graduated_Non-Convexity_Factor_Graph_Optimization.pdf`, 14页, SHA256 `7d13d97ccfb8b15d936f4c244579e220691fb252df3aa0f839d0bb33778dc11f`. | 原始伪距、Doppler和广播星历；伪距位置/钟偏因子、Doppler解算速度形成相邻位置约束、GM/GNC交替权重优化。 | 鲁棒GNSS位置层补充；无IMU或姿态因子，不补造姿态，也不保留没有因子约束的自由速度状态。 |

三篇全文由本轮主代理/文献代理完成阅读。OiSAM核看PDF p4、7、8、10、12；Wen2021核对p3–8、17状态/因子/坐标；GNC核看p3–6公式、因子图及Algorithm 1原页。全文及页图在 `<FGO_PAPER_CACHE>`；复用前轮成员索引，既有论文缓存原样保留，新提取件不上传。

## 必需输入及复用

- RAWX码、载波、Doppler、C/N0/状态及广播星历实际存在：`<EXT_REPRO_ROOT>/inputs/{BY2,BY2H,BY2O}/`，完整配对数1509/1483/2231。新伪距因子用GNSS1未差分码，不调用动基线双差整数模型。载波不为三主实现必需。
- GNSS1位置/STD为NAV-HPPOSECEF和同iTOW NAV-PVT hAcc/vAcc；不是商业融合轨迹。位置、速度、A1 yaw字段角色分别记录，速度/yaw不自动成为OiSAM额外因子。
- Go2体IMU及既有校准增量、Go2 quaternion/RPY现存。统一复用 `<CLEAN_ROOT>/stages/CLEAN5_CALIBRATED_SENSOR_MODEL/02_CALIBRATED_PROVIDERS/{SEQ}/CALIBRATED_{GNSS.gnss,IMU.imu}` 及bundle；已做FLU→FRD、安装和固定比例处理，不重复施加。含重力比力仍须正确加重力；本地Go2 yaw不能直接视为全球AHRS。
- 相机、激光、轮速、原始关节/接触因子不是所选三篇必需输入；本轮不建立这些链。
- 复用 `horizontal_literature/phase2_runner.py` 的只读RAWX缓存、`shared_raw_backend.py` 的广播星历/坐标/原始SPP初始化、`reproduction_backend.py` 的单次地球自转处理，以及既有时间、物理点、离线统计定义。新算法均在 `paper_rebuild/fgo_comparison/`，入口在 `scripts/paper_rebuild/`。
- 旧 `src/legsa_gins/fgo/` 从选定EKF的EVAL_NAV建状态并平滑，不符合这些文献，禁止复用为方法或初始轨迹。未发现同文、同输入、同评价身份的已完成运行。
- 作者 [GraphGNSSLib](https://github.com/weisongwen/GraphGNSSLib) 检查到提交 `d861802ce69de420b7d99f4becac44ed85be4c42`；README声明代码与论文不同，当前伪距/Doppler入口仅Huber/Cauchy/NULL，未提供GNC连续化。保留作者因子/权重约定依据，独立实现GNC；不宣称作者原程序复现。源码本地 `<FGO_BUILD>/author_GraphGNSSLib`，GPLv3。

## 原文设置和事前工程决定

- OiSAM：p3–4 Eq4–7、p6–10 Algorithm1、p11–12 Algorithm2；1Hz节点/当前输出，T1/T2=30/40节点，roll/pitch=3°、yaw=15°触发，重线性化最多20步。自行实现带状增量Givens缓存和A-JSWR；不把最终平滑状态回填历史输出。Algorithm2删至 `L<T1` 与正文T1有差异，按算法框并记录。尾部缓存须保留前缀消元影响，以增量解等于完整QR的小例核验。地球自转项按Eq4处理，库差异明确说明。
- Wen TC：p4–5 Eq3/10/13–16，p6–8 Eq20–32及Fig2；完整批处理为原文主比较模式，1Hz节点、原始伪距、位置运动/偏置演化及加速度速度联系，LM迭代求解；位置运动STD0.3m、偏置步进STD0.01m/s²、速度联系STD0.15m/s来自Eq22/27。AHRS仅输入；固定安装和已确认比例沿用，任何重力移除/杆臂运动适配明示。
- GNC：p3–6 Eq4–24和Algorithm1；WLS初始状态、初始权重1、cGM=2、theta按最大标准化残差初始化并除1.4，全批处理，保留每轮权重/目标。Eq21的导数与Eq22未平方权重存在原文内部冲突；实现遵循Algorithm1指向的Eq21/GM目标（权重为分式平方），明确列出推导并做驻点/异常观测测试，不能默默用另一损失函数。
- 原文没有公开的数值容差、缺测规则和Go2噪声转换，在首次主运行前写入固定配置/REPRODUCTION_NOTES；三序列一致，不读参考调参。初始姿态如需绝对yaw，仅用首次合法A1观测一次；无连续双天线/HV/RP附加因子。姿态输入与姿态估计分开。
- GNSS-only输出物理点是GNSS1天线，离线将reference由已确认POI天线中点按 `[0,b/2,0]` FRD投影到GNSS1，使用reference自身姿态；算法输出不动。OiSAM沿用IMU→POI v3转换。旧V3保留原评价点和原指标，不能冒称同输入层或同点NAV身份。

## 队列、其他候选及结束边界

| 序列 | base_time (Unix s) | 评价窗（相对秒） |
|---|---:|---:|
| BY2 | 1772784000 | 66–340 |
| BY2H | 1772784000 | 413–683 |
| BY2O | 1772780400 | 3186–3563 |

只登记上述3方法×3自然序列=9组合；保留各自合法窗前历史。共同退化清单为 `[]`：已知小子集主要改成品provider，不能代表相同RAWX故障；不新建故障矩阵。

`2109.00667v1`是GNC预印本，不另计；`1712.05873v2`是Hartley正运动学/接触预积分FGO，不能用高层足端位置代替原始编码器链；`2106.01594v1`是GNSS/RTK相关FGO，不追加第四篇，也不新增基站或载波研究。

V3、EXT01–03、RTKLIB、LC01等仅按既有索引读取留存结果。每方法实现/必要测试、每序列结果、最终图表分别提交推送并核远端；失败和未输出保留分母。所有新运行、评价、连续图及限制说明完成后结束实验扩展，交付写作入口，无新包、算法、数据集或校准研究。
