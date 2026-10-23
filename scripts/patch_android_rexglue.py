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



def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sdk", required=True, type=Path, help="ReXGlue SDK source directory")
    args = parser.parse_args()

    source = args.sdk / "src/ui/vulkan/vulkan_device.cpp"
    if not source.is_file():
        raise SystemExit(f"ReXGlue Vulkan source not found: {source}")

    chrono_header = args.sdk / "include/rex/chrono/chrono.h"
    chrono_text = chrono_header.read_text(encoding="utf-8")
    original, patched = ANDROID_CHRONO_FALLBACK_PATCH
    if patched not in chrono_text:
        if chrono_text.count(original) != 1:
            raise SystemExit(f"Expected one C++20 clock-cast compatibility point in {chrono_header}")
        chrono_header.write_text(chrono_text.replace(original, patched, 1), encoding="utf-8")
        print("Enabled ReXGlue's chrono compatibility shim for Android libc++.")
    else:
        print("Android libc++ chrono compatibility shim is already applied.")

    host_entry = args.sdk / "src/filesystem/devices/host_path_entry.cpp"
    host_entry_text = host_entry.read_text(encoding="utf-8")
    entry_changed = False
    for original, patched in (HOST_FILE_OPEN_TRACE_PATCH, HOST_FILE_MAPPED_TRACE_PATCH):
        if patched in host_entry_text:
            continue
        if host_entry_text.count(original) != 1:
            raise SystemExit(f"Expected one host-file I/O trace insertion point in {host_entry}")
        host_entry_text = host_entry_text.replace(original, patched, 1)
        entry_changed = True
    if entry_changed:
        host_entry.write_text(host_entry_text, encoding="utf-8")
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

    host_entry = args.sdk / "src/filesystem/devices/host_path_entry.cpp"
    host_entry_text = host_entry.read_text(encoding="utf-8")
    entry_changed = False
    for original, patched in (HOST_FILE_OPEN_TRACE_PATCH, HOST_FILE_MAPPED_TRACE_PATCH):
        if patched in host_entry_text:
            continue
        if host_entry_text.count(original) != 1:
            raise SystemExit(f"Expected one host-file I/O trace insertion point in {host_entry}")
        host_entry_text = host_entry_text.replace(original, patched, 1)
        entry_changed = True
    if entry_changed:
        host_entry.write_text(host_entry_text, encoding="utf-8")
        print("Added Android host-file open and mapped-file trace records.")
    else:
        print("Android host-file open tracing is already applied.")

    host_file = args.sdk / "src/filesystem/devices/host_path_file.cpp"
    host_file_text = host_file.read_text(encoding="utf-8")
    original, patched = HOST_FILE_READ_TRACE_PATCH
    if patched not in host_file_text:
        if host_file_text.count(original) != 1:
            raise SystemExit(f"Expected one host-file read trace insertion point in {host_file}")
        host_file.write_text(host_file_text.replace(original, patched, 1), encoding="utf-8")
        print("Added Android host-file byte-count trace records.")
    else:
        print("Android host-file read tracing is already applied.")

    pipeline_cache = args.sdk / "src/graphics/vulkan/pipeline_cache.cpp"
    if not pipeline_cache.is_file():
        raise SystemExit(f"ReXGlue Vulkan pipeline cache source not found: {pipeline_cache}")

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
