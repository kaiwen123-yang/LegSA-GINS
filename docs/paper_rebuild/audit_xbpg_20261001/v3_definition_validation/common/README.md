# 共同观察层：完整P的限定诊断

`covariance_diagnostics.hpp`是纯只读函数，检查完整矩阵、正对角、对角归一化对称性和无jitter的Cholesky诊断。固定阈值见上级定义文件；仅诊断副本作近似对称化，输入P和原checkCov/停止规则保持。每个分项有独立tested状态，不能把未执行分解算作通过。

本轮`test_covariance_diagnostics.cpp`编译为一个新的原生合成fixture进程，12场景包括完整21维SPD、跨400数量级的对角、相关项、非对角NaN、Inf、零对角、超限/限内非对称、正对角不定、秩亏和近奇异。12场景符合预期，输入矩阵逐字节不变。源码/二进制/命令绑定在`TEST_RECEIPT.json`，各场景完整结果在`TEST_CASES.json`；不是12次真实运行。

`install_observation.py`只写新候选隔离源：新增诊断header，在原newImuProcess的checkCov前插入只读hook，并加候选定义及实际innovation residual_vector输出。它不改变P、不调用第二次SA policy、不放宽科学停止条件，拒绝重复安装、保护根、路径逃逸和任何写路径中的symlink。原源码及上一阶段观察版不改。

只读planner审阅确认N12数学差异和本诊断无科学写回、阈值/未决分类正确。审阅提出的安装路径门与测试身份绑定已由主代理补齐；仅安装器边界改变，诊断header/test没有变化，不因此重复fixture。已经安装的N12三个目标另核无symlink、均在新隔离源内。后续各候选仍完成自己的新原生测试和最终source/binary登记。

实际调用：新合成fixture1，真实native0，evaluator/provider0，失败/重试0。该小项不提供真实P健康结论，也不宣告原实现全部协方差有效。
