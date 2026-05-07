// 中文说明：LegSAEngine 是自主 runtime skeleton；本阶段只保持最小 dry-run 链路，不实现 INS mechanization、EKF、raw Doppler、Go2、weighting 或 FGO。
// English note: comments define module responsibility and safety boundaries only.

#pragma once

#include <cstddef>
#include <filesystem>
#include <memory>
#include <vector>

#include "legsa_gins/config/runtime_config.hpp"
#include "legsa_gins/factors/factor_registry.hpp"
#include "legsa_gins/io/eval_nav_writer_bridge.hpp"
#include "legsa_gins/io/nav_writer.hpp"
#include "legsa_gins/io/std_writer.hpp"
#include "legsa_gins/types/nav_types.hpp"

namespace legsa_gins::engine {

class LegSAEngine {
 public:
  explicit LegSAEngine(config::RuntimeConfig config);

  void initialize();
  void addImuData(const types::ImuSample& imu);
  void addGnssData(const types::GnssNativeMeasurement& gnss);
  void processNext();
  types::NavState getNavState() const;
  types::StdState getStdState() const;
  double timestamp() const;
  void writeCurrentOutputs();
  void runDryDemo();
  void runFilterToyDemo();
  void runFilterCsvTrial(const std::filesystem::path& imu_csv,
                         const std::filesystem::path& receiver_csv,
                         std::size_t max_epochs);

 private:
  void applyConfigToRegistry();

  config::RuntimeConfig config_;
  factors::FactorRegistry registry_;
  types::NavState nav_state_;
  types::StdState std_state_;
  std::vector<types::ImuSample> imu_buffer_;
  std::vector<types::GnssNativeMeasurement> gnss_buffer_;
  std::unique_ptr<io::NavWriter> nav_writer_;
  std::unique_ptr<io::StdWriter> std_writer_;
  std::unique_ptr<io::EvalNavWriterBridge> eval_nav_writer_;
  bool initialized_ = false;
};

}  // namespace legsa_gins::engine
