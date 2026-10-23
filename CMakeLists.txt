# mcla - ReXGlue Recompiled Project
#
# SDK boilerplate lives in generated/rexglue.cmake.

cmake_minimum_required(VERSION 3.25)
project(mcla LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
option(MCLA_ANDROID_IO_TRACE "Log Android runtime file opens and bytes read (temporary diagnostics)" OFF)

# Android Gradle currently configures native Release as RelWithDebInfo, which
# defaults to -O2. Keep the useful symbol information while optimizing the
# generated guest code and runtime sources at -O3 on Android.
if(ANDROID AND CMAKE_BUILD_TYPE STREQUAL "RelWithDebInfo")
    add_compile_options("$<$<COMPILE_LANGUAGE:CXX>:-O3>")
endif()

if(ANDROID)
    if(NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/third_party/libadrenotools/CMakeLists.txt")
        message(FATAL_ERROR "Initialize submodules recursively to build Android Vulkan driver support.")
    endif()
    add_subdirectory(third_party/libadrenotools)
    # The linker namespace helper is a static archive embedded in librexruntime.
    # Android's NDK normally enables PIC globally; native Termux builds need it
    # declared explicitly for these two static targets.
    set_target_properties(adrenotools linkernsbypass PROPERTIES POSITION_INDEPENDENT_CODE ON)
endif()

include(generated/rexglue.cmake)
if(ANDROID)
    include_directories("${REXSDK_DIR}/thirdparty/libucontext/include"
                        "${REXSDK_DIR}/thirdparty/imgui"
                        "${REXSDK_DIR}/thirdparty/libucontext/arch/aarch64/include")

    # Vulkan initialization lives in librexruntime, so its Android loader
    # callback must be defined there as well. Keeping this in libmain.so leaves
    # librexruntime with an unresolved MclaAndroidOpenVulkanLoader symbol.
    target_sources(rexruntime PRIVATE src/android_gpu_driver.cpp)
    target_include_directories(rexruntime PRIVATE third_party/libadrenotools/include)
    target_link_libraries(rexruntime PRIVATE adrenotools)
endif()

# Sources
set(MCLA_SOURCES
    src/main.cpp
    src/mcla_app.cpp
    src/crash_trace.cpp
    src/audio_fallback.cpp
    src/frame_timing.cpp
    src/render_perf.cpp
    src/perf_options.cpp
    src/warp_fix.cpp
    src/button_prompts.cpp
    src/settings_menu.cpp
    src/sampling_profiler.cpp
    src/code_pointer_scan.cpp
)

if(ANDROID)
    # SDL3 Android loads libmain.so and enters through SDL_main.
    add_library(mcla SHARED ${MCLA_SOURCES})
    target_sources(mcla PRIVATE src/touch_controls.cpp)
    set_target_properties(mcla PROPERTIES OUTPUT_NAME main)
    target_compile_options(mcla PRIVATE -include SDL3/SDL_main.h)
elseif(WIN32)
    add_executable(mcla WIN32 ${MCLA_SOURCES})
else()
    add_executable(mcla ${MCLA_SOURCES})
endif()

rexglue_setup_target(mcla)

if(ANDROID AND TARGET mcla_recomp)
    # Recompiled guest code is an OBJECT library linked into libmain.so; make
    # its generated PPC objects position-independent for Android shared loading.
    set_target_properties(mcla_recomp PROPERTIES POSITION_INDEPENDENT_CODE ON)
endif()

if(ANDROID AND MCLA_ANDROID_IO_TRACE)
    include(cmake/AndroidIoTrace.cmake)
    mcla_enable_android_io_trace()
endif()

if(WIN32)
    # timeBeginPeriod for the frame limiter.
    target_link_libraries(mcla PRIVATE winmm)
endif()
