# 固定 BY2 80–82 s raw 元数据审计合同

状态 PREPARED，审计记录尚未读取。根代理提交本合同后执行。

- 唯一分析窗口：BY2 相对 base_time=1772784000 的 [80,82] s，闭区间。不得扩窗、插值、重新配对时标或按估计角度选择。
- 来源：原 hash 锁的双接收机 RAW CSV 对应既有 UBX 重建字节流，使用其已登记原始来源与 UBX hashes；重新核 hash、UBX校验和及原始GPS week/tow。用原始两端时间独立配对，不以缓存重建时强制相等的时间当作新证明。完整文件读取只用于 hash/解帧，元数据统计仅限该窗。
- 字段：GPS week/tow、receiver_status、signal identity(gnss_id,sv_id,sig_id,freq_id)、PR/CP valid、halfCyc、subHalfCyc、locktime_ms、CNO、PR/CP不确定度状态。分开计两端、common、CP-valid、resolved-half-cycle及strict GPS L1 code/carrier eligible。
- 连续性：继承锁定 TrackingContinuity 规则，同时缺失/重现与相邻间隔>0.21s结束连续支持；锁计数回退、half-cycle/subHalfCyc变化、CP有效性变化、clock reset全部记录。窗口首样本为左删失，不声称其之前连续。
- 输出：逐历元配对/有效数量；同窗全部 constellation/signal 原始键分组数量；GPS L1逐信号事件与可延续的连续公共集合；候选固定pivot只按identity排序作元数据可行性说明，不冒称已有最高仰角pivot或实际几何资格。至少4颗连续公共严格有效GPS L1才记“存在候选弧输入”，缺少仰角/几何与整数验收仍单独标未检验。
- 保留所有缺失、重复时间、未配对、失效与短弧；只在固定窗内部报告可能子段，不择优冒充全窗。
- 禁止 SPP、C-ILS、导航、参考/旧估计输出、角度误差、噪声调参或科学算法比较。预算：两份UBX及其已登记raw源只读，单次元数据审计，失败保留不扩展。
- 新脚本/回执记录 source hashes、实际读取/配对计数、窗口与执行commit；输出新 <TIM_AR_SCRATCH>/RAW_ARC_80_82，不覆盖旧数据。代码和审计小表随结果提交。
