// Compiles the generated InitializeAndroidPipelineCache method with a fake
// Vulkan device whose driver rejects persisted data once, then accepts empty data.
#include <atomic>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <vector>

#define REXGPU_INFO(...) ((void)0)
#define REXGPU_WARN(...) ((void)0)

using VkDevice = int;
using VkPhysicalDevice = int;
using VkPipelineCache = int;
using VkResult = int;
using VkStructureType = int;
using VkPipelineCacheHeaderVersion = int;
constexpr VkPipelineCache VK_NULL_HANDLE = 0;
constexpr VkResult VK_SUCCESS = 0;
constexpr VkResult VK_ERROR_INITIALIZATION_FAILED = -3;
constexpr VkStructureType VK_STRUCTURE_TYPE_PIPELINE_CACHE_CREATE_INFO = 17;
constexpr VkPipelineCacheHeaderVersion VK_PIPELINE_CACHE_HEADER_VERSION_ONE = 1;
constexpr size_t VK_UUID_SIZE = 16;

struct VkPhysicalDeviceProperties {
  uint32_t vendorID = 0;
  uint32_t deviceID = 0;
  uint8_t pipelineCacheUUID[VK_UUID_SIZE]{};
};

struct VkPipelineCacheHeaderVersionOne {
  uint32_t headerSize = 0;
  VkPipelineCacheHeaderVersion headerVersion = 0;
  uint32_t vendorID = 0;
  uint32_t deviceID = 0;
  uint8_t pipelineCacheUUID[VK_UUID_SIZE]{};
};

struct VkPipelineCacheCreateInfo {
  VkStructureType sType = 0;
  size_t initialDataSize = 0;
  const void* pInitialData = nullptr;
};

namespace ui::vulkan {
struct VulkanInstance {
  struct Functions {
    void vkGetPhysicalDeviceProperties(VkPhysicalDevice,
                                       VkPhysicalDeviceProperties* properties) const {
      properties->vendorID = 0x1234;
      properties->deviceID = 0x5678;
      for (size_t i = 0; i < VK_UUID_SIZE; ++i) properties->pipelineCacheUUID[i] = uint8_t(i);
    }
  } funcs;
  const Functions& functions() const { return funcs; }
};

struct VulkanDevice {
  struct Functions {
    VkResult vkCreatePipelineCache(VkDevice, const VkPipelineCacheCreateInfo* info, const void*,
                                    VkPipelineCache* cache) const {
      ++create_calls;
      if (info->initialDataSize != 0) return VK_ERROR_INITIALIZATION_FAILED;
      *cache = 7;
      return VK_SUCCESS;
    }
    void vkDestroyPipelineCache(VkDevice, VkPipelineCache, const void*) const {}
    mutable int create_calls = 0;
  } funcs;
  VulkanInstance instance;
  const Functions& functions() const { return funcs; }
  VkDevice device() const { return 1; }
  const VulkanInstance* vulkan_instance() const { return &instance; }
  VkPhysicalDevice physical_device() const { return 2; }
};
}  // namespace ui::vulkan

struct VulkanPipelineCache {
  struct Processor {
    ui::vulkan::VulkanDevice device;
    const ui::vulkan::VulkanDevice* GetVulkanDevice() const { return &device; }
  } command_processor_;
  std::mutex driver_pipeline_cache_lock_, driver_pipeline_cache_save_lock_;
  VkPipelineCache driver_pipeline_cache_ = VK_NULL_HANDLE;
  std::filesystem::path driver_pipeline_cache_path_;
  std::atomic<bool> android_vk_cache_dirty_{false};
  std::atomic<unsigned> android_vk_cache_loaded_{0};
  std::atomic<unsigned> android_vk_cache_rejected_{0};
  void InitializeAndroidPipelineCache(const std::filesystem::path& cache_path);
};

// INSERT_INIT_METHOD

int main() {
  const std::filesystem::path cache_path = "persisted.vk.bin";
  VkPipelineCacheHeaderVersionOne header{};
  header.headerSize = sizeof(header);
  header.headerVersion = VK_PIPELINE_CACHE_HEADER_VERSION_ONE;
  header.vendorID = 0x1234;
  header.deviceID = 0x5678;
  for (size_t i = 0; i < VK_UUID_SIZE; ++i) header.pipelineCacheUUID[i] = uint8_t(i);
  std::ofstream output(cache_path, std::ios::binary | std::ios::trunc);
  output.write(reinterpret_cast<const char*>(&header), sizeof(header));
  output.write("data", 4);
  output.close();

  VulkanPipelineCache cache;
  cache.InitializeAndroidPipelineCache(cache_path);
  assert(cache.driver_pipeline_cache_ == 7);
  assert(cache.command_processor_.device.funcs.create_calls == 2);
  assert(cache.android_vk_cache_loaded_ == 0);
  assert(cache.android_vk_cache_rejected_ == 1);
}
