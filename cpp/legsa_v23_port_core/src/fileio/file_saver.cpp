// LegSA-GINS source-backed port file.
// Source reference: KF-GINS-graduation-design / final_v23 reference.
// Source commit: 5a4471efd4fcfcdc31e258a677af354c652ff16f.
// Port role: mature GNSS/INS backbone implementation, not proposed novelty.
// Boundary: no final_v23 output substitution, no trace solver input.
// 中文说明：该文件为受控移植的组合导航骨架代码，后续创新因子将在该骨架通过 parity 后再接入。

#include "legsa_v23_port_core/fileio/file_saver.hpp"

#include "legsa_v23_port_core/common/earth.hpp"

#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <stdexcept>

namespace legsa_v23_port_core {
namespace {

// 中文说明：统一创建输出目录；toy 输出只写 runtime output dir，不进入 Git。
void ensureOutputDir(const std::string& output_dir) {
  std::filesystem::create_directories(output_dir);
}

}  // namespace

// 中文说明：NAV writer 输出 toy 状态，不做 output-only correction。
void FileSaver::writeNav(const std::string& output_dir, const std::vector<NavState>& states) {
  ensureOutputDir(output_dir);
  std::ofstream out(std::filesystem::path(output_dir) / "LegSA_PORT_NAV.nav");
  out << std::fixed << std::setprecision(10);
  out << "# time lat_deg lon_deg height_m vn ve vd roll_deg pitch_deg yaw_deg\n";
  for (const auto& state : states) {
    out << state.time << ' ' << Earth::radToDeg(state.pos_blh_rad_m[0]) << ' '
        << Earth::radToDeg(state.pos_blh_rad_m[1]) << ' ' << state.pos_blh_rad_m[2] << ' '
        << state.vel_ned_mps[0] << ' ' << state.vel_ned_mps[1] << ' ' << state.vel_ned_mps[2]
        << ' ' << Earth::radToDeg(state.euler_rad[0]) << ' ' << Earth::radToDeg(state.euler_rad[1])
        << ' ' << Earth::radToDeg(state.euler_rad[2]) << '\n';
  }
}

// 中文说明：STD writer 只写协方差对角 sqrt，R1 不声明真实统计一致性。
void FileSaver::writeStd(const std::string& output_dir, const std::vector<std::vector<double>>& covariances) {
  ensureOutputDir(output_dir);
  std::ofstream out(std::filesystem::path(output_dir) / "LegSA_PORT_STD.csv");
  out << "row";
  for (std::size_t i = 0; i < kErrorStateSize; ++i) {
    out << ",std_" << i;
  }
  out << '\n';
  for (std::size_t row = 0; row < covariances.size(); ++row) {
    out << row;
    for (double value : covariances[row]) {
      out << ',' << std::sqrt(std::max(0.0, value));
    }
    out << '\n';
  }
}

// 中文说明：EVAL_NAV 使用 Python evaluator 可读字段；R1 toy 不是 performance。
void FileSaver::writeEvalNav(const std::string& output_dir, const std::vector<NavState>& states) {
  ensureOutputDir(output_dir);
  std::ofstream out(std::filesystem::path(output_dir) / "EVAL_NAV.csv");
  out << "time,lat_deg,lon_deg,height_m,vn,ve,vd,roll_deg,pitch_deg,yaw_deg\n";
  out << std::fixed << std::setprecision(10);
  for (const auto& state : states) {
    out << state.time << ',' << Earth::radToDeg(state.pos_blh_rad_m[0]) << ','
        << Earth::radToDeg(state.pos_blh_rad_m[1]) << ',' << state.pos_blh_rad_m[2] << ','
        << state.vel_ned_mps[0] << ',' << state.vel_ned_mps[1] << ',' << state.vel_ned_mps[2]
        << ',' << Earth::radToDeg(state.euler_rad[0]) << ',' << Earth::radToDeg(state.euler_rad[1])
        << ',' << Earth::radToDeg(state.euler_rad[2]) << '\n';
  }
}

// 中文说明：RUN_MANIFEST 锁定 R1 禁用项，明确 parity_not_attempted。
void FileSaver::writeRunManifest(const std::string& output_dir, const PortOptions& options) {
  ensureOutputDir(output_dir);
  std::ofstream out(std::filesystem::path(output_dir) / "RUN_MANIFEST.json");
  if (!out) {
    throw std::runtime_error("failed to write RUN_MANIFEST");
  }
  out << "{\n"
      << "  \"phase\": \"N4H4R1\",\n"
      << "  \"port_role\": \"source_backed_port_foundation\",\n"
      << "  \"parity_attempted\": false,\n"
      << "  \"final_v23_output_solver_input\": false,\n"
      << "  \"trace_solver_input\": false,\n"
      << "  \"output_only_correction\": false,\n"
      << "  \"bad_epoch_deletion_for_metric\": false,\n"
      << "  \"raw_doppler\": false,\n"
      << "  \"go2_prior\": false,\n"
      << "  \"lsim_oim\": false,\n"
      << "  \"fgo\": false,\n"
      << "  \"performance_claim\": false,\n"
      << "  \"final_v23_is_proposed\": false,\n"
      << "  \"run_label\": \"" << options.run_label << "\"\n"
      << "}\n";
}

}  // namespace legsa_v23_port_core

