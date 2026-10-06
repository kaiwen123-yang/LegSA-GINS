# 固定六维上限导航控制计划

本轮已按父任务授权于源码冻结 c25a48ed4ddf2ac8748f0a393dcbaa87cba85c3b 后建立持久控制器。只等待 PARTIAL6_COMPLETE.json / PARTIAL6_FAILED.json 终态，不在模型对话中轮询中间指标。

- 输入：PARTIAL6_TRACKING/CARRIER_TRACKED_PARTIAL.csv；全固定臂复用 TRACKING_V2/CARRIER_TRACKED_FULL.csv。两表均要求完整 1200 历元，100.198–339.998 s，后者全 invalid。
- 入口核查：来源文件 hash、原始模型 PLAN、partial max=6/min=4、120 个登记搜索窗、跟踪零 C-ILS/零参考读取；来源不符立即终止。
- 导航：NAVIGATION_PARTIAL6，完整 66–340 s，共同 body HV、同一 BUILD_BODY_HV 二进制与 P/RV/RD/RP 输入。四臂 C0 标量、C1 双位置向量、C2 全固定载波、C3 六维上限部分固定载波各运行一次。
- 全部四次 native 封存后，先核 C0/C1/C2 NAV/STD 与 TRACKING_V2 字节一致，再执行四次冻结离线评价。不因候选数量或指标省略任何臂；失败保留并停止，自动重试为零。
- 完整共同时间支持比较 V1、V2、TRACKING_V2 和 PARTIAL6，保留 66–340、66–100、100–340 三域 H/V/3D/yaw 与实际接纳计数。输出 PARTIAL6_NAVIGATION_ 前缀五份结果。
- 控制器没有新增 C-ILS、原始数据读取或在线参考读取。Fixposition 派生参考并非独立真值；连续跟踪历元不等于独立正确固定。

控制器：<CARRIER_SCRATCH>/NAVIGATION_DRIVER_PARTIAL6/driver.py。注册 SHA-256：f85a7800049dfe8284079f81c8f8809cf9853bd18e2a53891d993d9384df053c。运行日志 PROGRESS.log；终态 COMPLETE.json 或 FAILED.json。每个 prepare/native/evaluate/summarize 调用独立保存 argv、stdout、stderr 和返回码。控制器源码及注册保留在该目录；不修改在途科学源码。
