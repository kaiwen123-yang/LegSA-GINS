// 中文说明：toy CSV reader 只用于 N4 测试，不读取 BY2 raw data、trace 或 final_v23 输出。
// English note: Missing fields and non-monotonic timestamps are hard errors.

#pragma once

#include <filesystem>
#include <vector>

#include "legsa_gins/types/filter_types.hpp"
#include "legsa_gins/types/imu_types.hpp"

namespace legsa_gins::readers {

std::vector<types::LegSAImuSample> readToyImuCsv(const std::filesystem::path& path);
std::vector<types::ReceiverNativeMeasurement> readToyReceiverCsv(
    const std::filesystem::path& path);

}  // namespace legsa_gins::readers
