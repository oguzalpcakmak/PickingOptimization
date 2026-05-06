cmake_minimum_required(VERSION 3.16)
project(picking_current_best_cpp LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(picking_current_best_cpp src/main.cpp)

if(MSVC)
  target_compile_options(picking_current_best_cpp PRIVATE /O2 /W4)
else()
  target_compile_options(picking_current_best_cpp PRIVATE -O3 -Wall -Wextra -pedantic)
endif()
