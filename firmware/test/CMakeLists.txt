# Arduino'dan bagimsiz firmware modulleri icin host testleri.
#
#   cmake -S firmware/test -B build/test
#   cmake --build build/test
#   ctest --test-dir build/test --output-on-failure

cmake_minimum_required(VERSION 3.16)
project(acoustic_node_firmware_tests CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE RelWithDebInfo)
endif()

set(FW_SRC ${CMAKE_CURRENT_SOURCE_DIR}/../src)
set(FW_INC ${CMAKE_CURRENT_SOURCE_DIR}/../include)

function(fw_test name)
    add_executable(${name} ${name}.cpp ${ARGN})
    target_include_directories(${name} PRIVATE ${FW_INC} ${CMAKE_CURRENT_SOURCE_DIR})
    target_compile_options(${name} PRIVATE
        -Wall -Wextra -Wpedantic -Wconversion -Werror
        -fsanitize=address,undefined -fno-omit-frame-pointer)
    target_link_options(${name} PRIVATE -fsanitize=address,undefined)
    add_test(NAME ${name} COMMAND ${name})
endfunction()

enable_testing()
fw_test(test_dsp ${FW_SRC}/acoustic_dsp.cpp ${FW_SRC}/dsp_filter.cpp)
fw_test(test_bfsk_modem ${FW_SRC}/bfsk_modem.cpp ${FW_SRC}/swarm_mesh.cpp)
fw_test(test_swarm_mesh ${FW_SRC}/swarm_mesh.cpp)
fw_test(test_power_manager ${FW_SRC}/power_manager.cpp)
