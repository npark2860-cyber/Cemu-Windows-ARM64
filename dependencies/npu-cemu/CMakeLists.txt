# cemu_npu.dll: Windows ARM64 NPU frame generation (ONNX Runtime + QNN HTP).
#
# Built as part of Cemu with -DCEMU_ENABLE_NPU=ON: the module and the ONNX
# Runtime/QNN DLLs it needs land in bin/ beside Cemu, next to the committed
# models and shaders in bin/npu, so bin/ is a complete runtime folder.
#
# Standalone, for the module and its CPU contract tests only:
#   cmake -S dependencies/npu-cemu -B build-npu -G Ninja && cmake --build build-npu
#   ctest --test-dir build-npu
# Off Windows ARM64 the standalone build compiles just the portable tests.
cmake_minimum_required(VERSION 3.21)
set(CEMU_NPU_STANDALONE OFF)
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
    set(CEMU_NPU_STANDALONE ON)
endif()
if(CEMU_NPU_STANDALONE)
    project(cemu_npu LANGUAGES CXX)
    set(CMAKE_CXX_STANDARD 20)
    set(CMAKE_CXX_STANDARD_REQUIRED ON)
    set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
    set(CEMU_NPU_OUTPUT_DIR "${CMAKE_BINARY_DIR}/bin")
    enable_testing()
else()
    set(CEMU_NPU_OUTPUT_DIR "${CMAKE_SOURCE_DIR}/bin")
endif()
option(CEMU_NPU_TESTS "Build the NPU module's CPU contract tests" ${CEMU_NPU_STANDALONE})

if(WIN32 AND CMAKE_CXX_COMPILER_ARCHITECTURE_ID STREQUAL "ARM64")
    # Pinned ONNX Runtime with the QNN execution provider. The package carries
    # the headers, the import library and every runtime DLL the module loads.
    set(CEMU_NPU_ORT_VERSION "1.24.4")
    set(CEMU_NPU_ORT_SHA256 "e4d6eabb9e503d4f3c78494fc9400f02509b2ee315d9f707644a174ece8da17f")
    set(CEMU_NPU_ORT_PACKAGE "" CACHE FILEPATH "Local microsoft.ml.onnxruntime.qnn.${CEMU_NPU_ORT_VERSION}.nupkg; downloaded from nuget.org when empty")
    set(ort "${CMAKE_BINARY_DIR}/_deps/onnxruntime-qnn-${CEMU_NPU_ORT_VERSION}")
    if(NOT EXISTS "${ort}/extracted.stamp")
        set(package "${CEMU_NPU_ORT_PACKAGE}")
        if(NOT package)
            set(package "${CMAKE_BINARY_DIR}/_deps/microsoft.ml.onnxruntime.qnn.${CEMU_NPU_ORT_VERSION}.nupkg")
            message(STATUS "Downloading ONNX Runtime QNN ${CEMU_NPU_ORT_VERSION} from nuget.org")
            file(DOWNLOAD "https://api.nuget.org/v3-flatcontainer/microsoft.ml.onnxruntime.qnn/${CEMU_NPU_ORT_VERSION}/microsoft.ml.onnxruntime.qnn.${CEMU_NPU_ORT_VERSION}.nupkg"
                "${package}" EXPECTED_HASH SHA256=${CEMU_NPU_ORT_SHA256} TLS_VERIFY ON)
        endif()
        file(SHA256 "${package}" actual)
        if(NOT actual STREQUAL CEMU_NPU_ORT_SHA256)
            message(FATAL_ERROR "${package} is not the pinned ONNX Runtime QNN ${CEMU_NPU_ORT_VERSION} package")
        endif()
        file(REMOVE_RECURSE "${ort}")
        file(ARCHIVE_EXTRACT INPUT "${package}" DESTINATION "${ort}" PATTERNS "build/native/include/*" "runtimes/win-arm64/native/*")
        file(TOUCH "${ort}/extracted.stamp")
    endif()

    add_library(cemu_npu SHARED npu_cemu.cpp)
    target_include_directories(cemu_npu PRIVATE "${ort}/build/native/include" "${CMAKE_CURRENT_SOURCE_DIR}/../Vulkan-Headers/include")
    target_link_libraries(cemu_npu PRIVATE "${ort}/runtimes/win-arm64/native/onnxruntime.lib")
    target_compile_definitions(cemu_npu PRIVATE NOMINMAX WIN32_LEAN_AND_MEAN)
    target_compile_options(cemu_npu PRIVATE /utf-8)
    # $<1:> keeps multi-config generators from adding a configuration folder.
    set_target_properties(cemu_npu PROPERTIES PREFIX "" RUNTIME_OUTPUT_DIRECTORY "${CEMU_NPU_OUTPUT_DIR}/$<1:>")

    # Only what the module loads: ORT, its QNN provider, and the QNN HTP
    # backend with the stubs and skels for Snapdragon X (V73) and X2 (V81).
    set(runtime onnxruntime.dll onnxruntime_providers_qnn.dll onnxruntime_providers_shared.dll
        QnnHtp.dll QnnHtpPrepare.dll QnnSystem.dll
        QnnHtpV73Stub.dll libQnnHtpV73Skel.so libqnnhtpv73.cat
        QnnHtpV81Stub.dll libQnnHtpV81Skel.so libqnnhtpv81.cat)
    list(TRANSFORM runtime PREPEND "${ort}/runtimes/win-arm64/native/")
    add_custom_command(TARGET cemu_npu POST_BUILD
        COMMAND "${CMAKE_COMMAND}" -E copy_if_different ${runtime} "${CEMU_NPU_OUTPUT_DIR}"
        VERBATIM)
endif()

if(CEMU_NPU_TESTS)
    set(tests buffered_timeline processing_profile npu_scheduling qnn_context_cache)
    if(WIN32)
        list(APPEND tests ort_paths)
    endif()
    foreach(test IN LISTS tests)
        add_executable(cemu_npu_test_${test} test_${test}.cpp)
        if(MSVC)
            target_compile_options(cemu_npu_test_${test} PRIVATE /utf-8)
            target_compile_definitions(cemu_npu_test_${test} PRIVATE NOMINMAX WIN32_LEAN_AND_MEAN)
        else()
            find_package(Threads REQUIRED)
            target_link_libraries(cemu_npu_test_${test} PRIVATE Threads::Threads)
        endif()
        add_test(NAME npu_${test} COMMAND cemu_npu_test_${test} "${CMAKE_CURRENT_BINARY_DIR}/test-scratch")
    endforeach()
endif()
