#pragma once

#include "legsa_v23_core/state/imu_types.hpp"
#include "legsa_v23_core/state/nav_state.hpp"

namespace legsa_v23_core {

// 中文说明：LegSA 自有 INS 机械编排；输入是 process_data-compatible IMU increment，不做二次 FLU->FRD。
class INSMechanization {
 public:
  // 中文说明：机械编排主入口，顺序固定为 velUpdate -> posUpdate -> attUpdate，不可调换。
  static void insMech(const PVAState& pvapre, PVAState& pvacur, const IMUData& imupre, const IMUData& imucur);

  // 中文说明：速度更新使用双子样增量、coning/sculling-like 修正、body-to-nav 投影、重力和 Coriolis。
  static void velUpdate(const PVAState& pvapre, PVAState& pvacur, const IMUData& imupre, const IMUData& imucur);

  // 中文说明：位置更新使用 midpoint velocity 和 DRi，把 NED 位移映射到 BLH(rad,rad,m)。
  static void posUpdate(const PVAState& pvapre, PVAState& pvacur, const IMUData& imucur);

  // 中文说明：姿态更新使用 b-frame 增量、n-frame 转率和 coning correction，输出 RPY(rad)。
  static void attUpdate(const PVAState& pvapre, PVAState& pvacur, const IMUData& imupre, const IMUData& imucur);
};

}  // namespace legsa_v23_core
