// 中文说明：N4 使用轻量 Vec3，后续可替换矩阵库；当前不引入 Eigen 等重依赖。
// English note: Minimal vector math for the toy-run-capable filter core.

#pragma once

#include <cmath>

namespace legsa_gins::math {

struct Vec3 {
  double x = 0.0;
  double y = 0.0;
  double z = 0.0;
};

inline Vec3 add(const Vec3& lhs, const Vec3& rhs) {
  return {lhs.x + rhs.x, lhs.y + rhs.y, lhs.z + rhs.z};
}

inline Vec3 subtract(const Vec3& lhs, const Vec3& rhs) {
  return {lhs.x - rhs.x, lhs.y - rhs.y, lhs.z - rhs.z};
}

inline Vec3 scale(const Vec3& value, double factor) {
  return {value.x * factor, value.y * factor, value.z * factor};
}

inline double dot(const Vec3& lhs, const Vec3& rhs) {
  return lhs.x * rhs.x + lhs.y * rhs.y + lhs.z * rhs.z;
}

inline Vec3 cross(const Vec3& lhs, const Vec3& rhs) {
  return {
      lhs.y * rhs.z - lhs.z * rhs.y,
      lhs.z * rhs.x - lhs.x * rhs.z,
      lhs.x * rhs.y - lhs.y * rhs.x,
  };
}

inline double norm(const Vec3& value) { return std::sqrt(dot(value, value)); }

inline bool isFinite(const Vec3& value) {
  return std::isfinite(value.x) && std::isfinite(value.y) && std::isfinite(value.z);
}

}  // namespace legsa_gins::math
