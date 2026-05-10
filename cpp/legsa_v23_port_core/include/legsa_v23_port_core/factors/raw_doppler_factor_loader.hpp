// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference; LegSA-owned N5A extension.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: first proposed raw Doppler auxiliary factor path, not final_v23 output substitution.
// 中文说明：CSV 必须来自 RAWX + satellite-state provider 的速度因子导出；
// loader 明确拒绝 provider 缺失行，不能读取 .gnss velocity 冒充 raw Doppler。

#pragma once

#include "legsa_v23_port_core/factors/raw_doppler_types.hpp"

#include <string>
#include <vector>

namespace legsa_v23_port_core {

struct RawDopplerFactorLoadResult {
  std::vector<RawDopplerVelocityMeasurement> measurements;
  RawDopplerFactorStatus status;
};

class RawDopplerFactorLoader {
 public:
  static RawDopplerFactorLoadResult loadCsv(const std::string& path, const RawDopplerFactorConfig& config);
};

}  // namespace legsa_v23_port_core
