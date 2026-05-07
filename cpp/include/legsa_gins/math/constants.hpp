// 中文说明：这是 LegSA-GINS 自主 C++ filter core 的基础常量，不从外部 KF-GINS 源码复制。
// English note: These constants support the self-owned N4 filter foundation only.

#pragma once

namespace legsa_gins::math {

constexpr double pi = 3.141592653589793238462643383279502884;
constexpr double deg_to_rad = pi / 180.0;
constexpr double rad_to_deg = 180.0 / pi;

constexpr double wgs84_a = 6378137.0;
constexpr double wgs84_f = 1.0 / 298.257223563;
constexpr double wgs84_e2 = wgs84_f * (2.0 - wgs84_f);
constexpr double wgs84_wie = 7.292115e-5;
constexpr double normal_gravity_equator = 9.7803253359;

}  // namespace legsa_gins::math
