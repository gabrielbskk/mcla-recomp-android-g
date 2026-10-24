#include "generated/default/mcla_init.h"

#include "mcla_app.h"
#include "render_metrics.h"

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <string>
#include <thread>
#include <vector>
#if defined(__ANDROID__)
#include <SDL3/SDL_system.h>
#endif

#include <imgui.h>

#include <rex/cvar.h>
#include <rex/filesystem.h>
#include <rex/filesystem/vfs.h>
#include <rex/logging.h>
#include <rex/runtime.h>
#include <rex/system/gpu_plugin.h>
#include <rex/ui/imgui_dialog.h>
#include <rex/ui/imgui_drawer.h>
#include <rex/ui/windowed_app_context.h>

REXCVAR_DEFINE_BOOL(mcla_perf_logging, false, "MCLA",
                    "Write one-second render performance summaries to private storage");

namespace {

std::atomic<MclaApp*> g_mcla_app{nullptr};
#if defined(__ANDROID__)
std::string g_android_settings_path;
std::string g_android_path_diagnostics;
std::string g_android_perf_log_path;
constexpr size_t kPerfFrameRingSize = 4096;
std::array<std::atomic<float>, kPerfFrameRingSize> g_perf_frame_times_ms{};
std::atomic<uint64_t> g_perf_frame_sequence{0};
std::atomic<bool> g_perf_log_enabled{false};
std::atomic<bool> g_perf_log_stop{false};
std::thread g_perf_log_thread;

void RotatePerformanceLog(const std::filesystem::path& path) {
  std::error_code error;
  if (!std::filesystem::exists(path, error) || error ||
      std::filesystem::file_size(path, error) < 10u * 1024u * 1024u || error) return;
  std::filesystem::remove(path.string() + ".2", error);
  error.clear();
  std::filesystem::rename(path.string() + ".1", path.string() + ".2", error);
  error.clear();
  std::filesystem::rename(path, path.string() + ".1", error);
}

void StartAndroidPerformanceLog() {
  if (rex::cvar::GetFlagByName("mcla_perf_logging") != "true" ||
      g_android_perf_log_path.empty() || g_perf_log_thread.joinable()) return;
  g_perf_log_enabled.store(true, std::memory_order_release);
  g_perf_log_stop.store(false, std::memory_order_release);
  const std::filesystem::path path(g_android_perf_log_path);
  g_perf_log_thread = std::thread([path] {
    std::error_code error;
    std::filesystem::create_directories(path.parent_path(), error);
    RotatePerformanceLog(path);
    const bool has_content = std::filesystem::exists(path, error) &&
                             std::filesystem::file_size(path, error) > 0;
    std::ofstream output(path, std::ios::app);
    if (!output) {
      REXLOG_ERROR("performance log: cannot open {}", path.string());
      g_perf_log_enabled.store(false, std::memory_order_release);
      return;
    }
    if (!has_content) {
      output << "elapsed_s,draw_fps,frame_ms_avg,frame_ms_p50,frame_ms_p95,frame_ms_p99,"
                "frame_ms_max,frames_over_50ms,fence_submit_wait_ms,fence_readback_wait_ms,"
                "fence_acquire_wait_ms\n";
      output.flush();
    }
    using Clock = std::chrono::steady_clock;
    const auto process_started = Clock::now();
    auto last_flush = Clock::now();
    uint64_t last_sequence = g_perf_frame_sequence.load(std::memory_order_acquire);
    while (!g_perf_log_stop.load(std::memory_order_acquire)) {
      std::this_thread::sleep_for(std::chrono::milliseconds(100));
      const auto now = Clock::now();
      if (now - last_flush < std::chrono::seconds(1)) continue;
      const uint64_t sequence = g_perf_frame_sequence.load(std::memory_order_acquire);
      const uint64_t available = sequence - last_sequence;
      const uint64_t count = std::min<uint64_t>(available, kPerfFrameRingSize);
      std::vector<float> samples;
      samples.reserve(static_cast<size_t>(count));
      const uint64_t first = sequence - count;
      for (uint64_t index = first; index < sequence; ++index) {
        const float sample = g_perf_frame_times_ms[index % kPerfFrameRingSize].load(
            std::memory_order_relaxed);
        samples.push_back(sample);
      }
      const double elapsed = std::chrono::duration<double>(now - last_flush).count();
      const auto summary = mcla::perf::SummarizeFrameTimes(samples, elapsed);
      output << std::fixed << std::setprecision(3) << std::chrono::duration<double>(
          now - process_started).count() << ',' << summary.draws_per_second << ','
             << summary.mean_ms << ',' << summary.p50_ms << ',' << summary.p95_ms << ','
             << summary.p99_ms << ',' << summary.max_ms << ',' << summary.over_50ms
             << ",unavailable,unavailable,unavailable\n";
      output.flush();
      last_sequence = sequence;
      last_flush = now;
      std::error_code size_error;
      if (output && std::filesystem::file_size(path, size_error) >= 10u * 1024u * 1024u &&
          !size_error) {
        output.close();
        RotatePerformanceLog(path);
        output.open(path, std::ios::app);
        if (!output) {
          REXLOG_ERROR("performance log: could not reopen {} after rotation", path.string());
          break;
        }
      }
    }
    output.flush();
    g_perf_log_enabled.store(false, std::memory_order_release);
  });
}

void StopAndroidPerformanceLog() {
  g_perf_log_stop.store(true, std::memory_order_release);
  if (g_perf_log_thread.joinable()) g_perf_log_thread.join();
  g_perf_log_enabled.store(false, std::memory_order_release);
}

void RecordAndroidRenderFrame(double frame_ms) {
  if (!g_perf_log_enabled.load(std::memory_order_relaxed)) return;
  if (!std::isfinite(frame_ms) || frame_ms <= 0.0) return;
  const uint64_t sequence = g_perf_frame_sequence.load(std::memory_order_relaxed);
  g_perf_frame_times_ms[sequence % kPerfFrameRingSize].store(static_cast<float>(frame_ms),
                                                              std::memory_order_relaxed);
  g_perf_frame_sequence.store(sequence + 1, std::memory_order_release);
}
#endif

class FpsCounterDialog final : public rex::ui::ImGuiDialog {
 public:
  explicit FpsCounterDialog(rex::ui::ImGuiDrawer* drawer) : ImGuiDialog(drawer) {}

  void SetOverlayVisible(bool visible) { overlay_visible_ = visible; }

 protected:
  void OnDraw(ImGuiIO& /*io*/) override {
    using Clock = std::chrono::steady_clock;
    const double now_seconds = std::chrono::duration<double>(Clock::now().time_since_epoch()).count();
    mcla::perf::DrawRateSnapshot snapshot;
    if (draw_rate_.RecordDraw(now_seconds, &snapshot)) {
      measured_draw_fps_ = snapshot.draws_per_second;
      measured_mean_frame_ms_ = snapshot.mean_frame_ms;
      has_measurement_ = true;
    }
#if defined(__ANDROID__)
    RecordAndroidRenderFrame(draw_rate_.last_frame_ms());
#endif
    if (!overlay_visible_) {
      return;
    }
    ImGui::SetNextWindowPos(ImVec2(12.0f, 12.0f), ImGuiCond_Always);
    ImGui::SetNextWindowBgAlpha(0.45f);
    constexpr ImGuiWindowFlags kFlags = ImGuiWindowFlags_NoDecoration |
                                        ImGuiWindowFlags_NoInputs |
                                        ImGuiWindowFlags_AlwaysAutoResize |
                                        ImGuiWindowFlags_NoSavedSettings |
                                        ImGuiWindowFlags_NoFocusOnAppearing;
    if (ImGui::Begin("MCLA FPS", nullptr, kFlags)) {
#if defined(__ANDROID__)
      ImGui::SetWindowFontScale(0.82f);
      if (has_measurement_) {
        ImGui::Text("DRAW FPS: %.0f  |  %.1f ms", measured_draw_fps_, measured_mean_frame_ms_);
      } else {
        ImGui::Text("DRAW FPS: --  |  FRAME: -- ms");
      }
      ImGui::SetWindowFontScale(1.0f);
#else
      ImGui::Text("DRAW FPS: %.0f", measured_draw_fps_);
#endif
    }
    ImGui::End();
  }

 private:
  bool overlay_visible_ = false;
  mcla::perf::DrawRateWindow draw_rate_;
  double measured_draw_fps_ = 0.0;
  double measured_mean_frame_ms_ = 0.0;
  bool has_measurement_ = false;
};

}  // namespace

REXCVAR_DEFINE_STRING(mcla_gpu_backend, "any", "MCLA",
                      "Graphics backend for the Xenos GPU plugin: any, vulkan or d3d12");

#if defined(__ANDROID__)
extern const char* g_mcla_settings_path;
#endif


std::unique_ptr<rex::system::IAudioSystem> CreateMclaAudioSystem(
    rex::runtime::FunctionDispatcher* function_dispatcher);

#if defined(__ANDROID__)
std::unique_ptr<rex::ui::ImGuiDialog> CreateAndroidTouchControlsDialog(
    rex::ui::ImGuiDrawer* drawer);
#endif

MclaApp::~MclaApp() {
  MclaApp* expected = this;
  g_mcla_app.compare_exchange_strong(expected, nullptr, std::memory_order_acq_rel);
  touch_controls_dialog_.reset();
  fps_counter_dialog_.reset();
  fps_drawer_ = nullptr;
#if defined(__ANDROID__)
  StopAndroidPerformanceLog();
#endif
}

void MclaApp::OnCreateDialogs(rex::ui::ImGuiDrawer* drawer) {
  fps_drawer_ = drawer;
#if defined(__ANDROID__)
  touch_controls_dialog_ = CreateAndroidTouchControlsDialog(drawer);
#endif
  g_mcla_app.store(this, std::memory_order_release);
  SetFpsCounterVisible(rex::cvar::GetFlagByName("mcla_fps_counter") == "true");
}

void MclaApp::SetFpsCounterVisible(bool visible) {
  if (!fps_drawer_) {
    return;
  }
#if defined(__ANDROID__)
  if (!fps_counter_dialog_) {
    fps_counter_dialog_ = std::make_unique<FpsCounterDialog>(fps_drawer_);
  }
  static_cast<FpsCounterDialog*>(fps_counter_dialog_.get())->SetOverlayVisible(visible);
#else
  if (visible && !fps_counter_dialog_) {
    fps_counter_dialog_ = std::make_unique<FpsCounterDialog>(fps_drawer_);
  } else if (!visible) {
    fps_counter_dialog_.reset();
  }
#endif
}

void MclaRequestFpsCounter(bool visible) {
  MclaApp* app = g_mcla_app.load(std::memory_order_acquire);
  if (!app) {
    return;
  }
  app->app_context().CallInUIThreadDeferred([app, visible] {
    if (g_mcla_app.load(std::memory_order_acquire) == app) {
      app->SetFpsCounterVisible(visible);
    }
  });
}

// Started with no options (a double-click on mcla.exe), the game should just
// run: find the extracted game next to the executable or, as the build leaves
// it, in the repository a few folders up, and load the Xenos GPU plugin.
void MclaApp::OnConfigurePaths(rex::PathConfig& paths) {
#if defined(__ANDROID__)
  // Game assets, settings, shader caches, and logs stay in app-private storage.
  // SAF grants are used only by the Java import/export UI.
  if (const char* internal_storage = SDL_GetAndroidInternalStoragePath();
      internal_storage && *internal_storage) {
    const std::filesystem::path app_files = internal_storage;
    const std::filesystem::path app_data = app_files / "mcla-recomp";
    paths.game_data_root = app_files / "game";
    paths.user_data_root = app_data / "userdata";
    paths.cache_root = app_data / "cache";
    paths.config_path = paths.user_data_root / "mcla.toml";

    std::error_code create_error;
    std::filesystem::create_directories(paths.user_data_root, create_error);
    if (create_error) {
      g_android_path_diagnostics = "user storage setup failed: " + create_error.message();
    }
    create_error.clear();
    std::filesystem::create_directories(paths.cache_root, create_error);
    if (create_error) {
      if (!g_android_path_diagnostics.empty()) g_android_path_diagnostics += "; ";
      g_android_path_diagnostics += "cache setup failed: " + create_error.message();
    }
    create_error.clear();
    const auto log_dir = app_data / "logs";
    g_android_perf_log_path = (log_dir / "performance-v2.csv").string();
    std::filesystem::create_directories(log_dir, create_error);
    if (create_error) {
      if (!g_android_path_diagnostics.empty()) g_android_path_diagnostics += "; ";
      g_android_path_diagnostics += "private log setup failed: " + create_error.message();
    } else {
      const auto log_file = log_dir / "mcla.log";
      if (!rex::cvar::SetFlagByName("log_file", log_file.string())) {
        if (!g_android_path_diagnostics.empty()) g_android_path_diagnostics += "; ";
        g_android_path_diagnostics += "could not set private log path";
      }
      rex::cvar::SetFlagByName("log_max_file_size_mb", "10");
      rex::cvar::SetFlagByName("log_max_files", "3");
      rex::cvar::SetFlagByName("log_flush_interval", "2");
    }
    g_android_settings_path = paths.config_path.string();
    g_mcla_settings_path = g_android_settings_path.c_str();
    if (!g_android_path_diagnostics.empty()) g_android_path_diagnostics += "; ";
    g_android_path_diagnostics += "game data root=" + paths.game_data_root.string();
  } else {
    g_android_path_diagnostics = "SDL did not provide Android internal app storage";
  }
#else
  std::filesystem::path folder = rex::filesystem::GetExecutableFolder();
  for (int level = 0; level < 5 && !folder.empty(); ++level) {
    std::error_code error;
    if (std::filesystem::exists(folder / "game" / "default.xex", error)) {
      paths.game_data_root = folder / "game";
      return;
    }
    if (folder == folder.parent_path()) {
      break;
    }
    folder = folder.parent_path();
  }
#endif
}

void MclaApp::OnPostInitLogging() {
#if defined(__ANDROID__)
  if (!g_android_path_diagnostics.empty()) REXLOG_INFO("{}", g_android_path_diagnostics);
#endif
}

void MclaApp::OnPreSetup(rex::RuntimeConfig& config) {
#if defined(__ANDROID__)
  MclaApplyStartupSettings();
  // Avoid the scaled guest-clock path on Android. The SDK's vblank worker
  // subtracts guest timestamps as unsigned values; using the monotonic host
  // clock directly avoids the clock-rebase underflow documented upstream.
  if (rex::cvar::SetFlagByName("clock_no_scaling", "true")) {
    REXLOG_INFO("android: enabled monotonic guest clock to avoid vblank catch-up underflow");
  } else {
    REXLOG_WARN("android: could not enable monotonic guest clock mitigation");
  }
#endif
  config.audio_factory = &CreateMclaAudioSystem;
  if (config.gpu_plugin.empty()) {
    config.gpu_plugin = "xenos";
  }

  // Left to the SDK when "any"; it then loads the plugin named by --gpu_plugin
  // with its own default backend.
  std::string backend = REXCVAR_GET(mcla_gpu_backend);
  if (backend != "any") {
    config.graphics = rex::system::LoadGpuPlugin("xenos", backend);
    if (!config.graphics) {
      REXLOG_ERROR("could not load the xenos GPU plugin with backend '{}'", backend);
    }
  }
}

void MclaApp::OnPostSetup() {
  ConfigureFrameTiming();
#if defined(__ANDROID__)
  StartAndroidPerformanceLog();
  REXLOG_INFO(
      "android settings: backend={}, preset={}, guest={}x{}, fps={}, shadows={}, city_lod={}, "
      "traffic_lod={}, traffic_distance={}, pedestrians={}, parked_cars={}, single_tile={}, "
      "fence_yield={}",
      rex::cvar::GetFlagByName("mcla_gpu_backend"),
      rex::cvar::GetFlagByName("mcla_graphics_preset"),
      rex::cvar::GetFlagByName("video_mode_width"),
      rex::cvar::GetFlagByName("video_mode_height"),
      rex::cvar::GetFlagByName("mcla_fps"),
      rex::cvar::GetFlagByName("mcla_shadows"),
      rex::cvar::GetFlagByName("mcla_city_lod"),
      rex::cvar::GetFlagByName("mcla_traffic_lod"),
      rex::cvar::GetFlagByName("mcla_traffic_distance"),
      rex::cvar::GetFlagByName("mcla_pedestrians"),
      rex::cvar::GetFlagByName("mcla_parked_cars"),
      rex::cvar::GetFlagByName("mcla_single_tile"),
      rex::cvar::GetFlagByName("mcla_fence_yield"));
#endif

  // The game probes for loose city data on a "t:" drive that retail consoles
  // do not have. Give it a device so the probes fail with "not found" rather
  // than "no such device". LARecomp does the same.
  if (runtime() && runtime()->file_system()) {
    runtime()->file_system()->RegisterSymbolicLink("t:", "\\Device\\Harddisk0\\Partition1");
  }
}
