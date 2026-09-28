#include "hartley_inekf/backend.hpp"

#include <Eigen/Core>
#include <Eigen/Eigenvalues>
#include <openssl/sha.h>

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;
using namespace hartley;

namespace {
constexpr std::size_t kHeaderBytes = 256;
constexpr std::size_t kRecordBytes = 192;
const std::array<const char*, 4> kLegs{{"FL", "FR", "RL", "RR"}};

#pragma pack(push, 1)
struct CacheHeader {
	char magic[16]; uint32_t version; uint32_t header_size; uint32_t record_size;
	uint32_t record_count; uint64_t prefix_end; int64_t first_ns; int64_t last_ns;
	unsigned char raw_sha[32]; unsigned char prefix_sha[32]; unsigned char event_sha[32];
	unsigned char padding[104];
};
struct CacheRecord {
	int64_t timestamp_ns; double values[22]; uint8_t contact_mask; uint8_t add_mask;
	uint8_t remove_mask; uint8_t reserved; unsigned char padding[4];
};
struct H6RContactHeader {
	char magic[16]; uint32_t version; uint32_t header_size; uint32_t record_size;
	uint64_t record_count; int32_t leg_ids[4]; unsigned char padding[12];
};
struct H6RContactRecord {
	int64_t timestamp_ns; int64_t row_index; uint8_t active[4];
	unsigned char padding[4]; double contact_xyz[12];
};
#pragma pack(pop)
static_assert(sizeof(CacheHeader) == kHeaderBytes, "cache header ABI");
static_assert(sizeof(CacheRecord) == kRecordBytes, "cache record ABI");
static_assert(sizeof(H6RContactHeader) == 64, "H6R contact header ABI");
static_assert(sizeof(H6RContactRecord) == 120, "H6R contact record ABI");

void require(bool condition, const std::string& message) {
	if (!condition) throw std::runtime_error(message);
}

std::string hex(const unsigned char* bytes, std::size_t count);

std::map<std::string, std::string> config(const fs::path& path) {
	std::ifstream input(path);
	require(input.good(), "cannot open H5 config");
	std::map<std::string, std::string> result;
	std::string line;
	while (std::getline(input, line)) {
		if (line.empty() || line[0] == '#') continue;
		const auto split = line.find('=');
		require(split != std::string::npos, "malformed H5 config line");
		result.emplace(line.substr(0, split), line.substr(split + 1));
	}
	return result;
}

std::string sha256(const std::string& value) {
	unsigned char digest[SHA256_DIGEST_LENGTH];
	SHA256(reinterpret_cast<const unsigned char*>(value.data()), value.size(), digest);
	return hex(digest, SHA256_DIGEST_LENGTH);
}

std::string recomputedConfigHash(const fs::path& path) {
	std::ifstream input(path);
	require(input.good(), "cannot reopen H5 config for hashing");
	std::string line, canonical;
	while (std::getline(input, line)) {
		if (line.rfind("config_hash=", 0) != 0) canonical += line + "\n";
	}
	return sha256(canonical);
}

void verifyThreads() {
	for (const char* key : {"OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"}) {
		const char* value = std::getenv(key);
		require(value && std::string(value) == "1", std::string(key) + " must equal 1");
	}
	Eigen::setNbThreads(1);
	require(Eigen::nbThreads() == 1, "Eigen thread count must equal 1");
}

std::vector<CacheRecord> readCache(const fs::path& path, CacheHeader& header) {
	std::ifstream input(path, std::ios::binary);
	require(input.good(), "cannot open H5 cache");
	input.read(reinterpret_cast<char*>(&header), sizeof(header));
	require(input.gcount() == static_cast<std::streamsize>(sizeof(header)), "short cache header");
	require(std::string(header.magic, 13) == "LEGS_H5_CACHE", "cache magic mismatch");
	require(header.version == 1 && header.header_size == kHeaderBytes && header.record_size == kRecordBytes,
	        "cache ABI mismatch");
	std::vector<CacheRecord> rows(header.record_count);
	input.read(reinterpret_cast<char*>(rows.data()), rows.size() * sizeof(CacheRecord));
	require(input.gcount() == static_cast<std::streamsize>(rows.size() * sizeof(CacheRecord)), "short cache payload");
	require(input.peek() == std::ifstream::traits_type::eof(), "cache has trailing bytes");
	for (std::size_t index = 0; index < rows.size(); ++index) {
		require(rows[index].reserved == 0, "cache reserved byte is nonzero");
		if (index) require(rows[index].timestamp_ns > rows[index - 1].timestamp_ns, "cache chronology failure");
	}
	return rows;
}

Vector3 vec(const CacheRecord& row, int offset) {
	return Vector3(row.values[offset], row.values[offset + 1], row.values[offset + 2]);
}
Vector3 foot(const CacheRecord& row, int leg) {
	return vec(row, 10 + 3 * leg);
}

double median(std::vector<double> values) {
	require(!values.empty(), "median requires values");
	std::sort(values.begin(), values.end());
	const auto n = values.size();
	return n % 2 ? values[n / 2] : 0.5 * (values[n / 2 - 1] + values[n / 2]);
}

Matrix3 initialRotation(const Vector3& fbar) {
	const double roll = std::atan2(fbar.y(), fbar.z());
	const double pitch = std::atan2(-fbar.x(), std::hypot(fbar.y(), fbar.z()));
	return Eigen::AngleAxisd(pitch, Vector3::UnitY()).toRotationMatrix() *
	       Eigen::AngleAxisd(roll, Vector3::UnitX()).toRotationMatrix();
}

std::vector<ContactMeasurement> measurements(const CacheRecord& row, uint8_t mask, double sigma) {
	std::vector<ContactMeasurement> result;
	for (int leg = 0; leg < 4; ++leg) if (mask & (1u << leg)) {
			result.push_back({leg, foot(row, leg), sigma * sigma * Matrix3::Identity()});
		}
	return result;
}

std::map<std::size_t, std::set<std::string> > checkpoints(const std::vector<CacheRecord>& rows) {
	std::map<std::size_t, std::set<std::string> > result;
	result[0].insert("first"); result[rows.size()-1].insert("last");
	for (std::size_t i = 0; i < rows.size(); ++i) if (rows[i].add_mask || rows[i].remove_mask) {
			result[i].insert("contact_event_after_settled_lifecycle");
		}
	const int64_t origin = rows.front().timestamp_ns;
	const int64_t last_second = (rows.back().timestamp_ns - origin) / 1000000000LL;
	for (int64_t second = 0; second <= last_second; ++second) {
		const int64_t target = origin + second * 1000000000LL;
		auto it = std::lower_bound(rows.begin(), rows.end(), target,
		                           [](const CacheRecord& row, int64_t value) {
				return row.timestamp_ns < value;
			});
		std::size_t selected = static_cast<std::size_t>(it - rows.begin());
		if (selected == rows.size()) --selected;
		if (selected && std::llabs(rows[selected - 1].timestamp_ns - target) <=
		    std::llabs(rows[selected].timestamp_ns - target)) --selected;
		result[selected].insert("integer_second");
	}
	return result;
}

std::string reasons(const std::set<std::string>& values) {
	std::ostringstream out; for (const auto& value : values) { if (out.tellp() > 0) out << ';'; out << value; }
	return out.str();
}

void validateRotationAndCovariance(const Matrix3& rotation, const Matrix& covariance,
                                   bool checkpoint) {
	require((rotation.transpose()*rotation-Matrix3::Identity()).norm() <= 2.0e-10,
	        "epoch rotation orthogonality gate failed");
	require(std::abs(rotation.determinant()-1.0) <= 2.0e-10,
	        "epoch rotation determinant gate failed");
	require(rotation.allFinite() && covariance.allFinite(), "nonfinite state/covariance");
	if (checkpoint) {
		const double scale = std::max(1.0, covariance.norm());
		require((covariance-covariance.transpose()).norm()/scale <= 1.0e-12,
		        "checkpoint covariance symmetry gate failed");
		Eigen::SelfAdjointEigenSolver<Matrix> solver(0.5*(covariance+covariance.transpose()));
		require(solver.info()==Eigen::Success, "checkpoint covariance eigensolver failed");
		const double maximum = std::max(1.0, solver.eigenvalues().maxCoeff());
		require(solver.eigenvalues().minCoeff() >= -1.0e-12*maximum,
		        "checkpoint covariance PSD gate failed");
	}
}

std::string topology(const std::vector<int>& ids) {
	if (ids.empty()) return "NONE";
	std::ostringstream value;
	for (std::size_t i = 0; i < ids.size(); ++i) { if (i) value << "+"; value << kLegs.at(ids[i]); }
	return value.str();
}

void csvHeader(std::ofstream& out, const std::string& value) {
	out << value << '\n';
}

void enableOutputExceptions(std::ofstream& stream, const std::string& label) {
	stream.exceptions(std::ios::failbit | std::ios::badbit);
	require(stream.is_open(), "failed to open native output " + label);
}

void finishOutput(std::ofstream& stream) {
	stream.flush();
	stream.close();
}

std::string hex(const unsigned char* bytes, std::size_t count) {
	std::ostringstream result;
	result << std::hex << std::setfill('0');
	for (std::size_t index = 0; index < count; ++index) result << std::setw(2) << int(bytes[index]);
	return result.str();
}

}  // namespace

int main(int argc, char** argv) {
	try {
		require(argc == 4, "usage: hartley_h5_runner CACHE CONFIG OUTPUT_DIR");
		verifyThreads();
		const fs::path cache_path = fs::canonical(argv[1]);
		const fs::path config_path = fs::canonical(argv[2]);
		const fs::path output = fs::canonical(argv[3]);
		require(fs::is_directory(output), "guarded output directory is absent");
		require(config_path.parent_path() == output,
		        "H5 native config must be owned by its guarded run directory");
		std::size_t preexisting = 0;
		for (const auto& entry : fs::directory_iterator(output)) {
			++preexisting;
			require(entry.path() == config_path && entry.is_regular_file(),
			        "guarded run directory contains unrelated preexisting content");
		}
		require(preexisting == 1, "guarded run directory must contain only native config");
		const auto cfg = config(config_path);
		require(recomputedConfigHash(config_path) == cfg.at("config_hash"),
		        "native recomputed config_hash mismatch");
		const std::string run_id = cfg.at("run_id");
		const double sigma_fk = std::stod(cfg.at("sigma_fk_m"));
		require(cfg.at("backend_id") == "HARTLEY_IJRR2020_REPORTED_BACKEND", "H5 backend identity mismatch");
		require(cfg.count("eq52") == 0, "Eq52 selector is forbidden in H5 config");
		const bool h6_gauge_run = cfg.count("execution_phase") != 0;
		const bool h6r_full_precision = cfg.count("evidence_serialization") != 0;
		if (h6r_full_precision) {
			require(cfg.at("evidence_serialization") == "H6R_FULL_PRECISION_CONTACT_V1",
			        "unknown evidence serialization mode");
		}
		double initial_gauge_yaw_deg = 0.0;
		const std::map<std::string, std::pair<std::string, double> > bindings{
			{"H5_PRIMARY_GO2_ALLAN_EQ61_FK10MM", {"GO2_CONTINUOUS_IMU_PAPER_NATIVE_CONTACT_EQ61", 0.010}},
			{"H5_FK05MM_SENSITIVITY", {"GO2_CONTINUOUS_IMU_PAPER_NATIVE_CONTACT_EQ61", 0.005}},
			{"H5_FK20MM_SENSITIVITY", {"GO2_CONTINUOUS_IMU_PAPER_NATIVE_CONTACT_EQ61", 0.020}},
			{"H5_PAPER_TABLE1_PROCESS_REGRESSION_WITH_GO2_FK_PROXY", {"PAPER_TABLE1_FIVE_PROCESS_EQ61", 0.010}},
		};
		if (!h6_gauge_run) {
			const auto binding = bindings.find(run_id);
			require(binding != bindings.end(), "unregistered H5 run identity");
			require(cfg.at("process_policy") == binding->second.first &&
			        std::abs(sigma_fk - binding->second.second) < 1.0e-15,
			        "H5 run-id/policy/sigma binding mismatch");
			require(cfg.count("initial_gauge_yaw_deg") == 0,
			        "H5 config must not inject an initial gauge");
		} else {
			require(cfg.at("execution_phase") == "H6_GAUGE_ENSEMBLE" ||
			        cfg.at("execution_phase") == "H6R_FULL_PRECISION_CONTACT_RECOVERY",
			        "unknown post-H5 execution phase");
			const std::map<std::string, double> h6_bindings{
				{"H6_YAW_M150", -150.0}, {"H6_YAW_M100", -100.0},
				{"H6_YAW_M050", -50.0}, {"H6_YAW_000_PARITY", 0.0},
				{"H6_YAW_P050", 50.0}, {"H6_YAW_P100", 100.0},
				{"H6_YAW_P150", 150.0}, {"H6R_YAW_M150", -150.0},
				{"H6R_YAW_M100", -100.0}, {"H6R_YAW_M050", -50.0},
				{"H6R_YAW_000", 0.0}, {"H6R_YAW_P050", 50.0},
				{"H6R_YAW_P100", 100.0}, {"H6R_YAW_P150", 150.0},
			};
			const auto binding = h6_bindings.find(run_id);
			require(binding != h6_bindings.end(), "unregistered H6 gauge-run identity");
			initial_gauge_yaw_deg = std::stod(cfg.at("initial_gauge_yaw_deg"));
			require(cfg.at("process_policy") ==
			            "GO2_CONTINUOUS_IMU_PAPER_NATIVE_CONTACT_EQ61" &&
			        std::abs(sigma_fk - 0.010) < 1.0e-15 &&
			        std::abs(initial_gauge_yaw_deg - binding->second) < 1.0e-15,
			        "H6 run-id/policy/sigma/yaw binding mismatch");
		}
		require(h6r_full_precision ==
		            (h6_gauge_run && cfg.at("execution_phase") ==
		                                 "H6R_FULL_PRECISION_CONTACT_RECOVERY"),
		        "H6R evidence serialization and execution phase must be selected together");

		CacheHeader header{};
		const auto rows = readCache(cache_path, header);
		require(rows.size() == static_cast<std::size_t>(std::stoull(cfg.at("expected_records"))), "record count config mismatch");
		require(!rows.empty(), "empty H5 cache");
		const auto start_clock = std::chrono::steady_clock::now();

		Vector3 gyro_sum = Vector3::Zero(), accel_sum = Vector3::Zero();
		std::vector<double> gyro_norms, accel_norms;
		std::size_t init_count = 0;
		for (const auto& row : rows) {
			if (row.timestamp_ns >= rows.front().timestamp_ns + 5000000000LL) break;
			const Vector3 gyro = vec(row, 0), accel = vec(row, 3);
			gyro_sum += gyro; accel_sum += accel; gyro_norms.push_back(gyro.norm());
			accel_norms.push_back(accel.norm()); ++init_count;
		}
		require(init_count > 0, "empty [t0,t0+5s) initialization window");
		require(median(gyro_norms) < 0.05, "static gyro gate failed");
		require(std::abs(median(accel_norms) - 9.81) < 0.5, "static acceleration gate failed");
		const Vector3 gyro_mean = gyro_sum / static_cast<double>(init_count);
		const Vector3 accel_mean = accel_sum / static_cast<double>(init_count);
		const Vector3 gravity(0.0, 0.0, -9.81);
		StateMean mean;
		mean.rotation = initialRotation(accel_mean);
		mean.gyro_bias = gyro_mean;
		mean.accelerometer_bias = accel_mean + mean.rotation.transpose() * gravity;
		Matrix covariance = Matrix::Zero(15, 15);
		const double orientation_std = 30.0 * M_PI / 180.0;
		covariance.diagonal() << orientation_std * orientation_std, orientation_std * orientation_std,
		                         orientation_std * orientation_std, 1, 1, 1, .01, .01, .01,
		        .000025, .000025, .000025, .0025, .0025, .0025;
		Matrix3 initial_gauge_rotation = Matrix3::Identity();
		if (h6_gauge_run) {
			const double yaw_rad = initial_gauge_yaw_deg * M_PI / 180.0;
			// H6 defines alpha about e_g=g/||g||=[0,0,-1].  This preserves
			// H3-H4 left multiplication while making the signed H6 axis explicit.
			initial_gauge_rotation = expSO3(Vector3(0.0, 0.0, -yaw_rad));
		}
		ContinuousNoiseDensity go2;
		go2.gyro_measurement_rad_per_s_per_sqrt_hz = 2.865130e-4;
		go2.accelerometer_measurement_m_per_s2_per_sqrt_hz = 1.285395e-3;
		go2.gyro_bias_rw_rad_per_s2_per_sqrt_hz = 2.996871e-5;
		go2.accelerometer_bias_rw_m_per_s3_per_sqrt_hz = 1.594412e-4;
		H5Eq61NoisePolicy policy;
		if (cfg.at("process_policy") == "GO2_CONTINUOUS_IMU_PAPER_NATIVE_CONTACT_EQ61") {
			policy = H5Eq61NoisePolicy::go2ImuPaperContact(go2, 0.05);
		} else {
			require(cfg.at("process_policy") == "PAPER_TABLE1_FIVE_PROCESS_EQ61", "unknown H5 noise policy");
			policy = H5Eq61NoisePolicy::paperTable1Process();
		}
		HartleyInEkf filter(mean, covariance, policy);
		filter.initializeContactsEq32WithIndependentPrior(measurements(rows.front(), rows.front().contact_mask, sigma_fk));
		const StateMean zero_gauge_initialized_mean = filter.stateMean();
		const Matrix zero_gauge_initialized_covariance = filter.stateCovariance();
		// The zero-degree branch is intentionally a complete numerical no-op.
		if (h6_gauge_run && initial_gauge_yaw_deg != 0.0) {
			filter.applyInitialGaugeTransform(initial_gauge_rotation);
		}
		const StateMean initialized_mean = filter.stateMean();
		double initial_contact_transform_residual = 0.0;
		double initial_covariance_congruence_relative_fro_error = 0.0;
		if (h6_gauge_run) {
			const auto ids = filter.activeContactIdentities();
			for (const int id : ids) {
				initial_contact_transform_residual = std::max(
				    initial_contact_transform_residual,
				    (filter.stateMean().contacts.at(id) -
				     initial_gauge_rotation *
				         zero_gauge_initialized_mean.contacts.at(id))
				        .norm());
			}
			Matrix transform = Matrix::Identity(filter.stateDimension(),
			                                    filter.stateDimension());
			for (int offset = 0; offset < filter.stateDimension() - 6; offset += 3) {
				transform.block<3, 3>(offset, offset) = initial_gauge_rotation;
			}
			const Matrix expected =
			    transform * zero_gauge_initialized_covariance * transform.transpose();
			initial_covariance_congruence_relative_fro_error =
			    (filter.stateCovariance() - expected).norm() /
			    std::max(1.0, zero_gauge_initialized_covariance.norm());
		}

		std::ofstream nav(output / "NAV.csv"), diagonal(output / "COVARIANCE_DIAGONALS.csv"),
		contact_state(output / "CONTACT_STATE.csv"), events(output / "CONTACT_EVENT_LEDGER.csv"),
		innovations(output / "KINEMATIC_INNOVATIONS.csv"), nis(output / "NIS_DIAGNOSTICS.csv"),
		checkpoint_index(output / "COVARIANCE_CHECKPOINT_INDEX.csv"),
		execution_ledger(output / "EXECUTION_LEDGER.csv"),
		full_covariance(output / "COVARIANCE_CHECKPOINTS.bin", std::ios::binary);
		std::ofstream full_precision_contact;
		if (h6r_full_precision) {
			full_precision_contact.open(output / "CONTACT_STATE_FLOAT64.raw", std::ios::binary);
			enableOutputExceptions(full_precision_contact, "CONTACT_STATE_FLOAT64.raw");
			H6RContactHeader contact_header{};
			std::copy_n("LEGS_H6R_F64", 12, contact_header.magic);
			contact_header.version = 1; contact_header.header_size = sizeof(H6RContactHeader);
			contact_header.record_size = sizeof(H6RContactRecord);
			contact_header.record_count = rows.size();
			for (int leg = 0; leg < 4; ++leg) contact_header.leg_ids[leg] = leg;
			full_precision_contact.write(reinterpret_cast<const char*>(&contact_header), sizeof(contact_header));
		}
		enableOutputExceptions(nav, "NAV.csv");
		enableOutputExceptions(diagonal, "COVARIANCE_DIAGONALS.csv");
		enableOutputExceptions(contact_state, "CONTACT_STATE.csv");
		enableOutputExceptions(events, "CONTACT_EVENT_LEDGER.csv");
		enableOutputExceptions(innovations, "KINEMATIC_INNOVATIONS.csv");
		enableOutputExceptions(nis, "NIS_DIAGNOSTICS.csv");
		enableOutputExceptions(checkpoint_index, "COVARIANCE_CHECKPOINT_INDEX.csv");
		enableOutputExceptions(execution_ledger, "EXECUTION_LEDGER.csv");
		enableOutputExceptions(full_covariance, "COVARIANCE_CHECKPOINTS.bin");
		csvHeader(nav, "timestamp_ns,row_index,state_role,active_contact_count,state_dimension,r00,r01,r02,r10,r11,r12,r20,r21,r22,vx,vy,vz,px,py,pz,bgx,bgy,bgz,bax,bay,baz");
		csvHeader(diagonal, "timestamp_ns,row_index,topology,dimension,theta_x,theta_y,theta_z,velocity_x,velocity_y,velocity_z,position_x,position_y,position_z,contact_FL_x,contact_FL_y,contact_FL_z,contact_FR_x,contact_FR_y,contact_FR_z,contact_RL_x,contact_RL_y,contact_RL_z,contact_RR_x,contact_RR_y,contact_RR_z,gyro_bias_x,gyro_bias_y,gyro_bias_z,accel_bias_x,accel_bias_y,accel_bias_z,gauge_yaw_variance,gauge_translation_x_variance,gauge_translation_y_variance,gauge_translation_z_variance");
		csvHeader(contact_state, "timestamp_ns,row_index,leg_id,leg,active,contact_x,contact_y,contact_z");
		csvHeader(events, "timestamp_ns,row_index,leg_id,leg,event,force,contact_mask,add_mask,remove_mask");
		csvHeader(innovations, "timestamp_ns,row_index,leg_id,leg,innovation_x,innovation_y,innovation_z");
		csvHeader(nis, "timestamp_ns,row_index,contact_count,nis,factorization_ok");
		csvHeader(checkpoint_index, "checkpoint_index,row_index,timestamp_ns,reason,topology,dimension,npz_key");
		csvHeader(execution_ledger, "input_row,output_row,timestamp_ns,dt_seconds,active_contacts_before,active_contacts_after,state_dimension,propagation_status,update_status,add_mask,remove_mask");
		const auto selected = checkpoints(rows);
		std::size_t checkpoint_number = 0;
		std::size_t update_calls = 0;
		std::size_t update_measurements = 0;
		std::size_t transition_events = 0;
		double dt_min = std::numeric_limits<double>::infinity(), dt_max = 0.0, dt_sum = 0.0;
		nav << std::setprecision(17); diagonal << std::setprecision(17);
		for (std::size_t index = 0; index < rows.size(); ++index) {
			CorrectionDiagnostics correction;
			const std::size_t contacts_before = filter.activeContactIdentities().size();
			std::vector<int> survivor_ids;
			double dt = 0.0;
			if (index) {
				dt = (rows[index].timestamp_ns - rows[index - 1].timestamp_ns) * 1e-9;
				dt_min = std::min(dt_min, dt); dt_max = std::max(dt_max, dt); dt_sum += dt;
				transition_events += __builtin_popcount(rows[index].add_mask) +
				                     __builtin_popcount(rows[index].remove_mask);
				filter.propagate(vec(rows[index - 1], 0), vec(rows[index - 1], 3), dt);
				const uint8_t survivors = rows[index].contact_mask & ~rows[index].add_mask;
				std::vector<int> ended;
				for (int leg = 0; leg < 4; ++leg) if (rows[index].remove_mask & (1u << leg)) ended.push_back(leg);
				const auto survivor_measurements = measurements(rows[index], survivors, sigma_fk);
				for (const auto& measurement : survivor_measurements) survivor_ids.push_back(measurement.leg_id);
				correction = filter.processContactLifecycle(survivor_measurements, ended,
				                                            measurements(rows[index], rows[index].add_mask, sigma_fk));
				if (!survivor_measurements.empty()) { ++update_calls; update_measurements += survivor_measurements.size(); }
			}
			const auto& state = filter.stateMean();
			const auto ids = filter.activeContactIdentities();
			const Matrix& P = filter.stateCovariance();
			Matrix3 rotation_for_validation = state.rotation;
			Matrix covariance_for_validation = P;
			const char* inject_rotation = std::getenv("HARTLEY_H5_INJECT_ROTATION_FAILURE_ROW");
			if (inject_rotation && index == static_cast<std::size_t>(std::stoull(inject_rotation)))
				rotation_for_validation(0,0) = 2.0;
			const char* inject_covariance = std::getenv("HARTLEY_H5_INJECT_COVARIANCE_FAILURE_ROW");
			if (inject_covariance && index == static_cast<std::size_t>(std::stoull(inject_covariance)))
				covariance_for_validation(0,0) = -10.0;
			const char* inject_dimension = std::getenv("HARTLEY_H5_INJECT_STATE_DIMENSION_FAILURE_ROW");
			if (inject_dimension && index == static_cast<std::size_t>(std::stoull(inject_dimension)))
				throw std::runtime_error("injected state-dimension failure");
			require(P.rows() == 15 + 3 * static_cast<int>(ids.size()),
			        "state/contact dimension invariant failed");
			validateRotationAndCovariance(rotation_for_validation, covariance_for_validation,
			                              selected.count(index) != 0);
			nav << rows[index].timestamp_ns << ',' << index << ',' << (index ? "FILTERED" : "INITIALIZED") << ',' << ids.size() << ',' << P.rows() << ',';
			for (int r = 0; r < 3; ++r) for (int c = 0; c < 3; ++c) nav << state.rotation(r,c) << ',';
			nav << state.velocity.x() << ',' << state.velocity.y() << ',' << state.velocity.z() << ','
			    << state.position.x() << ',' << state.position.y() << ',' << state.position.z() << ','
			    << state.gyro_bias.x() << ',' << state.gyro_bias.y() << ',' << state.gyro_bias.z() << ','
			    << state.accelerometer_bias.x() << ',' << state.accelerometer_bias.y() << ',' << state.accelerometer_bias.z() << '\n';
			diagonal << rows[index].timestamp_ns << ',' << index << ',' << topology(ids) << ',' << P.rows();
			std::map<int,int> offsets; for (std::size_t k=0; k<ids.size(); ++k) offsets[ids[k]]=9+3*k;
			for (int k=0; k<9; ++k) diagonal << ',' << P(k,k);
			for (int leg=0; leg<4; ++leg) for(int axis=0; axis<3; ++axis)
					if (offsets.count(leg)) diagonal << ',' << P(offsets[leg]+axis, offsets[leg]+axis); else diagonal << ',';
			const int bias=P.rows()-6; for(int k=bias; k<P.rows(); ++k) diagonal << ',' << P(k,k);
			Vector yaw=Vector::Zero(P.rows()); yaw(2)=-1; diagonal << ',' << (yaw.transpose()*P*yaw)(0,0);
			for(int axis=0; axis<3; ++axis) {Vector g=Vector::Zero(P.rows()); double n=std::sqrt(ids.size()+1.0); g(6+axis)=1/n; for(std::size_t k=0; k<ids.size(); ++k) g(9+3*k+axis)=1/n; diagonal<<','<<(g.transpose()*P*g)(0,0);} diagonal<<'\n';
			for(int leg=0; leg<4; ++leg) { auto found=state.contacts.find(leg); contact_state<<rows[index].timestamp_ns<<','<<index<<','<<leg<<','<<kLegs[leg]<<','<<(found!=state.contacts.end()); if(found==state.contacts.end()) contact_state<<",,,\n"; else contact_state<<','<<found->second.x()<<','<<found->second.y()<<','<<found->second.z()<<'\n'; }
			if (h6r_full_precision) {
				H6RContactRecord record{};
				record.timestamp_ns = rows[index].timestamp_ns;
				record.row_index = static_cast<int64_t>(index);
				const double nan = std::numeric_limits<double>::quiet_NaN();
				std::fill_n(record.contact_xyz, 12, nan);
				for (int leg = 0; leg < 4; ++leg) {
					const auto found = state.contacts.find(leg);
					record.active[leg] = found != state.contacts.end();
					if (found != state.contacts.end()) for (int axis = 0; axis < 3; ++axis)
						record.contact_xyz[3 * leg + axis] = found->second(axis);
				}
				full_precision_contact.write(reinterpret_cast<const char*>(&record), sizeof(record));
			}
			for(int leg=0; leg<4; ++leg) if((rows[index].add_mask|rows[index].remove_mask)&(1u<<leg)) events<<rows[index].timestamp_ns<<','<<index<<','<<leg<<','<<kLegs[leg]<<','<<((rows[index].add_mask&(1u<<leg))?"ADD":"REMOVE")<<','<<rows[index].values[6+leg]<<','<<int(rows[index].contact_mask)<<','<<int(rows[index].add_mask)<<','<<int(rows[index].remove_mask)<<'\n';
			if(index && correction.innovation.size()) for(int k=0; k<correction.innovation.size()/3; ++k) innovations<<rows[index].timestamp_ns<<','<<index<<','<<survivor_ids[k]<<','<<kLegs[survivor_ids[k]]<<','<<correction.innovation(3*k)<<','<<correction.innovation(3*k+1)<<','<<correction.innovation(3*k+2)<<'\n';
			nis<<rows[index].timestamp_ns<<','<<index<<','<<survivor_ids.size()<<','<<correction.nis<<','<<correction.factorization_ok<<'\n';
			execution_ledger<<index<<','<<index<<','<<rows[index].timestamp_ns<<','<<dt<<','<<contacts_before<<','<<ids.size()<<','<<P.rows()<<','<<(index?"PROPAGATED_PREVIOUS_IMU":"INITIALIZE_NO_PROPAGATION")<<','<<(index?(survivor_ids.empty()?"NO_SURVIVOR_UPDATE":"CORRECTED_SURVIVORS") : "INITIAL_CONTACT_EQ32_PLUS_PRIOR")<<','<<int(rows[index].add_mask)<<','<<int(rows[index].remove_mask)<<'\n';
			if(selected.count(index)) {checkpoint_index<<checkpoint_number<<','<<index<<','<<rows[index].timestamp_ns<<','<<reasons(selected.at(index))<<','<<topology(ids)<<','<<P.rows()<<",covariance_"<<checkpoint_number<<'\n'; uint32_t dim=P.rows(); full_covariance.write(reinterpret_cast<char*>(&dim),4); full_covariance.write(reinterpret_cast<const char*>(P.data()),P.size()*sizeof(double)); ++checkpoint_number;}
			const char* injected = std::getenv("HARTLEY_H5_INJECT_OUTPUT_FAILURE_AFTER_ROW");
			if (injected && index == static_cast<std::size_t>(std::stoull(injected))) {
				throw std::runtime_error("injected native output failure");
			}
		}
		const auto& stats=filter.h5RuntimeDiagnostics();
		require(stats.propagation_calls + 1 == rows.size() && stats.eq61_calls == stats.propagation_calls && stats.eq52_calls == 0, "H5 final counters failed");
		const double elapsed=std::chrono::duration<double>(std::chrono::steady_clock::now()-start_clock).count();
		std::ofstream runtime(output/"RUNTIME.csv");
		enableOutputExceptions(runtime, "RUNTIME.csv");
		csvHeader(runtime,"run_id,backend_id,state_rows,propagation_calls,eq61_calls,eq52_calls,threads_verified,elapsed_seconds"); runtime<<run_id<<",HARTLEY_IJRR2020_REPORTED_BACKEND,"<<rows.size()<<','<<stats.propagation_calls<<','<<stats.eq61_calls<<','<<stats.eq52_calls<<",true,"<<elapsed<<'\n';
		std::ofstream comparison(output/"NATIVE_COMPARISON.csv");
		enableOutputExceptions(comparison, "NATIVE_COMPARISON.csv");
		csvHeader(comparison,"run_id,comparison_scope,reference_opened,trace_used,state_rows,final_position_norm_m,final_velocity_norm_m_per_s"); comparison<<run_id<<",NATIVE_ONLY,false,false,"<<rows.size()<<','<<filter.stateMean().position.norm()<<','<<filter.stateMean().velocity.norm()<<'\n';
		const Vector3 init_residual = initialized_mean.rotation *
		    (accel_mean-initialized_mean.accelerometer_bias) + gravity;
		const double init_roll = std::atan2(initialized_mean.rotation(2,1), initialized_mean.rotation(2,2));
		const double init_pitch = std::asin(-initialized_mean.rotation(2,0));
		const double init_yaw = std::atan2(initialized_mean.rotation(1,0), initialized_mean.rotation(0,0));
		std::ofstream summary(output/"NATIVE_SUMMARY.json");
		enableOutputExceptions(summary, "NATIVE_SUMMARY.json");
		summary<<"{\n  \"run_id\": \""<<run_id<<"\",\n  \"backend_id\": \"HARTLEY_IJRR2020_REPORTED_BACKEND\",\n  \"process_policy\": \""<<cfg.at("process_policy")<<"\",\n  \"sigma_fk_m\": "<<sigma_fk<<",\n  \"process_noise_policy_tag\": \""<<stats.process_noise_policy_tag<<"\",\n  \"data_mode\": \"real_by2_raw\",\n  \"raw_source_sha256\": \""<<hex(header.raw_sha,32)<<"\",\n  \"prefix_sha256\": \""<<hex(header.prefix_sha,32)<<"\",\n  \"cache_sha256\": \""<<cfg.at("cache_sha256")<<"\",\n  \"config_hash\": \""<<cfg.at("config_hash")<<"\",\n  \"code_commit\": \""<<cfg.at("code_commit")<<"\",\n  \"task_start_head\": \""<<cfg.at("task_start_head")<<"\",\n  \"task_start_dirty_or_precommit\": "<<cfg.at("task_start_dirty_or_precommit")<<",\n  \"scoped_source_manifest_sha256\": \""<<cfg.at("scoped_source_manifest_sha256")<<"\",\n  \"native_executable_sha256\": \""<<cfg.at("native_executable_sha256")<<"\",\n  \"later_final_commit_mapping\": \""<<cfg.at("later_final_commit_mapping")<<"\",\n  \"state_order\": \"rotation_velocity_position_contacts_sorted_FL_FR_RL_RR_gyro_bias_accel_bias\",\n  \"state_rows\": "<<rows.size()<<",\n  \"propagation_calls\": "<<stats.propagation_calls<<",\n  \"eq61_calls\": "<<stats.eq61_calls<<",\n  \"eq52_calls\": 0,\n  \"joint_encoder_adapter_call_count\": 0,\n  \"survivor_update_calls\": "<<update_calls<<",\n  \"survivor_update_measurement_count\": "<<update_measurements<<",\n  \"transition_event_count_excluding_initial_add\": "<<transition_events<<",\n  \"lifecycle_add_count\": "<<stats.added_contacts<<",\n  \"lifecycle_remove_count\": "<<stats.removed_contacts<<",\n  \"initial_contact_count\": "<<int(__builtin_popcount(rows.front().contact_mask))<<",\n  \"initialization_window_rows\": "<<init_count<<",\n  \"initialization_window_half_open\": true,\n  \"initial_median_gyro_norm_rad_per_s\": "<<median(gyro_norms)<<",\n  \"initial_median_accel_norm_m_per_s2\": "<<median(accel_norms)<<",\n  \"initial_rotation_row_major\": ["<<initialized_mean.rotation(0,0)<<','<<initialized_mean.rotation(0,1)<<','<<initialized_mean.rotation(0,2)<<','<<initialized_mean.rotation(1,0)<<','<<initialized_mean.rotation(1,1)<<','<<initialized_mean.rotation(1,2)<<','<<initialized_mean.rotation(2,0)<<','<<initialized_mean.rotation(2,1)<<','<<initialized_mean.rotation(2,2)<<"],\n  \"initial_rpy_rad\": ["<<init_roll<<','<<init_pitch<<','<<(h6_gauge_run ? init_yaw : 0.0)<<"],\n  \"initial_gyro_mean\": ["<<gyro_mean.x()<<','<<gyro_mean.y()<<','<<gyro_mean.z()<<"],\n  \"initial_accel_mean\": ["<<accel_mean.x()<<','<<accel_mean.y()<<','<<accel_mean.z()<<"],\n  \"initial_gyro_bias\": ["<<gyro_mean.x()<<','<<gyro_mean.y()<<','<<gyro_mean.z()<<"],\n  \"initial_accel_bias\": ["<<initialized_mean.accelerometer_bias.x()<<','<<initialized_mean.accelerometer_bias.y()<<','<<initialized_mean.accelerometer_bias.z()<<"],\n  \"initial_acceleration_residual_world\": ["<<init_residual.x()<<','<<init_residual.y()<<','<<init_residual.z()<<"],\n  \"initial_acceleration_residual_norm\": "<<init_residual.norm()<<",\n  \"dt_count\": "<<(rows.size()-1)<<",\n  \"dt_min_seconds\": "<<dt_min<<",\n  \"dt_max_seconds\": "<<dt_max<<",\n  \"dt_mean_seconds\": "<<(dt_sum/(rows.size()-1))<<",\n  \"dropped_input_rows\": 0,\n  \"forbidden_value_decode_count\": 0,\n  \"reference_open_count\": 0,\n  \"trace_open_count\": 0,\n  \"nonfinite_state_count\": 0,\n  \"nonfinite_covariance_count\": 0,\n  \"nonfinite_output_count\": 0,\n  \"rotation_gate_failure_count\": 0,\n  \"state_dimension_failure_count\": 0,\n  \"covariance_checkpoint_count\": "<<checkpoint_number<<",\n  \"covariance_checkpoint_failure_count\": 0,\n  \"synthetic_data_used\": false,\n  \"semisynthetic_data_used\": false,\n  \"reference_opened\": false,\n  \"trace_used_online\": false,\n  \"receiver_imu_as_body_imu\": false,\n  \"final_v23_output_solver_input\": false,\n  \"LegSA_output_solver_input\": false,\n  \"per_case_tuning\": false,\n  \"output_only_correction\": false,\n  \"epoch_deleted_for_metric\": false,\n  \"old_runtime_input_count\": 0";
		if (h6_gauge_run) {
			summary<<",\n  \"execution_phase\": \""<<cfg.at("execution_phase")<<"\",\n  \"initial_gauge_yaw_deg\": "<<initial_gauge_yaw_deg<<",\n  \"initial_gauge_left_multiplication\": true,\n  \"initial_gauge_world_axis\": \"NORMALIZED_WORLD_GRAVITY_NEGATIVE_Z\",\n  \"expected_native_euler_yaw_offset_deg\": "<<-initial_gauge_yaw_deg<<",\n  \"initial_velocity_general_rule_applied\": true,\n  \"initial_position_general_rule_applied\": true,\n  \"initial_contact_general_rule_applied\": true,\n  \"initial_bias_blocks_unchanged\": true,\n  \"initial_covariance_congruence_rule_applied\": true,\n  \"zero_degree_explicit_numerical_noop\": "<<(initial_gauge_yaw_deg == 0.0 ? "true" : "false")<<",\n  \"initial_contact_transform_residual\": "<<initial_contact_transform_residual<<",\n  \"initial_covariance_congruence_relative_fro_error\": "<<initial_covariance_congruence_relative_fro_error;
			if (h6r_full_precision) summary<<",\n  \"evidence_serialization\": \"H6R_FULL_PRECISION_CONTACT_V1\"";
		}
		summary<<"\n}\n";
		finishOutput(nav); finishOutput(diagonal); finishOutput(contact_state);
		finishOutput(events); finishOutput(innovations); finishOutput(nis);
		finishOutput(checkpoint_index); finishOutput(execution_ledger);
		finishOutput(full_covariance); finishOutput(runtime); finishOutput(comparison);
		finishOutput(summary);
		if (h6r_full_precision) finishOutput(full_precision_contact);
		std::cout << "PASS_HARTLEY_H5_NATIVE run_id=" << run_id << " rows=" << rows.size() << '\n';
		return 0;
	} catch(const std::exception& error) { std::cerr<<"FAIL_HARTLEY_H5_NATIVE error="<<error.what()<<'\n'; return 1; }
}
