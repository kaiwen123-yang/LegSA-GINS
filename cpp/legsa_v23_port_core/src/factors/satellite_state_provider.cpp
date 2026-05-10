// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference; LegSA-owned N5A extension.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: first proposed raw Doppler auxiliary factor path, not final_v23 output substitution.
// 中文说明：NullSatelliteStateProvider 是显式 blocker，不会把 raw Doppler 写成已应用。

#include "legsa_v23_port_core/factors/satellite_state_provider.hpp"

namespace legsa_v23_port_core {

bool NullSatelliteStateProvider::available() const {
  return false;
}

std::string NullSatelliteStateProvider::status() const {
  return "provider_missing_sat_state_export";
}

}  // namespace legsa_v23_port_core
