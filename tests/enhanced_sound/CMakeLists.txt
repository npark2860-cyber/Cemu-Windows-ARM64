cmake_minimum_required(VERSION 3.20)
project(EnhancedSoundLookupTests LANGUAGES CXX)
enable_testing()
add_executable(enhanced_sound_lookup_tests lookup_tests.cpp)
target_compile_features(enhanced_sound_lookup_tests PRIVATE cxx_std_20)
# Compile the production headers against a small guest-memory fixture. No game
# assets, audio device, graphics dependencies, or main Cemu build are required.
target_include_directories(enhanced_sound_lookup_tests PRIVATE stubs ../../src)
if(MSVC)
  target_compile_options(enhanced_sound_lookup_tests PRIVATE /W4 /EHsc)
else()
  target_compile_options(enhanced_sound_lookup_tests PRIVATE -Wall -Wextra -Wpedantic)
endif()
add_test(NAME enhanced_sound_lookup_equivalence COMMAND enhanced_sound_lookup_tests)

find_package(Threads REQUIRED)
add_executable(enhanced_sound_haptic_tests haptic_tests.cpp)
target_compile_features(enhanced_sound_haptic_tests PRIVATE cxx_std_20)
target_include_directories(enhanced_sound_haptic_tests PRIVATE ../../src)
target_link_libraries(enhanced_sound_haptic_tests PRIVATE Threads::Threads)
add_test(NAME enhanced_sound_haptic_lifecycle COMMAND enhanced_sound_haptic_tests
  "${CMAKE_CURRENT_SOURCE_DIR}/../../enhanced_sound_policies/BreathOfTheWild/DualSenseExperienceUnified/haptics")
