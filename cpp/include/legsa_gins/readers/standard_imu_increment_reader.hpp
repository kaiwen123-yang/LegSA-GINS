// 中文说明：N4G IMU increment reader 只读取 Go2 body-state diagnostic 转换结果；
// 优先使用 algo_time_sec，不读取 receiver imu-data.csv，不读取 trace，不做 Go2 prior claim。
// English note: The CSV is a propagation source for diagnostic filter-core trials only.

#pragma once

#include <cstddef>
#include <filesystem>
#include <vector>

#include "legsa_gins/types/imu_types.hpp"

namespace legsa_gins::readers {

std::vector<types::LegSAImuSample> readStandardImuIncrementCsv(
    const std::filesystem::path& path,
    std::size_t max_rows = 0);

}  // namespace legsa_gins::readers
