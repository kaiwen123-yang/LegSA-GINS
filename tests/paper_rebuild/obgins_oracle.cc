// Test oracle: direct unmodified upstream class, no production bridge ABI.
#include "src/preintegration/preintegration_earth.h"
#include <iostream>
#include <iomanip>
int main() {
    auto p=std::make_shared<IntegrationParameters>();
    std::cin>>p->station[0]>>p->station[1]>>p->station[2]>>p->gravity>>p->corr_time
        >>p->gyr_arw>>p->acc_vrw>>p->gyr_bias_std>>p->acc_bias_std;
    IntegrationState a{};
    double qx,qy,qz,qw;
    for(int i=0;i<3;++i) std::cin>>a.p[i];
    std::cin>>qx>>qy>>qz>>qw; a.q=Quaterniond(qw,qx,qy,qz);
    for(int i=0;i<3;++i) std::cin>>a.v[i];
    for(int i=0;i<3;++i) std::cin>>a.bg[i];
    for(int i=0;i<3;++i) std::cin>>a.ba[i];
    IMU seed{};
    std::cin>>seed.time>>seed.dt;
    for(int i=0;i<3;++i) std::cin>>seed.dtheta[i];
    for(int i=0;i<3;++i) std::cin>>seed.dvel[i];
    PreintegrationEarth model(p,seed,a);
    int n; std::cin>>n;
    for(int k=0;k<n;++k) {
        IMU u{}; std::cin>>u.time>>u.dt;
        for(int i=0;i<3;++i) std::cin>>u.dtheta[i];
        for(int i=0;i<3;++i) std::cin>>u.dvel[i];
        model.addNewImu(u);
    }
    const auto b=model.currentState();
    double res[15]; model.evaluate(a,b,res);
    std::cout<<std::setprecision(17);
    for(int i=0;i<3;++i) std::cout<<b.p[i]<<" ";
    for(int i=0;i<4;++i) std::cout<<b.q.coeffs()[i]<<" ";
    for(int i=0;i<3;++i) std::cout<<b.v[i]<<" ";
    for(int i=0;i<3;++i) std::cout<<b.bg[i]<<" ";
    for(int i=0;i<3;++i) std::cout<<b.ba[i]<<" ";
    for(int i=0;i<15;++i) std::cout<<res[i]<<" ";
    std::cout<<"\n";
}
