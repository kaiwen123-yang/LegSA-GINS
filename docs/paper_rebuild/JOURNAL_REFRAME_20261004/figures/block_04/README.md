# READY 04：动基线误差与实际覆盖一起看

4张宽图，均300dpi PNG/PDF/SVG。三个R09各保留一个序列全部原paired历元，四个预定条件的native-valid heading误差和真正有效的时刻同时展示。没有连接缺测、保持旧解或删除大误差。每条件的n/N与原保存RMSE在图例中明确。

R10展示全部12条件的有效解RMSE及原paired历元覆盖率；灰叉只表示原保存hold-last诊断，它的支持与native-valid不同。V0、V0E、V1、V2是原条件、仅星历修改、扩展星座、fix-and-hold四个工程条件，不是四篇方法。未择优取一个条件代表方法。

原分母为BY2 1370、BY2H 1350、BY2O 1885。native Q1固定解标志不能证明整数模糊度正确。水平基线投影角与Euler参考航向的定义差别保留，不用于同输入算法排名。数据来自原已封存HX07R误差CSV和指标JSON；没有读取原reference或调用求解/评价。

data/保存每个误差CSV的完整列副本及12条件指标；BUILD_RECEIPT逐一绑定24个原文件与全部导出hash。汇总CSV是12份已保存指标的转录，全部来源列在同一receipt中。最终4PNG均实际打开，坐标、标签、图例、全部范围和脚注可读；PDF/SVG同一Figure导出，没有另外渲染PDF。
