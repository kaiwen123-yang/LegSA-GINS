# 完整似然加速与预选观测似然：九版本导航比较

前端两项试验各新增 120 次搜索，共 240 次，tracking/serial 只复用各自前端结果，不重复计为新搜索。本导航控制器新增 C-ILS 为 0。本轮实际新增 16 次 native 与 16 次冻结离线评价；每个变体四个 native 全部封存并通过控制检查后才评价。已有五版本的 20 次导航仅复用。九版本、36 条链均有共同的 56,642 个原始/STD/评价时间键；完整名义窗口 66–340 s，实际输出 66.005054–339.997056 s，未按载波成功时刻筛选。

本轮预先指定的当前开发变体是 SELECTED_LIKELIHOOD_SERIAL，不按下表指标选优，也不等于生产方法验收。NATIVE_FULL6 保留原完整观测似然及 nuisance 整数，只换可选球面内核；SELECTED_LIKELIHOOD 先选择观测支持再构造新的似然，属于不同模型，不能称为等价加速。

| 主对照/新变体 | 含义 | H RMSE (m) | V RMSE (m) | yaw RMSE (deg) | 最大绝对 yaw (deg) | valid | native 接纳 |
|---|---|---:|---:|---:|---:|---:|---:|
| C1 双位置向量 | 四新变体共同、字节一致 | 0.098646 | 0.048823 | 1.620834 | 8.018893 | NA | 1302 |
| NATIVE_FULL6_TRACKING / C3 | 原完整 likelihood + native kernel；不计搜索延迟 | 0.099972 | 0.048782 | 1.996090 | 7.275205 | 71 | 69 |
| NATIVE_FULL6_SERIAL / C3 | 原完整 likelihood + native kernel；计自身记录搜索耗时 | 0.101195 | 0.048793 | 2.282673 | 6.676239 | 26 | 25 |
| SELECTED_LIKELIHOOD_TRACKING / C3 | 预选观测 likelihood；Python；不计搜索延迟 | 0.100087 | 0.048783 | 2.036194 | 7.205476 | 62 | 60 |
| SELECTED_LIKELIHOOD_SERIAL / C3 | 预选观测 likelihood；Python；计自身记录搜索耗时 | 0.100087 | 0.048783 | 2.036194 | 7.205476 | 62 | 60 |

四个新变体的 C0/C1/C2 NAV 与 STD 均和 PARTIAL6 对应控制字节一致。全量 RESULTS 保留九版本四臂三域（108 行）；RUN_COUNTS 保留 36 条链；DIFFERENCES 保留当前开发变体对其余八版本的三域差值（96 行）；NEW_C3_CONTRASTS 列出四个新 C3 对 PARTIAL6、原串行 PARTIAL6 和同变体 C1 的比较（36 行）。

SERIAL 使用各自完整试验的原 certificate.elapsed_s，单 worker busy-drop/noqueue，晚到结果经逐历史历元追赶且仅输出当前测量。没有从少量基准外推运行费用。TRACKING 仍是不计计算延迟的回放；两类结果不能混称实时效果。准备、验证、GLRT、追赶、tracking、IO、导航和资源争用成本仍计零，SERIAL 也不是硬件实时验证。

本轮只改变登记的前端模型/计算实现与可用时间流，导航二进制、body HV、P/RV/RD/RP、初始化、评价器和噪声门固定。没有按参考误差筛选观测、选择候选或调整参数；评价参考是 Fixposition 派生结果，非独立真值。真实整数没有标签，连续历元共享整数，认证或更新数量不能解释为同数量的正确固定、校准完整性或泛化证据。
