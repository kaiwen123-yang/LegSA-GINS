# 密集机会前端差分只读审查

当前 integration_frontend.py / latency_tracking_frontend.py 差分及新增测试
未发现阻止1191窗口试验的实质问题。未修改冻结源码，未执行真实求解。

- timed_search_call 的 finally 捕获实际调用耗时，即使求解抛出异常。
  正常返回仍保留内层certificate耗时，不覆盖或用外层耗时替代。
- recorded_service_cost 在certificate存在时严格采用certificate.elapsed_s；
  无效字段直接拒绝，不能偷偷以attempt timer兜底。仅无certificate的
  已尝试失败使用正的实测whole-call timer；缺失、NaN、负值、bool拒绝。
- 显式未进入求解的presearch_unavailable，才记0 CILS工作；保持invalid，
  不构造pending result，不占虚构求解时间。准备/I/O本来就是理想化模型
  未收费项，文档已明说。busy-drop优先级对这种机会也相同。
- 有效measurements必须有真global certificate；未cert或失败结果只能
  作为付出算时但不可用的返回，不能生成可信测量。
- cadence由原selected_at差值推导；round只用于摘要，不改原时刻。
  格式化起点碰撞检查防止两个窗口覆盖同一JSON身份。
- selected_windows与acquisition_schedule仍各取[start,start+2)内10点。
  独立读取V2 PLAN时间metadata核得1191个唯一机会，每窗均恰10点，
  前5选择后5验证；首100.198..101.998，末338.198..339.998。
  selected_at间隔为0.1999998093..0.2000000477秒；没有缩短窗口。

新增测试覆盖timer异常、presearch无假timer、certificate优先级、坏字段
不得回退、busy-drop、pending与cadence元数据。此次仅审查测试内容，
没有声称重跑这些已由root执行的测试。

common120比较脚本已准备，只有DENSE_SELECTED_COMPLETE.json存在并为
COMPLETE时才读取最终总体；不导入生产算法，不调用CILS/验收/导航/参考。
