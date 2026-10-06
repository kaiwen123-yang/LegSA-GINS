#include "legsa_v23_port_core/factors/foot_pair_events.hpp"
#include "legsa_v23_port_core/factors/attitude_clone.hpp"
#include <algorithm>
#include <cmath>
#include <fstream>
#include <limits>
#include <sstream>
#include <stdexcept>

namespace legsa_v23_port_core {
namespace {
void require(bool ok,const std::string& message) {
  if(!ok) throw std::runtime_error("FOOT_PAIR_"+message);
}
std::vector<std::string> split(std::string line) {
  if(!line.empty() && line.back()=='\r') line.pop_back();
  std::vector<std::string> out;std::size_t begin=0;
  while(true) {
    const auto end=line.find(',',begin);
    out.push_back(line.substr(begin,end==std::string::npos?end:end-begin));
    if(end==std::string::npos) break;
    begin=end+1;
  }
  return out;
}
double number(const std::string& value) {
  std::size_t used=0; double x=0;
  try{x=std::stod(value,&used);}catch(...){throw std::runtime_error("FOOT_PAIR_BAD_NUMBER");}
  require(used==value.size() && std::isfinite(x),"NONFINITE_OR_TRAILING_NUMBER");
  return x;
}
}
void validateAttitudeCloneConfig(const AttitudeCloneConfig& c,const std::string& contract) {
  require(c.mode=="off" || c.mode=="NULL_CLONE" || c.mode=="PAIR_YOUNG","UNKNOWN_MODE");
  if(c.mode=="off") {
    require(c.events_path.empty(),"OFF_MUST_NOT_OPEN_FOOT_INPUT");
    return;
  }
  require(contract=="research_experiment","RESEARCH_ONLY");
  require(!c.events_path.empty() && !c.position_source_id.empty() && !c.covariance_source_id.empty() &&
          !c.covariance_assumption.empty() && !c.frame_source_id.empty(),"EXPLICIT_SOURCES_REQUIRED");
  require(c.position_gnss_input_status=="unknown" || c.position_gnss_input_status=="declared_no" ||
          c.position_gnss_input_status=="declared_yes","EXPLICIT_POSITION_GNSS_INPUT_STATUS_REQUIRED");
  require(c.availability_policy=="source_time_replay_assumption","UNSUPPORTED_AVAILABILITY_POLICY");
  attitude_clone::requireRotation(c.foot_frd_to_engine_body,"FOOT_FRD_TO_ENGINE");
}
std::vector<FootPairEvent> readFootPairEvents(const AttitudeCloneConfig& c) {
  require(c.mode!="off","OFF_INPUT_READ_FORBIDDEN");
  std::ifstream input(c.events_path);
  require(input.good(),"INPUT_OPEN");
  std::string line;
  require(static_cast<bool>(std::getline(input,line)),"MISSING_HEADER");
  std::vector<std::string> expected={"event_time_s","available_time_s","event_type","clone_id","source_time_s",
    "endpoint_id","foot_i","foot_j","episode_i","episode_j","d_body_frd_x_m","d_body_frd_y_m","d_body_frd_z_m","reason"};
  for(int i=0;i<6;++i) for(int j=0;j<6;++j) expected.push_back("sigma_"+std::to_string(i)+std::to_string(j));
  require(split(line)==expected,"HEADER_CONTRACT_50_COLUMNS");
  std::vector<FootPairEvent> events;
  double last=-std::numeric_limits<double>::infinity();
  while(std::getline(input,line)) {
    require(!line.empty(),"EMPTY_ROW");
    auto x=split(line);require(x.size()==50,"COLUMN_COUNT");
    FootPairEvent e;
    e.time=number(x[0]);e.available_time=number(x[1]);e.type=x[2];e.clone_id=x[3];
    e.source_time=e.type=="RETIRE" ? std::numeric_limits<double>::quiet_NaN() : number(x[4]);
    require(e.time>last,"STRICT_EVENT_TIME_ORDER");last=e.time;
    require(e.available_time==e.time && (e.type=="RETIRE" || e.time==e.source_time),
            "EXACT_SOURCE_TIME_REPLAY_REQUIRED");
    require(!e.clone_id.empty() && !x[13].empty(),"EVENT_ID_REASON_REQUIRED");e.reason=x[13];
    require(e.type=="START" || e.type=="END" || e.type=="RETIRE","UNKNOWN_EVENT_TYPE");
    if(e.type=="RETIRE") {
      require(x[4].empty(),"RETIRE_HAS_NO_MEASUREMENT_SOURCE_TIME");
      for(std::size_t i=5;i<13;++i) require(x[i].empty(),"RETIRE_HAS_MEASUREMENT_FIELDS");
      for(std::size_t i=14;i<50;++i) require(x[i].empty(),"RETIRE_HAS_COVARIANCE");
    } else {
      e.endpoint_id=x[5];e.foot_i=x[6];e.foot_j=x[7];e.episode_i=x[8];e.episode_j=x[9];
      const std::vector<std::string> feet={"FR","FL","RR","RL"};
      require(!e.endpoint_id.empty() && !e.episode_i.empty() && !e.episode_j.empty() &&
              e.foot_i!=e.foot_j && std::find(feet.begin(),feet.end(),e.foot_i)!=feet.end() &&
              std::find(feet.begin(),feet.end(),e.foot_j)!=feet.end(),"ENDPOINT_IDENTITY");
      e.direction_body_frd={number(x[10]),number(x[11]),number(x[12])};
      require(norm(e.direction_body_frd)>1e-10,"DEGENERATE_DIRECTION");
      if(e.type=="END") {
        e.difference_covariance=Matrix(6,6);
        for(std::size_t i=0;i<36;++i) e.difference_covariance.data[i]=number(x[14+i]);
        e.difference_covariance=attitude_clone::symmetricPsd(e.difference_covariance,6,"INPUT_SIGMA6");
      } else for(std::size_t i=14;i<50;++i) require(x[i].empty(),"START_MUST_NOT_CONTAIN_FUTURE_SIGMA");
    }
    events.push_back(e);
  }
  return events;  // Empty stream is an explicit zero-opportunity outcome, not a fake measurement.
}
}  // namespace legsa_v23_port_core
