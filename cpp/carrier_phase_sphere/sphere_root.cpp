// Optional ABI-checked 3D scalar kernel for BaselineSphereMetric.solve.
// Python retains covariance factors, frame projection, and objective evaluation.
// Build only with strict IEEE arithmetic; no fast math or contraction.
#include <algorithm>
#include <cmath>
#include <limits>
#include <cstdint>

#if defined(__FAST_MATH__) || (defined(__FINITE_MATH_ONLY__) && __FINITE_MATH_ONLY__ != 0)
#error "carrier sphere kernel does not support fast/finite-only math"
#endif
static_assert(sizeof(double)==8 && std::numeric_limits<double>::is_iec559, "IEEE binary64 required");

extern "C" std::uint32_t legsa_sphere_abi_version() { return 1; }
extern "C" const char* legsa_sphere_kernel_version() { return "delta_bisection_3d_v1"; }

extern "C" int legsa_sphere_root3(const double* eigen, const double* coordinate,
                                   double length, double tolerance,
                                   double* out, int* hard, int* iterations) {
    if (!eigen || !coordinate || !out || !hard || !iterations ||
        !std::isfinite(length) || length <= 0.0) return 3;
    for (int i=0; i<3; ++i)
        if (!std::isfinite(eigen[i]) || !std::isfinite(coordinate[i])) return 3;
    const double minimum=eigen[0], lower=-minimum;
    bool mask[3]; bool hard_case=true;
    for (int i=0; i<3; ++i) {
        mask[i]=(eigen[i]==minimum);
        if (mask[i] && coordinate[i]!=0.0) hard_case=false;
    }
    *hard=0; *iterations=0;
    if (hard_case) {
        double fixed[3]={0.,0.,0.};
        for (int i=0;i<3;++i)
            if (!mask[i]) fixed[i]=eigen[i]*coordinate[i]/(eigen[i]+lower);
        const double squared=(fixed[0]*fixed[0]+fixed[1]*fixed[1])+fixed[2]*fixed[2];
        const double remaining=length*length-squared;
        if (remaining >= -tolerance) {
            int first=-1;
            for (int i=0;i<3;++i) if (mask[i]) {fixed[i]=0.; if(first<0)first=i;}
            fixed[first]=std::sqrt(std::max(0.,remaining));
            for (int i=0;i<3;++i) out[i]=fixed[i];
            out[3]=lower; *hard=1; return 0;
        }
    }
    auto value_at = [&](double delta, double* value) {
        for (int i=0;i<3;++i)
            value[i]=eigen[i]*coordinate[i]/((eigen[i]-minimum)+delta);
    };
    auto secular = [&](double delta) {
        double value[3];value_at(delta,value);
        return ((value[0]*value[0]+value[1]*value[1])+value[2]*value[2])-length*length;
    };
    double numerator=0.;
    for (int i=0;i<3;++i)
        if(mask[i]) numerator=std::max(numerator,std::abs(eigen[i]*coordinate[i]));
    const double tiny=std::numeric_limits<double>::min();
    double lo=numerator/(2.*length);
    if(lo==0.) lo=tiny;
    double hi=std::max(1.,minimum);
    while(secular(hi)>0.) {
        hi*=2.;
        if(!std::isfinite(hi)) return 1;
    }
    if(secular(lo)<0.) return 2;
    for (int j=0;j<300;++j) {
        const double mid=(lo+hi)*.5;
        if(secular(mid)>0.) lo=mid;else hi=mid;
        *iterations=j+1;
        if(hi-lo<=1e-14*std::max(tiny,mid))break;
    }
    const double delta=(lo+hi)*.5;
    value_at(delta,out);out[3]=lower+delta;
    return 0;
}
