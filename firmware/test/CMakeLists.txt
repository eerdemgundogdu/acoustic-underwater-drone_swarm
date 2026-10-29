cmake_minimum_required(VERSION 3.14)
project(pelagos_firmware_tests LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(test_acoustic_node
    test_acoustic_node.cpp
    ../src/acoustic_dsp.cpp
    ../src/swarm_mesh.cpp
    ../src/piezo_harvester.cpp
)
target_include_directories(test_acoustic_node PRIVATE ../include)

enable_testing()
add_test(NAME test_acoustic_node COMMAND test_acoustic_node)
