cmake_minimum_required(VERSION 3.16)

project(legsa_gins_cpp_runtime LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

file(GLOB_RECURSE LEGSA_GINS_RUNTIME_SOURCES CONFIGURE_DEPENDS
  # N4 math/filter/mechanization/updates/readers sources stay under cpp/src
  # and are picked up here without adding external dependencies.
  # N4E standardized receiver reader is also included by this source glob.
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

file(GLOB_RECURSE LEGSA_V23_CORE_SOURCES CONFIGURE_DEPENDS
  # N4H4A LegSA-owned v23-core sources are intentionally isolated from
  # the final_v23 reference submodule.  That submodule is documentation/audit
  # evidence only and is never compiled into the proposed runtime.
  "${CMAKE_CURRENT_SOURCE_DIR}/legsa_v23_core/src/*.cpp"
)
list(REMOVE_ITEM LEGSA_V23_CORE_SOURCES
  "${CMAKE_CURRENT_SOURCE_DIR}/legsa_v23_core/src/legsa_v23_core_demo.cpp"
)

add_library(legsa_v23_core STATIC
  ${LEGSA_V23_CORE_SOURCES}
)

target_include_directories(legsa_v23_core
  PUBLIC
    "${CMAKE_CURRENT_SOURCE_DIR}/legsa_v23_core/include"
)

add_executable(legsa_v23_core_demo
  "${CMAKE_CURRENT_SOURCE_DIR}/legsa_v23_core/src/legsa_v23_core_demo.cpp"
)

target_link_libraries(legsa_v23_core_demo
  PRIVATE
    legsa_v23_core
)

file(GLOB_RECURSE LEGSA_V23_PORT_CORE_SOURCES CONFIGURE_DEPENDS
  # N4H4R1 source-backed port files are LegSA-owned copies/refactors under
  # cpp/legsa_v23_port_core.  The external reference submodule remains
  # provenance evidence only and is never compiled by this target.
  # N5A raw Doppler factor sources are also LegSA-owned port-core extensions.
  "${CMAKE_CURRENT_SOURCE_DIR}/legsa_v23_port_core/src/*.cpp"
)
list(REMOVE_ITEM LEGSA_V23_PORT_CORE_SOURCES
  "${CMAKE_CURRENT_SOURCE_DIR}/legsa_v23_port_core/src/demo/port_demo.cpp"
)

add_library(legsa_v23_port_core STATIC
  ${LEGSA_V23_PORT_CORE_SOURCES}
)

target_include_directories(legsa_v23_port_core
  PUBLIC
    "${CMAKE_CURRENT_SOURCE_DIR}/legsa_v23_port_core/include"
)

add_executable(legsa_v23_port_core_demo
  "${CMAKE_CURRENT_SOURCE_DIR}/legsa_v23_port_core/src/demo/port_demo.cpp"
)

target_link_libraries(legsa_v23_port_core_demo
  PRIVATE
    legsa_v23_port_core
)
