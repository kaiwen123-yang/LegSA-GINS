cmake_minimum_required(VERSION 3.16)

project(legsa_gins_cpp_runtime LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

file(GLOB_RECURSE LEGSA_GINS_RUNTIME_SOURCES CONFIGURE_DEPENDS
  "${CMAKE_CURRENT_SOURCE_DIR}/src/*.cpp"
)

add_executable(legsa_gins
  ${LEGSA_GINS_RUNTIME_SOURCES}
  "${CMAKE_CURRENT_SOURCE_DIR}/apps/legsa_gins.cpp"
)

target_include_directories(legsa_gins
  PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/include"
)
