#include <atomic>
#include <cassert>
#include <chrono>
#include <cstdint>
#include <mutex>

using VkDevice = int;
using VkPipeline = int;
using VkResult = int;
constexpr VkResult VK_SUCCESS = 0;

struct FakeFunctions {
  VkResult vkCreateGraphicsPipelines(VkDevice, VkPipeline, int, const int*, const void*,
                                     VkPipeline* pipeline) const {
    *pipeline = 7;
    return VK_SUCCESS;
  }
};

struct VulkanPipelineCache {
  FakeFunctions dfn;
  VkDevice device = 1;
  VkPipeline driver_pipeline_cache_ = 2;
  VkPipeline pipeline = 0;
  int pipeline_create_info = 0;
  std::mutex driver_pipeline_cache_lock_;
  std::atomic<bool> android_vk_cache_dirty_{false};
  std::atomic<uint64_t> android_vk_pipeline_create_us_total_{0};
  std::atomic<uint64_t> android_vk_pipeline_cache_lock_wait_us_total_{0};
  std::atomic<uint64_t> android_vk_pipelines_created_{0};

  void Create() {
    // INSERT_CREATE_BLOCK
    // INSERT_CREATE_METRICS
    assert(create_result == VK_SUCCESS);
    assert(pipeline == 7);
    assert(android_vk_cache_dirty_);
    assert(android_vk_pipelines_created_ == 1);
  }
};

int main() {
  VulkanPipelineCache cache;
  cache.Create();
}
