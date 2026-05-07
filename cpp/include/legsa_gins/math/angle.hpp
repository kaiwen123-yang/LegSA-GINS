// 中文说明：角度工具固定 heading/yaw residual 的 wrap 约定，不做 trace tuning。
// English note: Heading uses [0, 360); yaw residuals use centered intervals.

#pragma once

#include <cmath>

#include "legsa_gins/math/constants.hpp"

namespace legsa_gins::math {

inline double wrapRadPi(double angle) {
  double wrapped = std::fmod(angle + pi, 2.0 * pi);
  if (wrapped < 0.0) {
    wrapped += 2.0 * pi;
  }
  return wrapped - pi;
}

inline double wrapRad2Pi(double angle) {
  double wrapped = std::fmod(angle, 2.0 * pi);
  if (wrapped < 0.0) {
    wrapped += 2.0 * pi;
  }
  return wrapped;
}

inline double wrapDeg180(double angle) {
  double wrapped = std::fmod(angle + 180.0, 360.0);
  if (wrapped < 0.0) {
    wrapped += 360.0;
  }
  return wrapped - 180.0;
}

inline double wrapDeg360(double angle) {
  double wrapped = std::fmod(angle, 360.0);
  if (wrapped < 0.0) {
    wrapped += 360.0;
  }
  return wrapped;
}

}  // namespace legsa_gins::math
