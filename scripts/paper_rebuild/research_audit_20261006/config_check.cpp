#include "legsa_v23_port_core/config/port_config_loader.hpp"
#include <iostream>
#include <stdexcept>
int main(int argc,char** argv){try{for(int i=1;i<argc;++i){
auto o=legsa_v23_port_core::PortConfigLoader::loadYamlLike(argv[i]);
std::cout<<o.run_id<<" "<<o.protocol_id<<" PASS\n";}return 0;}
catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
