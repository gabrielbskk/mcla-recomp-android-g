#if defined(__ANDROID__)

#include <adrenotools/driver.h>
#include <rex/logging.h>
#include <rex/ui/vulkan/api.h>

#include <SDL3/SDL_system.h>

#include <dlfcn.h>
#include <link.h>
#include <unistd.h>

#include <algorithm>
#include <cctype>
#include <cstring>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

extern "C" void* MclaAndroidOpenVulkanLoader();

namespace {

struct DriverProfile {
  const char* id;
  const char* library;
  const char* expected_vendor;
  const char* expected_model;
};

constexpr DriverProfile kTurnip{"turnip-adreno740", "libvulkan_freedreno.so", "adreno", "740"};
constexpr DriverProfile kPanvk{"panvk-mali-g52", "libvulkan_panfrost.so", "mali", "g52"};

std::filesystem::path InternalDriverRoot() {
  const char* path = SDL_GetAndroidInternalStoragePath();
  if (!path || !*path) return {};
  return std::filesystem::path(path) / "gpu_drivers";
}

std::string ReadSelectedDriver(const std::filesystem::path& root) {
  std::ifstream input(root / "selected-driver.txt");
  std::string profile;
  if (!input || !std::getline(input, profile)) return "system";
  profile.erase(std::remove_if(profile.begin(), profile.end(), [](unsigned char ch) {
                  return std::isspace(ch);
                }),
                profile.end());
  return profile;
}

std::string NativeLibraryDirectory() {
  Dl_info info{};
  auto* callback = reinterpret_cast<void*>(&MclaAndroidOpenVulkanLoader);
  if (!dladdr(callback, &info) || !info.dli_fname || !*info.dli_fname) return {};
  std::filesystem::path library_path(info.dli_fname);
  return library_path.parent_path().string() + "/";
}

std::string Lowercase(std::string value) {
  std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) {
    return static_cast<char>(std::tolower(ch));
  });
  return value;
}

bool ProbeCustomLoader(void* handle, const DriverProfile& profile) {
  auto get_instance_proc_addr = reinterpret_cast<PFN_vkGetInstanceProcAddr>(
      dlsym(handle, "vkGetInstanceProcAddr"));
  if (!get_instance_proc_addr) {
    REXLOG_WARN("android gpu: {} loader has no vkGetInstanceProcAddr", profile.id);
    return false;
  }

  auto create_instance = reinterpret_cast<PFN_vkCreateInstance>(
      get_instance_proc_addr(VK_NULL_HANDLE, "vkCreateInstance"));
  if (!create_instance) {
    REXLOG_WARN("android gpu: {} loader has no vkCreateInstance", profile.id);
    return false;
  }

  auto enumerate_instance_extensions = reinterpret_cast<PFN_vkEnumerateInstanceExtensionProperties>(
      get_instance_proc_addr(VK_NULL_HANDLE, "vkEnumerateInstanceExtensionProperties"));
  if (!enumerate_instance_extensions) {
    REXLOG_WARN("android gpu: {} loader cannot enumerate instance extensions", profile.id);
    return false;
  }

  uint32_t extension_count = 0;
  VkResult extension_result = enumerate_instance_extensions(nullptr, &extension_count, nullptr);
  if ((extension_result != VK_SUCCESS && extension_result != VK_INCOMPLETE)
      || extension_count == 0 || extension_count > 4096) {
    REXLOG_WARN("android gpu: {} returned an invalid instance extension list ({})", profile.id,
                static_cast<int>(extension_result));
    return false;
  }
  std::vector<VkExtensionProperties> extensions(extension_count);
  extension_result = enumerate_instance_extensions(nullptr, &extension_count, extensions.data());
  if (extension_result != VK_SUCCESS && extension_result != VK_INCOMPLETE) {
    REXLOG_WARN("android gpu: {} failed to enumerate instance extensions ({})", profile.id,
                static_cast<int>(extension_result));
    return false;
  }
  const uint32_t valid_extension_count =
      std::min<uint32_t>(extension_count, static_cast<uint32_t>(extensions.size()));
  const auto has_extension = [&extensions, valid_extension_count](const char* name) {
    return std::any_of(extensions.begin(), extensions.begin() + valid_extension_count,
                       [name](const VkExtensionProperties& extension) {
                         return std::strcmp(extension.extensionName, name) == 0;
                       });
  };
  if (!has_extension("VK_KHR_surface") || !has_extension("VK_KHR_android_surface")) {
    REXLOG_WARN("android gpu: {} lacks VK_KHR_surface or VK_KHR_android_surface; using system Vulkan",
                profile.id);
    return false;
  }

  VkApplicationInfo application_info{VK_STRUCTURE_TYPE_APPLICATION_INFO};
  application_info.pApplicationName = "MCLA Recomp driver probe";
  application_info.apiVersion = VK_API_VERSION_1_0;
  const char* required_extensions[] = {"VK_KHR_surface", "VK_KHR_android_surface"};
  VkInstanceCreateInfo create_info{VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};
  create_info.pApplicationInfo = &application_info;
  create_info.enabledExtensionCount = 2;
  create_info.ppEnabledExtensionNames = required_extensions;

  VkInstance instance = VK_NULL_HANDLE;
  const VkResult create_result = create_instance(&create_info, nullptr, &instance);
  if (create_result != VK_SUCCESS || instance == VK_NULL_HANDLE) {
    REXLOG_WARN("android gpu: {} vkCreateInstance failed ({})", profile.id,
                static_cast<int>(create_result));
    return false;
  }

  auto destroy_instance = reinterpret_cast<PFN_vkDestroyInstance>(
      get_instance_proc_addr(instance, "vkDestroyInstance"));
  auto enumerate_physical_devices = reinterpret_cast<PFN_vkEnumeratePhysicalDevices>(
      get_instance_proc_addr(instance, "vkEnumeratePhysicalDevices"));
  auto get_physical_device_properties = reinterpret_cast<PFN_vkGetPhysicalDeviceProperties>(
      get_instance_proc_addr(instance, "vkGetPhysicalDeviceProperties"));

  bool compatible = false;
  if (enumerate_physical_devices && get_physical_device_properties) {
    uint32_t count = 0;
    VkResult result = enumerate_physical_devices(instance, &count, nullptr);
    if ((result == VK_SUCCESS || result == VK_INCOMPLETE) && count > 0 && count < 32) {
      std::vector<VkPhysicalDevice> devices(count, VK_NULL_HANDLE);
      result = enumerate_physical_devices(instance, &count, devices.data());
      if (result == VK_SUCCESS || result == VK_INCOMPLETE) {
        for (uint32_t i = 0; i < std::min<uint32_t>(count, devices.size()); ++i) {
          VkPhysicalDeviceProperties properties{};
          get_physical_device_properties(devices[i], &properties);
          const std::string device_name = properties.deviceName;
          REXLOG_INFO("android gpu: {} probe found '{}' (Vulkan {}.{})", profile.id,
                      device_name,
                      VK_VERSION_MAJOR(properties.apiVersion),
                      VK_VERSION_MINOR(properties.apiVersion));
          const std::string normalized_name = Lowercase(device_name);
          if (normalized_name.find(profile.expected_vendor) != std::string::npos
              && normalized_name.find(profile.expected_model) != std::string::npos) {
            compatible = true;
            break;
          }
        }
      }
    }
  }

  if (destroy_instance) destroy_instance(instance, nullptr);
  if (!compatible) {
    REXLOG_WARN("android gpu: {} did not expose its expected GPU; falling back to system Vulkan",
                profile.id);
  }
  return compatible;
}

std::filesystem::path g_crash_marker;

void ClearCrashMarker() {
  if (g_crash_marker.empty()) return;
  std::error_code error;
  std::filesystem::remove(g_crash_marker, error);
}

bool MarkCustomDriverInUse(const std::filesystem::path& root, const char* profile) {
  g_crash_marker = root / "custom-driver-starting";
  std::error_code error;
  std::filesystem::create_directories(root, error);
  if (error) return false;
  std::ofstream marker(g_crash_marker, std::ios::trunc);
  if (!marker) return false;
  marker << profile << '\n';
  marker.close();
  if (!marker) return false;
  static const bool registered = std::atexit(ClearCrashMarker) == 0;
  if (!registered) {
    ClearCrashMarker();
    return false;
  }
  return true;
}

}  // namespace

extern "C" void* MclaAndroidOpenVulkanLoader() {
  const std::filesystem::path root = InternalDriverRoot();
  if (root.empty()) return nullptr;

  const std::string selected = ReadSelectedDriver(root);
  const DriverProfile* profile = nullptr;
  if (selected == kTurnip.id) {
    profile = &kTurnip;
  } else if (selected == kPanvk.id) {
    profile = &kPanvk;
  } else {
    return nullptr;
  }

  const std::filesystem::path driver_directory = root / profile->id;
  const std::filesystem::path driver_library = driver_directory / profile->library;
  std::error_code error;
  if (!std::filesystem::is_regular_file(driver_library, error) || error) {
    REXLOG_WARN("android gpu: selected {} library is missing; using system Vulkan", profile->id);
    return nullptr;
  }

  const std::string hook_directory = NativeLibraryDirectory();
  if (hook_directory.empty()) {
    REXLOG_WARN("android gpu: cannot locate packaged Vulkan hooks; using system Vulkan");
    return nullptr;
  }

  std::string driver_directory_with_slash = driver_directory.string() + "/";
  REXLOG_INFO("android gpu: probing {} from {}", profile->id, driver_directory_with_slash);
  void* loader = adrenotools_open_libvulkan(
      RTLD_NOW, ADRENOTOOLS_DRIVER_CUSTOM, nullptr, hook_directory.c_str(),
      driver_directory_with_slash.c_str(), profile->library, nullptr, nullptr);
  if (!loader) {
    REXLOG_WARN("android gpu: custom loader for {} failed; using system Vulkan", profile->id);
    return nullptr;
  }

  if (!ProbeCustomLoader(loader, *profile)) {
    dlclose(loader);
    return nullptr;
  }

  if (!MarkCustomDriverInUse(root, profile->id)) {
    REXLOG_WARN("android gpu: cannot write driver crash marker; keeping the system loader safer");
    dlclose(loader);
    return nullptr;
  }

  REXLOG_INFO("android gpu: selected custom Vulkan driver {}", profile->id);
  return loader;
}

#endif  // defined(__ANDROID__)
