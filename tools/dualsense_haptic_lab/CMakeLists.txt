cmake_minimum_required(VERSION 3.20)
project(CemuDualSenseHapticLab LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(GAMEPAD_CORE_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../dependencies/Gamepad-Core")
set(BUILD_TESTS OFF CACHE BOOL "Disable upstream integration tests for Haptic Lab" FORCE)
set(AUTOMATED_TESTS OFF CACHE BOOL "Disable upstream automated tests" FORCE)

add_subdirectory("${GAMEPAD_CORE_ROOT}" "${CMAKE_BINARY_DIR}/gamepad-core" EXCLUDE_FROM_ALL)

add_library(GamepadCoreWindowsSupport STATIC
    "${GAMEPAD_CORE_ROOT}/Tests/Common/Platform/windows/windows_device_info.cpp"
)

target_include_directories(GamepadCoreWindowsSupport PUBLIC
    "${GAMEPAD_CORE_ROOT}/Source/Public"
    "${GAMEPAD_CORE_ROOT}/Tests/Common"
)

target_compile_definitions(GamepadCoreWindowsSupport PUBLIC
    BUILD_GAMEPAD_CORE_TESTS
    GAMEPAD_CORE_HAS_AUDIO=0
    UNICODE
    _UNICODE
)

target_link_libraries(GamepadCoreWindowsSupport PUBLIC
    GamepadCore
    Setupapi
    Hid
    ole32
    oleaut32
    uuid
    winmm
)

add_executable(CemuDualSenseHapticLab WIN32
    main.cpp
)

target_compile_definitions(CemuDualSenseHapticLab PRIVATE
    UNICODE
    _UNICODE
)

target_link_libraries(CemuDualSenseHapticLab PRIVATE
    GamepadCoreWindowsSupport
    comctl32
)
