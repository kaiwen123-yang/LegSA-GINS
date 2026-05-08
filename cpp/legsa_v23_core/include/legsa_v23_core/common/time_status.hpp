#pragma once

namespace legsa_v23_core {

// 中文说明：GNSS 更新相对 IMU 区间的位置；N4H4A 只用于运行链路判定。
enum class TimeUpdateStatus {
  kBeforeInterval = -1,
  kInsideInterval = 0,
  kAfterInterval = 1,
};

}  // namespace legsa_v23_core
