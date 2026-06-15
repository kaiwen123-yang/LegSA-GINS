// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference; LegSA-owned N7A extension.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: Go2 body-state roll/pitch weak-prior extension, not final_v23 output substitution.
// Boundary: no trace solver input, no final_v23 output solver input, no Go2 position truth.
// LegSA-GINS N7A Go2 weak-prior CSV loader.
// 中文说明：loader 只读取 runtime-only GO2_ATTITUDE_WEAK_PRIORS.csv，不读取 by2.txt 原始文件进入 solver。

#pragma once

#include "legsa_v23_port_core/factors/go2_weak_prior_types.hpp"

#include <string>
#include <vector>

namespace legsa_v23_port_core {

struct Go2AttitudeWeakPriorLoadResult {
  std::vector<Go2AttitudeWeakPriorMeasurement> measurements;
  Go2AttitudeWeakPriorStatus status;
};

struct Go2VelocityDiagnosticPriorLoadResult {
  std::vector<Go2VelocityDiagnosticPriorMeasurement> measurements;
  Go2VelocityDiagnosticPriorStatus status;
};

struct Go2ReadinessLsimMetadataLoadResult {
  std::vector<Go2ReadinessLsimMetadataMeasurement> measurements;
  Go2ReadinessLsimMetadataStatus status;
};

class Go2WeakPriorLoader {
 public:
  static Go2AttitudeWeakPriorLoadResult loadCsv(const std::string& path,
                                                const Go2AttitudeWeakPriorConfig& config);
  static Go2VelocityDiagnosticPriorLoadResult loadVelocityDiagnosticCsv(
      const std::string& path,
      const Go2VelocityDiagnosticPriorConfig& config);
  static Go2ReadinessLsimMetadataLoadResult loadReadinessLsimMetadataCsv(
      const std::string& path,
      const Go2ReadinessLsimMetadataConfig& config);
};

}  // namespace legsa_v23_port_core
