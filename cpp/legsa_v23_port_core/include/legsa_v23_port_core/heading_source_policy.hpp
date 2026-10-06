#pragma once
#include <cmath>
#include <stdexcept>
#include <string>

namespace legsa_v23_port_core {
// Engineering source arbitration only. These constants do not identify receiver
// epochs or model cross-epoch / cross-sensor statistical independence.
struct HeadingSourceDecision {
  double time = 0.0, pvt_time = 0.0, pvt_age_s = 0.0;
  bool pvt_known = false, pvt_source_valid = false, pvt_present = false;
  bool carrier_present = false, carrier_valid = false;
  bool use_pvt = false, use_carrier = false, accepted = false;
  std::string pvt_reason = "NO_PVT_ROW", carrier_reason = "NO_CARRIER_ROW";
};
struct HeadingSourceCounts {
  std::size_t pvt_attempts = 0, pvt_accepted = 0, pvt_suppressed = 0;
  std::size_t carrier_attempts = 0, carrier_accepted = 0, carrier_bypassed = 0;
};
class HeadingSourcePolicy {
 public:
  static constexpr double kNearTimeS = 0.01;
  static constexpr double kPvtFreshnessS = 0.21;
  HeadingSourceDecision arrive(double t, bool pvt_present, bool pvt_valid,
                               bool carrier_present, bool carrier_valid, bool control) {
    if (!std::isfinite(t) || (event_known_ && !(t > last_event_time_)))
      throw std::runtime_error("HEADING_SOURCE_NONMONOTONIC_EVENT");
    event_known_ = true; last_event_time_ = t;
    if (pvt_present) { pvt_known_ = true; pvt_time_ = t; pvt_valid_ = pvt_valid; }
    HeadingSourceDecision d;
    d.time=t; d.pvt_present=pvt_present; d.carrier_present=carrier_present;
    d.carrier_valid=carrier_valid; d.pvt_known=pvt_known_;
    d.pvt_source_valid=pvt_valid_; d.pvt_time=pvt_time_;
    d.pvt_age_s=pvt_known_ ? t-pvt_time_ : 0.0;
    if (pvt_present) {
      d.use_pvt = pvt_valid && !near(t, carrier_accepted_, last_carrier_);
      d.pvt_reason = !pvt_valid ? "PVT_SOURCE_INVALID" :
          d.use_pvt ? "PVT_PRIORITY" : "ACCEPTED_CARRIER_NEAR_TIME";
    }
    if (carrier_present) {
      if (control) d.carrier_reason="CONTROL_CARRIER_BYPASS";
      else if (!carrier_valid) d.carrier_reason="CARRIER_SOURCE_INVALID";
      else if (!pvt_known_) d.carrier_reason="PVT_STATUS_UNKNOWN";
      else if (d.pvt_age_s > kPvtFreshnessS + 1e-12) d.carrier_reason="PVT_STATUS_STALE";
      else if (pvt_valid_) d.carrier_reason="PVT_SOURCE_VALID";
      else if (near(t, pvt_accepted_, last_pvt_)) d.carrier_reason="ACCEPTED_PVT_NEAR_TIME";
      else { d.use_carrier=true; d.carrier_reason="FRESH_PVT_GAP_CARRIER_ATTEMPT"; }
    }
    return d;
  }
  void accepted(const HeadingSourceDecision& d) {
    if (!event_known_ || d.time != last_event_time_ || d.use_pvt == d.use_carrier)
      throw std::runtime_error("HEADING_SOURCE_INVALID_ACCEPT_RECEIPT");
    if (d.use_pvt) { pvt_accepted_=true; last_pvt_=d.time; }
    else { carrier_accepted_=true; last_carrier_=d.time; }
  }
 private:
  static bool near(double t, bool known, double last) {
    return known && t >= last && t-last <= kNearTimeS + 1e-12;
  }
  bool pvt_known_=false, pvt_valid_=false, event_known_=false;
  bool pvt_accepted_=false, carrier_accepted_=false;
  double pvt_time_=0.0, last_event_time_=0.0, last_pvt_=0.0, last_carrier_=0.0;
};
}  // namespace legsa_v23_port_core
