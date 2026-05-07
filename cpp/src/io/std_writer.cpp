#include "legsa_gins/io/std_writer.hpp"

#include <iomanip>
#include <stdexcept>
#include <utility>

namespace legsa_gins::io {

StdWriter::StdWriter(std::filesystem::path output_dir)
    : path_(std::move(output_dir) / "LegSA_STD.csv") {
  std::filesystem::create_directories(path_.parent_path());
  stream_.open(path_);
  if (!stream_) {
    throw std::runtime_error("Failed to open STD output: " + path_.string());
  }
  stream_ << "tow,std_pos_n_m,std_pos_e_m,std_pos_d_m,std_vel_n_mps,"
             "std_vel_e_mps,std_vel_d_mps,std_roll_deg,std_pitch_deg,std_yaw_deg,"
             "std_gyrbias_x_dph,std_gyrbias_y_dph,std_gyrbias_z_dph,"
             "std_accbias_x_mgal,std_accbias_y_mgal,std_accbias_z_mgal,"
             "std_gyrscale_x_ppm,std_gyrscale_y_ppm,std_gyrscale_z_ppm,"
             "std_accscale_x_ppm,std_accscale_y_ppm,std_accscale_z_ppm\n";
}

StdWriter::~StdWriter() { close(); }

void StdWriter::write(const types::StdState& state) {
  if (has_last_tow_ && state.tow < last_tow_) {
    throw std::runtime_error("STD tow must be monotonically non-decreasing.");
  }
  has_last_tow_ = true;
  last_tow_ = state.tow;

  stream_ << std::fixed << std::setprecision(9) << state.tow << ','
          << std::setprecision(6) << state.std_pos_n_m << ',' << state.std_pos_e_m
          << ',' << state.std_pos_d_m << ',' << state.std_vel_n_mps << ','
          << state.std_vel_e_mps << ',' << state.std_vel_d_mps << ','
          << state.std_roll_deg << ',' << state.std_pitch_deg << ','
          << state.std_yaw_deg << ',' << state.std_gyrbias_x_dph << ','
          << state.std_gyrbias_y_dph << ',' << state.std_gyrbias_z_dph << ','
          << state.std_accbias_x_mgal << ',' << state.std_accbias_y_mgal << ','
          << state.std_accbias_z_mgal << ',' << state.std_gyrscale_x_ppm << ','
          << state.std_gyrscale_y_ppm << ',' << state.std_gyrscale_z_ppm << ','
          << state.std_accscale_x_ppm << ',' << state.std_accscale_y_ppm << ','
          << state.std_accscale_z_ppm << '\n';
}

void StdWriter::close() {
  if (stream_.is_open()) {
    stream_.flush();
    stream_.close();
  }
}

const std::filesystem::path& StdWriter::path() const { return path_; }

}  // namespace legsa_gins::io
