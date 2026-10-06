# RV归因纠正：F02/F03是联合结构对比

结论：原F02→F03同时改变接收机速度更新与航向处理，不能称“RV单开关”“独立RV对照”，不能把曲线差值归因于RV。本次只修PPT资源的解释与图中文字，未重跑任何求解或评价，原V3科学结果和9份绘图data副本字节保持。此前绘图脚本只看显式enable开关，把algorithm_id误当运行元数据；这个解释错误现已纠正。

## 实际运行证据

封存根：`/mnt/g/LegSA-GINS-project/clean_rebuild_202607/stages/CLEAN8_PROTOCOL_V3/03_NATIVE/`。下表每个目录内读取`V3_RUNTIME_CONFIG.yaml`与`RUN_MANIFEST.json`，完整SHA及路径在RV_CONFOUNDING_EVIDENCE.json；并读取现存RUN_STARTED元数据，没有打开rawreference。

|序列|F02目录|F03目录|F02 RV更新|F03 RV更新|F02 yaw 正常/降权/拒绝|F03 yaw 正常/降权/拒绝|
|---|---|---|---:|---:|---|---|
|BY2|RUN_00002|RUN_00003|0|1369|1369/0/0|1285/63/21|
|BY2H|V3R_CONTINUATION/SEQUENCE_BY2H_F02|V3R_CONTINUATION/SEQUENCE_BY2H_F03|0|1349|1349/0/0|1287/47/15|
|BY2O|V3R_CONTINUATION/SEQUENCE_BY2O_F02|V3R_CONTINUATION/SEQUENCE_BY2O_F03|0|1882|1591/0/0|1506/80/5|

六份manifest均L75为enable_basic_dual_yaw_baseline，L77为basic_dual_yaw_fixed_std_deg，L324为yaw_scheme_C_enabled，L336为receiver_velocity_update_count，L349–351为yaw_NORMAL/DOWNWEIGHT/REJECT。F02 basic=true、Scheme-C=false；F03 basic=false、Scheme-C=true。L73更新顺序亦不同：F02 position→basic yaw→feedback；F03 position→yaw→receiver velocity→feedback。

**实际F02固定航向标准差为2.933193°**：BY2 config L55、H/O config L56及全部manifest L77一致。current full_method_registry.py L28–31明确F02 scheme_c=False/RV=False、F03 scheme_c=True/RV=True，但L62–64的注册表固定1.5°约定不能当作这些历史运行的实际值。此处报告登记与实际运行的区别，不改历史注册、配置或指标。

当前CPP `src/config/port_config_loader.cpp` L453–454由algorithm_id计算basic与Scheme-C启用；`src/kf_gins/gi_engine.cpp` L382–390为basic直接分支，L1042–1057为固定std直接航向更新。另只读旧ca73cb1fb48a020fd2a450d79e520562c34eeb24源码核对：loader L420–421同样路由，engine L367–373 basic分支，L931–946 Scheme-C按观测std与残差决定拒绝/降权，L978–993 basic使用固定std而无这些门。其blob内容SHA保存在证据JSON。历史manifest的source_commit旧字段与启动/冻结身份各按原样保存，不以该字段反推精确运行binary源码；本结论由实际manifest、config与实际计数共同支持。

## 最小PPT修正文案

- 第68页：“RV单开关”改“F02/F03联合结构对比；RD/HV配对消融”。F02/F03不能作为RV独立信息增量的证据。
- 第88页F02：“RV关闭；固定2.933193°航向权重直接更新”。
- 第88页F03：“RV开启；Scheme-C航向质量/残差处理；无RD/RP/HV/来源膨胀”。
- 配套图标题：“速度与航向处理联合结构对比”；说明：“两者同时改变，差值不能分离归因于RV”。

此次没有改deck builder（由根负责），只修自己拥有的figures内容。

## 资源修订范围与保持项

block05三个R11的标题、图例、RMSE标签、解释和BUILD元数据已改为联合结构对比；CONFIG_DIFF_EVIDENCE保留原逐行diff并补有效路由、六manifest身份与实际计数。原`receiver_velocity_toggle`文件名继续作为已接入PPT的资源定位符，不能再解读为单因素身份；六行指标副本仍按真实F02/F03标识，不改值或列。

block05 README、总README、build_figure_catalog.py章节名以及FIGURE_CATALOG/目录收据同步纠正。其余七个图块源码、导出、READY均不改；其RD/HV/RP/来源膨胀消融不替换成RV归因。全figures当前文本检索未见其它未纠正的pureRV/单开关肯定声明（旧before历史证据刻意保留原错误标签）。

原9个data/*.csv.gz的compressed SHA全部与before完全相同；原BUILD绑定的全部16个源文件与原SHA相同。4张最终PNG本次重新实际打开，3个R11可见显式非单因素说明，曲线全窗、原分母与不利BY2O yaw结果保留。R12的PNG/PDF字节与原版本相同；SVG重新序列化后hash有变化，数据与图文内容未变。PDF/SVG同Figure导出，本次没有另做PDF渲染。

旧图块/目录收据身份、旧标签与所有原文件hash保存在RV_CONFOUNDING_CORRECTION_BEFORE.json；新READY另含superseded身份，不伪称原验收已正确。RV_CONFOUNDING_CORRECTION_READY.json列出精确变动。无需新实验即可撤回过强因果解释；若将来要识别RV独立效应，需要另有保持航向分支不变的事前登记配对运行，本次不启动。
