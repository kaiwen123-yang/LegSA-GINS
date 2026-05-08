#pragma once

#include "legsa_v23_core/config/gins_options.hpp"
#include "legsa_v23_core/state/filter_state.hpp"
#include "legsa_v23_core/state/nav_state.hpp"

#include <string>

namespace legsa_v23_core {

// 中文说明：LegSA-v23-core runtime 负责 reader-engine-writer 串联，不实现完整 EKF 数学。
class LegSAV23Runtime {
 public:
  // 中文说明：运行 toy dry-run，生成 NAV/STD/EVAL_NAV/RUN_MANIFEST 骨架文件。
  static void runDryToy(const std::string& output_dir);

  // 中文说明：运行 N4H4B propagation toy，验证 mechanization + EKF predict 传播链路。
  static void runDryPropagationToy(const std::string& output_dir);

  // 中文说明：运行 N4H4C update toy，触发 position/velocity/yaw、EKFUpdate 和 stateFeedback。
  static void runDryUpdateToy(const std::string& output_dir);

  // 中文说明：从轻量配置读取 .imu/.gnss 并跑 LegSA-v23-core 链路；不读取 trace/final_v23 输出。
  static void runFromConfig(const std::string& config_path, const std::string& output_dir_override = "");

 private:
  // 中文说明：写四类运行输出；输出只表示 N4H4A 框架链路成功。
  static void writeOutputs(const std::string& output_dir, const GINSOptions& options, double time,
                           const NavState& nav_state, const FilterState& filter_state);
};

}  // namespace legsa_v23_core
