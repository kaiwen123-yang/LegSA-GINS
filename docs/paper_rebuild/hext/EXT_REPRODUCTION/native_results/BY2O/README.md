# BY2O 完整原生历史

三方法各处理全部2231对原始观测，3次方法×序列任务均正常终止，没有重试。原生表完整保留失败；尚不由此推断精度。

|方法|float阶段完成|搜索尝试|搜索完成/候选返回|有效输出|ratio-fixed|无输出|
|---|---:|---:|---:|---:|---:|---:|
|EXT01|1566|1566|1511|1511|NA|720|
|EXT02|NA|1566|1527|1527|NA|704|
|EXT03|493|493|493|493|7|1738|

来源NATIVE_SUMMARY.csv，以method为键。所有分母为2231，EXT01/02无接受检验，NA不是0%正确固定。EXT03其余486为float；ratio-fixed不证明真实整数。

EXT01共有55个SEARCH_TIMEOUT，使用运行前登记60 s/历元预算，未输出假固定，也未扩大预算/挑例补跑。其余93个CP有效位门、572个half-cycle门失败。1511个返回解带既有搜索证书，证书范围仅为对应模型和数值判据；不涵盖超时历元或真实整数正确性。

EXT02的39个NUMERICAL_FAILURE逐项见../../FAILURE_DETAIL.csv及FAILURE_EXPLANATION.md；其余输入门计数同上。EXT03的1049/675个GNSS1/GNSS2 SPP拒绝、8/6个GPS/BDS双频状态门不满足均保留；不把它们重标为KF数值发散。

完整HEADING表、RUN身份、原生输入/库访问核对均已保存。实际求解数据来自隔离inputs，不打开reference；详细模型/整数/协方差在<EXT_REPRO_ROOT>/runs/BY2O__<METHOD>__RAW_REPRO_V1/EPOCH_EVIDENCE.jsonl.gz。此批评价调用0，下一项使用冻结离线heading定义评价固定原窗[3186,3563] s。
