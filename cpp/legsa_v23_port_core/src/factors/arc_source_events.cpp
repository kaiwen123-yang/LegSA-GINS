#include "legsa_v23_port_core/factors/arc_source_events.hpp"
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <limits>
#include <set>
#include <sstream>
#include <stdexcept>

namespace legsa_v23_port_core {
namespace {
void require(bool ok,const char* message) { if(!ok) throw std::runtime_error(std::string("ARC_")+message); }
bool safeId(const std::string& text) {
  if(text.empty()) return false;
  for(unsigned char c:text) if(!((c>='a' && c<='z') || (c>='A' && c<='Z') ||
      (c>='0' && c<='9') || c=='_' || c=='-' || c=='.' || c==':' || c=='+')) return false;
  return true;
}
bool hex(const std::string& text,std::size_t size) {
  if(text.size()!=size) return false;
  for(char c:text) if(!((c>='0' && c<='9') || (c>='a' && c<='f'))) return false;
  return true;
}
std::vector<std::string> split(std::string line) {
  if(!line.empty() && line.back()=='\r') line.pop_back();
  std::vector<std::string> cells;std::size_t pos=0;
  while(true) {
    const auto end=line.find(',',pos);
    cells.push_back(line.substr(pos,end==std::string::npos?end:end-pos));
    if(end==std::string::npos) break;
    pos=end+1;
  }
  return cells;
}
double number(const std::string& text) {
  require(!text.empty() && text.find_first_of(" \t\r\n")==std::string::npos,"BAD_NUMBER");
  std::size_t used=0;double value=0;
  try {value=std::stod(text,&used);} catch(...) {throw std::runtime_error("ARC_BAD_NUMBER");}
  require(used==text.size() && std::isfinite(value),"NONFINITE_OR_TRAILING_NUMBER");
  return value;
}
std::size_t integer(const std::string& text) {
  require(!text.empty(),"BAD_EPOCH_INDEX");
  for(char c:text) require(c>='0' && c<='9',"BAD_EPOCH_INDEX");
  unsigned long long value=0;
  try {value=std::stoull(text);} catch(...) {throw std::runtime_error("ARC_BAD_EPOCH_INDEX");}
  require(value<=std::numeric_limits<std::size_t>::max(),"EPOCH_INDEX_OVERFLOW");
  return static_cast<std::size_t>(value);
}
}
std::string arcSourceTimeBits(double value) {
  static_assert(sizeof(double)==sizeof(std::uint64_t),"ARC needs binary64");
  static_assert(std::numeric_limits<double>::is_iec559,"ARC needs IEEE754");
  std::uint64_t bits=0;std::memcpy(&bits,&value,sizeof(bits));
  std::ostringstream out;out<<std::hex<<std::setw(16)<<std::setfill('0')<<bits;return out.str();
}
void validateArcCloneConfig(const ArcCloneConfig& c,const std::string& contract) {
  require(c.mode=="off" || c.mode=="NULL_ARC_DIAGNOSTIC","UNKNOWN_MODE");
  if(c.mode=="off") {require(c.events_path.empty(),"OFF_MUST_NOT_OPEN_SOURCE_INPUT");return;}
  require(contract=="research_experiment","RESEARCH_ONLY");
  require(!c.events_path.empty() && hex(c.events_sha256,64) && hex(c.manifest_sha256,64),"EXPLICIT_INPUT_PINS_REQUIRED");
  require(safeId(c.source_time_scale_id) && safeId(c.time_mapping_source_id) &&
          c.source_time_scale_id.find("UNKNOWN")==std::string::npos &&
          c.time_mapping_source_id.find("UNKNOWN")==std::string::npos &&
          c.source_time_scale_id.find("unknown")==std::string::npos &&
          c.time_mapping_source_id.find("unknown")==std::string::npos,"EXPLICIT_TIME_MAPPING_REQUIRED");
  require(c.availability_policy=="source_time_replay_assumption","UNSUPPORTED_AVAILABILITY_POLICY");
}
void validateArcSourceEvents(const std::vector<ArcSourceEvent>& events) {
  double last=-std::numeric_limits<double>::infinity();
  std::set<std::string> blocks,endpoints;const ArcSourceEvent* active=nullptr;
  std::string sequence;
  for(const auto& e:events) {
    require(safeId(e.sequence_id) && safeId(e.block_id) && safeId(e.endpoint_id),"UNSAFE_OR_EMPTY_ID");
    require(e.endpoint_model_fingerprint.empty() || safeId(e.endpoint_model_fingerprint),"UNSAFE_FINGERPRINT");
    if(sequence.empty()) sequence=e.sequence_id;
    require(e.sequence_id==sequence,"MIXED_SEQUENCE_STREAM");
    require(std::isfinite(e.source_time) && e.source_time>last && e.replay_time==e.source_time &&
            hex(e.source_time_bits_hex,16) && arcSourceTimeBits(e.source_time)==e.source_time_bits_hex &&
            arcSourceTimeBits(e.replay_time)==e.source_time_bits_hex,
            "EXACT_TIME_ORDER_OR_BITS");
    require(std::isnan(e.actual_available_time) && e.availability_mode=="SOURCE_TIME_REPLAY_ASSUMPTION",
            "ACTUAL_AVAILABILITY_MUST_BE_UNKNOWN");
    require(endpoints.insert(e.endpoint_id).second,"DUPLICATE_ENDPOINT");
    require(e.role=="START" || e.role=="END","UNKNOWN_ROLE");
    if(e.role=="START") {
      require(active==nullptr,"OVERLAPPING_BLOCKS");
      require(blocks.insert(e.block_id).second,"REUSED_BLOCK_ID");active=&e;
    } else {
      require(active && e.block_id==active->block_id && e.epoch_index>active->epoch_index,"END_WITHOUT_MATCHING_START");
      active=nullptr;
    }
    last=e.source_time;
  }
  // A final START without source END is an explicit uncovered terminal block; no pose is invented.
}
std::vector<ArcSourceEvent> readArcSourceEvents(const ArcCloneConfig& config) {
  require(config.mode!="off","OFF_INPUT_READ_FORBIDDEN");
  validateArcCloneConfig(config,"research_experiment");
  std::ifstream input(config.events_path);require(input.good(),"INPUT_OPEN");
  std::string line;require(static_cast<bool>(std::getline(input,line)),"MISSING_HEADER");
  const std::vector<std::string> expected={"schema_version","sequence_id","block_id","endpoint_id","role",
    "source_time_s","source_time_bits_hex","replay_execution_time_s","actual_available_time_s",
    "availability_mode","epoch_index","endpoint_model_fingerprint"};
  require(split(line)==expected,"HEADER_CONTRACT_12_COLUMNS");
  std::vector<ArcSourceEvent> events;
  while(std::getline(input,line)) {
    require(!line.empty(),"EMPTY_ROW");const auto x=split(line);
    require(x.size()==12 && x[0]=="1","SCHEMA_OR_COLUMN_COUNT");
    require(x[8].empty(),"ACTUAL_AVAILABLE_FIELD_MUST_BE_EMPTY");
    ArcSourceEvent e;e.sequence_id=x[1];e.block_id=x[2];e.endpoint_id=x[3];e.role=x[4];
    e.source_time=number(x[5]);e.source_time_bits_hex=x[6];e.replay_time=number(x[7]);
    e.availability_mode=x[9];e.epoch_index=integer(x[10]);e.endpoint_model_fingerprint=x[11];
    events.push_back(e);
  }
  require(!input.bad(),"INPUT_READ_ERROR");validateArcSourceEvents(events);return events;
}
}  // namespace legsa_v23_port_core
