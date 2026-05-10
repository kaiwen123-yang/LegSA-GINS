// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference; LegSA-owned N5A extension.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: first proposed raw Doppler auxiliary factor path, not final_v23 output substitution.
// 中文说明：raw Doppler 因子必须依赖 satellite position/velocity/clock drift provider；
// Null provider 表示缺失，不能启用真实 solver factor。

#pragma once

#include <string>

namespace legsa_v23_port_core {

class SatelliteStateProvider {
 public:
  virtual ~SatelliteStateProvider() = default;
  virtual bool available() const = 0;
  virtual std::string status() const = 0;
};

class NullSatelliteStateProvider final : public SatelliteStateProvider {
 public:
  bool available() const override;
  std::string status() const override;
};

}  // namespace legsa_v23_port_core
