// Thin C ABI for the pinned upstream OB_GINS PreintegrationEarth.
// Upstream is GPL-3.0-or-later; see the pinned checkout LICENSE and attribution.
// No upstream propagation, residual, covariance or Jacobian formula is replaced.
#include "src/preintegration/preintegration_earth.h"
#include <cmath>
#include <cstring>
#include <stdexcept>
#include <string>

namespace {
thread_local std::string last_error;
IntegrationState state(const double *x) {
    IntegrationState s{};
    s.p = Eigen::Map<const Vector3d>(x);
    s.q = Eigen::Map<const Quaterniond>(x + 3);
    s.q.normalize();
    s.v = Eigen::Map<const Vector3d>(x + 7);
    s.bg = Eigen::Map<const Vector3d>(x + 10);
    s.ba = Eigen::Map<const Vector3d>(x + 13);
    return s;
}
void pack(const IntegrationState &s, double *x) {
    std::memcpy(x, s.p.data(), 3 * sizeof(double));
    std::memcpy(x + 3, s.q.coeffs().data(), 4 * sizeof(double));
    std::memcpy(x + 7, s.v.data(), 3 * sizeof(double));
    std::memcpy(x + 10, s.bg.data(), 3 * sizeof(double));
    std::memcpy(x + 13, s.ba.data(), 3 * sizeof(double));
}
IMU imu(const double *x) {
    IMU u{};
    u.time=x[0]; u.dt=x[1];
    u.dtheta=Eigen::Map<const Vector3d>(x+2);
    u.dvel=Eigen::Map<const Vector3d>(x+5);
    return u;
}
class Bridge : public PreintegrationEarth {
public:
    Bridge(std::shared_ptr<IntegrationParameters> p, const IMU &seed,
           IntegrationState s, const double *noise_variance)
        : PreintegrationEarth(p, seed, s) {
        // Upstream has isotropic scalar parameters. Real Go2 calibration is
        // anisotropic: retain its per-axis densities without changing any
        // propagation algebra. Scalar settings reproduce upstream exactly.
        noise_.setZero();
        for(int i=0;i<12;++i) noise_(i,i)=noise_variance[i];
    }
    void diagnostics(double *cov, double *jac) const {
        Eigen::Map<Eigen::Matrix<double,15,15,Eigen::RowMajor>> c(cov), j(jac);
        c=covariance_; j=jacobian_;
    }
};
}
extern "C" {
const char *ob_error() { return last_error.c_str(); }
void *ob_create(const double *station, double gravity, double tau,
                const double *noise_variance, const double *initial,
                const double *seed, const double *samples, int count) {
    try {
        if(count<2 || !(tau>0) || !(gravity>0)) throw std::runtime_error("invalid preintegration inputs");
        auto p=std::make_shared<IntegrationParameters>();
        p->station=Eigen::Map<const Vector3d>(station); p->gravity=gravity;
        p->corr_time=tau;
        p->gyr_arw=std::sqrt(noise_variance[0]); p->acc_vrw=std::sqrt(noise_variance[3]);
        p->gyr_bias_std=std::sqrt(noise_variance[6]*tau/2);
        p->acc_bias_std=std::sqrt(noise_variance[9]*tau/2);
        auto *b=new Bridge(p,imu(seed),state(initial),noise_variance);
        for(int i=0;i<count;++i) {
            const IMU u=imu(samples+8*i);
            if(!(u.dt>0) || !u.dtheta.allFinite() || !u.dvel.allFinite()) {
                delete b; throw std::runtime_error("invalid IMU sample");
            }
            b->addNewImu(u);
        }
        return b;
    } catch(const std::exception &e) { last_error=e.what(); return nullptr; }
}
void ob_destroy(void *p) { delete static_cast<Bridge*>(p); }
int ob_predict(void *p, double *x) {
    try { pack(static_cast<Bridge*>(p)->currentState(),x); return 1; }
    catch(const std::exception &e) { last_error=e.what(); return 0; }
}
int ob_diagnostics(void *p, double *c, double *j) {
    try { static_cast<Bridge*>(p)->diagnostics(c,j); return 1; }
    catch(const std::exception &e) { last_error=e.what(); return 0; }
}
int ob_evaluate(void *p, const double *x0, const double *x1,
                double *r, double *jpose0, double *jmix0,
                double *jpose1, double *jmix1) {
    try {
        auto *b=static_cast<Bridge*>(p);
        const auto a=state(x0), c=state(x1);
        b->evaluate(a,c,r);
        if(jpose0) {
            b->residualJacobianPose0(a,c,jpose0); b->residualJacobianMix0(a,c,jmix0);
            b->residualJacobianPose1(a,c,jpose1); b->residualJacobianMix1(a,c,jmix1);
        }
        for(int i=0;i<15;++i) if(!std::isfinite(r[i])) throw std::runtime_error("nonfinite upstream residual");
        return 1;
    } catch(const std::exception &e) { last_error=e.what(); return 0; }
}
}
