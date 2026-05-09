#pragma once

#include "legsa_v23_core/config/gins_options.hpp"
#include "legsa_v23_core/state/filter_state.hpp"
#include "legsa_v23_core/state/nav_state.hpp"

#include <string>

namespace legsa_v23_core {

// 中文说明：运行期诊断开关只用于 N4H4D1 isolation，不是性能配置，也不进入常规 parity claim。
struct RuntimeDiagnosticOptions {
  std::string debug_output_dir;
  int debug_max_updates = 30;
  int debug_max_rows = 100000;
  bool debug_full_update_trace = false;
  bool debug_full_state_trace = false;
  bool debug_measurement_matrix_trace = false;
  bool debug_gain_trace = false;
  bool debug_update_blocks = false;
  bool debug_feedback_delta = false;
  bool debug_covariance_gain = false;
  bool disable_position_update = false;
  bool disable_velocity_update = false;
  bool disable_yaw_update = false;
  bool disable_measurement_update = false;
  bool disable_state_feedback = false;
  std::string diagnostic_run_label;
  std::string diagnostic_model_variant = "baseline_current";
  std::string diagnostic_feedback_mode = "normal";
  std::string diagnostic_update_block_mode = "all";
  std::string diagnostic_covariance_mode = "normal";
};

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
  static void runFromConfig(const std::string& config_path, const std::string& output_dir_override = "",
                            const RuntimeDiagnosticOptions& diagnostic_options = RuntimeDiagnosticOptions{});

 private:
  // 中文说明：写四类运行输出；输出只表示 N4H4A 框架链路成功。
  static void writeOutputs(const std::string& output_dir, const GINSOptions& options, double time,
                           const NavState& nav_state, const FilterState& filter_state);
};

}  // namespace legsa_v23_core
