// Small synthetic algebra harness: no navigation inputs or engine mutation.
#include "legsa_v23_port_core/factors/pose_clone.hpp"
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
using namespace legsa_v23_port_core;
namespace pc = legsa_v23_port_core::pose_clone;
double number() { double x; if (!(std::cin >> x)) throw std::runtime_error("input"); return x; }
Matrix matrix(std::size_t n, std::size_t m) {
  Matrix a(n, m); for (double& x : a.data) x = number(); return a;
}
std::vector<double> vector(std::size_t n) {
  std::vector<double> a(n); for (double& x : a) x = number(); return a;
}
Vec3 point() { Vec3 a; for (double& x : a) x = number(); return a; }
Matrix3 rotation() { Matrix3 a; for (auto& row : a) for (double& x : row) x = number(); return a; }
void print(const Matrix& a) {
  std::cout << '[';
  for (std::size_t i = 0; i < a.rows; ++i) {
    if (i) std::cout << ',';
    std::cout << '[';
    for (std::size_t j = 0; j < a.cols; ++j) { if (j) std::cout << ','; std::cout << a(i, j); }
    std::cout << ']';
  }
  std::cout << ']';
}
void print(const std::vector<double>& a) {
  std::cout << '[';
  for (std::size_t i = 0; i < a.size(); ++i) { if (i) std::cout << ','; std::cout << a[i]; }
  std::cout << ']';
}
void gaussian(const pc::Gaussian& s) {
  std::cout << "{\"P\":"; print(s.covariance); std::cout << ",\"mean\":"; print(s.mean); std::cout << '}';
}
pc::FootModel model() {
  const std::size_t n = static_cast<std::size_t>(number());
  const bool horizontal = number() != 0;
  std::vector<Vec3> f0(n), f1(n);
  for (auto& p : f0) p = point(); for (auto& p : f1) p = point();
  const auto p0 = point(); const auto c0 = rotation(); const auto cbn = rotation();
  const auto blh = point(); const auto sigma = matrix(6 * n, 6 * n); const auto lever = point();
  return pc::footModel(f0, f1, p0, c0, cbn, blh, sigma, lever, horizontal);
}
int main(int argc, char** argv) {
  try {
    if (argc != 2) throw std::runtime_error("operation required");
    std::cout << std::setprecision(17);
    const std::string op = argv[1];
    if (op == "model") {
      const auto m = model();
      std::cout << "{\"residual\":"; print(m.residual); std::cout << ",\"H\":"; print(m.H);
      std::cout << ",\"R\":"; print(m.R); std::cout << ",\"A\":"; print(m.foot_error_map); std::cout << '}';
    } else if (op == "augment") {
      const auto blh = point(); const auto p = matrix(21, 21); const auto mean = vector(21);
      const auto j = pc::augmentationJacobian(blh); const auto s = pc::augment(p, mean, j);
      std::cout << "{\"P\":"; print(s.covariance); std::cout << ",\"mean\":"; print(s.mean);
      std::cout << ",\"J\":"; print(j); std::cout << '}';
    } else {
      const std::size_t n = static_cast<std::size_t>(number());
      const auto p = matrix(n, n); const auto mean = vector(n); const pc::Gaussian s{p, mean};
      if (op == "propagate") {
        const auto phi = matrix(21, 21); const auto q = matrix(21, 21); gaussian(pc::propagate(s, phi, q));
      } else if (op == "reset") {
        gaussian(pc::reset(s, rotation()));
      } else if (op == "marginal") {
        gaussian(pc::marginalCurrent(s));
      } else if (op == "ordinary") {
        const std::size_t rows = static_cast<std::size_t>(number());
        const auto h = matrix(rows, n); const auto r = matrix(rows, rows); const auto z = vector(rows);
        gaussian(pc::ordinaryUpdate(s, z, h, r));
      } else if (op == "foot") {
        gaussian(pc::footUpdate(s, model()));
      } else throw std::runtime_error("unknown operation");
    }
    std::cout << '\n';
  } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
