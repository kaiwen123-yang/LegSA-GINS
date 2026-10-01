#include "legsa_v23_port_core/common/rotation.hpp"
#include "legsa_v23_port_core/types.hpp"
#include <cmath>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
using namespace legsa_v23_port_core;
int main(int argc,char**argv){try {
  if(argc<2)return 2;std::string mode=argv[1];
  if(mode=="column") {Matrix m(2,2);m(0,2)=42;std::cout<<"mutated="<<m(1,0)<<'\n';}
  else if(mode=="const_column") {const Matrix m(2,2);std::cout<<m(0,2)<<'\n';}
  else if(mode=="wrap") std::cout<<std::setprecision(17)<<Rotation::wrapRad(std::stod(argv[2]))<<'\n';
  else if(mode=="wrap2pi") std::cout<<std::setprecision(17)<<Rotation::wrap2Pi(std::stod(argv[2]))<<'\n';
  else if(mode=="normal") {for(int i=-10000;i<=10000;++i){double a=i*0.001;std::cout<<std::hexfloat<<Rotation::wrapRad(a)<<','<<Rotation::wrap2Pi(a)<<'\n';}}
  else return 3;
  return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
