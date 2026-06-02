cmake_minimum_required(VERSION 3.16)
project(picking_current_best_cpp LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(CTest)

add_library(picking_solver_core src/core.cpp)
target_include_directories(picking_solver_core PUBLIC include)

add_executable(picking_current_best_cpp src/main.cpp)
target_link_libraries(picking_current_best_cpp PRIVATE picking_solver_core)

if(EMSCRIPTEN)
  target_compile_definitions(picking_solver_core PRIVATE PICKING_SOLVER_DISABLE_LKH=1)
  target_compile_options(picking_solver_core PRIVATE -fexceptions)

  add_executable(picking_solver_wasm wasm/wasm_bindings.cpp)
  target_link_libraries(picking_solver_wasm PRIVATE picking_solver_core)
  target_compile_options(picking_solver_wasm PRIVATE -fexceptions)
  target_link_options(
    picking_solver_wasm
    PRIVATE
      --bind
      --no-entry
      -fexceptions
      -sMODULARIZE=1
      -sEXPORT_ES6=1
      -sEXPORT_NAME=createPickingSolver
      -sENVIRONMENT=web,worker,node
      -sALLOW_MEMORY_GROWTH=1
      -sFILESYSTEM=0
  )
  set_target_properties(picking_solver_wasm PROPERTIES OUTPUT_NAME picking_solver SUFFIX ".mjs")

  file(GLOB LKH_WASM_SOURCES CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/../external/LKH-3.0.14/SRC/*.c")
  list(FILTER LKH_WASM_SOURCES EXCLUDE REGEX "KSwapKick\\.HUNT\\.c$")
  add_executable(lkh_wasm ${LKH_WASM_SOURCES})
  target_include_directories(lkh_wasm PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/../external/LKH-3.0.14/SRC/INCLUDE")
  target_compile_definitions(lkh_wasm PRIVATE TWO_LEVEL_TREE)
  target_compile_options(lkh_wasm PRIVATE -O3 -fno-common)
  target_link_options(
    lkh_wasm
    PRIVATE
      -sMODULARIZE=1
      -sEXPORT_ES6=1
      -sEXPORT_NAME=createLkh
      -sENVIRONMENT=web,worker,node
      -sINVOKE_RUN=0
      -sEXIT_RUNTIME=0
      -sALLOW_MEMORY_GROWTH=1
      -sFORCE_FILESYSTEM=1
      -sEXPORTED_RUNTIME_METHODS=FS,callMain
  )
  set_target_properties(lkh_wasm PROPERTIES OUTPUT_NAME lkh SUFFIX ".mjs")
endif()

if(BUILD_TESTING)
  add_executable(picking_solver_core_smoke tests/core_smoke.cpp)
  target_link_libraries(picking_solver_core_smoke PRIVATE picking_solver_core)
  add_test(
    NAME picking_solver_core_smoke
    COMMAND picking_solver_core_smoke
      ${CMAKE_CURRENT_SOURCE_DIR}/../data/full/PickOrder.csv
      ${CMAKE_CURRENT_SOURCE_DIR}/../data/full/StockData.csv
  )
endif()

if(MSVC)
  target_compile_options(picking_solver_core PRIVATE /O2 /W4)
  target_compile_options(picking_current_best_cpp PRIVATE /O2 /W4)
  if(BUILD_TESTING)
    target_compile_options(picking_solver_core_smoke PRIVATE /O2 /W4)
  endif()
else()
  target_compile_options(picking_solver_core PRIVATE -O3 -Wall -Wextra -pedantic)
  target_compile_options(picking_current_best_cpp PRIVATE -O3 -Wall -Wextra -pedantic)
  if(BUILD_TESTING)
    target_compile_options(picking_solver_core_smoke PRIVATE -O3 -Wall -Wextra -pedantic)
  endif()
endif()
