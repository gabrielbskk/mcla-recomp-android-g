// mcla - ReXGlue Recompiled Project
//
// Customize your app by overriding virtual hooks from rex::ReXApp.

#pragma once

#include <memory>
#include <rex/rex_app.h>

namespace rex::ui {
class ImGuiDialog;
class ImGuiDrawer;
}  // namespace rex::ui

class MclaApp : public rex::ReXApp {
 public:
  using rex::ReXApp::ReXApp;

  static std::unique_ptr<rex::ui::WindowedApp> Create(
      rex::ui::WindowedAppContext& ctx) {
    return std::unique_ptr<MclaApp>(new MclaApp(ctx, "mcla",
        PPCImageConfig));
  }

  ~MclaApp() override;
  void SetFpsCounterVisible(bool visible);

 protected:
  void OnCreateDialogs(rex::ui::ImGuiDrawer* drawer) override;
  void OnConfigurePaths(rex::PathConfig& paths) override;
  void OnPostInitLogging() override;
  void OnPreSetup(rex::RuntimeConfig& config) override;
  void OnPostSetup() override;
  void OnPreLaunchModule() override;

 private:
  rex::ui::ImGuiDrawer* fps_drawer_ = nullptr;
  std::unique_ptr<rex::ui::ImGuiDialog> fps_counter_dialog_;
#if defined(__ANDROID__)
  std::unique_ptr<rex::ui::ImGuiDialog> touch_controls_dialog_;
#endif

  void InstallCrashTrace();
  void ConfigureFrameTiming();
  void StartProfilerIfRequested();
};

void MclaRequestFpsCounter(bool visible);
