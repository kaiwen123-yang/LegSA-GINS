# 本轮只读核验器准备记录

核验器第一次实际读取到已封FGO共同支持时，预设字段`COMMON_VALID`与原字段`COMMON_THREE_TIME_KEYS`不一致，抛出StopIteration，尚未写完成收据。按原字段修正读取，不改变任何科学数据。

第二次核验完成313个RMSE复算、零数值差异失败，但GINav旧审计JSON没有`passed/pass`字段，核验器因默认False记录三条schema读取失败。完整查看三旧JSON后，按真实`reference_open_count=0`、`old_runtime_input_count=0`及`undeclared_raw_paths=[]`进行准入。不是GINav产生了三个科学失败。最终收据以最终脚本SHA绑定。

BY2早期LC01/单接收机更新的native源准确定位到CLEAN4两方法共享batch的EXT05A_C00_NATIVE_SUMMARY；对应CLEAN5评价另身份，不能把汇总表当native receipt，也不能把评价commit冒充最早执行commit。

本核验器修订只影响审查工具；solver/evaluator/raw-reference调用均为0。现成保存误差复算是审查数值验证，不生成或替换科学轨迹/评价。
