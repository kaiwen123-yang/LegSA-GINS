# READY 05：速度与航向处理联合结构对比、真实航向接受状态

三个R11保留原F02/F03全部水平误差和yaw误差曲线，不能识别接收机速度RV的独立因果效应。F02为RV关闭、固定2.933193°航向标准差直接更新；F03同时启用RV以及依据观测精度与残差进行接受、降权、拒绝的Scheme-C航向处理。`algorithm_id`是实际路由分支，不能归为普通运行标签。六份封存native manifest均证实这些差异；CONFIG_DIFF_EVIDENCE保留逐行配置差异并补实际分支和计数。

两配置保留共同dual-heading初始化。图中RMSE只转录原汇总，不重算评价；各序列的不利变化照报，但不归因于单独RV。matched/output仅表示原观察输出历元，不代替物理全时域覆盖。历史文件名中的`receiver_velocity_toggle`仅作为既有PPT资源定位符，不再表示单变量实验。

R12原图与数据内容保留：原BY2 Proposed完整yaw误差和全部1369条native事件为NORMAL1225、DOWNWEIGHT123、REJECT21。这是算法接受状态，不是真值质量标签；同轴观察不是因果收益。原trace的yaw residual字段全空，没有重建创新曲线或门限。

只修解释、图内文字、图例和元数据，原9份data副本字节与所有原科学源hash保持；300dpi PNG/PDF/SVG重新导出。完整样本保留，>.1s断线，未平滑、求解、评价或读取rawreference。最终PNG重新实际打开；PDF/SVG由同Figure导出，本小块未另渲染。旧验收身份保存在上级RV_CONFOUNDING_CORRECTION_BEFORE.json，新纠正收据独立绑定。
