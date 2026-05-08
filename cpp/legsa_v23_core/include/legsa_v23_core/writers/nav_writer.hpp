#pragma once

#include "legsa_v23_core/state/nav_state.hpp"

#include <fstream>
#include <string>

namespace legsa_v23_core {

// 中文说明：写 LegSA_V23_NAV.nav skeleton 输出；BLH 输出为 deg/deg/m，姿态输出为 deg。
class NavWriter {
 public:
  // 中文说明：打开 NAV 文件并写入列头；N4H4A 输出不能作为性能证据。
  explicit NavWriter(const std::string& path);

  // 中文说明：写一行名义导航状态，单位为 s/deg/deg/m/mps/deg。
  void write(double time, const NavState& state);

 private:
  std::ofstream output_;
};

}  // namespace legsa_v23_core
