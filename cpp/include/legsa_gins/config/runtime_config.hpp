// 中文说明：RuntimeConfig 是配置骨架；final_v23_is_proposed 与 proposed_reads_final_v23_output 必须保持 false，高级因子默认关闭。
// English note: comments define module responsibility and safety boundaries only.

#pragma once

#include <string>

namespace legsa_gins::config {

struct RuntimeConfig {
  std::string dataset_name = "dry_demo";
  std::string output_dir = "results/proposed/n3a_cpp_runtime";
  bool dry_run = true;
  std::string algorithm_role = "proposed";
  std::string algorithm_name = "LegSA-GINS-CPP-Runtime";
  bool final_v23_is_proposed = false;
  bool proposed_reads_final_v23_output = false;
  bool enable_receiver_position = true;
  bool enable_receiver_velocity = true;
  bool enable_receiver_heading = true;
  bool enable_raw_doppler = false;
  bool enable_go2_yawrate_prior = false;
  bool enable_go2_attitude_prior = false;
  bool enable_support_integrity = false;
  bool enable_source_aware_weighting = false;
  bool enable_fixed_lag_smoother = false;
};

RuntimeConfig defaultRuntimeConfig();
RuntimeConfig loadRuntimeConfigPlaceholder(const std::string& config_path);

}  // namespace legsa_gins::config
