# Loader 首次跟踪工具冲突：有界修复登记

82e56f0 的prepare成功生成921块1842端点，所有身份门通过。随后root外层strace -f与loader runner内层strace -f竞争跟踪，内层报PTRACE_TRACEME Operation not permitted并在编译器启动前退出。外层日志无g++、cc1plus、as、collect2或ld exec；checker文件未生成。应记1次编译包装尝试、实际compiler0、loader/parser/native/evaluator0，不是C++编译失败。fusion只读独立核实了该根因。

本次不重跑prepare，不改生产源、库、配置、CSV或manifest；复用82e56f0封存PREPARED。新登记仅将loader输出改为独占LOADER_CHECK_REPAIR01子目录，并将原LOADER_CHECK与外层失败证据加前后hash白名单。旧失败目录及所有原文件完整保留。固定预算仍实际编译1、loader3、生产CSVparser3，无自动重试、无完整导航。

外层只跟踪Python父进程（不加-f），记录父进程对source/plan/metadata的读取；实际compiler/loader仅由各自已有内层strace -f -yy跟踪。非科学Git身份验证子进程不在外层跟随范围，不能据父trace称覆盖所有子进程。编译与三个loader的实际I/O分别由内层完整trace审计。

先前失败不是自动审批拒绝或要求扩大权限；问题是同一个进程不能同时由这两层ptrace跟踪。本修复不修改系统权限或禁用子进程访问审计。
