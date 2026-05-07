#include "legsa_gins/io/nav_writer.hpp"

#include <iomanip>
#include <stdexcept>
#include <utility>

namespace legsa_gins::io {

NavWriter::NavWriter(std::filesystem::path output_dir, int gps_week)
    : path_(std::move(output_dir) / "LegSA_NAV.nav"), gps_week_(gps_week) {
  std::filesystem::create_directories(path_.parent_path());
  stream_.open(path_);
  if (!stream_) {
    throw std::runtime_error("Failed to open NAV output: " + path_.string());
  }
  stream_ << "gps_week tow lat_deg lon_deg height_m vn_mps ve_mps vd_mps "
             "roll_deg pitch_deg yaw_deg status source_role\n";
}

NavWriter::~NavWriter() { close(); }

void NavWriter::write(const types::NavState& state) {
  if (has_last_tow_ && state.tow < last_tow_) {
    throw std::runtime_error("NAV tow must be monotonically non-decreasing.");
  }
  has_last_tow_ = true;
  last_tow_ = state.tow;

  stream_ << gps_week_ << ' ' << std::fixed << std::setprecision(9) << state.tow
          << ' ' << std::setprecision(12) << state.lat_deg << ' ' << state.lon_deg
          << ' ' << std::setprecision(6) << state.height_m << ' ' << state.vn_mps
          << ' ' << state.ve_mps << ' ' << state.vd_mps << ' ' << state.roll_deg
          << ' ' << state.pitch_deg << ' ' << state.yaw_deg << ' ' << state.status
          << ' ' << state.source_role << '\n';
}

void NavWriter::close() {
  if (stream_.is_open()) {
    stream_.flush();
    stream_.close();
  }
}

const std::filesystem::path& NavWriter::path() const { return path_; }

}  // namespace legsa_gins::io
