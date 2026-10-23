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



def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sdk", required=True, type=Path, help="ReXGlue SDK source directory")
    args = parser.parse_args()

    source = args.sdk / "src/ui/vulkan/vulkan_device.cpp"
    if not source.is_file():
        raise SystemExit(f"ReXGlue Vulkan source not found: {source}")

    pipeline_cache = args.sdk / "src/graphics/vulkan/pipeline_cache.cpp"
    if not pipeline_cache.is_file():
        raise SystemExit(f"ReXGlue Vulkan pipeline cache source not found: {pipeline_cache}")
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
