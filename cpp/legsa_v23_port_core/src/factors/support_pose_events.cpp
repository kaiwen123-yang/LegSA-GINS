#include "legsa_v23_port_core/factors/support_pose_events.hpp"
#include "legsa_v23_port_core/factors/attitude_clone.hpp"
#include <cmath>
#include <fstream>
#include <limits>
#include <sstream>
#include <stdexcept>
namespace legsa_v23_port_core {
namespace {
std::vector<std::string> split(std::string line) {
  if(!line.empty() && line.back()=='\r') line.pop_back();
  std::vector<std::string> out; std::istringstream in(line);std::string word;
  while(std::getline(in,word,',')) out.push_back(word);
  if(!line.empty() && line.back()==',') out.push_back("");
  return out;
}
}
void validateSupportPoseConfig(const SupportPoseConfig& c,const std::string& runtime) {
  if(c.mode=="off") return;
  if(runtime!="research_experiment" || c.events_path.empty() ||
    (c.mode!="SDK_NULL" && c.mode!="REPLACE_NULL" && c.mode!="REPLACE_SUPPORT") ||
    !(c.point_sigma_m>0) || !std::isfinite(c.point_sigma_m))
    throw std::runtime_error("SUPPORT_POSE_RESEARCH_CONFIG");
  attitude_clone::requireRotation(c.foot_frd_to_engine_body,"SUPPORT_POSE_FRAME");
}
std::vector<SupportPoseEvent> readSupportPoseEvents(const SupportPoseConfig& c) {
  std::ifstream in(c.events_path);std::string line;
  if(!in || !std::getline(in,line)) throw std::runtime_error("SUPPORT_POSE_INPUT_OPEN");
  const std::vector<std::string> header={"event_time_s","available_time_s","event_type","clone_id","source_time_s",
    "endpoint_id","foot_i","foot_j","episode_i","episode_j","r_i_body_frd_x_m","r_i_body_frd_y_m","r_i_body_frd_z_m",
    "r_j_body_frd_x_m","r_j_body_frd_y_m","r_j_body_frd_z_m","point_sigma_m","reason"};
  if(split(line)!=header) throw std::runtime_error("SUPPORT_POSE_HEADER");
  std::vector<SupportPoseEvent> out; double last=-std::numeric_limits<double>::infinity();
  while(std::getline(in,line)) {
    auto x=split(line);if(x.size()!=18) throw std::runtime_error("SUPPORT_POSE_COLUMNS");
    SupportPoseEvent e;e.time=std::stod(x[0]);e.available_time=std::stod(x[1]);e.type=x[2];e.clone_id=x[3];
    e.endpoint_id=x[5];e.foot_i=x[6];e.foot_j=x[7];e.episode_i=x[8];e.episode_j=x[9];e.reason=x[17];
    if(!std::isfinite(e.time) || e.time<last || e.available_time!=e.time || e.clone_id.empty())
      throw std::runtime_error("SUPPORT_POSE_CAUSAL_TIME");
    last=e.time;
    if(e.type=="START" || e.type=="END") {
      e.source_time=std::stod(x[4]);e.point_sigma_m=std::stod(x[16]);
      if(e.source_time!=e.time || e.point_sigma_m!=c.point_sigma_m)
        throw std::runtime_error("SUPPORT_POSE_ENDPOINT_MODEL");
      for(int i=0;i<2;++i) {
        Vec3 point{};for(int j=0;j<3;++j) {
          point[j]=std::stod(x[10+3*i+j]);
          if(!std::isfinite(point[j])) throw std::runtime_error("SUPPORT_POSE_NONFINITE_POINT");
        }
        e.positions_body_frd.push_back(point);
      }
    } else if(e.type!="RETIRE" && e.type!="REVOKE") throw std::runtime_error("SUPPORT_POSE_EVENT_TYPE");
    out.push_back(e);
  }
  return out;
}
}
