// Compiles the actual generated SaveAndroidPipelineCache method with a fake
// Vulkan data provider and real file writes. Probe disk entry from another thread.
#include <atomic>
#include <cassert>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <mutex>
#include <thread>
#include <vector>
#define REXGPU_INFO(...) ((void)0)
#define REXGPU_WARN(...) ((void)0)
using VkDevice = int;
using VkResult = int;
constexpr int VK_NULL_HANDLE = 0;
constexpr int VK_SUCCESS = 0;
constexpr int VK_INCOMPLETE = 5;
bool fail_snapshot = false;
bool grow_snapshot_once = false;
namespace ui::vulkan {
struct VulkanDevice {
  struct Functions {
    int vkGetPipelineCacheData(int, int, size_t* size, void* data) const {
      if (fail_snapshot) return -1;
      if (!data) {
        *size = 4;
        return VK_SUCCESS;
      }
      if (grow_snapshot_once && *size < 8) {
        *size = 8;
        return VK_INCOMPLETE;
      }
      *size = grow_snapshot_once ? 8 : 4;
      std::memcpy(data, grow_snapshot_once ? "testdata" : "test", *size);
      return VK_SUCCESS;
    }
  } funcs;
  const Functions& functions() const { return funcs; }
  int device() const { return 1; }
};
}
struct VulkanPipelineCache {
  std::mutex driver_pipeline_cache_lock_, driver_pipeline_cache_save_lock_;
  int driver_pipeline_cache_ = 1;
  std::filesystem::path driver_pipeline_cache_path_ = "cache.bin";
  std::atomic<bool> android_vk_cache_dirty_{true};
  std::atomic<unsigned> android_vk_cache_saved_{0};
  struct Processor {
    ui::vulkan::VulkanDevice device;
    const ui::vulkan::VulkanDevice* GetVulkanDevice() const { return &device; }
  } command_processor_;
  void SaveAndroidPipelineCache();
};
VulkanPipelineCache* active_cache;
bool pipeline_can_progress = false;
bool saves_serialized = false;
int disk_opens = 0;
struct ProbeOutput : std::ofstream {
  ProbeOutput(const std::filesystem::path& path, std::ios::openmode mode)
      : std::ofstream(path, mode) {
    ++disk_opens;
    std::thread worker([] {
      if (active_cache->driver_pipeline_cache_lock_.try_lock()) {
        pipeline_can_progress = true;
        // A new pipeline must remain dirty after this older snapshot is saved.
        active_cache->android_vk_cache_dirty_.store(true);
        active_cache->driver_pipeline_cache_lock_.unlock();
      }
      if (active_cache->driver_pipeline_cache_save_lock_.try_lock()) {
        active_cache->driver_pipeline_cache_save_lock_.unlock();
      } else {
        saves_serialized = true;
      }
    });
    worker.join();
  }
};
// INSERT_SAVE_METHOD
int main() {
  VulkanPipelineCache cache;
  active_cache = &cache;
  cache.SaveAndroidPipelineCache();
  if (!pipeline_can_progress) {
    std::cerr << "pipeline creation blocked during disk I/O\n";
    return 1;
  }
  assert(saves_serialized);
  assert(cache.android_vk_cache_dirty_);
  assert(cache.android_vk_cache_saved_ == 1);
  assert(std::filesystem::file_size("cache.bin") == 4);
  assert(!std::filesystem::exists("cache.bin.tmp"));
  cache.android_vk_cache_dirty_ = true;
  grow_snapshot_once = true;
  cache.SaveAndroidPipelineCache();
  assert(std::filesystem::file_size("cache.bin") == 8);
  assert(cache.android_vk_cache_saved_ == 2);
  grow_snapshot_once = false;
  cache.android_vk_cache_dirty_ = false;
  cache.SaveAndroidPipelineCache();
  assert(disk_opens == 2);
  cache.android_vk_cache_dirty_ = true;
  fail_snapshot = true;
  cache.SaveAndroidPipelineCache();
  assert(cache.android_vk_cache_dirty_);
  assert(disk_opens == 2);
  fail_snapshot = false;
  cache.driver_pipeline_cache_path_ = "missing/cache.bin";
  cache.SaveAndroidPipelineCache();
  assert(cache.android_vk_cache_dirty_);
  assert(cache.android_vk_cache_saved_ == 2);
  std::cout << "pipeline save lock and retry: PASS\n";
}
