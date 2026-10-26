import importlib.util
import unittest

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "patch_android_rexglue", ROOT / "scripts" / "patch_android_rexglue.py"
)
PATCHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCHER)


SDK_ROOT_CMAKE = """\
if(WIN32)
    set(REX_PLATFORM \"win-arm64\")
    add_compile_definitions(REX_PLATFORM_WINDOWS=1)
elseif(UNIX AND NOT APPLE)
    set(REX_PLATFORM \"linux-arm64\")
    add_compile_definitions(REX_PLATFORM_LINUX=1)
elseif(APPLE)
    set(REX_PLATFORM \"mac-arm64\")
    add_compile_definitions(REX_PLATFORM_MAC=1)
endif()
"""


SDK_UI_CMAKE = """\
if(WIN32)
    set(REXUI_PLATFORM_SOURCES surface_win.cpp)
elseif(APPLE)
    set(REXUI_PLATFORM_SOURCES surface_mac.cpp)
else()
    set(REXUI_PLATFORM_SOURCES surface_gnulinux.cpp)
endif()

if(UNIX AND NOT APPLE)
    find_package(PkgConfig REQUIRED)
    pkg_check_modules(X11_XCB REQUIRED x11-xcb)
    pkg_check_modules(WAYLAND REQUIRED wayland-client)
endif()
"""


SDK_THIRDPARTY_CMAKE = """\
set(SDL_VIDEO ON CACHE BOOL \"\" FORCE)
if(UNIX AND NOT APPLE)
    set(SDL_X11 ON CACHE BOOL \"\" FORCE)
    set(SDL_WAYLAND ON CACHE BOOL \"\" FORCE)
    set(SDL_ALSA ON CACHE BOOL \"\" FORCE)
endif()
"""


SDK_CORE_CMAKE = """\
add_library(rexcore OBJECT fiber_posix.cpp)
add_library(rex::core ALIAS rexcore)
if(APPLE)
    target_link_libraries(rexcore PRIVATE pthread)
elseif(UNIX)
    target_link_libraries(rexcore PRIVATE pthread rt dl)
endif()
"""


SDK_FILESYSTEM_CMAKE = """\
add_library(rexfilesystem OBJECT
    device.cpp
)
add_library(rex::filesystem ALIAS rexfilesystem)
target_link_libraries(rexfilesystem PUBLIC rexcore)
"""


FIBER_HEADER = """\
#if REX_PLATFORM_LINUX || REX_PLATFORM_MAC
#include <ucontext.h>
struct Fiber {
  ucontext_t context_{};
};
#endif
"""


FIBER_SOURCE = """\
#include <rex/thread/fiber.h>
void Switch(Fiber* from, Fiber* target) {
  getcontext(&from->context_);
  makecontext(&target->context_, nullptr, 0);
  swapcontext(&from->context_, &target->context_);
}
"""


WINDOW_SOURCE = """\
#if REX_PLATFORM_WIN32
#include <rex/ui/surface_win.h>
#elif REX_PLATFORM_MAC
#include <rex/ui/surface_mac.h>
#else
#include <X11/Xlib-xcb.h>
#include <rex/ui/surface_gnulinux.h>
#endif

void* WindowSDL::GetNativeWindowHandle() const {
#if REX_PLATFORM_WIN32
  return nullptr;
#elif REX_PLATFORM_MAC
  return nullptr;
#else
  return nullptr;
#endif
}

std::unique_ptr<Surface> WindowSDL::CreateSurfaceImpl(Surface::TypeFlags allowed_types) {
#if REX_PLATFORM_WIN32
  return nullptr;
#elif REX_PLATFORM_MAC
  return nullptr;
#else
  SDL_PropertiesID props = SDL_GetWindowProperties(sdl_window_);
  // linux
#endif
}
"""


class AndroidPlatformPatchTest(unittest.TestCase):
    def test_root_cmake_selects_android_without_linux_host_flags(self):
        patched = PATCHER.patch_android_platform_cmake(SDK_ROOT_CMAKE)
        self.assertIn('elseif(ANDROID OR CMAKE_SYSTEM_NAME STREQUAL "Android")', patched)
        self.assertIn('set(REX_PLATFORM "android-arm64")', patched)
        self.assertIn("add_compile_definitions(REX_PLATFORM_ANDROID=1)", patched)
        self.assertLess(patched.index('elseif(ANDROID OR CMAKE_SYSTEM_NAME STREQUAL "Android")'),
                        patched.index('elseif(UNIX AND NOT APPLE)'))
        self.assertEqual(patched, PATCHER.patch_android_platform_cmake(patched))

    def test_ui_uses_android_surface_and_skips_pkg_config(self):
        patched = PATCHER.patch_android_ui_cmake(SDK_UI_CMAKE)
        self.assertIn("elseif(ANDROID)", patched)
        self.assertIn("surface_android.cpp", patched)
        self.assertIn("if(UNIX AND NOT APPLE AND NOT ANDROID)", patched)
        self.assertEqual(patched, PATCHER.patch_android_ui_cmake(patched))

    def test_third_party_skips_linux_backends_on_android(self):
        patched = PATCHER.patch_android_thirdparty_cmake(SDK_THIRDPARTY_CMAKE)
        self.assertIn("if(UNIX AND NOT APPLE AND NOT ANDROID)", patched)
        self.assertEqual(patched, PATCHER.patch_android_thirdparty_cmake(patched))

    def test_window_sources_select_android_native_window(self):
        patched = PATCHER.patch_android_window_sources(WINDOW_SOURCE)
        self.assertIn("#elif REX_PLATFORM_ANDROID", patched)
        self.assertIn("surface_android.h", patched)
        self.assertIn("SDL_PROP_WINDOW_ANDROID_WINDOW_POINTER", patched)
        self.assertEqual(patched, PATCHER.patch_android_window_sources(patched))

    def test_android_surface_files_are_generated(self):
        header, source = PATCHER.android_surface_sources()
        self.assertIn("class AndroidNativeWindowSurface", header)
        self.assertIn("ANativeWindow_getWidth", source)
        self.assertIn("ANativeWindow_getHeight", source)

    def test_core_uses_libucontext_on_android(self):
        patched = PATCHER.patch_android_core_cmake(SDK_CORE_CMAKE)
        self.assertIn("MCLA_LIBUCONTEXT_ROOT", patched)
        self.assertIn("REX_USE_LIBUCONTEXT=1", patched)
        self.assertIn("elseif(ANDROID)", patched)
        self.assertIn("target_link_libraries(rexcore PRIVATE dl log)", patched)
        self.assertEqual(patched, PATCHER.patch_android_core_cmake(patched))

    def test_filesystem_adds_android_content_bridge(self):
        patched = PATCHER.patch_android_filesystem_cmake(SDK_FILESYSTEM_CMAKE)
        self.assertIn("android/android_content.cpp", patched)
        self.assertIn("SDL3::SDL3", patched)
        self.assertEqual(patched, PATCHER.patch_android_filesystem_cmake(patched))
        self.assertIn("OpenAndroidContentFileDescriptor", PATCHER.ANDROID_CONTENT_SOURCE)

    def test_fiber_uses_libucontext_symbols(self):
        header = PATCHER.patch_android_fiber_header(FIBER_HEADER)
        source = PATCHER.patch_android_fiber_source(FIBER_SOURCE)
        self.assertIn("libucontext/libucontext.h", header)
        self.assertIn("libucontext_ucontext_t", header)
        self.assertIn("libucontext_getcontext", source)
        self.assertIn("libucontext_makecontext", source)
        self.assertIn("libucontext_swapcontext", source)
        self.assertEqual(header, PATCHER.patch_android_fiber_header(header))
        self.assertEqual(source, PATCHER.patch_android_fiber_source(source))

    def test_memory_backend_includes_android_api_helper(self):
        source = '#include <android/api-level.h>\n'
        patched = PATCHER.patch_android_memory_api_helper(source)
        self.assertIn('#include <rex/main_android.h>', patched)
        self.assertEqual(patched, PATCHER.patch_android_memory_api_helper(patched))
        self.assertIn('GetAndroidApiLevel', PATCHER.android_main_header())

    def test_android_threading_skips_linux_robust_mutex_api(self):
        source = "#if REX_PLATFORM_LINUX\nrobust_mutex();\n#endif\n" * 3
        patched = PATCHER.patch_android_threading_source(source)
        self.assertEqual(patched.count("REX_PLATFORM_LINUX && !REX_PLATFORM_ANDROID"), 3)
        self.assertEqual(patched, PATCHER.patch_android_threading_source(patched))


if __name__ == "__main__":
    unittest.main()
