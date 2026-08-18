cmake_minimum_required(VERSION 3.16)
project(hartley_inekf_h3_h4 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Eigen3 3.3 REQUIRED NO_MODULE)

add_library(hartley_inekf STATIC src/backend.cpp)
target_include_directories(hartley_inekf PUBLIC include)
target_link_libraries(hartley_inekf PUBLIC Eigen3::Eigen)
target_compile_options(hartley_inekf PRIVATE -Wall -Wextra -Wpedantic)

add_executable(hartley_backend_tests tests/backend_tests.cpp)
target_link_libraries(hartley_backend_tests PRIVATE hartley_inekf)

add_executable(hartley_backend_validator tools/validate_backend.cpp)
target_link_libraries(hartley_backend_validator PRIVATE hartley_inekf)

enable_testing()
add_test(NAME hartley_backend_tests COMMAND hartley_backend_tests)
