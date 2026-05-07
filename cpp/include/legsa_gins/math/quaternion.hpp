// 中文说明：qbn 表示 body 到 navigation 的姿态四元数；本模块只实现 N4 toy filter 所需基础操作。
// English note: This does not claim final_v23 attitude-mechanization parity.

#pragma once

#include <cmath>
#include <stdexcept>

#include "legsa_gins/math/vec3.hpp"

namespace legsa_gins::math {

struct Quaternion {
  double w = 1.0;
  double x = 0.0;
  double y = 0.0;
  double z = 0.0;
};

inline Quaternion identity() { return {}; }

inline Quaternion normalize(const Quaternion& q) {
  const double n = std::sqrt(q.w * q.w + q.x * q.x + q.y * q.y + q.z * q.z);
  if (n <= 0.0 || !std::isfinite(n)) {
    throw std::runtime_error("Cannot normalize invalid quaternion.");
  }
  return {q.w / n, q.x / n, q.y / n, q.z / n};
}

inline Quaternion conjugate(const Quaternion& q) { return {q.w, -q.x, -q.y, -q.z}; }

inline Quaternion multiply(const Quaternion& a, const Quaternion& b) {
  return {
      a.w * b.w - a.x * b.x - a.y * b.y - a.z * b.z,
      a.w * b.x + a.x * b.w + a.y * b.z - a.z * b.y,
      a.w * b.y - a.x * b.z + a.y * b.w + a.z * b.x,
      a.w * b.z + a.x * b.y - a.y * b.x + a.z * b.w,
  };
}

inline Quaternion inverse(const Quaternion& q) {
  const double n2 = q.w * q.w + q.x * q.x + q.y * q.y + q.z * q.z;
  if (n2 <= 0.0 || !std::isfinite(n2)) {
    throw std::runtime_error("Cannot invert invalid quaternion.");
  }
  const Quaternion c = conjugate(q);
  return {c.w / n2, c.x / n2, c.y / n2, c.z / n2};
}

inline Quaternion fromRotVec(const Vec3& rot_vec) {
  const double angle = norm(rot_vec);
  if (angle < 1.0e-12) {
    return normalize({1.0, 0.5 * rot_vec.x, 0.5 * rot_vec.y, 0.5 * rot_vec.z});
  }
  const double half = 0.5 * angle;
  const double s = std::sin(half) / angle;
  return normalize({std::cos(half), rot_vec.x * s, rot_vec.y * s, rot_vec.z * s});
}

inline Vec3 rotateVector(const Quaternion& q, const Vec3& v) {
  const Quaternion qn = normalize(q);
  const Quaternion rotated = multiply(multiply(qn, {0.0, v.x, v.y, v.z}), inverse(qn));
  return {rotated.x, rotated.y, rotated.z};
}

}  // namespace legsa_gins::math
