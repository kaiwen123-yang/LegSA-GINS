// HX-02E: binary input decoding, initial conditions, official public API, NAV I/O.
// No propagation, correction, contact augmentation or covariance-update mathematics.
#include "InEKF.h"
#include <Eigen/Geometry>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

struct Record {
    std::int64_t timestamp;
    Eigen::Matrix<double,6,1> imu;
    Eigen::Vector3d foot[4];
    unsigned char contacts;
};

static void require(bool ok, const std::string& why) {
    if (!ok) throw std::runtime_error(why);
}

template<class T> static T decode(const char* p) {
    T value;
    std::memcpy(&value, p, sizeof(value));
    return value;
}

static std::vector<Record> read_cache(const std::string& path) {
    std::ifstream input(path, std::ios::binary);
    require(input.good(), "cannot read input cache");
    char header[256];
    input.read(header, 256);
    require(input.gcount() == 256 && std::memcmp(header, "LEGS_H5_CACHE", 13) == 0, "cache header");
    require(decode<uint32_t>(header+16) == 1 && decode<uint32_t>(header+20) == 256 && decode<uint32_t>(header+24) == 192, "cache schema");
    const auto count = decode<uint32_t>(header+28);
    require(count > 1 && count < 10000000, "cache count");
    std::vector<Record> rows;
    rows.reserve(count);
    for (uint32_t i=0; i<count; ++i) {
        char bytes[192];
        input.read(bytes, 192);
        require(input.gcount() == 192, "cache truncated");
        Record r;
        r.timestamp = decode<int64_t>(bytes);
        for (int j=0;j<6;++j) r.imu(j) = decode<double>(bytes+8+8*j);
        for (int leg=0;leg<4;++leg)
            for (int j=0;j<3;++j) r.foot[leg](j) = decode<double>(bytes+8+8*(10+3*leg+j));
        r.contacts = static_cast<unsigned char>(bytes[184]);
        require(bytes[187] == 0 && r.contacts < 16 && r.imu.allFinite(), "invalid input");
        for (auto p:r.foot) require(p.allFinite(), "nonfinite foot");
        require(rows.empty() || r.timestamp > rows.back().timestamp, "non-increasing time");
        rows.push_back(r);
    }
    require(input.peek() == std::ifstream::traits_type::eof(), "cache trailing bytes");
    require(rows.front().timestamp == decode<int64_t>(header+40) && rows.back().timestamp == decode<int64_t>(header+48), "cache time endpoints");
    return rows;
}

static void contact_observation(inekf::InEKF& filter, const Record& row, double fk_var, double rotation_var) {
    std::vector<std::pair<int,bool>> flags;
    inekf::vectorKinematics observations;
    Eigen::Matrix<double,6,6> covariance = Eigen::Matrix<double,6,6>::Zero();
    covariance.block<3,3>(0,0) = rotation_var * Eigen::Matrix3d::Identity();
    covariance.block<3,3>(3,3) = fk_var * Eigen::Matrix3d::Identity();
    for (int leg=0;leg<4;++leg) {
        flags.emplace_back(leg, (row.contacts & (1 << leg)) != 0);
        Eigen::Matrix4d pose = Eigen::Matrix4d::Identity();
        pose.block<3,1>(0,3) = row.foot[leg];
        observations.emplace_back(leg, pose, covariance);
    }
    filter.setContacts(flags);
    filter.CorrectKinematics(observations);
}

int main(int argc, char** argv) {
    try {
        require(argc == 4, "usage: driver CACHE CONFIG NAV");
        std::map<std::string,double> cfg;
        std::ifstream config(argv[2]);
        require(config.good(), "config unreadable");
        std::string key; double value;
        while (config >> key >> value) require(cfg.emplace(key,value).second, "duplicate config key");
        require(config.eof(), "invalid config token");
        auto get = [&](const std::string& k) {return cfg.at(k);};
        const auto rows = read_cache(argv[1]);
        Eigen::Vector3d acceleration = Eigen::Vector3d::Zero();
        size_t init_count=0;
        for (const auto& r:rows) {
            if ((r.timestamp-rows.front().timestamp)*1e-9 >= get("initial_seconds")) break;
            acceleration += r.imu.tail<3>(); ++init_count;
        }
        require(init_count > 0, "empty initialization");
        acceleration /= init_count;
        require(acceleration.norm() > 1e-9, "undefined gravity direction");
        const double roll = std::atan2(acceleration.y(), acceleration.z());
        const double pitch = std::atan2(-acceleration.x(), std::hypot(acceleration.y(),acceleration.z()));
        inekf::RobotState state;
        state.setRotation((Eigen::AngleAxisd(pitch,Eigen::Vector3d::UnitY()) * Eigen::AngleAxisd(roll,Eigen::Vector3d::UnitX())).toRotationMatrix());
        state.setVelocity(Eigen::Vector3d::Zero());
        state.setPosition(Eigen::Vector3d::Zero());
        state.setGyroscopeBias(Eigen::Vector3d::Zero());
        state.setAccelerometerBias(Eigen::Vector3d::Zero());
        auto initial_covariance = [&](int dimensions) {
            Eigen::MatrixXd P = Eigen::MatrixXd::Zero(dimensions,dimensions);
            const std::string names[] = {"initial_rotation_std_rad","initial_velocity_std","initial_position_std"};
            for (int block=0;block<3;++block) P.block<3,3>(3*block,3*block) = std::pow(get(names[block]),2)*Eigen::Matrix3d::Identity();
            for (int k=9;k<dimensions-6;k+=3) P.block<3,3>(k,k) = std::pow(get("initial_foot_std"),2)*Eigen::Matrix3d::Identity();
            P.block<3,3>(dimensions-6,dimensions-6) = std::pow(get("initial_gyro_bias_std"),2)*Eigen::Matrix3d::Identity();
            P.block<3,3>(dimensions-3,dimensions-3) = std::pow(get("initial_accel_bias_std"),2)*Eigen::Matrix3d::Identity();
            return P;
        };
        if (get("paper_initial_covariance") != 0) state.setP(initial_covariance(15));
        inekf::NoiseParams noise;
        noise.setGyroscopeNoise(get("gyro_std"));
        noise.setAccelerometerNoise(get("accel_std"));
        noise.setGyroscopeBiasNoise(get("gyro_bias_std"));
        noise.setAccelerometerBiasNoise(get("accel_bias_std"));
        noise.setContactNoise(get("contact_std"));
        inekf::InEKF filter(state,noise);
        contact_observation(filter,rows.front(),get("fk_translation_variance"),get("fk_rotation_variance"));
        if (get("paper_initial_covariance") != 0) {
            // Initial covariance configuration only, including contacts present at t0.
            state = filter.getState();
            state.setP(initial_covariance(state.dimP()));
            filter.setState(state);
        }
        std::ofstream out(argv[3]);
        require(out.good(), "NAV unwritable");
        out << "timestamp_ns,row_index,r00,r01,r02,r10,r11,r12,r20,r21,r22,vx,vy,vz,px,py,pz,roll_deg,pitch_deg,yaw_deg,bgx,bgy,bgz,bax,bay,baz,active_contact_count,state_dimension\n" << std::setprecision(17);
        std::cout << std::setprecision(17) << "initial_count=" << init_count << " initial_roll_rad=" << roll << " initial_pitch_rad=" << pitch << "\n" << filter.getNoiseParams() << filter.getState() << std::endl;
        for (size_t i=0;i<rows.size();++i) {
            if (i) {
                const double dt=(rows[i].timestamp-rows[i-1].timestamp)*1e-9;
                filter.Propagate(rows[i-1].imu,dt);
                contact_observation(filter,rows[i],get("fk_translation_variance"),get("fk_rotation_variance"));
            }
            state=filter.getState();
            const auto R=state.getRotation(); const auto v=state.getVelocity(); const auto p=state.getPosition();
            require(R.allFinite() && v.allFinite() && p.allFinite() && state.getTheta().allFinite() && state.getP().allFinite(), "ALGORITHM_FAILURE_DIVERGED: nonfinite state");
            const double degrees=180.0/std::acos(-1.0);
            out << rows[i].timestamp << ',' << i;
            for(int a=0;a<3;++a) for(int b=0;b<3;++b) out << ',' << R(a,b);
            for(int j=0;j<3;++j) out << ',' << v(j);
            for(int j=0;j<3;++j) out << ',' << p(j);
            out << ',' << std::atan2(R(2,1),R(2,2))*degrees << ',' << std::asin(std::max(-1.0,std::min(1.0,-R(2,0))))*degrees << ',' << std::atan2(R(1,0),R(0,0))*degrees;
            for(int j=0;j<3;++j) out << ',' << state.getGyroscopeBias()(j);
            for(int j=0;j<3;++j) out << ',' << state.getAccelerometerBias()(j);
            out << ',' << filter.getEstimatedContactPositions().size() << ',' << state.dimP() << '\n';
            if (p.norm()>get("max_displacement_m") || v.norm()>get("max_speed_mps") || std::abs(p.z())>get("max_height_m")) {
                std::cerr << "ALGORITHM_FAILURE_DIVERGED at row " << i << '\n'; return 20;
            }
            if (i%10000==0) {out.flush(); std::cout << "rows=" << i+1 << '/' << rows.size() << std::endl;}
        }
        require(out.good(), "NAV write failed");
        std::cout << "COMPLETED rows=" << rows.size() << std::endl;
        return 0;
    } catch(const std::exception& e) {
        std::cerr << e.what() << std::endl;
        return std::string(e.what()).find("ALGORITHM_FAILURE_DIVERGED") == 0 ? 20 : 2;
    }
}
