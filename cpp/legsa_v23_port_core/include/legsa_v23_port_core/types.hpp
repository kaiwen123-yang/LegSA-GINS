// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#pragma once

#include <array>
#include <cstddef>
#include <string>
#include <vector>

namespace legsa_v23_port_core {

using Vec3 = std::array<double, 3>;
using Matrix3 = std::array<std::array<double, 3>, 3>;

// 中文说明：误差状态维度沿用 KF-GINS 风格的 21 维合同，R1 只保留骨架索引。
constexpr std::size_t kErrorStateSize = 21;

// 中文说明：小工具函数避免 R1 引入 Eigen；R2 可替换为完整矩阵实现。
Vec3 makeVec3(double x, double y, double z);
double norm(const Vec3& value);
Vec3 add(const Vec3& lhs, const Vec3& rhs);
Vec3 scale(const Vec3& value, double factor);
std::vector<double> makeCovarianceDiagonal(double value);

}  // namespace legsa_v23_port_core

