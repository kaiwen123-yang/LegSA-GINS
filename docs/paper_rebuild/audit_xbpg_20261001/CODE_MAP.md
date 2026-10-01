# 代码图谱、计数边界与阅读入口

图谱以 `eb3cbed314693358c7c38442b6fbbb7afcf0342e` Git树及原worktree的28个未跟踪代码/配置为底，实际逐文件语义状态见 CODE_REVIEW_COVERAGE.csv。初始清单3,085文件/552,271行；后续发现suffix筛选漏掉25个configs CSV注册表和9个自有.diff/.patch文本，**只追加34文件/1,862行UNREAD**，形成3,119文件/554,133行修订分母。INVENTORY_SCOPE_ADDENDUM.csv记录每项身份及理由；追加程序验证原3,085行所有字段完全保留。后续语义receipt再作有据增量更新，不重新跑inventory。

物理行含注释、空行、配置和测试，不是有效SLOC。CSV结果、JSON运行记录、图/压缩包/文稿不是可执行代码，不计此分母；按路径识别的配置/schema、源码中的生成器及历史自有脚本仍计入。补丁是自有代码/配置变更的审查对象，不表示已应用到正式树。同内容但不同路径各保留，不能用同名或重复blob代替调用身份。未跟踪脚本只有身份/已实际读取的语义范围，原文件未复制到审查分支。

后缀复核还检查了 c/cc/cxx/h/hpp/py/pyi/sh/ps1/js/ts/m/f/ipynb/cmake/proto/lua/r/rs/go/bat 及 CMakeLists/Makefile/Dockerfile，在基线已跟踪路径中没有发现额外遗漏。该检查是枚举证据，不把任何文件升级为语义已审。ignored构建生成文件、外部源码和本轮新审查代码分别用构建/方法身份及 NEW_AUDIT_CODE_COVERAGE.csv关联；不假称已枚举用户所有磁盘上未知脚本。

## 调用与身份层次

|代码组|实际角色和调用边界|审查解释入口|
|---|---|---|
|cpp/legsa_v23_port_core|正式port target和当前B3可选实现；config→loader→21维engine→观测→NAV/STD，当前源码与正式保留binary分开|NATIVE_REVIEW.md、NATIVE_COVERAGE.csv、METHOD_IDENTITY.csv|
|cpp/src、cpp/include、cpp/legsa_v23_core|另两套自有target/简化滤波和旧core；同名rotation/Matrix/engine不共享数值身份|NATIVE_OTHER_REVIEW.md、NATIVE_OTHER_COVERAGE.csv；已隔离构建，不作为正式F04|
|input_generation、raw_gnss、frames、time_alignment|输入解码、物理转换、Doppler helper生成、时间与provider边界；不同调用者的旧LS和正式native RD需区分|PYTHON_INPUT_REVIEW.md、RAW_GNSS_REVIEW.md、SHARED_SENSOR_REVIEW.md|
|paper_rebuild/clean6_sensor_v21、protocol_v3|正式providers、控制器、runtime、registry、评价捕获、聚合/图；v3仅主heading替换不等于HV同步换源|PYTHON_INPUT_REVIEW.md、PYTHON_EVALUATION_REVIEW.md、FORMAL_CONTROL_REVIEW.md|
|paper_rebuild路径/manifest/methods/subprocess_guard|local config、早期方法合约、源hash、进程组timeout；部分是CLEAN0/CLEAN1专用，不能冒充当前全协议校验|CONTRACT_REVIEW.md|
|paper_rebuild/hext、horizontal_literature|自有外部驱动/适配/后端；已有移植、early官方回归与目标完整论文复现分开|PYTHON_EVALUATION_REVIEW.md、NATIVE_EXTERNAL_REVIEW.md；其余明确未审|
|paper_rebuild其它控制器、scripts、tests、configs|生成/执行/评价/归档/绘图/合约大量未完成，历史标签不豁免；不调用legacy runner进行新正式运行|REMAINING_REVIEW_QUEUE.csv及逐文件UNREAD/PARTIAL|
|本轮四个audit专用目录|解析88个输入、真实GNSS-only运行、输出校验、合成反例、汇总和图；全部新增，不覆盖以上实现|NEW_AUDIT_CODE_COVERAGE.csv、TEST_RECEIPTS.json、RUNS.csv|

完整正式端到端图和方法开关见 CODE_AUDIT_REPORT.md。模块已读不等于所有历史providers的raw lineage/未跟踪动态导入彻底闭合。外部参考评价器421行另列完整阅读，它不在当前Git分母。

## 重复与第三方

初始库存明确发现两对同blob的自有脚本：

- `docs/paper_rebuild/hext/HX02D/00_CONTROL/INITIAL_DIAGNOSTIC_SOURCES/hx02d_execute.py` 与 `scripts/paper_rebuild/hx02d_execute.py`。
- 同目录 `hx02d_reference_evaluation.py` 与 `src/legsa_gins/paper_rebuild/hext/hx02d_reference_evaluation.py`。

追加补丁有档案副本；其身份由逐文件Git blob保留，不能由多数副本投票认正式版本。三套C++中同名函数属于不同namespace/target，OTHER审查已有不同矩阵/调度反例，不能将一套测试通过推广到另一套。

`reference/final_v23_repo` gitlink为 `5a4471efd4fcfcdc31e258a677af354c652ff16f`，隔离worktree未初始化。RTKLIB本机commit及binary、GINav本机commit/tree已分别核查并记录，但本轮仅审实际依赖的调用/编译/解码/配置片段，**没有逐行审整个第三方库、编译器、Eigen/OpenSSL**。Hartley official driver的include/链接来源在其自身文件中不能唯一确定，保持UNVERIFIED；自有InEKF源完整读过也不升级三篇完整复现为完成。

附加全文语义阅读：Hartley目录的CMakeLists.txt共30行。1–9要求C++17、Eigen3.3配置包和OpenSSL，但不锁实际安装库版本；11–14仅编译backend静态库并公开Eigen/include，warning flags仅库自身；16–26建立两个测试、validator和H5 runner（Crypto只链接后者）；28–30仅将两个测试注册CTest，validator和官方early regression/driver不在CTest。未在本轮构建/运行这些外部目标。根代理独立receipt计入这30行，未假称外部编译动态通过。
