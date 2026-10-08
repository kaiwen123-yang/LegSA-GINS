# M2 完整 BY 一次性收尾

实际状态：`NAVIGATION_PROCESS_EXITED_WITHOUT_TERMINAL_RECEIPT`；原导航：`PROCESS_EXITED_WITHOUT_TERMINAL_RECEIPT`。

仅收尾既有 FULL09（66–340 秒，b5adc7a）；未启动新导航、改参数、重试或读取测试集。原始失败/中断不改写为完成。

位置/航向使用已存误差序列在 M2、FULL07、冻结 V3 三者共同有限域上计算；速度由冻结评估器同时输入三者。不同有限覆盖保留，NO_INIT 不计零误差。

这些是实测完整输出的读数，不能单凭本次结果宣称正式 AR、独立真值验证或航向改善导致速度收益。M2 与旧 FULL07 源码不同，不是纯噪声消融；载波与足约束虽进入共同状态，足式增量、失效撤销及稳定导航收益仍需各自证据。

M2 的 τ=2 是预声明工作域边界模型，概率校准未完成。结果不触发再调参。冻结 V3 不修改。

全部源/输出/评估哈希、覆盖与真实评价终态见 [JSON](BY_M2_FULL_NAVIGATION_RESULT.json)。当前暂停，后续方案须经用户新的明确继续指令，见 [停止边界](USER_REVIEW_STOP.md)。
