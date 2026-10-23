#include "generated/default/mcla_init.h"

#include "mcla_app.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <map>
#include <sstream>
#include <string>
#include <vector>
#if defined(__ANDROID__)
#include <SDL3/SDL_system.h>
#include <unistd.h>
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

#if defined(__ANDROID__)
double MclaAndroidGuestTickRate();
#endif

namespace {

std::atomic<MclaApp*> g_mcla_app{nullptr};
#if defined(__ANDROID__)
std::string g_android_settings_path;
std::string g_android_path_diagnostics;
#endif

class FpsCounterDialog final : public rex::ui::ImGuiDialog {
 public:
  explicit FpsCounterDialog(rex::ui::ImGuiDrawer* drawer) : ImGuiDialog(drawer) {}

  void SetOverlayVisible(bool visible) { overlay_visible_ = visible; }

 protected:
  void OnDraw(ImGuiIO& io) override {
    if (!(io.DeltaTime > 0.0f) || !std::isfinite(io.DeltaTime)) {
      return;
    }
    const float instant_fps = 1.0f / io.DeltaTime;
    smoothed_fps_ = smoothed_fps_ > 0.0f ? smoothed_fps_ * 0.85f + instant_fps * 0.15f
                                         : instant_fps;
#if defined(__ANDROID__)
    RecordPerformanceSample(io.DeltaTime);
#endif
    if (!overlay_visible_) {
      return;
    }
    ImGui::SetNextWindowPos(ImVec2(16.0f, 16.0f), ImGuiCond_Always);
    ImGui::SetNextWindowBgAlpha(0.60f);
    constexpr ImGuiWindowFlags kFlags = ImGuiWindowFlags_NoDecoration |
                                        ImGuiWindowFlags_NoInputs |
                                        ImGuiWindowFlags_AlwaysAutoResize |
                                        ImGuiWindowFlags_NoSavedSettings |
                                        ImGuiWindowFlags_NoFocusOnAppearing;
    if (ImGui::Begin("MCLA FPS", nullptr, kFlags)) {
#if defined(__ANDROID__)
      ImGui::Text("UI FPS: %.0f", smoothed_fps_);
      const double game_tick_rate = MclaAndroidGuestTickRate();
      if (game_tick_rate > 0.0) {
        ImGui::Text("Game ticks/s: %.1f", game_tick_rate);
      } else {
        ImGui::Text("Game ticks/s: --");
      }
#else
      ImGui::Text("FPS: %.0f", smoothed_fps_);
#endif
    }
    ImGui::End();
  }

 private:
#if defined(__ANDROID__)
  static uint64_t ReadVmRssKiB() {
    std::ifstream status("/proc/self/status");
    std::string line;
    while (std::getline(status, line)) {
      if (line.compare(0, 6, "VmRSS:") == 0) {
        std::istringstream value_stream(line.substr(6));
        uint64_t rss_kib = 0;
        value_stream >> rss_kib;
        return rss_kib;
      }
    }
    return 0;
  }

  struct ThreadCpuSample {
    std::string name;
    uint64_t ticks = 0;
  };

  static std::map<uint64_t, ThreadCpuSample> ReadThreadCpuSamples() {
    std::map<uint64_t, ThreadCpuSample> samples;
    const long ticks_per_second = sysconf(_SC_CLK_TCK);
    if (ticks_per_second <= 0) {
      return samples;
    }
    std::error_code error;
    for (std::filesystem::directory_iterator it("/proc/self/task", error), end;
         !error && it != end; it.increment(error)) {
      const std::string tid_text = it->path().filename().string();
      uint64_t tid = 0;
      try {
        tid = std::stoull(tid_text);
      } catch (...) {
        continue;
      }
      std::ifstream stat(it->path() / "stat");
      std::string line;
      if (!std::getline(stat, line)) {
        continue;
      }
      // The command name is parenthesized and may itself contain spaces or
      // parentheses, so parse the numeric fields only after its final ')'.
      const size_t command_end = line.rfind(')');
      if (command_end == std::string::npos || command_end + 1 >= line.size()) {
        continue;
      }
      std::istringstream fields(line.substr(command_end + 1));
      std::string field;
      uint64_t user_ticks = 0;
      uint64_t system_ticks = 0;
      // The remaining fields start at field 3 (state); utime/stime are 14/15.
      for (int index = 0; index <= 12; ++index) {
        if (!(fields >> field)) {
          break;
        }
        if (index == 11) {
          try {
            user_ticks = std::stoull(field);
          } catch (...) {
            user_ticks = 0;
          }
        } else if (index == 12) {
          try {
            system_ticks = std::stoull(field);
          } catch (...) {
            system_ticks = 0;
          }
        }
      }
      if (!user_ticks && !system_ticks) {
        continue;
      }
      std::ifstream comm(it->path() / "comm");
      std::string name;
      std::getline(comm, name);
      samples.emplace(tid, ThreadCpuSample{std::move(name), user_ticks + system_ticks});
    }
    return samples;
  }

  void RecordThreadCpuSample(std::chrono::steady_clock::time_point now) {
    const auto current = ReadThreadCpuSamples();
    if (thread_cpu_sample_started_ == std::chrono::steady_clock::time_point{}) {
      thread_cpu_previous_ = current;
      thread_cpu_sample_started_ = now;
      return;
    }
    const double elapsed =
        std::chrono::duration<double>(now - thread_cpu_sample_started_).count();
    const long ticks_per_second = sysconf(_SC_CLK_TCK);
    if (elapsed <= 0.0 || ticks_per_second <= 0) {
      thread_cpu_previous_ = current;
      thread_cpu_sample_started_ = now;
      return;
    }

    struct BusyThread {
      std::string name;
      uint64_t tid;
      double cpu_percent;
    };
    std::vector<BusyThread> busy;
    for (const auto& [tid, sample] : current) {
      const auto previous = thread_cpu_previous_.find(tid);
      if (previous == thread_cpu_previous_.end() || sample.ticks < previous->second.ticks) {
        continue;
      }
      const double cpu_percent =
          100.0 * double(sample.ticks - previous->second.ticks) / double(ticks_per_second) / elapsed;
      busy.push_back({sample.name, tid, cpu_percent});
    }
    std::sort(busy.begin(), busy.end(), [](const BusyThread& a, const BusyThread& b) {
      return a.cpu_percent > b.cpu_percent;
    });
    std::ostringstream top;
    const size_t count = std::min<size_t>(5, busy.size());
    for (size_t i = 0; i < count; ++i) {
      if (i) {
        top << ", ";
      }
      top << busy[i].name << "#" << busy[i].tid << "=" << std::fixed << std::setprecision(1)
          << busy[i].cpu_percent << "%";
    }
    REXLOG_INFO("android thread CPU (one core=100%): {}", top.str());
    thread_cpu_previous_ = current;
    thread_cpu_sample_started_ = now;
  }

  void RecordPerformanceSample(float delta_time) {
    using Clock = std::chrono::steady_clock;
    const auto now = Clock::now();
    if (sample_started_ == Clock::time_point{}) {
      sample_started_ = now;
      RecordThreadCpuSample(now);
    }
    ++sample_frames_;
    frame_times_ms_.push_back(delta_time * 1000.0f);
    const double elapsed_seconds = std::chrono::duration<double>(now - sample_started_).count();
    if (elapsed_seconds < 10.0 || frame_times_ms_.empty()) {
      return;
    }

    std::sort(frame_times_ms_.begin(), frame_times_ms_.end());
    const size_t p95_index = std::min(
        frame_times_ms_.size() - 1,
        static_cast<size_t>(std::ceil(static_cast<double>(frame_times_ms_.size()) * 0.95)) - 1);
    REXLOG_INFO("android perf: render-loop estimate {:.1f} FPS, frame p95 {:.1f} ms, "
                "max {:.1f} ms, VmRSS {} KiB",
                static_cast<double>(sample_frames_) / elapsed_seconds,
                frame_times_ms_[p95_index], frame_times_ms_.back(), ReadVmRssKiB());
    RecordThreadCpuSample(now);
    frame_times_ms_.clear();
    sample_frames_ = 0;
    sample_started_ = now;
  }

  std::chrono::steady_clock::time_point sample_started_{};
  uint64_t sample_frames_ = 0;
  std::vector<float> frame_times_ms_;
  std::chrono::steady_clock::time_point thread_cpu_sample_started_{};
  std::map<uint64_t, ThreadCpuSample> thread_cpu_previous_;
#endif
  bool overlay_visible_ = false;
  float smoothed_fps_ = 0.0f;
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
