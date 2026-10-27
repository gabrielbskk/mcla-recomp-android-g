import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "patch_android_rexglue", ROOT / "scripts" / "patch_android_rexglue.py"
)
PATCHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCHER)


PIPELINE_CACHE_SOURCE = """#include <cstring>
#include <rex/graphics/vulkan/pipeline_cache.h>

VulkanPipelineCache::~VulkanPipelineCache() {
  Shutdown();
}

bool VulkanPipelineCache::Initialize() {
  return true;
}

void VulkanPipelineCache::InitializeShaderStorage(const std::filesystem::path& cache_root,
                                                   uint32_t title_id, bool blocking) {
  auto shader_storage_root = cache_root / "shaders";
  auto shader_storage_shareable_root = shader_storage_root / "shareable";
}

void VulkanPipelineCache::ShutdownShaderStorage() {
  if (storage_write_thread_) {
  }
}

void VulkanPipelineCache::StorageWriteThread() {
  bool flush_pipelines = false;

  while (true) {
    const Shader* shader = nullptr;
    bool write_pipeline = false;
    {
      std::unique_lock<std::mutex> lock(storage_write_request_lock_);
      if (!shader && !write_pipeline) {
        storage_write_request_cond_.wait(lock);
        continue;
      }
    }
    if (shader) {
      shader_header.ucode_data_hash = shader->ucode_data_hash();
    }
  }
}

bool VulkanPipelineCache::EnsurePipelineCreated() {
  VkPipelineCacheCreateInfo pipeline_cache_create_info;
  pipeline_cache_create_info.sType = VK_STRUCTURE_TYPE_PIPELINE_CACHE_CREATE_INFO;
  pipeline_cache_create_info.pNext = nullptr;
  pipeline_cache_create_info.flags = 0;
  pipeline_cache_create_info.initialDataSize = 0;
  pipeline_cache_create_info.pInitialData = nullptr;
  VkResult result = dfn.vkCreatePipelineCache(device, &pipeline_cache_create_info, nullptr,
                                              &pipeline_cache_);
  VkResult create_result = dfn.vkCreateGraphicsPipelines(device, VK_NULL_HANDLE, 1,
                                                         &pipeline_create_info, nullptr, &pipeline);
}

void VulkanPipelineCache::Shutdown() {
  ShutdownShaderStorage();

  const ui::vulkan::VulkanDevice* const vulkan_device = command_processor_.GetVulkanDevice();
  const ui::vulkan::VulkanDevice::Functions& dfn = vulkan_device->functions();
  const VkDevice device = vulkan_device->device();

  ProcessDeferredPipelineDestructions(true);
  dfn.vkDestroyPipelineCache(device, pipeline_cache_, nullptr);
}
"""


class AndroidPipelineCachePatchTest(unittest.TestCase):
    def test_save_allows_pipeline_creation_during_disk_io(self):
        compiler = shutil.which("clang++") or shutil.which("c++")
        if not compiler:
            self.skipTest("C++ compiler required")
        patched = PATCHER.patch_android_vulkan_pipeline_cache(PIPELINE_CACHE_SOURCE)
        start = patched.index("void VulkanPipelineCache::SaveAndroidPipelineCache()")
        end = patched.index("void VulkanPipelineCache::LogAndroidPipelineCacheMetrics()", start)
        method = patched[start:end].replace("std::ofstream", "ProbeOutput")
        harness = (ROOT / "tests/pipeline_cache_save_harness.cpp").read_text()
        with tempfile.TemporaryDirectory(prefix="mcla-cache-save-") as directory:
            source = Path(directory) / "test.cpp"
            binary = Path(directory) / "test"
            source.write_text(harness.replace("// INSERT_SAVE_METHOD", method))
            build = subprocess.run([compiler, "-std=c++17", "-pthread", str(source),
                                    "-o", str(binary)], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(binary)], cwd=directory, capture_output=True,
                                 text=True, timeout=15)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_save_retries_when_driver_cache_grows_during_snapshot(self):
        compiler = shutil.which("clang++") or shutil.which("c++")
        if not compiler:
            self.skipTest("C++ compiler required")
        patched = PATCHER.patch_android_vulkan_pipeline_cache(PIPELINE_CACHE_SOURCE)
        start = patched.index("void VulkanPipelineCache::SaveAndroidPipelineCache()")
        end = patched.index("void VulkanPipelineCache::LogAndroidPipelineCacheMetrics()", start)
        method = patched[start:end].replace("std::ofstream", "ProbeOutput")
        harness = (ROOT / "tests/pipeline_cache_save_harness.cpp").read_text()
        with tempfile.TemporaryDirectory(prefix="mcla-cache-incomplete-") as directory:
            source = Path(directory) / "test.cpp"
            binary = Path(directory) / "test"
            source.write_text(harness.replace("// INSERT_SAVE_METHOD", method))
            build = subprocess.run([compiler, "-std=c++17", "-pthread", str(source),
                                    "-o", str(binary)], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(binary)], cwd=directory, capture_output=True,
                                 text=True, timeout=15)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_init_retries_rejected_persisted_cache_with_empty_cache(self):
        compiler = shutil.which("clang++") or shutil.which("c++")
        if not compiler:
            self.skipTest("C++ compiler required")
        patched = PATCHER.patch_android_vulkan_pipeline_cache(PIPELINE_CACHE_SOURCE)
        start = patched.index(
            "void VulkanPipelineCache::InitializeAndroidPipelineCache(")
        end = patched.index("void VulkanPipelineCache::SaveAndroidPipelineCache()", start)
        method = patched[start:end]
        harness = (ROOT / "tests/pipeline_cache_init_harness.cpp").read_text()
        with tempfile.TemporaryDirectory(prefix="mcla-cache-init-") as directory:
            source = Path(directory) / "test.cpp"
            binary = Path(directory) / "test"
            source.write_text(harness.replace("// INSERT_INIT_METHOD", method))
            build = subprocess.run([compiler, "-std=c++17", "-pthread", str(source),
                                    "-o", str(binary)], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(binary)], cwd=directory, capture_output=True,
                                 text=True, timeout=15)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_upgrades_current_cache_save_without_reapplying_unrelated_patches(self):
        current = PATCHER.patch_android_vulkan_pipeline_cache(PIPELINE_CACHE_SOURCE)
        upgraded = PATCHER.patch_android_vulkan_pipeline_cache(current)
        self.assertIn("driver_pipeline_cache_save_lock_", upgraded)
        self.assertEqual(PATCHER.patch_android_vulkan_pipeline_cache(upgraded), upgraded)
        header = PATCHER.patch_android_vulkan_pipeline_cache_header(
            "class Cache {\n  void StorageWriteThread();\n};\n")
        self.assertIn("std::mutex driver_pipeline_cache_save_lock_;", header)
        self.assertEqual(PATCHER.patch_android_vulkan_pipeline_cache_header(header), header)

    def test_repairs_partial_save_lock_patch_without_duplicate_initialize_lock(self):
        partial = PATCHER.PIPELINE_CACHE_SOURCE_CONSTRUCTOR_PATCH.replace(
            "void VulkanPipelineCache::InitializeAndroidPipelineCache(const std::filesystem::path& cache_path) {\n"
            "  std::lock_guard<std::mutex> lock(driver_pipeline_cache_lock_);",
            "void VulkanPipelineCache::InitializeAndroidPipelineCache(const std::filesystem::path& cache_path) {\n"
            "  std::lock_guard<std::mutex> save_lock(driver_pipeline_cache_save_lock_);\n"
            "  std::lock_guard<std::mutex> lock(driver_pipeline_cache_lock_);",
            1,
        )
        partial += """
VkResult VulkanPipelineCache::EnsurePipelineCreated() {
  VkResult create_result;
  const auto android_pipeline_create_start = std::chrono::steady_clock::now();
  {
    std::lock_guard<std::mutex> lock(driver_pipeline_cache_lock_);
    create_result = dfn.vkCreateGraphicsPipelines(device, driver_pipeline_cache_, 1,
                                                   &pipeline_create_info, nullptr, &pipeline);
  }
}
"""
        repaired = PATCHER.patch_android_vulkan_pipeline_cache(partial)
        self.assertEqual(
            repaired.count("std::lock_guard<std::mutex> save_lock(driver_pipeline_cache_save_lock_);"),
            2,
        )
        self.assertIn(
            "std::unique_lock<std::mutex> lock(driver_pipeline_cache_lock_);",
            repaired,
        )
        self.assertEqual(PATCHER.patch_android_vulkan_pipeline_cache(repaired), repaired)

    def test_orders_cache_destroy_after_serialized_saves(self):
        source = PATCHER.patch_android_vulkan_pipeline_cache(PIPELINE_CACHE_SOURCE) + """
void VulkanPipelineCache::Shutdown() {
  const ui::vulkan::VulkanDevice* const vulkan_device = command_processor_.GetVulkanDevice();
  const ui::vulkan::VulkanDevice::Functions& dfn = vulkan_device->functions();
  const VkDevice device = vulkan_device->device();
  {
    std::lock_guard<std::mutex> lock(driver_pipeline_cache_lock_);
    if (driver_pipeline_cache_ != VK_NULL_HANDLE) {
      dfn.vkDestroyPipelineCache(device, driver_pipeline_cache_, nullptr);
      driver_pipeline_cache_ = VK_NULL_HANDLE;
    }
  }
}
"""
        patched = PATCHER.patch_android_vulkan_pipeline_cache(source)
        destroy_start = patched.index("void VulkanPipelineCache::Shutdown()")
        destroy_body = patched[destroy_start:]
        self.assertIn(
            "std::lock_guard<std::mutex> save_lock(driver_pipeline_cache_save_lock_);",
            destroy_body,
        )
        self.assertEqual(PATCHER.patch_android_vulkan_pipeline_cache(patched), patched)

    def test_adds_validated_initial_data_and_atomic_write(self):
        patched = PATCHER.patch_android_vulkan_pipeline_cache(PIPELINE_CACHE_SOURCE)

        self.assertIn("VkPipelineCacheHeaderVersionOne", patched)
        self.assertIn("vendorID", patched)
        self.assertIn("deviceID", patched)
        self.assertIn("pipelineCacheUUID", patched)
        self.assertIn("std::memcpy(&header", patched)
        self.assertIn("driver_pipeline_cache_lock_", patched)
        self.assertIn("pipeline_cache_create_info.pInitialData", patched)
        self.assertIn("vkGetPipelineCacheData", patched)
        self.assertIn(".tmp", patched)
        self.assertIn("rename", patched)
        self.assertIn("rename failed", patched)
        self.assertNotIn("remove(driver_pipeline_cache_path_", patched)

    def test_retries_rejected_persisted_cache_with_empty_cache(self):
        patched = PATCHER.patch_android_vulkan_pipeline_cache(PIPELINE_CACHE_SOURCE)
        self.assertIn("android_vk_cache_initial_data_rejected", patched)
        self.assertIn("retrying empty", patched)
        self.assertIn("create_info.initialDataSize = 0", patched)
        self.assertIn("create_info.pInitialData = nullptr", patched)

    def test_retries_incomplete_cache_data_without_marking_save_failed(self):
        patched = PATCHER.patch_android_vulkan_pipeline_cache(PIPELINE_CACHE_SOURCE)
        self.assertIn("VkResult android_vk_cache_data_result = VK_INCOMPLETE;", patched)
        self.assertIn("android_vk_cache_data_result != VK_INCOMPLETE", patched)
        self.assertIn("data.resize(data_size);", patched)

    def test_adds_handle_to_header(self):
        header = """class VulkanPipelineCache {
 private:
  void StorageWriteThread();
};
"""
        patched = PATCHER.patch_android_vulkan_pipeline_cache_header(header)
        self.assertIn("driver_pipeline_cache_", patched)
        self.assertIn("driver_pipeline_cache_path_", patched)

    def test_upgrades_legacy_header_with_driver_cache(self):
        legacy_header = """class VulkanPipelineCache {
 private:
  VkPipelineCache driver_pipeline_cache_ = VK_NULL_HANDLE;
  std::filesystem::path driver_pipeline_cache_path_;
  std::mutex driver_pipeline_cache_lock_;
};
"""
        upgraded = PATCHER.patch_android_vulkan_pipeline_cache_header(legacy_header)
        self.assertIn("android_vk_cache_dirty_", upgraded)
        self.assertIn("android_vk_pipeline_create_us_total_", upgraded)

    def test_adds_pipeline_cache_functions_to_device_table(self):
        functions = "XE_UI_VULKAN_FUNCTION(vkCreatePipelineLayout)\n"
        patched = PATCHER.patch_android_vulkan_pipeline_functions(functions)
        self.assertIn("vkCreatePipelineCache", patched)
        self.assertIn("vkDestroyPipelineCache", patched)
        self.assertIn("vkGetPipelineCacheData", patched)

    def test_is_idempotent(self):
        once = PATCHER.patch_android_vulkan_pipeline_cache(PIPELINE_CACHE_SOURCE)
        twice = PATCHER.patch_android_vulkan_pipeline_cache(once)
        self.assertEqual(once, twice)

    def test_emits_periodic_cache_metrics(self):
        patched = PATCHER.patch_android_vulkan_pipeline_cache(PIPELINE_CACHE_SOURCE)

        for metric in (
            "android_vk_cache_loaded",
            "android_vk_cache_rejected",
            "android_vk_cache_saved",
            "android_vk_pipelines_created",
            "android_vk_pipeline_create_us_total",
        ):
            self.assertIn(metric, patched)
        self.assertIn("android_vk_cache_dirty_", patched)
        self.assertIn("std::chrono::seconds(10)", patched)
        self.assertNotIn("next_android_vk_cache_save = now + std::chrono::seconds(1)", patched)
        self.assertIn("lock.unlock();", patched)
        self.assertIn("android_vk_pipelines_created_.fetch_add", patched)

    def test_emits_cache_lock_wait_metric_for_worker_contention(self):
        patched = PATCHER.patch_android_vulkan_pipeline_cache(PIPELINE_CACHE_SOURCE)
        self.assertIn("android_vk_pipeline_cache_lock_wait_us_total_", patched)
        self.assertIn("android_pipeline_cache_lock_wait_start", patched)
        self.assertIn("std::unique_lock<std::mutex> lock(driver_pipeline_cache_lock_);", patched)

    def test_generated_pipeline_creation_metrics_compile(self):
        compiler = shutil.which("clang++") or shutil.which("c++")
        if not compiler:
            self.skipTest("C++ compiler required")
        source = (ROOT / "tests/pipeline_cache_create_harness.cpp").read_text()
        source = source.replace("// INSERT_CREATE_BLOCK", PATCHER.PIPELINE_CACHE_CREATE_PATCH)
        source = source.replace("// INSERT_CREATE_METRICS", PATCHER.PIPELINE_CACHE_CREATE_METRICS_PATCH)
        with tempfile.TemporaryDirectory(prefix="mcla-cache-create-") as directory:
            test_source = Path(directory) / "test.cpp"
            binary = Path(directory) / "test"
            test_source.write_text(source)
            build = subprocess.run([compiler, "-std=c++17", "-pthread", str(test_source),
                                    "-o", str(binary)], capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_upgrades_existing_cache_source_with_lock_wait_metric(self):
        current = PATCHER.patch_android_vulkan_pipeline_cache(PIPELINE_CACHE_SOURCE)
        current = current.replace(
            PATCHER.PIPELINE_CACHE_CREATE_LOCK_WAIT_PATCH,
            PATCHER.PIPELINE_CACHE_CREATE_LOCK_WAIT_ANCHOR,
            1,
        )
        current = current.replace(
            '      "android_vk_pipelines_created={} android_vk_pipeline_create_us_total={} "\n'
            '      "android_vk_pipeline_cache_lock_wait_us_total={}",\n',
            '      "android_vk_pipelines_created={} android_vk_pipeline_create_us_total={}",\n',
            1,
        )
        current = current.replace(
            "      android_vk_pipeline_cache_lock_wait_us_total_.load(std::memory_order_relaxed),\n",
            "",
            1,
        )
        current = current.replace(
            "      android_vk_pipeline_create_us_total_.load(std::memory_order_relaxed),\n",
            "      android_vk_pipeline_create_us_total_.load(std::memory_order_relaxed));\n",
            1,
        )
        upgraded = PATCHER.patch_android_vulkan_pipeline_cache(current)
        self.assertIn("android_vk_pipeline_cache_lock_wait_us_total_", upgraded)
        self.assertIn("android_pipeline_cache_lock_wait_start", upgraded)

    def test_repairs_lock_wait_metric_when_only_the_log_is_legacy(self):
        current = PATCHER.patch_android_vulkan_pipeline_cache(PIPELINE_CACHE_SOURCE)
        current = current.replace(
            '      "android_vk_pipelines_created={} android_vk_pipeline_create_us_total={} "\n'
            '      "android_vk_pipeline_cache_lock_wait_us_total={}",\n',
            '      "android_vk_pipelines_created={} android_vk_pipeline_create_us_total={}",\n',
            1,
        )
        current = current.replace(
            "      android_vk_pipeline_create_us_total_.load(std::memory_order_relaxed),\n"
            "      android_vk_pipeline_cache_lock_wait_us_total_.load(std::memory_order_relaxed));",
            "      android_vk_pipeline_create_us_total_.load(std::memory_order_relaxed));",
            1,
        )
        repaired = PATCHER.patch_android_vulkan_pipeline_cache(current)
        self.assertIn('"android_vk_pipeline_cache_lock_wait_us_total={}"', repaired)
        self.assertIn("android_vk_pipeline_cache_lock_wait_us_total_.load", repaired)

    def test_rejects_unknown_source(self):
        with self.assertRaises(SystemExit):
            PATCHER.patch_android_vulkan_pipeline_cache("void DifferentPipelineCache() {}")

    def test_rejects_incomplete_legacy_source(self):
        with self.assertRaises(SystemExit):
            PATCHER.patch_android_vulkan_pipeline_cache(
                "void InitializeAndroidPipelineCache() {}"
            )


if __name__ == "__main__":
    unittest.main()
