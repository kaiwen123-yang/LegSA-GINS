# RAWX 频率重新获取：十一版本导航比较

本轮新增两变体、8 次 native 与 8 次冻结离线评价。每个变体四个 native 全部封存并通过控制检查后才评价；此前九版本的 36 条链只读复用。十一版本、44 条链使用相同完整时间支持，不按载波成功时刻筛选。名义窗口 66–340 s，实际输出 66.005054–339.997056 s；结束时刻由输入清单的最后 IMU 样本确定。

DENSE_SELECTED 在原 1200 个 RAWX 历元上登记 1191 个重叠两秒窗，每窗仍为五个选择和五个未来验证历元，只将机会间隔从 2 s 改为 0.2 s。采用预选观测似然及已核对的 native 球面内核，cap 6/min 4、观测协方差、门限和导航链固定。此处列出的当前开发变体 DENSE_SELECTED_SERIAL 表示本轮含耗时的登记变体，不按评价指标选优，也不表示生产固定验收。

| 主对照/变体 | 含义 | H RMSE (m) | V RMSE (m) | yaw RMSE (deg) | 最大绝对 yaw (deg) | valid | native 接纳 |
|---|---|---:|---:|---:|---:|---:|---:|
| C1 双位置向量 | 所有新变体共同、字节一致 | 0.098646 | 0.048823 | 1.620834 | 8.018893 | NA | 1302 |
| SELECTED_LIKELIHOOD_TRACKING / C3 | 原 2 s 机会；Python；不计搜索延迟 | 0.100087 | 0.048783 | 2.036194 | 7.205476 | 62 | 60 |
| SELECTED_LIKELIHOOD_SERIAL / C3 | 原 2 s 机会；Python；计自身记录搜索耗时 | 0.100087 | 0.048783 | 2.036194 | 7.205476 | 62 | 60 |
| DENSE_SELECTED_TRACKING / C3 | RAWX 5 Hz 机会；native kernel；不计搜索延迟 | 0.098965 | 0.048794 | 1.937270 | 7.993303 | 157 | 145 |
| DENSE_SELECTED_SERIAL / C3 | RAWX 5 Hz 机会；native kernel；计自身记录搜索耗时 | 0.098965 | 0.048794 | 1.937270 | 7.993303 | 157 | 145 |

前端登记 1191 个窗口，实际 C-ILS 调用 1191 次；tracking 与 serial 复用同一批候选，不再搜索。本导航控制器新增 C-ILS 为 0。串行调度动作：{"SEARCH_LAUNCHED": 1172, "BUSY_DROP_NO_QUEUE": 19}；到达处理：{"ORIGINAL_RESULT_UNAVAILABLE": 961, "AVAILABLE_CURRENT_CANDIDATE": 55, "SUPPRESSED_OWNER_AT_ENTRY": 156}；窗口结束仍等待 0 个结果。显式无 C-ILS 的选择前不可用与真正搜索启动分别计数，忙时仍按原规则丢弃。

两新变体的 C0/C1/C2 NAV 与 STD 均和 PARTIAL6 对应控制字节一致。RESULTS 保留十一版本四臂三域（132 行）；RUN_COUNTS 保留 44 条链；DIFFERENCES 保留当前含耗时变体对其余十版本的三域差值（120 行）；NEW_C3_CONTRASTS 列出两新 C3 对原 selected-likelihood tracking、serial 和同变体 C1 的比较（18 行）。

SERIAL 使用本次每窗自身记录的证书耗时；无证书失败采用保存的正调用耗时，显式选择前失败记零 C-ILS 工作。单 worker busy-drop/noqueue，晚到结果逐历史历元追赶且只输出当前测量。TRACKING 不计搜索延迟。准备、验证、GLRT、追赶、tracking、IO、导航和资源争用成本仍计零，SERIAL 也不是硬件实时验证。原两秒机会使用 Python 内核，本轮使用已核对的 native 内核；串行差异不能全部归因为机会密度。

导航二进制、body HV、P/RV/RD/RP、初始化、评价器和噪声门固定。没有按参考误差筛选观测、选择候选或调整参数；参考是 Fixposition 派生结果，非独立真值。重叠窗口和连续历元共享原始观测与整数，不能把更多测试、认证或更新当成等数量独立正确固定或校准的全程错固定风险。
