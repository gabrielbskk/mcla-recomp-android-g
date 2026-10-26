#!/usr/bin/env python3
"""Apply Android-specific defaults and Vulkan fallbacks to the ReXGlue SDK."""

from pathlib import Path
import argparse


PATCHES = {
    "vulkan_require_geometry_shader": (
        "REXCVAR_DEFINE_BOOL(vulkan_require_geometry_shader, !REX_PLATFORM_MAC,",
        "REXCVAR_DEFINE_BOOL(vulkan_require_geometry_shader, !REX_PLATFORM_MAC && !REX_PLATFORM_ANDROID,",
    ),
    "vulkan_require_fill_mode_non_solid": (
        "REXCVAR_DEFINE_BOOL(vulkan_require_fill_mode_non_solid, !REX_PLATFORM_MAC,",
        "REXCVAR_DEFINE_BOOL(vulkan_require_fill_mode_non_solid, !REX_PLATFORM_MAC && !REX_PLATFORM_ANDROID,",
    ),
}

DYN_LIBRARY_PATCH = (
    "  bool Load(const std::filesystem::path& path, SymbolResolution mode = SymbolResolution::kLazy);\n",
    "  bool Load(const std::filesystem::path& path, SymbolResolution mode = SymbolResolution::kLazy);\n"
    "  // Takes ownership of an already-opened platform loader handle.\n"
    "  bool LoadFromHandle(void* handle) { Close(); handle_ = handle; return handle_ != nullptr; }\n",
)

VULKAN_LOADER_PATCH = (
    "#else\n"
    "  loader_loaded = vulkan_instance->loader_.Load(platform::lib_names::kVulkanLoader);\n"
    "  if (!loader_loaded) {\n"
    "    REXLOG_ERROR(\"Failed to load {}\", platform::lib_names::kVulkanLoader);\n"
    "    return nullptr;\n"
    "  }\n"
    "#endif\n",
    "#elif REX_PLATFORM_ANDROID\n"
    "  // The app may return a validated custom driver loader; null means use Android's loader.\n"
    "  if (MclaAndroidOpenVulkanLoader) {\n"
    "    if (void* custom_loader = MclaAndroidOpenVulkanLoader()) {\n"
    "      loader_loaded = vulkan_instance->loader_.LoadFromHandle(custom_loader);\n"
    "      if (loader_loaded) {\n"
    "        REXLOG_INFO(\"Using app-selected Vulkan driver loader\");\n"
    "      }\n"
    "    }\n"
    "  }\n"
    "  if (!loader_loaded) {\n"
    "    loader_loaded = vulkan_instance->loader_.Load(platform::lib_names::kVulkanLoader);\n"
    "  }\n"
    "  if (!loader_loaded) {\n"
    "    REXLOG_ERROR(\"Failed to load {}\", platform::lib_names::kVulkanLoader);\n"
    "    return nullptr;\n"
    "  }\n"
    "#else\n"
    "  loader_loaded = vulkan_instance->loader_.Load(platform::lib_names::kVulkanLoader);\n"
    "  if (!loader_loaded) {\n"
    "    REXLOG_ERROR(\"Failed to load {}\", platform::lib_names::kVulkanLoader);\n"
    "    return nullptr;\n"
    "  }\n"
    "#endif\n",
)

VULKAN_LEGACY_LOADER_PATCH = (
    "#elif REX_PLATFORM_ANDROID\n"
    "  // The app may return a validated custom driver loader; null means use Android's loader.\n"
    "  if (void* custom_loader = MclaAndroidOpenVulkanLoader()) {\n"
    "    loader_loaded = vulkan_instance->loader_.LoadFromHandle(custom_loader);\n"
    "    if (loader_loaded) {\n"
    "      REXLOG_INFO(\"Using app-selected Vulkan driver loader\");\n"
    "    }\n"
    "  }\n"
    "  if (!loader_loaded) {\n"
    "    loader_loaded = vulkan_instance->loader_.Load(platform::lib_names::kVulkanLoader);\n"
    "  }\n"
    "  if (!loader_loaded) {\n"
    "    REXLOG_ERROR(\"Failed to load {}\", platform::lib_names::kVulkanLoader);\n"
    "    return nullptr;\n"
    "  }\n",
    VULKAN_LOADER_PATCH[1].split("#else\n", 1)[0],
)

VIDEO_MODE_DEFAULTS = (
    "REXCVAR_DEFINE_INT32(video_mode_width, 1280, \"Display\", \"Guest video mode width in pixels\")\n"
    "    .range(640, 0x0FFF)\n"
    "    .lifecycle(rex::cvar::Lifecycle::kRequiresRestart);\n\n"
    "REXCVAR_DEFINE_INT32(video_mode_height, 720, \"Display\", \"Guest video mode height in pixels\")\n"
    "    .range(480, 0x0FFF)\n"
    "    .lifecycle(rex::cvar::Lifecycle::kRequiresRestart);",
    "#if defined(__ANDROID__)\n"
    "// Start at 540p to reduce the guest's raster workload on mobile GPUs.\n"
    "REXCVAR_DEFINE_INT32(video_mode_width, 960, \"Display\", \"Guest video mode width in pixels\")\n"
    "    .range(640, 0x0FFF)\n"
    "    .lifecycle(rex::cvar::Lifecycle::kRequiresRestart);\n\n"
    "REXCVAR_DEFINE_INT32(video_mode_height, 540, \"Display\", \"Guest video mode height in pixels\")\n"
    "    .range(480, 0x0FFF)\n"
    "    .lifecycle(rex::cvar::Lifecycle::kRequiresRestart);\n"
    "#else\n"
    "REXCVAR_DEFINE_INT32(video_mode_width, 1280, \"Display\", \"Guest video mode width in pixels\")\n"
    "    .range(640, 0x0FFF)\n"
    "    .lifecycle(rex::cvar::Lifecycle::kRequiresRestart);\n\n"
    "REXCVAR_DEFINE_INT32(video_mode_height, 720, \"Display\", \"Guest video mode height in pixels\")\n"
    "    .range(480, 0x0FFF)\n"
    "    .lifecycle(rex::cvar::Lifecycle::kRequiresRestart);\n"
    "#endif",
)

PIPELINE_THREAD_DEFAULTS = (
    "REXCVAR_DEFINE_INT32(\n"
    "    vulkan_pipeline_creation_threads, -1, \"GPU/Vulkan\",\n",
    "#if defined(__ANDROID__)\n"
    "// Limit background shader compilation to leave CPU time for the game and renderer.\n"
    "constexpr int kDefaultVulkanPipelineCreationThreads = 2;\n"
    "#else\n"
    "constexpr int kDefaultVulkanPipelineCreationThreads = -1;\n"
    "#endif\n"
    "REXCVAR_DEFINE_INT32(\n"
    "    vulkan_pipeline_creation_threads, kDefaultVulkanPipelineCreationThreads, \"GPU/Vulkan\",\n",
)

PIPELINE_SUBMISSION_WAIT = (
    "      // Help worker threads on the processor thread to reduce warm-up latency.\n"
    "      CreateQueuedPipelinesOnProcessorThread();\n"
    "      bool await_creation_completion_event;\n"
    "      {\n"
    "        std::lock_guard<std::mutex> lock(creation_request_lock_);\n"
    "        // The queue is empty because of CreateQueuedPipelinesOnProcessorThread,\n"
    "        // only check in-flight creation by worker threads.\n"
    "        await_creation_completion_event = creation_threads_busy_ != 0;\n"
    "        if (await_creation_completion_event) {\n"
    "          creation_completion_event_->Reset();\n"
    "          creation_completion_set_event_ = true;\n"
    "        }\n"
    "      }\n"
    "      if (await_creation_completion_event) {\n"
    "        creation_request_cond_.notify_one();\n"
    "        rex::thread::Wait(creation_completion_event_.get(), false);\n"
    "      }",
    "#if REX_PLATFORM_ANDROID\n"
    "      // IssueSwap discards frames that used placeholders. Let the creation\n"
    "      // workers finish asynchronously instead of draining or joining them here.\n"
    "      if (!REXCVAR_GET(vulkan_async_skip_incomplete_frames)) {\n"
    "#endif\n"
    "        // Help worker threads on the processor thread to reduce warm-up latency.\n"
    "        CreateQueuedPipelinesOnProcessorThread();\n"
    "        bool await_creation_completion_event;\n"
    "        {\n"
    "          std::lock_guard<std::mutex> lock(creation_request_lock_);\n"
    "          // The queue is empty because of CreateQueuedPipelinesOnProcessorThread,\n"
    "          // only check in-flight creation by worker threads.\n"
    "          await_creation_completion_event = creation_threads_busy_ != 0;\n"
    "          if (await_creation_completion_event) {\n"
    "            creation_completion_event_->Reset();\n"
    "            creation_completion_set_event_ = true;\n"
    "          }\n"
    "        }\n"
    "        if (await_creation_completion_event) {\n"
    "          creation_request_cond_.notify_one();\n"
    "          rex::thread::Wait(creation_completion_event_.get(), false);\n"
    "        }\n"
    "#if REX_PLATFORM_ANDROID\n"
    "      }\n"
    "#endif",
)

PIPELINE_PENDING_ASYNC = (
    """    if (found_pipeline == VK_NULL_HANDLE) {
      PipelineCreationArguments creation_arguments;
      if (!TryGetPipelineCreationArgumentsForDescription(description, &*it, creation_arguments) ||
          !EnsurePipelineCreated(creation_arguments)) {
        return false;
      }
      found_pipeline = it->second.pipeline.load(std::memory_order_acquire);
    }
""",
    """    bool pending_async_placeholder = false;
    if (found_pipeline == VK_NULL_HANDLE) {
      pending_async_placeholder =
          use_async && it->second.is_placeholder.load(std::memory_order_acquire);
#if REX_PLATFORM_ANDROID
      pending_async_placeholder =
          pending_async_placeholder && REXCVAR_GET(vulkan_async_skip_incomplete_frames);
#endif
      if (!pending_async_placeholder) {
        PipelineCreationArguments creation_arguments;
        if (!TryGetPipelineCreationArgumentsForDescription(description, &*it,
                                                           creation_arguments) ||
            !EnsurePipelineCreated(creation_arguments)) {
          return false;
        }
        found_pipeline = it->second.pipeline.load(std::memory_order_acquire);
      }
    }
""",
)

PIPELINE_SKIP_SYNC_PLACEHOLDER = (
    """    if (TryGetPipelineCreationArgumentsForDescription(description, &pipeline,
                                                      creation_arguments_placeholder, true)) {
      pipeline.second.is_placeholder.store(true, std::memory_order_release);
      if (EnsurePipelineCreated(creation_arguments_placeholder, placeholder_pixel_shader_)) {
        {
          std::lock_guard<std::mutex> lock(creation_request_lock_);
          creation_queue_.push(creation_arguments_real);
        }
        creation_request_cond_.notify_one();
        queued_async_creation = true;
      } else {
        pipeline.second.is_placeholder.store(false, std::memory_order_release);
      }
    }
""",
    """    if (TryGetPipelineCreationArgumentsForDescription(description, &pipeline,
                                                      creation_arguments_placeholder, true)) {
      pipeline.second.is_placeholder.store(true, std::memory_order_release);
      pipeline.second.pipeline_layout.store(creation_arguments_placeholder.pipeline_layout,
                                            std::memory_order_release);
      bool skip_placeholder_creation = false;
#if REX_PLATFORM_ANDROID
      // When incomplete frames are discarded, do not compile a temporary
      // pipeline synchronously on the command processor thread. The draw path
      // marks the frame incomplete and IssueSwap drops it until the real
      // pipeline is ready on a worker.
      skip_placeholder_creation =
          REXCVAR_GET(vulkan_async_skip_incomplete_frames);
#endif
      if (skip_placeholder_creation ||
          EnsurePipelineCreated(creation_arguments_placeholder, placeholder_pixel_shader_)) {
        {
          std::lock_guard<std::mutex> lock(creation_request_lock_);
          creation_queue_.push(creation_arguments_real);
        }
        creation_request_cond_.notify_one();
        queued_async_creation = true;
      } else {
        pipeline.second.is_placeholder.store(false, std::memory_order_release);
      }
    }
""",
)

PIPELINE_ALLOW_PENDING_ASYNC = (
    "  return pipeline_out != VK_NULL_HANDLE && pipeline_layout_out != nullptr;\n"
    "}\n\nbool VulkanPipelineCache::IsCreatingPipelines() const {",
    "  return pipeline_layout_out != nullptr &&\n"
    "         (pipeline_out != VK_NULL_HANDLE || queued_async_creation);\n"
    "}\n\nbool VulkanPipelineCache::IsCreatingPipelines() const {",
)

PIPELINE_PENDING_LOOKUP_RETURN = (
    "    return pipeline_out != VK_NULL_HANDLE && pipeline_layout_out != nullptr;\n"
    "  }\n\n"
    "  // Create the pipeline if not already existing.",
    "    return pipeline_layout_out != nullptr &&\n"
    "           (pipeline_out != VK_NULL_HANDLE || pending_async_placeholder);\n"
    "  }\n\n"
    "  // Create the pipeline if not already existing.",
)

PIPELINE_CREATION_LOGS = (
    "  if (creation_arguments.pixel_shader) {\n"
    "    REXGPU_INFO(\"Creating graphics pipeline state with VS {:016X}, PS {:016X}\",\n"
    "                creation_arguments.vertex_shader->shader().ucode_data_hash(),\n"
    "                creation_arguments.pixel_shader->shader().ucode_data_hash());\n"
    "  } else {\n"
    "    REXGPU_INFO(\"Creating graphics pipeline state with VS {:016X}\",\n"
    "                creation_arguments.vertex_shader->shader().ucode_data_hash());\n"
    "  }",
    "  if (creation_arguments.pixel_shader) {\n"
    "#if REX_PLATFORM_ANDROID\n"
    "    REXGPU_DEBUG(\"Creating graphics pipeline state with VS {:016X}, PS {:016X}\",\n"
    "#else\n"
    "    REXGPU_INFO(\"Creating graphics pipeline state with VS {:016X}, PS {:016X}\",\n"
    "#endif\n"
    "                creation_arguments.vertex_shader->shader().ucode_data_hash(),\n"
    "                creation_arguments.pixel_shader->shader().ucode_data_hash());\n"
    "  } else {\n"
    "#if REX_PLATFORM_ANDROID\n"
    "    REXGPU_DEBUG(\"Creating graphics pipeline state with VS {:016X}\",\n"
    "#else\n"
    "    REXGPU_INFO(\"Creating graphics pipeline state with VS {:016X}\",\n"
    "#endif\n"
    "                creation_arguments.vertex_shader->shader().ucode_data_hash());\n"
    "  }",
)

PIPELINE_CACHE_HEADER_ANCHOR = "  void StorageWriteThread();\n"
PIPELINE_CACHE_HEADER_PATCH = """  void InitializeAndroidPipelineCache(const std::filesystem::path& cache_path);
  void SaveAndroidPipelineCache();
  void LogAndroidPipelineCacheMetrics();

  void StorageWriteThread();
"""

PIPELINE_CACHE_DEVICE_FUNCTIONS_ANCHOR = "XE_UI_VULKAN_FUNCTION(vkCreatePipelineLayout)\n"
PIPELINE_CACHE_DEVICE_FUNCTIONS_PATCH = (
    "XE_UI_VULKAN_FUNCTION(vkCreatePipelineLayout)\n"
    "XE_UI_VULKAN_FUNCTION(vkCreatePipelineCache)\n"
    "XE_UI_VULKAN_FUNCTION(vkDestroyPipelineCache)\n"
    "XE_UI_VULKAN_FUNCTION(vkGetPipelineCacheData)\n"
)

PIPELINE_CACHE_SOURCE_INCLUDE_ANCHOR = "#include <cstring>\n"
PIPELINE_CACHE_SOURCE_INCLUDE_PATCH = "#include <chrono>\n#include <cstring>\n#include <fstream>\n"

PIPELINE_CACHE_SOURCE_CONSTRUCTOR_ANCHOR = """VulkanPipelineCache::~VulkanPipelineCache() {
  Shutdown();
}

bool VulkanPipelineCache::Initialize() {
"""
PIPELINE_CACHE_SOURCE_CONSTRUCTOR_PATCH = """VulkanPipelineCache::~VulkanPipelineCache() {
  Shutdown();
}

void VulkanPipelineCache::InitializeAndroidPipelineCache(const std::filesystem::path& cache_path) {
  std::lock_guard<std::mutex> lock(driver_pipeline_cache_lock_);
  const ui::vulkan::VulkanDevice* const vulkan_device = command_processor_.GetVulkanDevice();
  const ui::vulkan::VulkanDevice::Functions& dfn = vulkan_device->functions();
  const VkDevice device = vulkan_device->device();

  if (driver_pipeline_cache_ != VK_NULL_HANDLE) {
    dfn.vkDestroyPipelineCache(device, driver_pipeline_cache_, nullptr);
    driver_pipeline_cache_ = VK_NULL_HANDLE;
  }
  driver_pipeline_cache_path_ = cache_path;

  std::vector<uint8_t> initial_data;
  std::ifstream input(cache_path, std::ios::binary | std::ios::ate);
  if (input) {
    const std::streamoff size = input.tellg();
    if (size >= static_cast<std::streamoff>(sizeof(VkPipelineCacheHeaderVersionOne))) {
      initial_data.resize(static_cast<size_t>(size));
      input.seekg(0, std::ios::beg);
      input.read(reinterpret_cast<char*>(initial_data.data()),
                 static_cast<std::streamsize>(size));
      if (input.gcount() != static_cast<std::streamsize>(size)) {
        initial_data.clear();
        android_vk_cache_rejected_.fetch_add(1, std::memory_order_relaxed);
        REXGPU_INFO("Android Vulkan pipeline cache rejected: truncated read");
      } else {
        VkPipelineCacheHeaderVersionOne header{};
        std::memcpy(&header, initial_data.data(), sizeof(header));
        VkPhysicalDeviceProperties properties;
        vulkan_device->vulkan_instance()->functions().vkGetPhysicalDeviceProperties(
            vulkan_device->physical_device(), &properties);
        const bool header_matches =
            header.headerSize == sizeof(VkPipelineCacheHeaderVersionOne) &&
            header.headerVersion == VK_PIPELINE_CACHE_HEADER_VERSION_ONE &&
            header.vendorID == properties.vendorID && header.deviceID == properties.deviceID &&
            std::memcmp(header.pipelineCacheUUID, properties.pipelineCacheUUID, VK_UUID_SIZE) == 0;
        if (!header_matches) {
          initial_data.clear();
          android_vk_cache_rejected_.fetch_add(1, std::memory_order_relaxed);
          REXGPU_INFO("Android Vulkan pipeline cache rejected: header mismatch");
        }
      }
    } else {
      initial_data.clear();
      android_vk_cache_rejected_.fetch_add(1, std::memory_order_relaxed);
      REXGPU_INFO("Android Vulkan pipeline cache rejected: truncated file");
    }
  }

  VkPipelineCacheCreateInfo create_info{};
  create_info.sType = VK_STRUCTURE_TYPE_PIPELINE_CACHE_CREATE_INFO;
  create_info.initialDataSize = initial_data.size();
  create_info.pInitialData = initial_data.empty() ? nullptr : initial_data.data();
  const VkResult result = dfn.vkCreatePipelineCache(device, &create_info, nullptr,
                                                    &driver_pipeline_cache_);
  if (result != VK_SUCCESS) {
    driver_pipeline_cache_ = VK_NULL_HANDLE;
    android_vk_cache_rejected_.fetch_add(1, std::memory_order_relaxed);
    REXGPU_WARN("Android Vulkan pipeline cache creation failed: {}", int32_t(result));
  } else if (!initial_data.empty()) {
    android_vk_cache_loaded_.fetch_add(1, std::memory_order_relaxed);
    REXGPU_INFO("Android Vulkan pipeline cache loaded: {} bytes", initial_data.size());
  } else {
    REXGPU_INFO("Android Vulkan pipeline cache started empty");
  }
}

void VulkanPipelineCache::SaveAndroidPipelineCache() {
  std::lock_guard<std::mutex> lock(driver_pipeline_cache_lock_);
  if (driver_pipeline_cache_ == VK_NULL_HANDLE || driver_pipeline_cache_path_.empty()) {
    return;
  }
  const ui::vulkan::VulkanDevice* const vulkan_device = command_processor_.GetVulkanDevice();
  const ui::vulkan::VulkanDevice::Functions& dfn = vulkan_device->functions();
  const VkDevice device = vulkan_device->device();
  size_t data_size = 0;
  if (dfn.vkGetPipelineCacheData(device, driver_pipeline_cache_, &data_size, nullptr) != VK_SUCCESS ||
      data_size == 0) {
    return;
  }
  std::vector<uint8_t> data(data_size);
  if (dfn.vkGetPipelineCacheData(device, driver_pipeline_cache_, &data_size, data.data()) != VK_SUCCESS) {
    return;
  }
  const std::filesystem::path temporary_path = driver_pipeline_cache_path_.string() + ".tmp";
  {
    std::ofstream output(temporary_path, std::ios::binary | std::ios::trunc);
    if (!output) {
      REXGPU_WARN("Android Vulkan pipeline cache save open failed");
      return;
    }
    output.write(reinterpret_cast<const char*>(data.data()), static_cast<std::streamsize>(data_size));
    if (!output) {
      return;
    }
  }
  std::error_code error;
  std::filesystem::rename(temporary_path, driver_pipeline_cache_path_, error);
  if (error) {
    REXGPU_WARN("Android Vulkan pipeline cache rename failed: {}", error.message());
    std::error_code cleanup_error;
    std::filesystem::remove(temporary_path, cleanup_error);
  }
  if (!error) {
    android_vk_cache_saved_.fetch_add(1, std::memory_order_relaxed);
    REXGPU_INFO("Android Vulkan pipeline cache saved: {} bytes", data_size);
  }
}

void VulkanPipelineCache::LogAndroidPipelineCacheMetrics() {
  REXGPU_INFO(
      "android_vk_cache_loaded={} android_vk_cache_rejected={} android_vk_cache_saved={} "
      "android_vk_pipelines_created={}",
      android_vk_cache_loaded_.load(std::memory_order_relaxed),
      android_vk_cache_rejected_.load(std::memory_order_relaxed),
      android_vk_cache_saved_.load(std::memory_order_relaxed),
      android_vk_pipelines_created_.load(std::memory_order_relaxed));
}

bool VulkanPipelineCache::Initialize() {
"""

PIPELINE_CACHE_STORAGE_ANCHOR = """  auto shader_storage_root = cache_root / "shaders";
  auto shader_storage_shareable_root = shader_storage_root / "shareable";
"""
PIPELINE_CACHE_STORAGE_PATCH = """  auto shader_storage_root = cache_root / "shaders";
  auto shader_storage_shareable_root = shader_storage_root / "shareable";
  auto shader_storage_local_root = shader_storage_root / "local";
  std::error_code shader_storage_error;
  std::filesystem::create_directories(shader_storage_local_root, shader_storage_error);
  if (shader_storage_error) {
    REXGPU_WARN("Android Vulkan pipeline cache directory creation failed: {}",
                shader_storage_error.message());
  } else {
    InitializeAndroidPipelineCache(
        shader_storage_local_root / fmt::format("{:08X}.vk.bin", title_id));
  }
"""

PIPELINE_CACHE_SHUTDOWN_SAVE_ANCHOR = """  ShutdownShaderStorage();

  const ui::vulkan::VulkanDevice* const vulkan_device = command_processor_.GetVulkanDevice();
"""
PIPELINE_CACHE_SHUTDOWN_SAVE_PATCH = """  SaveAndroidPipelineCache();
  ShutdownShaderStorage();

  const ui::vulkan::VulkanDevice* const vulkan_device = command_processor_.GetVulkanDevice();
"""

PIPELINE_CACHE_DESTROY_ANCHOR = """  const VkDevice device = vulkan_device->device();

  ProcessDeferredPipelineDestructions(true);
"""
PIPELINE_CACHE_DESTROY_PATCH = """  const VkDevice device = vulkan_device->device();

  {
    std::lock_guard<std::mutex> lock(driver_pipeline_cache_lock_);
    if (driver_pipeline_cache_ != VK_NULL_HANDLE) {
      dfn.vkDestroyPipelineCache(device, driver_pipeline_cache_, nullptr);
      driver_pipeline_cache_ = VK_NULL_HANDLE;
    }
  }

  ProcessDeferredPipelineDestructions(true);
"""

PIPELINE_CACHE_CREATE_ANCHOR = """VkResult create_result = dfn.vkCreateGraphicsPipelines(device, VK_NULL_HANDLE, 1,
                                                         &pipeline_create_info, nullptr, &pipeline);"""
PIPELINE_CACHE_CREATE_PATCH = """VkResult create_result;
  {
    std::lock_guard<std::mutex> lock(driver_pipeline_cache_lock_);
    create_result = dfn.vkCreateGraphicsPipelines(device, driver_pipeline_cache_, 1,
                                                   &pipeline_create_info, nullptr, &pipeline);
  }"""

PIPELINE_CACHE_STORAGE_THREAD_ANCHOR = (
    "  bool flush_pipelines = false;\n\n"
    "  while (true) {\n"
)
PIPELINE_CACHE_STORAGE_THREAD_PATCH = (
    "  bool flush_pipelines = false;\n"
    "  auto next_android_vk_cache_save =\n"
    "      std::chrono::steady_clock::now() + std::chrono::seconds(1);\n\n"
    "  while (true) {\n"
)
PIPELINE_CACHE_STORAGE_THREAD_WAIT_ANCHOR = (
    "      if (!shader && !write_pipeline) {\n"
    "        storage_write_request_cond_.wait(lock);\n"
    "        continue;\n"
    "      }\n"
)
PIPELINE_CACHE_STORAGE_THREAD_WAIT_PATCH = (
    "      if (!shader && !write_pipeline) {\n"
    "        storage_write_request_cond_.wait_for(lock, std::chrono::seconds(1));\n"
    "        const auto now = std::chrono::steady_clock::now();\n"
    "        if (now >= next_android_vk_cache_save) {\n"
    "          lock.unlock();\n"
    "          SaveAndroidPipelineCache();\n"
    "          LogAndroidPipelineCacheMetrics();\n"
    "          next_android_vk_cache_save = now + std::chrono::seconds(1);\n"
    "        }\n"
    "        continue;\n"
    "      }\n"
)
PIPELINE_CACHE_STORAGE_THREAD_METRICS_ANCHOR = (
    "    if (shader) {\n"
    "      shader_header.ucode_data_hash = shader->ucode_data_hash();\n"
)
PIPELINE_CACHE_STORAGE_THREAD_METRICS_PATCH = (
    "    const auto now = std::chrono::steady_clock::now();\n"
    "    if (now >= next_android_vk_cache_save) {\n"
    "      SaveAndroidPipelineCache();\n"
    "      LogAndroidPipelineCacheMetrics();\n"
    "      next_android_vk_cache_save = now + std::chrono::seconds(1);\n"
    "    }\n\n"
    "    if (shader) {\n"
    "      shader_header.ucode_data_hash = shader->ucode_data_hash();\n"
)

PIPELINE_CACHE_CREATE_METRICS_PATCH = (
    "\n"
    "  if (create_result == VK_SUCCESS) {\n"
    "    android_vk_pipelines_created_.fetch_add(1, std::memory_order_relaxed);\n"
    "  }"
)


def patch_android_vulkan_pipeline_cache(source: str) -> str:
    """Add Android-private Vulkan driver cache handling to ReXGlue v0.10.0."""
    if "InitializeAndroidPipelineCache" in source:
        return source
    anchors = (
        PIPELINE_CACHE_SOURCE_INCLUDE_ANCHOR,
        PIPELINE_CACHE_SOURCE_CONSTRUCTOR_ANCHOR,
        PIPELINE_CACHE_STORAGE_ANCHOR,
        PIPELINE_CACHE_SHUTDOWN_SAVE_ANCHOR,
        PIPELINE_CACHE_DESTROY_ANCHOR,
        PIPELINE_CACHE_CREATE_ANCHOR,
        PIPELINE_CACHE_STORAGE_THREAD_ANCHOR,
        PIPELINE_CACHE_STORAGE_THREAD_WAIT_ANCHOR,
        PIPELINE_CACHE_STORAGE_THREAD_METRICS_ANCHOR,
    )
    if any(source.count(anchor) != 1 for anchor in anchors):
        raise SystemExit("Expected ReXGlue v0.10.0 Vulkan pipeline cache anchors")
    source = source.replace(PIPELINE_CACHE_SOURCE_INCLUDE_ANCHOR,
                            PIPELINE_CACHE_SOURCE_INCLUDE_PATCH, 1)
    source = source.replace(PIPELINE_CACHE_SOURCE_CONSTRUCTOR_ANCHOR,
                            PIPELINE_CACHE_SOURCE_CONSTRUCTOR_PATCH, 1)
    source = source.replace(PIPELINE_CACHE_STORAGE_ANCHOR,
                            PIPELINE_CACHE_STORAGE_PATCH, 1)
    source = source.replace(PIPELINE_CACHE_SHUTDOWN_SAVE_ANCHOR,
                            PIPELINE_CACHE_SHUTDOWN_SAVE_PATCH, 1)
    source = source.replace(PIPELINE_CACHE_DESTROY_ANCHOR,
                            PIPELINE_CACHE_DESTROY_PATCH, 1)
    source = source.replace(PIPELINE_CACHE_CREATE_ANCHOR, PIPELINE_CACHE_CREATE_PATCH, 1)
    source = source.replace(PIPELINE_CACHE_CREATE_PATCH,
                            PIPELINE_CACHE_CREATE_PATCH + PIPELINE_CACHE_CREATE_METRICS_PATCH,
                            1)
    source = source.replace(PIPELINE_CACHE_STORAGE_THREAD_ANCHOR,
                            PIPELINE_CACHE_STORAGE_THREAD_PATCH, 1)
    source = source.replace(PIPELINE_CACHE_STORAGE_THREAD_WAIT_ANCHOR,
                            PIPELINE_CACHE_STORAGE_THREAD_WAIT_PATCH, 1)
    return source.replace(PIPELINE_CACHE_STORAGE_THREAD_METRICS_ANCHOR,
                          PIPELINE_CACHE_STORAGE_THREAD_METRICS_PATCH, 1)


def patch_android_vulkan_pipeline_cache_header(header: str) -> str:
    """Add the driver cache handle and path to the ReXGlue pipeline-cache object."""
    if "driver_pipeline_cache_" in header:
        return header
    if header.count(PIPELINE_CACHE_HEADER_ANCHOR) != 1:
        raise SystemExit("Expected ReXGlue v0.10.0 Vulkan pipeline cache header anchor")
    marker = "  VkPipelineCache driver_pipeline_cache_ = VK_NULL_HANDLE;\n"
    fields = (marker + "  std::filesystem::path driver_pipeline_cache_path_;\n"
              "  std::mutex driver_pipeline_cache_lock_;\n"
              "  std::atomic<uint64_t> android_vk_cache_loaded_{0};\n"
              "  std::atomic<uint64_t> android_vk_cache_rejected_{0};\n"
              "  std::atomic<uint64_t> android_vk_cache_saved_{0};\n"
              "  std::atomic<uint64_t> android_vk_pipelines_created_{0};\n\n")
    header = header.replace(PIPELINE_CACHE_HEADER_ANCHOR,
                            PIPELINE_CACHE_HEADER_PATCH + fields, 1)
    return header


def patch_android_vulkan_pipeline_functions(functions: str) -> str:
    """Expose Vulkan 1.0 pipeline-cache functions through ReXGlue's device table."""
    if "XE_UI_VULKAN_FUNCTION(vkCreatePipelineCache)" in functions:
        return functions
    if functions.count(PIPELINE_CACHE_DEVICE_FUNCTIONS_ANCHOR) != 1:
        raise SystemExit("Expected ReXGlue Vulkan 1.0 device-function anchor")
    return functions.replace(PIPELINE_CACHE_DEVICE_FUNCTIONS_ANCHOR,
                             PIPELINE_CACHE_DEVICE_FUNCTIONS_PATCH, 1)

ANDROID_MEMORY_BACKEND_PATCH = (
    "#if REX_PLATFORM_ANDROID\n"
    "  // TODO(Triang3l): Check if memfd can be used instead on API 30+.\n"
    "  if (android_ASharedMemory_create_) {\n"
    "    int sharedmem_fd = android_ASharedMemory_create_(path.c_str(), length);\n"
    "    return sharedmem_fd >= 0 ? static_cast<FileMappingHandle>(sharedmem_fd)\n"
    "                             : kFileMappingHandleInvalid;\n"
    "  }\n"
    "\n"
    "  // Use /dev/ashmem on API versions below 26, which added ASharedMemory.\n"
    "  // /dev/ashmem was disabled on API 29 for apps targeting it.\n"
    "  // https://chromium.googlesource.com/chromium/src/+/master/third_party/ashmem/ashmem-dev.c\n"
    "  int ashmem_fd = open(\"/\" ASHMEM_NAME_DEF, O_RDWR);\n"
    "  if (ashmem_fd < 0) {\n"
    "    return kFileMappingHandleInvalid;\n"
    "  }\n"
    "  char ashmem_name[ASHMEM_NAME_LEN];\n"
    "  strlcpy(ashmem_name, path.c_str(), rex::countof(ashmem_name));\n"
    "  if (ioctl(ashmem_fd, ASHMEM_SET_NAME, ashmem_name) < 0 ||\n"
    "      ioctl(ashmem_fd, ASHMEM_SET_SIZE, length) < 0) {\n"
    "    close(ashmem_fd);\n"
    "    return kFileMappingHandleInvalid;\n"
    "  }\n"
    "  return static_cast<FileMappingHandle>(ashmem_fd);\n"
    "#else\n",
    "#if REX_PLATFORM_ANDROID\n"
    "  static std::once_flag android_memory_init_once;\n"
    "  std::call_once(android_memory_init_once, AndroidInitialize);\n"
    "  if (android_ASharedMemory_create_) {\n"
    "    errno = 0;\n"
    "    int sharedmem_fd = android_ASharedMemory_create_(path.c_str(), length);\n"
    "    if (sharedmem_fd < 0) {\n"
    "      const int error = errno;\n"
    "      REXSYS_ERROR(\"ASharedMemory_create failed for {} ({} bytes): errno={} ({})\",\n"
    "                   path.string(), length, error, std::strerror(error));\n"
    "    } else {\n"
    "      REXSYS_INFO(\"Android guest memory backing store created: provider=ASharedMemory_create, \"\n"
    "                  \"name={}, bytes={}\", path.string(), length);\n"
    "      return static_cast<FileMappingHandle>(sharedmem_fd);\n"
    "    }\n"
    "  }\n"
    "\n"
    "  // Use /dev/ashmem only when the API 26+ shared-memory function is unavailable.\n"
    "  errno = 0;\n"
    "  int ashmem_fd = open(\"/\" ASHMEM_NAME_DEF, O_RDWR);\n"
    "  if (ashmem_fd < 0) {\n"
    "    const int error = errno;\n"
    "    REXSYS_ERROR(\"open(/dev/ashmem) failed for {} ({} bytes): errno={} ({})\",\n"
    "                 path.string(), length, error, std::strerror(error));\n"
    "    return kFileMappingHandleInvalid;\n"
    "  }\n"
    "  char ashmem_name[ASHMEM_NAME_LEN];\n"
    "  strlcpy(ashmem_name, path.c_str(), rex::countof(ashmem_name));\n"
    "  if (ioctl(ashmem_fd, ASHMEM_SET_NAME, ashmem_name) < 0) {\n"
    "    const int error = errno;\n"
    "    REXSYS_ERROR(\"ashmem ASHMEM_SET_NAME failed for {}: errno={} ({})\",\n"
    "                 path.string(), error, std::strerror(error));\n"
    "    close(ashmem_fd);\n"
    "    return kFileMappingHandleInvalid;\n"
    "  }\n"
    "  errno = 0;\n"
    "  if (ioctl(ashmem_fd, ASHMEM_SET_SIZE, length) < 0) {\n"
    "    const int error = errno;\n"
    "    REXSYS_ERROR(\"ashmem ASHMEM_SET_SIZE failed for {} ({} bytes): errno={} ({})\",\n"
    "                 path.string(), length, error, std::strerror(error));\n"
    "    close(ashmem_fd);\n"
    "    return kFileMappingHandleInvalid;\n"
    "  }\n"
    "  REXSYS_INFO(\"Android guest memory backing store created: provider=ashmem, name={}, bytes={}\",\n"
    "              path.string(), length);\n"
    "  return static_cast<FileMappingHandle>(ashmem_fd);\n"
    "#else\n",
)

ANDROID_MEMORY_INITIALIZER_PATCH = (
    "void AndroidInitialize() {\n"
    "  if (rex::GetAndroidApiLevel() >= 26) {\n"
    "    libandroid_ = dlopen(\"libandroid.so\", RTLD_NOW);\n"
    "    assert_not_null(libandroid_);\n"
    "    if (libandroid_) {\n"
    "      android_ASharedMemory_create_ = reinterpret_cast<decltype(android_ASharedMemory_create_)>(\n"
    "          dlsym(libandroid_, \"ASharedMemory_create\"));\n"
    "      assert_not_null(android_ASharedMemory_create_);\n"
    "    }\n"
    "  }\n"
    "}",
    "void AndroidInitialize() {\n"
    "  const int api_level = rex::GetAndroidApiLevel();\n"
    "  if (api_level < 26) {\n"
    "    REXSYS_WARN(\"ASharedMemory is unavailable on Android API {}; using ashmem fallback\",\n"
    "                api_level);\n"
    "    return;\n"
    "  }\n"
    "\n"
    "  if (!libandroid_) {\n"
    "    dlerror();\n"
    "    libandroid_ = dlopen(\"libandroid.so\", RTLD_NOW);\n"
    "  }\n"
    "  if (!libandroid_) {\n"
    "    const char* error = dlerror();\n"
    "    REXSYS_ERROR(\"dlopen(libandroid.so) failed: {}\", error ? error : \"unknown error\");\n"
    "    return;\n"
    "  }\n"
    "\n"
    "  if (!android_ASharedMemory_create_) {\n"
    "    dlerror();\n"
    "    android_ASharedMemory_create_ = reinterpret_cast<decltype(android_ASharedMemory_create_)>(\n"
    "        dlsym(libandroid_, \"ASharedMemory_create\"));\n"
    "    const char* error = dlerror();\n"
    "    if (error || !android_ASharedMemory_create_) {\n"
    "      REXSYS_ERROR(\"dlsym(ASharedMemory_create) failed: {}\",\n"
    "                   error ? error : \"symbol not found\");\n"
    "      android_ASharedMemory_create_ = nullptr;\n"
    "      return;\n"
    "    }\n"
    "  }\n"
    "  REXSYS_INFO(\"Android shared-memory backend initialized: API {} via ASharedMemory_create\",\n"
    "              api_level);\n"
    "}",
)


def patch_android_memory_initializer(text: str) -> str:
    """Make AndroidInitialize safe after library-load preinitialization."""
    original, patched = ANDROID_MEMORY_INITIALIZER_PATCH
    if patched in text:
        return text
    if original in text:
        return text.replace(original, patched, 1)

    start = text.find("void AndroidInitialize() {")
    if start < 0:
        raise SystemExit("Expected one Android memory initializer in SDK source")
    end = text.find("\n}\n", start)
    if end < 0:
        raise SystemExit("Android memory initializer has no closing brace")
    end += len("\n}")
    body = text[start:end]
    if "if (!libandroid_) {" in body and "if (!android_ASharedMemory_create_) {" in body:
        return text
    old_load = (
        '  dlerror();\n'
        '  libandroid_ = dlopen("libandroid.so", RTLD_NOW);'
    )
    guarded_load = (
        '  if (!libandroid_) {\n'
        '    dlerror();\n'
        '    libandroid_ = dlopen("libandroid.so", RTLD_NOW);\n'
        '  }'
    )
    if body.count(old_load) != 1:
        raise SystemExit("Unknown AndroidInitialize dlopen sequence in SDK source")
    body = body.replace(old_load, guarded_load, 1)

    old_lookup = (
        '  dlerror();\n'
        '  android_ASharedMemory_create_ = reinterpret_cast<decltype(android_ASharedMemory_create_)>(\n'
        '      dlsym(libandroid_, "ASharedMemory_create"));\n'
        '  const char* error = dlerror();\n'
        '  if (error || !android_ASharedMemory_create_) {\n'
        '    REXSYS_ERROR("dlsym(ASharedMemory_create) failed: {}",\n'
        '                 error ? error : "symbol not found");\n'
        '    android_ASharedMemory_create_ = nullptr;\n'
        '    return;\n'
        '  }'
    )
    guarded_lookup = (
        '  if (!android_ASharedMemory_create_) {\n'
        '    dlerror();\n'
        '    android_ASharedMemory_create_ = reinterpret_cast<decltype(android_ASharedMemory_create_)>(\n'
        '        dlsym(libandroid_, "ASharedMemory_create"));\n'
        '    const char* error = dlerror();\n'
        '    if (error || !android_ASharedMemory_create_) {\n'
        '      REXSYS_ERROR("dlsym(ASharedMemory_create) failed: {}",\n'
        '                   error ? error : "symbol not found");\n'
        '      android_ASharedMemory_create_ = nullptr;\n'
        '      return;\n'
        '    }\n'
        '  }'
    )
    if body.count(old_lookup) != 1:
        raise SystemExit("Unknown AndroidInitialize dlsym sequence in SDK source")
    body = body.replace(old_lookup, guarded_lookup, 1)
    return text[:start] + body + text[end:]

ANDROID_GUEST_MEMORY_ERROR_PATCH = (
    'REXSYS_ERROR("Unable to reserve the 4gb guest address space.");',
    'REXSYS_ERROR("Unable to create guest-memory backing store ({} bytes).", mapping_size);',
)

ANDROID_MEMORY_DIAGNOSTICS_HELPERS = r'''// MCLA_ANDROID_MEMFD_BACKEND: prepare the guest-memory backing store when
// librexruntime is loaded (before SDL starts its native main thread).
struct AndroidMemoryPreflightState {
  int fd;
  int provider;  // 1 = ASharedMemory, 2 = memfd.
  int ashared_errno;
  int memfd_errno;
  int memfd_truncate_errno;
  int rlimit_as_errno;
  long ashared_result;
  long memfd_result;
  size_t size;
  uint64_t rlimit_as_cur;
  uint64_t rlimit_as_max;
  uint64_t maps_entries;
  char first_map[64];
  char last_map[64];
};
static AndroidMemoryPreflightState android_memory_preflight = {};

static size_t AndroidGuestMemoryBackingSize() {
  long page_size = sysconf(_SC_PAGESIZE);
  if (page_size <= 0) page_size = 4096;
  const size_t granularity = static_cast<size_t>(page_size);
  const size_t guest_size = static_cast<size_t>(0x120000000ull);
  return ((guest_size + granularity + granularity - 1) / granularity) * granularity;
}

static void AndroidCaptureMemorySnapshot(AndroidMemoryPreflightState& state) {
  struct rlimit limit = {};
  if (getrlimit(RLIMIT_AS, &limit) == 0) {
    state.rlimit_as_cur = limit.rlim_cur == RLIM_INFINITY ? UINT64_MAX : limit.rlim_cur;
    state.rlimit_as_max = limit.rlim_max == RLIM_INFINITY ? UINT64_MAX : limit.rlim_max;
  } else {
    state.rlimit_as_errno = errno;
  }
  FILE* maps = std::fopen("/proc/self/maps", "r");
  if (!maps) return;
  char line[512];
  while (std::fgets(line, sizeof(line), maps)) {
    char range[64] = {};
    if (std::sscanf(line, "%63s", range) == 1) {
      if (state.maps_entries == 0) std::snprintf(state.first_map, sizeof(state.first_map), "%s", range);
      std::snprintf(state.last_map, sizeof(state.last_map), "%s", range);
      ++state.maps_entries;
    }
  }
  std::fclose(maps);
}

static void AndroidPreinitializeGuestMemoryBacking() {
  android_memory_preflight.fd = -1;
  android_memory_preflight.ashared_result = -1;
  android_memory_preflight.memfd_result = -1;
  AndroidCaptureMemorySnapshot(android_memory_preflight);
  android_memory_preflight.size = AndroidGuestMemoryBackingSize();

  libandroid_ = dlopen("libandroid.so", RTLD_NOW);
  if (libandroid_) {
    android_ASharedMemory_create_ = reinterpret_cast<decltype(android_ASharedMemory_create_)>(
        dlsym(libandroid_, "ASharedMemory_create"));
    if (android_ASharedMemory_create_) {
      errno = 0;
      android_memory_preflight.ashared_result = android_ASharedMemory_create_(
          "mcla-guest-memory", android_memory_preflight.size);
      android_memory_preflight.ashared_errno =
          android_memory_preflight.ashared_result < 0 ? errno : 0;
      if (android_memory_preflight.ashared_result >= 0) {
        android_memory_preflight.fd = static_cast<int>(android_memory_preflight.ashared_result);
        android_memory_preflight.provider = 1;
        return;
      }
    }
  }

  // memfd is available on Android 11+; it is also kept as the runtime fallback
  // if ASharedMemory_create is unavailable or rejects this backing size.
#if defined(SYS_memfd_create)
  if (android_get_device_api_level() >= 30) {
    errno = 0;
    android_memory_preflight.memfd_result =
        syscall(SYS_memfd_create, "mcla-guest-memory", MFD_CLOEXEC);
    android_memory_preflight.memfd_errno =
        android_memory_preflight.memfd_result < 0 ? errno : 0;
    if (android_memory_preflight.memfd_result >= 0) {
      if (ftruncate64(static_cast<int>(android_memory_preflight.memfd_result),
                      static_cast<off64_t>(android_memory_preflight.size)) == 0) {
        android_memory_preflight.fd = static_cast<int>(android_memory_preflight.memfd_result);
        android_memory_preflight.provider = 2;
        return;
      }
      android_memory_preflight.memfd_truncate_errno = errno;
      close(static_cast<int>(android_memory_preflight.memfd_result));
    }
  }
#endif
}

__attribute__((constructor)) static void AndroidPreinitializeGuestMemoryBackingAtLoad() {
  AndroidPreinitializeGuestMemoryBacking();
}

static const char* AndroidPreflightProviderName() {
  return android_memory_preflight.provider == 1 ? "ASharedMemory_create" :
         android_memory_preflight.provider == 2 ? "memfd_create" : "none";
}

static void AndroidLogMemoryDiagnostics(const std::filesystem::path& path, size_t bytes) {
  AndroidMemoryPreflightState current = {};
  AndroidCaptureMemorySnapshot(current);
  REXSYS_INFO("Android guest-memory preflight: stage=library_load provider={} result_fd={} "
              "bytes={} ASharedMemory_create_result={} errno={} ({}) "
              "memfd_create_result={} errno={} ({}) ftruncate64_errno={} ({}) "
              "RLIMIT_AS={}/{} rlimit_errno={} maps_entries={} first={} last={}",
              AndroidPreflightProviderName(), android_memory_preflight.fd,
              android_memory_preflight.size, android_memory_preflight.ashared_result,
              android_memory_preflight.ashared_errno,
              std::strerror(android_memory_preflight.ashared_errno),
              android_memory_preflight.memfd_result, android_memory_preflight.memfd_errno,
              std::strerror(android_memory_preflight.memfd_errno),
              android_memory_preflight.memfd_truncate_errno,
              std::strerror(android_memory_preflight.memfd_truncate_errno),
              android_memory_preflight.rlimit_as_cur, android_memory_preflight.rlimit_as_max,
              android_memory_preflight.rlimit_as_errno,
              android_memory_preflight.maps_entries, android_memory_preflight.first_map,
              android_memory_preflight.last_map);
  REXSYS_INFO("Android guest-memory request: name={} bytes={} stage=Runtime::Setup "
              "RLIMIT_AS={}/{} maps_entries={} first={} last={}", path.string(), bytes,
              current.rlimit_as_cur, current.rlimit_as_max, current.maps_entries,
              current.first_map, current.last_map);
}
'''

ANDROID_GUEST_MAP_FAILURE_PATCH = (
    "    if (!views_.all_views[n]) {\n"
    "      // Failed, so bail and try again.\n"
    "      UnmapViews();\n"
    "      return 1;\n"
    "    }",
    "    if (!views_.all_views[n]) {\n"
    "      const int error = errno;\n"
    "      const uintptr_t target_address = reinterpret_cast<uintptr_t>(\n"
    "          mapping_base + map_info[n].virtual_address_start);\n"
    "      const size_t view_size = map_info[n].virtual_address_end -\n"
    "                               map_info[n].virtual_address_start + 1;\n"
    "      const size_t file_offset = map_info[n].target_address & granularity_mask;\n"
    "      REXSYS_ERROR(\"Guest memory map attempt failed: base=0x{:016X}, view={}, \"\n"
    "                   \"addr=0x{:016X}, size=0x{:X}, offset=0x{:X}, \"\n"
    "                   \"flags=MAP_SHARED|MAP_FIXED, prot=RW, errno={} ({})\",\n"
    "                   reinterpret_cast<uintptr_t>(mapping_base), n, target_address, view_size,\n"
    "                   file_offset, error, std::strerror(error));\n"
    "      UnmapViews();\n"
    "      return 1;\n"
    "    }",
)

ANDROID_GUEST_MAP_SUCCESS_PATCH = (
    "  REXSYS_INFO(\"Guest memory arena mapped: virtual base 0x{:016X}, physical base 0x{:016X}\",\n"
    "              reinterpret_cast<uintptr_t>(virtual_membase_),\n"
    "              reinterpret_cast<uintptr_t>(physical_membase_));",
    "  REXSYS_INFO(\"Guest memory arena mapped: views={}, virtual base 0x{:016X}, physical base 0x{:016X}\",\n"
    "              rex::countof(views_.all_views),\n"
    "              reinterpret_cast<uintptr_t>(virtual_membase_),\n"
    "              reinterpret_cast<uintptr_t>(physical_membase_));",
)
ANDROID_GUEST_MAP_SUCCESS_PATCH_LEGACY = ANDROID_GUEST_MAP_SUCCESS_PATCH[1].replace(
    "rex::countof(views_.all_views)", "views_.all_views.size()"
)

ANDROID_MAP_FILE_ERRNO_PATCH = (
    "  if (file_offset % page != 0) {\n"
    "    return nullptr;\n"
    "  }",
    "  if (file_offset % page != 0) {\n"
    "    errno = EINVAL;\n"
    "    return nullptr;\n"
    "  }",
)

ANDROID_MAP_FILE_MISMATCH_PATCH = (
    "  if (base_address && result != base_address) {\n"
    "    munmap(result, length);\n"
    "    return nullptr;\n"
    "  }",
    "  if (base_address && result != base_address) {\n"
    "    munmap(result, length);\n"
    "    errno = EINVAL;\n"
    "    return nullptr;\n"
    "  }",
)


def patch_android_memory_backend(text: str) -> str:
    """Initialize Android shared memory lazily and report backing-store errors."""
    original, patched = ANDROID_MEMORY_BACKEND_PATCH
    if patched not in text:
        if text.count(original) == 1:
            text = text.replace(original, patched, 1)
        elif "ASharedMemory_create failed for" not in text:
            raise SystemExit("Expected one Android file-mapping backend block; SDK may have changed")

    if "MCLA_ANDROID_MEMFD_BACKEND" not in text:
        declaration = "static int (*android_ASharedMemory_create_)(const char* name, size_t size);\n"
        if text.count(declaration) != 1:
            raise SystemExit("Expected one Android shared-memory function pointer declaration")
        text = text.replace(declaration, declaration + ANDROID_MEMORY_DIAGNOSTICS_HELPERS, 1)
    elif "ASharedMemory_create_result" not in text:
        helper_start = text.find("// MCLA_ANDROID_MEMFD_BACKEND:")
        helper_end = text.find("void AndroidInitialize()", helper_start)
        if helper_start < 0 or helper_end < 0:
            raise SystemExit("Could not upgrade the previous Android memory diagnostics helper")
        text = text[:helper_start] + ANDROID_MEMORY_DIAGNOSTICS_HELPERS + "\n\n" + text[helper_end:]

    # Older outputs returned immediately when ASharedMemory_create failed,
    # making the memfd fallback below unreachable on precisely that failure.
    old_shared_failure = (
        '      REXSYS_ERROR("ASharedMemory_create failed for {} ({} bytes): errno={} ({})",\n'
        '                   path.string(), length, error, std::strerror(error));\n'
        '      return kFileMappingHandleInvalid;\n'
        '    }\n'
        '    REXSYS_INFO("Android guest memory backing store created: provider=ASharedMemory_create, "\n'
        '                "name={}, bytes={}", path.string(), length);\n'
        '    return static_cast<FileMappingHandle>(sharedmem_fd);'
    )
    new_shared_failure = (
        '      REXSYS_ERROR("ASharedMemory_create failed for {} ({} bytes): errno={} ({})",\n'
        '                   path.string(), length, error, std::strerror(error));\n'
        '    } else {\n'
        '      REXSYS_INFO("Android guest memory backing store created: provider=ASharedMemory_create, "\n'
        '                  "name={}, bytes={}", path.string(), length);\n'
        '      return static_cast<FileMappingHandle>(sharedmem_fd);\n'
        '    }'
    )
    if old_shared_failure in text:
        text = text.replace(old_shared_failure, new_shared_failure, 1)
    elif "ASharedMemory_create failed for" in text and "memfd_create failed for" in text:
        pass

    if "AndroidLogMemoryDiagnostics(path, length);" not in text:
        call_anchor = "  std::call_once(android_memory_init_once, AndroidInitialize);\n"
        if text.count(call_anchor) != 1:
            raise SystemExit("Expected one Android file-mapping initialization call")
        text = text.replace(call_anchor,
                            call_anchor + "  AndroidLogMemoryDiagnostics(path, length);\n", 1)

    if "MCLA_ANDROID_USE_PRECREATED_BACKING" not in text:
        precreated_anchor = "  AndroidLogMemoryDiagnostics(path, length);\n"
        use_precreated = (
            "  // MCLA_ANDROID_USE_PRECREATED_BACKING\n"
            "  if (android_memory_preflight.fd >= 0 && android_memory_preflight.size == length) {\n"
            "    const int fd = android_memory_preflight.fd;\n"
            "    android_memory_preflight.fd = -1;\n"
            "    REXSYS_INFO(\"Android guest memory backing store created: provider={}, bytes={}, stage=library_load\",\n"
            "                AndroidPreflightProviderName(), length);\n"
            "    return static_cast<FileMappingHandle>(fd);\n"
            "  }\n"
            "  if (android_memory_preflight.fd >= 0) {\n"
            "    close(android_memory_preflight.fd);\n"
            "    android_memory_preflight.fd = -1;\n"
            "  }\n"
        )
        if text.count(precreated_anchor) != 1:
            raise SystemExit("Expected one Android memory diagnostic call")
        text = text.replace(precreated_anchor, precreated_anchor + use_precreated, 1)

    if "memfd_create failed for" not in text:
        ashmem_anchor = (
            "  // Use /dev/ashmem only when the API 26+ shared-memory function is unavailable.\n"
            "  errno = 0;\n"
            "  int ashmem_fd = open(\"/\" ASHMEM_NAME_DEF, O_RDWR);\n"
        )
        memfd_fallback = (
            "  // Android 11+ fallback if early creation did not produce a usable descriptor.\n"
            "#if defined(SYS_memfd_create)\n"
            "  if (android_get_device_api_level() >= 30) {\n"
            "    errno = 0;\n"
            "    const long memfd = syscall(SYS_memfd_create, \"mcla-guest-memory\", MFD_CLOEXEC);\n"
            "    if (memfd < 0) {\n"
            "      const int error = errno;\n"
            "      REXSYS_ERROR(\"memfd_create failed for {} ({} bytes): errno={} ({})\",\n"
            "                   path.string(), length, error, std::strerror(error));\n"
            "    } else if (ftruncate64(static_cast<int>(memfd), static_cast<off64_t>(length)) < 0) {\n"
            "      const int error = errno;\n"
            "      REXSYS_ERROR(\"ftruncate64(memfd) failed for {} ({} bytes): errno={} ({})\",\n"
            "                   path.string(), length, error, std::strerror(error));\n"
            "      close(static_cast<int>(memfd));\n"
            "    } else {\n"
            "      REXSYS_INFO(\"Android guest memory backing store created: provider=memfd_create, "
            "bytes={}\", length);\n"
            "      return static_cast<FileMappingHandle>(memfd);\n"
            "    }\n"
            "  }\n"
            "#endif\n"
        )
        if text.count(ashmem_anchor) != 1:
            raise SystemExit("Expected one Android ashmem fallback point")
        text = text.replace(ashmem_anchor, memfd_fallback + ashmem_anchor, 1)
    return text


def patch_android_guest_maps(text: str) -> str:
    """Record one failed guest view per candidate base and the final mapped-view count."""
    text = text.replace(ANDROID_GUEST_MAP_SUCCESS_PATCH_LEGACY, ANDROID_GUEST_MAP_SUCCESS_PATCH[1])
    for original, patched in (ANDROID_GUEST_MAP_FAILURE_PATCH, ANDROID_GUEST_MAP_SUCCESS_PATCH):
        if patched in text:
            continue
        if text.count(original) != 1:
            raise SystemExit("Expected one guest-memory mapping diagnostic point; SDK may have changed")
        text = text.replace(original, patched, 1)
    return text


def patch_android_map_file_errno(text: str) -> str:
    """Preserve errno for invalid mmap inputs and unexpected fixed-address results."""
    for original, patched in (ANDROID_MAP_FILE_ERRNO_PATCH, ANDROID_MAP_FILE_MISMATCH_PATCH):
        if patched in text:
            continue
        if text.count(original) != 1:
            raise SystemExit("Expected one POSIX file-view mapping validation point; SDK may have changed")
        text = text.replace(original, patched, 1)
    return text


def patch_android_chrono_header(text: str) -> str:
    """Apply or recognize the Android chrono shim, including an extended libc++ variant."""
    original, patched = ANDROID_CHRONO_FALLBACK_PATCH
    if (patched in text or ANDROID_CHRONO_EXTENDED_LIBCPP_PATCH in text
            or ANDROID_CHRONO_SDK_ANDROID_PATCH in text):
        return text
    if text.count(original) != 1:
        raise SystemExit("Expected one C++20 clock-cast compatibility point; SDK may have changed")
    return text.replace(original, patched, 1)

TEXTURE_CACHE_MEMORY_SAMPLE = (
    "  if (destroyed_any) {\n"
    "    COUNT_profile_set(\"gpu/texture_cache/textures\", textures_.size());\n"
    "  }\n"
    "}\n\n"
    "void TextureCache::BeginSubmission",
    "  if (destroyed_any) {\n"
    "    COUNT_profile_set(\"gpu/texture_cache/textures\", textures_.size());\n"
    "  }\n"
    "#if defined(__ANDROID__)\n"
    "  // Pair with the application's VmRSS sample to compare texture-cache\n"
    "  // growth from other process or Vulkan-driver allocations.\n"
    "  static uint64_t last_android_memory_sample_ms = 0;\n"
    "  if (!last_android_memory_sample_ms ||\n"
    "      current_time - last_android_memory_sample_ms >= 10'000) {\n"
    "    last_android_memory_sample_ms = current_time;\n"
    "    const uint64_t texture_memory_mb =\n"
    "        (textures_total_host_memory_usage_ + ((UINT32_C(1) << 20) - 1)) >> 20;\n"
    "    REXLOG_INFO(\"android texture cache: {} MiB estimated allocation, {} entries \"\n"
    "                \"(soft limit {} MiB, hard limit {} MiB)\",\n"
    "                texture_memory_mb, textures_.size(), limit_soft_mb, limit_hard_mb);\n"
    "  }\n"
    "#endif\n"
    "}\n\n"
    "void TextureCache::BeginSubmission",
)

ASYNC_LOGGING_PATCHES = (
    (
        "#include <spdlog/sinks/rotating_file_sink.h>\n",
        "#include <spdlog/async.h>\n"
        "#include <spdlog/sinks/rotating_file_sink.h>\n",
    ),
    (
        "bool g_initialized = false;\n"
        "std::mutex g_mutex;",
        "bool g_initialized = false;\n"
        "#if defined(__ANDROID__)\n"
        "bool g_android_async_logging = false;\n"
        "#endif\n"
        "std::mutex g_mutex;",
    ),
    (
        "  auto logger = std::make_shared<spdlog::logger>(name, sinks.begin(), sinks.end());\n",
        "  std::shared_ptr<spdlog::logger> logger;\n"
        "#if defined(__ANDROID__)\n"
        "  if (g_android_async_logging) {\n"
        "    logger = std::make_shared<spdlog::async_logger>(\n"
        "        name, sinks.begin(), sinks.end(), spdlog::thread_pool(),\n"
        "        spdlog::async_overflow_policy::overrun_oldest);\n"
        "  } else\n"
        "#endif\n"
        "  {\n"
        "    logger = std::make_shared<spdlog::logger>(name, sinks.begin(), sinks.end());\n"
        "  }\n",
    ),
    (
        "  g_config = config;\n\n"
        "  // Early sink handling:",
        "  g_config = config;\n"
        "#if defined(__ANDROID__)\n"
        "  // Bounded async queue: logging calls enqueue quickly on the game thread;\n"
        "  // overrun_oldest prevents a slow flash write from blocking gameplay.\n"
        "  spdlog::init_thread_pool(8192, 1);\n"
        "  g_android_async_logging = true;\n"
        "#endif\n\n"
        "  // Early sink handling:",
    ),
)

PRIVATE_LOG_DEFAULTS_PATCH = (
    "  if (std::filesystem::exists(config_path_))\n"
    "    rex::cvar::LoadConfig(config_path_);\n\n"
    "  // Late-phase logging",
    "  if (std::filesystem::exists(config_path_))\n"
    "    rex::cvar::LoadConfig(config_path_);\n"
    "#if defined(__ANDROID__)\n"
    "  // Ignore stale external log paths from older app configs. Logs stay private;\n"
    "  // the launcher exports them through the Storage Access Framework on request.\n"
    "  const auto private_log_dir = user_data_root_.parent_path() / \"logs\";\n"
    "  std::error_code private_log_error;\n"
    "  std::filesystem::create_directories(private_log_dir, private_log_error);\n"
    "  if (!private_log_error) {\n"
    "    rex::cvar::SetFlagByName(\"log_file\", (private_log_dir / \"mcla.log\").string());\n"
    "    rex::cvar::SetFlagByName(\"log_max_file_size_mb\", \"10\");\n"
    "    rex::cvar::SetFlagByName(\"log_max_files\", \"3\");\n"
    "    rex::cvar::SetFlagByName(\"log_flush_interval\", \"2\");\n"
    "  }\n"
    "#endif\n\n"
    "  // Late-phase logging",
)

HOST_FILE_OPEN_TRACE_PATCH = (
    "  *out_file = new HostPathFile(desired_access, this, std::move(file_handle));\n"
    "  return X_STATUS_SUCCESS;",
    "  *out_file = new HostPathFile(desired_access, this, std::move(file_handle));\n"
    "#if defined(__ANDROID__) && defined(MCLA_ANDROID_IO_TRACE)\n"
    "  REXFS_INFO(\"android io trace open path='{}'\", host_path_.string());\n"
    "#endif\n"
    "  return X_STATUS_SUCCESS;",
)

HOST_FILE_MAPPED_TRACE_PATCH = (
    "  return memory::MappedMemory::Open(host_path_, mode, offset, length);",
    "  auto mapped = memory::MappedMemory::Open(host_path_, mode, offset, length);\n"
    "#if defined(__ANDROID__) && defined(MCLA_ANDROID_IO_TRACE)\n"
    "  if (mapped) {\n"
    "    REXFS_INFO(\"android io trace open_mapped path='{}' offset={} bytes={}\",\n"
    "               host_path_.string(), offset, length);\n"
    "  }\n"
    "#endif\n"
    "  return mapped;",
)


def patch_android_host_entry(text: str) -> str:
    """Add I/O tracing while accepting the older result-bearing trace format."""
    markers = (
        "android io trace open path=",
        "android io trace open_mapped path=",
    )
    for (original, patched), marker in zip(
        (HOST_FILE_OPEN_TRACE_PATCH, HOST_FILE_MAPPED_TRACE_PATCH), markers
    ):
        if patched in text or marker in text:
            continue
        if text.count(original) != 1:
            raise SystemExit("Expected one Android host-file I/O trace point; SDK may have changed")
        text = text.replace(original, patched, 1)
    return text

HOST_FILE_READ_TRACE_PATCH = (
    "  if (file_handle_->Read(byte_offset, buffer.data(), buffer.size(), out_bytes_read)) {\n"
    "    return X_STATUS_SUCCESS;",
    "  if (file_handle_->Read(byte_offset, buffer.data(), buffer.size(), out_bytes_read)) {\n"
    "#if defined(__ANDROID__) && defined(MCLA_ANDROID_IO_TRACE)\n"
    "    REXFS_INFO(\"android io trace read path='{}' offset={} bytes={}\",\n"
    "               entry()->absolute_path(), byte_offset, out_bytes_read ? *out_bytes_read : 0);\n"
    "#endif\n"
    "    return X_STATUS_SUCCESS;",
)

HOST_FILE_LOGGING_INCLUDE_PATCH = (
    "#include <rex/filesystem/devices/host_path_file.h>\n",
    "#include <rex/filesystem/devices/host_path_file.h>\n\n#include <rex/logging.h>\n",
)

ANDROID_CHRONO_FALLBACK_PATCH = (
    "#ifdef __APPLE__\n"
    "// Apple libc++ does not expose clock_time_conversion or clock_cast.",
    "#if defined(__APPLE__) || defined(__ANDROID__)\n"
    "// Apple and Android libc++ do not expose clock_time_conversion or clock_cast.",
)

ANDROID_CHRONO_EXTENDED_LIBCPP_PATCH = (
    "#if defined(__APPLE__) || defined(__ANDROID__) || "
    "(defined(__linux__) && defined(_LIBCPP_VERSION))"
)
ANDROID_CHRONO_SDK_ANDROID_PATCH = (
    "#if defined(__APPLE__) || defined(__ANDROID__)\n"
    "// Apple and Android NDK libc++ do not expose clock_time_conversion or clock_cast."
)


def patch_android_platform_cmake(text: str) -> str:
    """Make the SDK's platform selection explicit for Android toolchains."""
    if 'elseif(ANDROID OR CMAKE_SYSTEM_NAME STREQUAL "Android")' in text:
        return text
    anchor = (
        '    add_compile_definitions(REX_PLATFORM_WINDOWS=1)\n'
        'elseif(UNIX AND NOT APPLE)\n'
    )
    if text.count(anchor) != 1:
        raise SystemExit("Expected the ReXGlue platform-selection CMake block")
    android_block = (
        '    add_compile_definitions(REX_PLATFORM_WINDOWS=1)\n'
        'elseif(ANDROID OR CMAKE_SYSTEM_NAME STREQUAL "Android")\n'
        '    if(NOT REX_TARGET_PROCESSOR MATCHES "aarch64|ARM64|arm64")\n'
        '        message(FATAL_ERROR "Unsupported Android architecture: ${REX_TARGET_PROCESSOR}")\n'
        '    endif()\n'
        '    set(REX_PLATFORM "android-arm64")\n'
        '    add_compile_definitions(REX_PLATFORM_ANDROID=1)\n'
        'elseif(UNIX AND NOT APPLE)\n'
    )
    return text.replace(anchor, android_block, 1)


def patch_android_ui_cmake(text: str) -> str:
    """Select the Android native-window surface and avoid X11/Wayland probes."""
    if "surface_android.cpp" not in text:
        source_else = text.find("else()", text.find("surface_mac.cpp"))
        if source_else < 0:
            raise SystemExit("Expected the ReXGlue UI platform-source block")
        source_end = text.find("endif()", source_else)
        if source_end < 0 or "surface_gnulinux.cpp" not in text[source_else:source_end]:
            raise SystemExit("Expected the ReXGlue GNU/Linux UI source branch")
        replacement = (
            "elseif(ANDROID)\n"
            "    set(REXUI_PLATFORM_SOURCES\n"
            "        surface_android.cpp\n"
            "    )\n"
            "else()\n"
        )
        text = text[:source_else] + replacement + text[source_else + len("else()\n"):]
    if "if(UNIX AND NOT APPLE AND NOT ANDROID)" not in text:
        linux_anchor = "if(UNIX AND NOT APPLE)\n    find_package(PkgConfig REQUIRED)"
        if text.count(linux_anchor) != 1:
            raise SystemExit("Expected the ReXGlue UI host-backend dependency block")
        text = text.replace(
            linux_anchor,
            "if(UNIX AND NOT APPLE AND NOT ANDROID)\n    find_package(PkgConfig REQUIRED)",
            1,
        )
    return text


def patch_android_thirdparty_cmake(text: str) -> str:
    """Do not enable desktop Linux SDL drivers in an Android build."""
    if "if(UNIX AND NOT APPLE AND NOT ANDROID)" in text:
        return text
    anchor = "if(UNIX AND NOT APPLE)\n    set(SDL_X11"
    if text.count(anchor) != 1:
        raise SystemExit("Expected the ReXGlue SDL Linux-backend block")
    return text.replace(
        anchor,
        "if(UNIX AND NOT APPLE AND NOT ANDROID)\n    set(SDL_X11",
        1,
    )


def patch_android_core_cmake(text: str) -> str:
    """Link Android fibers against the vendored ARM64 libucontext."""
    if "REX_USE_LIBUCONTEXT=1" in text:
        return text
    anchor = "add_library(rex::core ALIAS rexcore)\n"
    if text.count(anchor) != 1:
        raise SystemExit("Expected the ReXGlue core target declaration")
    block = (
        anchor +
        "\nif(MCLA_LIBUCONTEXT_ROOT)\n"
        "    target_compile_definitions(rexcore PUBLIC REX_USE_LIBUCONTEXT=1)\n"
        "    target_include_directories(rexcore PUBLIC \"${MCLA_LIBUCONTEXT_ROOT}/include\")\n"
        "    target_link_libraries(rexcore PRIVATE \"${MCLA_LIBUCONTEXT_ROOT}/lib/libucontext.a\")\n"
        "endif()\n"
    )
    text = text.replace(anchor, block, 1)
    link_block = (
        "if(APPLE)\n"
        "    target_link_libraries(rexcore PRIVATE pthread)\n"
        "elseif(UNIX)\n"
        "    target_link_libraries(rexcore PRIVATE pthread rt dl)\n"
        "endif()"
    )
    if text.count(link_block) != 1:
        raise SystemExit("Expected the ReXGlue core platform link block")
    text = text.replace(
        link_block,
        "if(APPLE)\n"
        "    target_link_libraries(rexcore PRIVATE pthread)\n"
        "elseif(ANDROID)\n"
        "    target_link_libraries(rexcore PRIVATE dl log)\n"
        "elseif(UNIX)\n"
        "    target_link_libraries(rexcore PRIVATE pthread rt dl)\n"
        "endif()",
        1,
    )
    return text


def patch_android_fiber_header(text: str) -> str:
    """Use libucontext's Android-safe context type instead of removed bionic APIs."""
    if "libucontext/libucontext.h" not in text:
        include_anchor = "#include <ucontext.h>"
        if text.count(include_anchor) != 1:
            raise SystemExit("Expected the ReXGlue fiber ucontext include")
        text = text.replace(
            include_anchor,
            "#if REX_PLATFORM_ANDROID || defined(REX_USE_LIBUCONTEXT)\n"
            "#include <libucontext/libucontext.h>\n"
            "#else\n"
            "#include <ucontext.h>\n"
            "#endif",
            1,
        )
    if "libucontext_ucontext_t context_{};" not in text:
        context_anchor = "  ucontext_t context_{};"
        if text.count(context_anchor) != 1:
            raise SystemExit("Expected the ReXGlue fiber context member")
        text = text.replace(
            context_anchor,
            "#if REX_PLATFORM_ANDROID || defined(REX_USE_LIBUCONTEXT)\n"
            "  libucontext_ucontext_t context_{};\n"
            "#else\n"
            "  ucontext_t context_{};\n"
            "#endif",
            1,
        )
    return text


def patch_android_fiber_source(text: str) -> str:
    """Call the explicit libucontext entry points on Android."""
    if "libucontext_getcontext" in text:
        return text
    for old, new in (
        ("getcontext(", "libucontext_getcontext("),
        ("makecontext(", "libucontext_makecontext("),
        ("swapcontext(", "libucontext_swapcontext("),
    ):
        if text.count(old) < 1:
            raise SystemExit(f"Expected ReXGlue fiber call {old}")
        text = text.replace(old, new)
    return text


def patch_android_memory_api_helper(text: str) -> str:
    """Include the shared Android API-level helper in the POSIX memory backend."""
    if "#include <rex/main_android.h>" in text:
        return text
    anchor = "#include <android/api-level.h>\n"
    if text.count(anchor) != 1:
        raise SystemExit("Expected the Android API-level include in memory_posix.cpp")
    return text.replace(anchor, anchor + "#include <rex/main_android.h>\n", 1)


def patch_android_threading_source(text: str) -> str:
    """Avoid glibc-only robust mutex APIs absent from Android bionic."""
    old = "#if REX_PLATFORM_LINUX\n"
    new = "#if REX_PLATFORM_LINUX && !REX_PLATFORM_ANDROID\n"
    if new in text and old not in text:
        return text
    if text.count(old) < 1:
        raise SystemExit("Expected Linux mutex guards in threading_posix.cpp")
    return text.replace(old, new)


def android_main_header() -> str:
    return """#pragma once
#include <android/api-level.h>

namespace rex {
inline int GetAndroidApiLevel() { return android_get_device_api_level(); }
}  // namespace rex
"""


def patch_android_window_sources(text: str) -> str:
    """Route SDL's Vulkan surface discovery through ANativeWindow on Android."""
    if "#include <rex/ui/surface_android.h>" not in text:
        include_anchor = "#elif REX_PLATFORM_MAC\n"
        if text.count(include_anchor) < 1:
            raise SystemExit("Expected SDL window platform include block")
        text = text.replace(
            include_anchor,
            "#elif REX_PLATFORM_ANDROID\n#include <rex/ui/surface_android.h>\n"
            "#elif REX_PLATFORM_MAC\n",
            1,
        )
    android_surface_branch = (
        "#elif REX_PLATFORM_ANDROID\n"
        "  SDL_PropertiesID props = SDL_GetWindowProperties(sdl_window_);\n"
        "  if (allowed_types & Surface::kTypeFlag_AndroidNativeWindow) {\n"
        "    auto* native_window = static_cast<ANativeWindow*>(\n"
        "        SDL_GetPointerProperty(props, SDL_PROP_WINDOW_ANDROID_WINDOW_POINTER, nullptr));\n"
        "    if (native_window) {\n"
        "      return std::make_unique<AndroidNativeWindowSurface>(native_window);\n"
        "    }\n"
        "  }\n"
        "#else\n"
    )
    props_marker = "SDL_PropertiesID props = SDL_GetWindowProperties(sdl_window_);"
    create_pos = text.find("std::unique_ptr<Surface> WindowSDL::CreateSurfaceImpl")
    props_pos = text.find(props_marker, create_pos)
    if props_pos < 0:
        raise SystemExit("Expected SDL window surface creation block")
    if "#elif REX_PLATFORM_ANDROID" in text[create_pos:props_pos]:
        return text
    desktop_else_pos = text.rfind("#else\n", 0, props_pos)
    if desktop_else_pos < 0:
        raise SystemExit("Expected SDL desktop surface branch")
    return text[:desktop_else_pos] + android_surface_branch + text[desktop_else_pos + len("#else\n"):]


def patch_android_windowed_app_main(text: str) -> str:
    """Use the named Android app creator instead of the desktop singleton."""
    old = "    std::unique_ptr<rex::ui::WindowedApp> app = rex::ui::GetWindowedAppCreator()(app_context);"
    if "WindowedApp::GetCreator(\"mcla\")" in text:
        return text
    if text.count(old) != 1:
        raise SystemExit("Expected the SDL windowed-app creator call")
    new = (
        "#if REX_PLATFORM_ANDROID\n"
        "    auto app_creator = rex::ui::WindowedApp::GetCreator(\"mcla\");\n"
        "#else\n"
        "    auto app_creator = rex::ui::GetWindowedAppCreator();\n"
        "#endif\n"
        "    if (!app_creator) {\n"
        "      REXLOG_ERROR(\"No windowed app creator registered\");\n"
        "      return EXIT_FAILURE;\n"
        "    }\n"
        "    std::unique_ptr<rex::ui::WindowedApp> app = app_creator(app_context);"
    )
    return text.replace(old, new, 1)


def android_surface_sources() -> tuple[str, str]:
    """Return the small ANativeWindow surface adapter needed by Vulkan."""
    header = """#pragma once
#include <android/native_window.h>
#include <rex/ui/surface.h>

namespace rex::ui {
class AndroidNativeWindowSurface final : public Surface {
 public:
  explicit AndroidNativeWindowSurface(ANativeWindow* window) : window_(window) {}
  TypeIndex GetType() const override { return kTypeIndex_AndroidNativeWindow; }
  ANativeWindow* window() const { return window_; }

 protected:
  bool GetSizeImpl(uint32_t& width_out, uint32_t& height_out) const override;

 private:
  ANativeWindow* window_;
};
}  // namespace rex::ui
"""
    source = """#include <rex/ui/surface_android.h>

namespace rex::ui {
bool AndroidNativeWindowSurface::GetSizeImpl(uint32_t& width_out,
                                             uint32_t& height_out) const {
  if (!window_) {
    return false;
  }
  const int width = ANativeWindow_getWidth(window_);
  const int height = ANativeWindow_getHeight(window_);
  if (width <= 0 || height <= 0) {
    return false;
  }
  width_out = static_cast<uint32_t>(width);
  height_out = static_cast<uint32_t>(height);
  return true;
}
}  // namespace rex::ui
"""
    return header, source


def patch_android_platform_files(sdk: Path) -> None:
    """Apply only the CMake/windowing pieces needed by an Android SDK build."""
    cmake_patches = (
        (sdk / "CMakeLists.txt", patch_android_platform_cmake),
        (sdk / "src/core/CMakeLists.txt", patch_android_core_cmake),
        (sdk / "src/ui/CMakeLists.txt", patch_android_ui_cmake),
        (sdk / "thirdparty/CMakeLists.txt", patch_android_thirdparty_cmake),
        (sdk / "src/ui/window_sdl.cpp", patch_android_window_sources),
        (sdk / "src/ui/windowed_app_main_sdl.cpp", patch_android_windowed_app_main),
    )
    for path, patch in cmake_patches:
        if not path.is_file():
            raise SystemExit(f"ReXGlue Android platform source not found: {path}")
        original = path.read_text(encoding="utf-8")
        patched = patch(original)
        if patched != original:
            path.write_text(patched, encoding="utf-8")
            print(f"Patched Android platform support in {path}.")

    fiber_header = sdk / "include/rex/thread/fiber.h"
    fiber_source = sdk / "src/core/fiber_posix.cpp"
    for path, patch in ((fiber_header, patch_android_fiber_header),
                        (fiber_source, patch_android_fiber_source)):
        if not path.is_file():
            raise SystemExit(f"ReXGlue fiber source not found: {path}")
        original = path.read_text(encoding="utf-8")
        patched = patch(original)
        if patched != original:
            path.write_text(patched, encoding="utf-8")
            print(f"Patched Android fiber context support in {path}.")

    memory_source = sdk / "src/core/memory_posix.cpp"
    if not memory_source.is_file():
        raise SystemExit(f"ReXGlue memory source not found: {memory_source}")
    memory_original = memory_source.read_text(encoding="utf-8")
    memory_patched = patch_android_memory_api_helper(memory_original)
    if memory_patched != memory_original:
        memory_source.write_text(memory_patched, encoding="utf-8")
        print(f"Added Android API-level helper include to {memory_source}.")

    main_android_header = sdk / "include/rex/main_android.h"
    if not main_android_header.exists():
        main_android_header.write_text(android_main_header(), encoding="utf-8")
        print(f"Added {main_android_header}.")
    elif main_android_header.read_text(encoding="utf-8") != android_main_header():
        raise SystemExit(f"Unexpected existing Android API helper: {main_android_header}")

    threading_source = sdk / "src/core/threading_posix.cpp"
    if not threading_source.is_file():
        raise SystemExit(f"ReXGlue threading source not found: {threading_source}")
    threading_original = threading_source.read_text(encoding="utf-8")
    threading_patched = patch_android_threading_source(threading_original)
    if threading_patched != threading_original:
        threading_source.write_text(threading_patched, encoding="utf-8")
        print(f"Disabled glibc-only robust mutex recovery on Android in {threading_source}.")

    header, source = android_surface_sources()
    surface_header = sdk / "include/rex/ui/surface_android.h"
    surface_source = sdk / "src/ui/surface_android.cpp"
    if not surface_header.exists():
        surface_header.write_text(header, encoding="utf-8")
        print(f"Added {surface_header}.")
    elif surface_header.read_text(encoding="utf-8") != header:
        raise SystemExit(f"Unexpected existing Android surface header: {surface_header}")
    if not surface_source.exists():
        surface_source.write_text(source, encoding="utf-8")
        print(f"Added {surface_source}.")
    elif surface_source.read_text(encoding="utf-8") != source:
        raise SystemExit(f"Unexpected existing Android surface source: {surface_source}")



def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sdk", required=True, type=Path, help="ReXGlue SDK source directory")
    args = parser.parse_args()

    patch_android_platform_files(args.sdk)

    source = args.sdk / "src/ui/vulkan/vulkan_device.cpp"
    if not source.is_file():
        raise SystemExit(f"ReXGlue Vulkan source not found: {source}")

    memory_source = args.sdk / "src/core/memory_posix.cpp"
    if not memory_source.is_file():
        raise SystemExit(f"ReXGlue POSIX memory backend not found: {memory_source}")
    memory_text = memory_source.read_text(encoding="utf-8")
    include_anchor = "#include <sys/ioctl.h>\n"
    if memory_text.count(include_anchor) != 1:
        raise SystemExit(f"Expected one Android memory include point in {memory_source}")
    android_memory_includes = (
        "#include <android/api-level.h>\n"
        "#include <linux/memfd.h>\n"
        "#include <mutex>\n"
        "#include <sys/resource.h>\n"
        "#include <sys/syscall.h>\n"
        "#include <sys/types.h>\n"
    )
    for include in android_memory_includes.splitlines(keepends=True):
        if include not in memory_text:
            memory_text = memory_text.replace(include_anchor, include_anchor + include, 1)
    memory_text = patch_android_memory_initializer(memory_text)
    memory_text = patch_android_memory_backend(memory_text)
    memory_text = patch_android_map_file_errno(memory_text)
    if memory_text != memory_source.read_text(encoding="utf-8"):
        memory_source.write_text(memory_text, encoding="utf-8")
        print("Initialized ASharedMemory on demand and added errno diagnostics for guest-memory creation.")
    else:
        print("Android guest-memory initialization and diagnostics are already applied.")

    guest_memory_source = args.sdk / "src/system/xmemory.cpp"
    if not guest_memory_source.is_file():
        raise SystemExit(f"ReXGlue guest memory source not found: {guest_memory_source}")
    guest_memory_text = guest_memory_source.read_text(encoding="utf-8")
    original_guest_memory_text = guest_memory_text
    original, patched = ANDROID_GUEST_MEMORY_ERROR_PATCH
    if patched not in guest_memory_text:
        if guest_memory_text.count(original) != 1:
            raise SystemExit(f"Expected one guest-memory backing-store failure message in {guest_memory_source}")
        guest_memory_text = guest_memory_text.replace(original, patched, 1)
    guest_memory_text = patch_android_guest_maps(guest_memory_text)
    if guest_memory_text != original_guest_memory_text:
        guest_memory_source.write_text(guest_memory_text, encoding="utf-8")
        print("Added guest-memory mapping success/failure diagnostics.")
    else:
        print("Guest-memory backing-store and mapping diagnostics are already applied.")

    chrono_header = args.sdk / "include/rex/chrono/chrono.h"
    chrono_text = chrono_header.read_text(encoding="utf-8")
    patched_chrono_text = patch_android_chrono_header(chrono_text)
    if patched_chrono_text != chrono_text:
        chrono_header.write_text(patched_chrono_text, encoding="utf-8")
        print("Enabled ReXGlue's chrono compatibility shim for Android libc++.")
    else:
        print("Android libc++ chrono compatibility shim is already applied.")

    host_entry = args.sdk / "src/filesystem/devices/host_path_entry.cpp"
    host_entry_text = host_entry.read_text(encoding="utf-8")
    patched_host_entry_text = patch_android_host_entry(host_entry_text)
    entry_changed = patched_host_entry_text != host_entry_text
    if entry_changed:
        host_entry.write_text(patched_host_entry_text, encoding="utf-8")
        print("Added Android host-file open and mapped-file trace records.")
    else:
        print("Android host-file open tracing is already applied.")

    host_file = args.sdk / "src/filesystem/devices/host_path_file.cpp"
    host_file_text = host_file.read_text(encoding="utf-8")
    original_include, patched_include = HOST_FILE_LOGGING_INCLUDE_PATCH
    if patched_include not in host_file_text:
        if host_file_text.count(original_include) != 1:
            raise SystemExit(f"Expected one host-file logging include insertion point in {host_file}")
        host_file_text = host_file_text.replace(original_include, patched_include, 1)
    original, patched = HOST_FILE_READ_TRACE_PATCH
    if patched not in host_file_text:
        if host_file_text.count(original) != 1:
            raise SystemExit(f"Expected one host-file read trace insertion point in {host_file}")
        host_file_text = host_file_text.replace(original, patched, 1)
        print("Added Android host-file byte-count trace records.")
    else:
        print("Android host-file read tracing is already applied.")
    host_file.write_text(host_file_text, encoding="utf-8")

    pipeline_cache = args.sdk / "src/graphics/vulkan/pipeline_cache.cpp"
    if not pipeline_cache.is_file():
        raise SystemExit(f"ReXGlue Vulkan pipeline cache source not found: {pipeline_cache}")

    pipeline_cache_header = args.sdk / "include/rex/graphics/vulkan/pipeline_cache.h"
    if not pipeline_cache_header.is_file():
        raise SystemExit(f"ReXGlue Vulkan pipeline cache header not found: {pipeline_cache_header}")
    pipeline_header_text = pipeline_cache_header.read_text(encoding="utf-8")
    patched_pipeline_header_text = patch_android_vulkan_pipeline_cache_header(pipeline_header_text)
    if patched_pipeline_header_text != pipeline_header_text:
        pipeline_cache_header.write_text(patched_pipeline_header_text, encoding="utf-8")
        print("Added Android Vulkan driver pipeline-cache state to the ReXGlue header.")
    else:
        print("Android Vulkan driver pipeline-cache header state is already applied.")

    pipeline_functions = args.sdk / "include/rex/ui/vulkan/functions/device_1_0.inc"
    if not pipeline_functions.is_file():
        raise SystemExit(f"ReXGlue Vulkan device function list not found: {pipeline_functions}")
    pipeline_functions_text = pipeline_functions.read_text(encoding="utf-8")
    patched_pipeline_functions_text = patch_android_vulkan_pipeline_functions(
        pipeline_functions_text
    )
    if patched_pipeline_functions_text != pipeline_functions_text:
        pipeline_functions.write_text(patched_pipeline_functions_text, encoding="utf-8")
        print("Added Vulkan pipeline-cache functions to the ReXGlue device table.")
    else:
        print("Vulkan pipeline-cache functions are already in the ReXGlue device table.")

    pipeline_source_text = pipeline_cache.read_text(encoding="utf-8")
    patched_pipeline_source_text = patch_android_vulkan_pipeline_cache(pipeline_source_text)
    if patched_pipeline_source_text != pipeline_source_text:
        pipeline_cache.write_text(patched_pipeline_source_text, encoding="utf-8")
        print("Added Android Vulkan driver pipeline-cache load/use/save handling.")
    else:
        print("Android Vulkan driver pipeline-cache handling is already applied.")

    logging_source = args.sdk / "src/core/logging.cpp"
    if not logging_source.is_file():
        raise SystemExit(f"ReXGlue logging source not found: {logging_source}")
    logging_text = logging_source.read_text(encoding="utf-8")
    logging_changed = False
    for original, patched in ASYNC_LOGGING_PATCHES:
        if patched in logging_text:
            continue
        if logging_text.count(original) != 1:
            raise SystemExit(f"Expected one Android async logging patch point in {logging_source}")
        logging_text = logging_text.replace(original, patched, 1)
        logging_changed = True
    if logging_changed:
        logging_source.write_text(logging_text, encoding="utf-8")
        print("Moved Android log writes to a bounded async queue with drop-oldest overflow.")
    else:
        print("Android bounded async logging is already applied.")

    app_source = args.sdk / "src/ui/rex_app.cpp"
    if not app_source.is_file():
        raise SystemExit(f"ReXGlue app source not found: {app_source}")
    app_text = app_source.read_text(encoding="utf-8")
    original, patched = PRIVATE_LOG_DEFAULTS_PATCH
    if patched not in app_text:
        if app_text.count(original) != 1:
            raise SystemExit(f"Expected one private Android log setup point in {app_source}")
        app_source.write_text(app_text.replace(original, patched, 1), encoding="utf-8")
        print("Forced Android logs into app-private storage with 10 MiB / 3-file rotation.")
    else:
        print("Android private log storage and rotation defaults are already applied.")

    pipeline_text = pipeline_cache.read_text(encoding="utf-8")
    original, patched = PIPELINE_THREAD_DEFAULTS
    if patched not in pipeline_text:
        if pipeline_text.count(original) != 1:
            raise SystemExit(
                f"Expected one default Vulkan pipeline thread count; SDK may have changed: {pipeline_cache}"
            )
        pipeline_cache.write_text(pipeline_text.replace(original, patched, 1), encoding="utf-8")
        print("Set Android Vulkan shader compilation to two background workers by default.")
    else:
        print("Android Vulkan shader compilation worker default already applied.")

    pipeline_text = pipeline_cache.read_text(encoding="utf-8")
    original, patched = PIPELINE_SUBMISSION_WAIT
    if patched not in pipeline_text:
        if pipeline_text.count(original) != 1:
            raise SystemExit(
                "Expected one Vulkan pipeline submission wait block; SDK may have changed: "
                f"{pipeline_cache}"
            )
        pipeline_cache.write_text(pipeline_text.replace(original, patched, 1), encoding="utf-8")
        print("Kept Android async pipeline creation off the graphics submission thread.")
    else:
        print("Android async pipeline submission behavior already applied.")

    pipeline_text = pipeline_cache.read_text(encoding="utf-8")
    original, patched = PIPELINE_PENDING_ASYNC
    if patched not in pipeline_text:
        if pipeline_text.count(original) != 1:
            raise SystemExit(
                "Expected one missing-pipeline lookup block; SDK may have changed: "
                f"{pipeline_cache}"
            )
        pipeline_cache.write_text(pipeline_text.replace(original, patched, 1), encoding="utf-8")
        print("Kept incomplete Android pipelines queued instead of compiling them synchronously.")
    else:
        print("Android pending-pipeline lookup behavior already applied.")

    pipeline_text = pipeline_cache.read_text(encoding="utf-8")
    original, patched = PIPELINE_PENDING_LOOKUP_RETURN
    if patched not in pipeline_text:
        if pipeline_text.count(original) != 1:
            raise SystemExit(
                "Expected one pending Vulkan pipeline return block; SDK may have changed: "
                f"{pipeline_cache}"
            )
        pipeline_cache.write_text(pipeline_text.replace(original, patched, 1), encoding="utf-8")
        print("Kept queued Android pipelines valid while their handles are still null.")
    else:
        print("Android queued-pipeline handle lookup behavior already applied.")

    pipeline_text = pipeline_cache.read_text(encoding="utf-8")
    original, patched = PIPELINE_SKIP_SYNC_PLACEHOLDER
    if patched not in pipeline_text:
        if pipeline_text.count(original) != 1:
            raise SystemExit(
                "Expected one asynchronous placeholder pipeline block; SDK may have changed: "
                f"{pipeline_cache}"
            )
        pipeline_cache.write_text(pipeline_text.replace(original, patched, 1), encoding="utf-8")
        print("Skipped synchronous placeholder pipeline creation when Android drops incomplete frames.")
    else:
        print("Android asynchronous placeholder behavior already applied.")

    pipeline_text = pipeline_cache.read_text(encoding="utf-8")
    original, patched = PIPELINE_ALLOW_PENDING_ASYNC
    if patched not in pipeline_text:
        if pipeline_text.count(original) != 1:
            raise SystemExit(
                "Expected one Vulkan pipeline lookup return block; SDK may have changed: "
                f"{pipeline_cache}"
            )
        pipeline_cache.write_text(pipeline_text.replace(original, patched, 1), encoding="utf-8")
        print("Allowed Android callers to observe a queued pipeline with a valid layout and no handle.")
    else:
        print("Android queued-pipeline return behavior already applied.")

    pipeline_text = pipeline_cache.read_text(encoding="utf-8")
    original, patched = PIPELINE_CREATION_LOGS
    if patched not in pipeline_text:
        if pipeline_text.count(original) != 1:
            raise SystemExit(
                "Expected one Vulkan pipeline creation log block; SDK may have changed: "
                f"{pipeline_cache}"
            )
        pipeline_cache.write_text(pipeline_text.replace(original, patched, 1), encoding="utf-8")
        print("Reduced Android Vulkan pipeline creation logs from info to debug.")
    else:
        print("Android Vulkan pipeline creation logs are already debug-only.")

    texture_cache = args.sdk / "src/graphics/pipeline/texture/cache.cpp"
    if not texture_cache.is_file():
        raise SystemExit(f"ReXGlue texture cache source not found: {texture_cache}")
    texture_text = texture_cache.read_text(encoding="utf-8")
    original, patched = TEXTURE_CACHE_MEMORY_SAMPLE
    if patched not in texture_text:
        if texture_text.count(original) != 1:
            raise SystemExit(
                "Expected one texture-cache eviction/report block; SDK may have changed: "
                f"{texture_cache}"
            )
        texture_cache.write_text(texture_text.replace(original, patched, 1), encoding="utf-8")
        print("Added an Android-only texture-cache memory sample every 10 seconds.")
    else:
        print("Android texture-cache memory sampling is already applied.")

    text = source.read_text(encoding="utf-8")
    changed = False
    for name, (upstream, android) in PATCHES.items():
        if android in text:
            continue
        if text.count(upstream) != 1:
            raise SystemExit(f"Expected one known default for {name}; SDK may have changed: {source}")
        text = text.replace(upstream, android, 1)
        changed = True

    if changed:
        source.write_text(text, encoding="utf-8")
        print("Applied Android Vulkan fallback defaults for geometry shaders and non-solid fill.")
    else:
        print("Android Vulkan fallback defaults already applied.")

    header = args.sdk / "include/rex/platform/dynlib.h"
    if not header.is_file():
        raise SystemExit(f"ReXGlue dynamic-library header not found: {header}")
    header_text = header.read_text(encoding="utf-8")
    original, patched = DYN_LIBRARY_PATCH
    if patched not in header_text:
        if header_text.count(original) != 1:
            raise SystemExit(f"Expected one DynamicLibrary::Load declaration: {header}")
        header.write_text(header_text.replace(original, patched, 1), encoding="utf-8")
        print("Added ownership transfer for the Android Vulkan loader handle.")

    instance = args.sdk / "src/ui/vulkan/vulkan_instance.cpp"
    if not instance.is_file():
        raise SystemExit(f"ReXGlue Vulkan instance source not found: {instance}")
    instance_text = instance.read_text(encoding="utf-8")
    instance_changed = False
    strong_declaration = 'extern "C" void* MclaAndroidOpenVulkanLoader();'
    weak_declaration = 'extern "C" void* MclaAndroidOpenVulkanLoader() __attribute__((weak));'
    if weak_declaration not in instance_text:
        if strong_declaration in instance_text:
            instance_text = instance_text.replace(strong_declaration, weak_declaration, 1)
            instance_changed = True
        else:
            include = "#include <rex/ui/vulkan/presenter.h>\n"
            if instance_text.count(include) != 1:
                raise SystemExit(f"Expected one Vulkan presenter include: {instance}")
            declaration = (include + "\n#if REX_PLATFORM_ANDROID\n" + weak_declaration + "\n#endif\n")
            instance_text = instance_text.replace(include, declaration, 1)
            instance_changed = True

    original, patched = VULKAN_LOADER_PATCH
    if patched not in instance_text:
        legacy, replacement = VULKAN_LEGACY_LOADER_PATCH
        if legacy in instance_text:
            instance_text = instance_text.replace(legacy, replacement, 1)
            instance_changed = True
        else:
            if instance_text.count(original) != 1:
                raise SystemExit(f"Expected one Android loader insertion point: {instance}")
            instance_text = instance_text.replace(original, patched, 1)
            instance_changed = True

    if instance_changed:
        instance.write_text(instance_text, encoding="utf-8")
        print("Added Android custom-driver loading with system Vulkan fallback.")

    window = args.sdk / "src/ui/window.cpp"
    if not window.is_file():
        raise SystemExit(f"ReXGlue window source not found: {window}")
    window_text = window.read_text(encoding="utf-8")
    original, patched = VIDEO_MODE_DEFAULTS
    if patched not in window_text:
        if window_text.count(original) != 1:
            raise SystemExit(f"Expected one default guest video mode in {window}; SDK may have changed")
        window.write_text(window_text.replace(original, patched, 1), encoding="utf-8")
        print("Set the Android guest video mode default to 960x540 (540p).")


if __name__ == "__main__":
    main()
