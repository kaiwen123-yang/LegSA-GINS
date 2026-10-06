# BY2 三方法完整原生结果

每个方法均处理1509个完整文件历史配对，包含窗前/窗后；本目录HEADING是完整精度原表副本，`RUN.json`记录源码、配置与输入pin。全窗评价另交付，不能从原生有效数断言精度。

|方法|有效/配对|其中自身ratio-fixed|失败|
|---|---:|---:|---:|
|EXT01|1077/1509|无接受检验|432|
|EXT02|1057/1509|无接受检验|452|
|EXT03|609/1509|78|900|

[原生摘要](NATIVE_SUMMARY.csv)、三个完整 `*_HEADING.csv`、[访问核对](ACCESS_AUDIT.json) 可直接读取。FIRST_MODEL_GEOMETRY仅取预定首个可构建模型，逐星列出从各自原始码推导的已知卫星时刻几何/钟项，不使用reference或挑选误差最好历元。完整EPOCH_EVIDENCE与各批openat日志留 `<EXT_REPRO_ROOT>/runs/`、`batches/BY2/`。此处0评价调用，3个method×sequence任务，Linux worker进程数和逐历元库调用不能混成这个数。
