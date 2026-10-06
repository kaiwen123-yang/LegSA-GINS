# READY 07：三篇FGO位置曲线、原分母及严格/分段身份

三个R15显示各序列GNSS1天线点上的全部保存primary动态H误差和signed-Up误差。H用log轴、Up用symlog（±0.1m内线性），只改善不同量级可读性，没有裁剪、选支持、重算指标。原ERRORS列副本包含全部invalid/prior-only行；画线仅采用已登记primary有效行，不跨缺口或Oi block reset。

OiSAM的输入是RTK位置＋IMU；Wen TC是raw code＋AHRS/IMU；GNC是raw code＋Doppler。物理点相同不消除传感器层和信息窗差别，不能做同输入求解器排名。Oi自行估计的姿态用于lever点运输，未借用参考姿态。参考也不是独立真值。Wen/GNC没有姿态成绩。

R16保留原full-window分母275/271/378及全部九组合；primary Oi支持275/267/370，prior-inclusive secondary275/269/376独立标灰。旧严格一次init Oi 275/0/55来自旧已封总表且原身份保留，不混成新全窗成功成绩。新Oi依固定真实连续块1/3/7调用，共11初始化；六Wen/GNC身份明确复用。3286s原生迭代上限未收敛但usable的状态在O曲线显式标注，不伪称收敛或删掉。

只读ALL_OFFLINE_COMPLETE的逐输出SHA准入每个METRICS/ERRORS；旧strict表也核原SHA。data/保存完整原decimal列副本及36个已保存OWN/COMMON×PRIMARY/SECONDARY指标，不重新评分、不打开rawreference或调用science。最终4PNG均实际打开，全部范围、图例、有效支持、非收敛标记可读。300dpi PNG、PDF、SVG同Figure导出，未另渲染PDF。
