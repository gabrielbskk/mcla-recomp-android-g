#if defined(__ANDROID__)

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <deque>
#include <map>
#include <mutex>
#include <optional>
#include <utility>

#include <SDL3/SDL_events.h>
#include <SDL3/SDL_gamepad.h>
#include <SDL3/SDL_init.h>
#include <SDL3/SDL_joystick.h>
#include <SDL3/SDL_log.h>

#include <imgui.h>

#include <rex/ui/imgui_dialog.h>
#include <rex/ui/imgui_drawer.h>

namespace {

using Clock = std::chrono::steady_clock;
using FingerKey = std::pair<SDL_TouchID, SDL_FingerID>;

enum class Control {
  kNone,
  kToggle,
  kStick,
  kAccelerator,
  kBrake,
  kStart,
  kA,
  kB,
  kX,
  kY,
};

struct TouchLayout {
  ImVec2 toggle_min;
  ImVec2 toggle_max;
  ImVec2 start_center;
  ImVec2 start_size;
  ImVec2 stick_center;
  float stick_radius;
  ImVec2 accelerator_center;
  ImVec2 brake_center;
  float pedal_radius;
  std::array<ImVec2, 4> face_centers;
  float face_radius;
};

std::mutex g_dialog_mutex;
class TouchControlsDialog;
TouchControlsDialog *g_dialog = nullptr;

TouchLayout MakeLayout(float width, float height) {
  const float short_edge = std::max(1.0f, std::min(width, height));
  const float scale = std::clamp(short_edge / 600.0f, 0.62f, 1.25f);
  const float margin = 18.0f * scale;
  TouchLayout layout{};
  layout.toggle_min = ImVec2(width - margin - 76.0f * scale, margin);
  layout.toggle_max = ImVec2(width - margin, margin + 38.0f * scale);
  layout.start_center =
      ImVec2(width - margin - 130.0f * scale, margin + 19.0f * scale);
  layout.start_size = ImVec2(76.0f * scale, 38.0f * scale);
  layout.stick_center = ImVec2(width * 0.145f, height * 0.765f);
  layout.stick_radius = short_edge * 0.145f;
  layout.accelerator_center = ImVec2(width * 0.935f, height * 0.795f);
  layout.brake_center = ImVec2(width * 0.935f, height * 0.515f);
  layout.pedal_radius = short_edge * 0.066f;
  layout.face_centers = {
      ImVec2(width * 0.835f, height * 0.735f), // A
      ImVec2(width * 0.895f, height * 0.625f), // B
      ImVec2(width * 0.775f, height * 0.625f), // X
      ImVec2(width * 0.835f, height * 0.515f), // Y
  };
  layout.face_radius = short_edge * 0.052f;
  return layout;
}

float DistanceSquared(ImVec2 a, ImVec2 b) {
  const float dx = a.x - b.x;
  const float dy = a.y - b.y;
  return dx * dx + dy * dy;
}

class TouchControlsDialog final : public rex::ui::ImGuiDialog {
public:
  explicit TouchControlsDialog(rex::ui::ImGuiDrawer *drawer)
      : ImGuiDialog(drawer) {}

  ~TouchControlsDialog() override {
    {
      std::lock_guard<std::mutex> guard(g_dialog_mutex);
      if (g_dialog == this) {
        g_dialog = nullptr;
      }
    }

    if (event_watch_installed_ &&
        (SDL_WasInit(SDL_INIT_EVENTS) & SDL_INIT_EVENTS)) {
      SDL_RemoveEventWatch(&TouchControlsDialog::WatchEvent, nullptr);
      event_watch_installed_ = false;
    }

    std::lock_guard<std::mutex> guard(state_mutex_);
    ReleaseAllLocked();
    if (virtual_joystick_) {
      if (SDL_WasInit(SDL_INIT_GAMEPAD) & SDL_INIT_GAMEPAD) {
        SDL_DetachVirtualJoystick(joystick_id_);
        SDL_CloseJoystick(virtual_joystick_);
      }
      virtual_joystick_ = nullptr;
      joystick_id_ = 0;
    }
  }

protected:
  void OnDraw(ImGuiIO &io) override {
    EnsureVirtualGamepad();

    const ImVec2 display = io.DisplaySize;
    if (!(display.x > 0.0f && display.y > 0.0f)) {
      return;
    }

    std::deque<SDL_Event> pending_events;
    bool pending_events_overflowed = false;
    {
      std::lock_guard<std::mutex> queue_guard(pending_touch_mutex_);
      pending_events.swap(pending_touch_events_);
      pending_events_overflowed = pending_touch_overflowed_;
      pending_touch_overflowed_ = false;
    }

    std::lock_guard<std::mutex> guard(state_mutex_);
    display_width_ = display.x;
    display_height_ = display.y;
    layout_ = MakeLayout(display.x, display.y);
    if (pending_events_overflowed) {
      ReleaseAllLocked();
    }
    for (const SDL_Event &event : pending_events) {
      HandleFingerEventLocked(event);
    }
    if (visible_ && fingers_.empty() &&
        Clock::now() - last_touch_ >= std::chrono::seconds(5)) {
      visible_ = false;
      ReleaseAllLocked();
    }

    ImDrawList *draw = ImGui::GetForegroundDrawList();
    DrawToggle(draw, layout_, visible_);
    if (!visible_) {
      return;
    }

    DrawStick(draw, layout_, stick_x_, stick_y_);
    DrawButton(draw, layout_.accelerator_center, layout_.pedal_radius, "RT",
               trigger_counts_[SDL_GAMEPAD_AXIS_RIGHT_TRIGGER] > 0);
    DrawButton(draw, layout_.brake_center, layout_.pedal_radius, "LT",
               trigger_counts_[SDL_GAMEPAD_AXIS_LEFT_TRIGGER] > 0);
    DrawButton(draw, layout_.face_centers[0], layout_.face_radius, "A",
               button_counts_[SDL_GAMEPAD_BUTTON_SOUTH] > 0);
    DrawButton(draw, layout_.face_centers[1], layout_.face_radius, "B",
               button_counts_[SDL_GAMEPAD_BUTTON_EAST] > 0);
    DrawButton(draw, layout_.face_centers[2], layout_.face_radius, "X",
               button_counts_[SDL_GAMEPAD_BUTTON_WEST] > 0);
    DrawButton(draw, layout_.face_centers[3], layout_.face_radius, "Y",
               button_counts_[SDL_GAMEPAD_BUTTON_NORTH] > 0);
    DrawStart(draw, layout_, button_counts_[SDL_GAMEPAD_BUTTON_START] > 0);
  }

private:
  static bool SDLCALL WatchEvent(void *userdata, SDL_Event *event) {
    (void)userdata;
    if (!event || (event->type != SDL_EVENT_FINGER_DOWN &&
                   event->type != SDL_EVENT_FINGER_MOTION &&
                   event->type != SDL_EVENT_FINGER_UP &&
                   event->type != SDL_EVENT_FINGER_CANCELED)) {
      return true;
    }

    std::lock_guard<std::mutex> guard(g_dialog_mutex);
    if (g_dialog) {
      // SDL invokes event watches while it is dispatching an event. Updating
      // the virtual joystick here pushes more SDL events and can deadlock the
      // event-watch lock against the Android touch callback. Defer all SDL
      // joystick calls until OnDraw drains this small queue.
      g_dialog->QueueFingerEvent(*event);
    }
    return true;
  }

  void QueueFingerEvent(const SDL_Event &event) {
    std::lock_guard<std::mutex> guard(pending_touch_mutex_);
    if (event.type == SDL_EVENT_FINGER_MOTION) {
      const auto &touch = event.tfinger;
      for (auto it = pending_touch_events_.rbegin();
           it != pending_touch_events_.rend(); ++it) {
        const auto &queued_touch = it->tfinger;
        if (queued_touch.touchID == touch.touchID &&
            queued_touch.fingerID == touch.fingerID) {
          if (it->type == SDL_EVENT_FINGER_MOTION) {
            *it = event;
            return;
          }
          break;
        }
      }
      if (pending_touch_events_.size() >= kMaxPendingTouchEvents) {
        return;
      }
    } else if (pending_touch_events_.size() >= kMaxPendingTouchEvents) {
      const auto motion = std::find_if(
          pending_touch_events_.begin(), pending_touch_events_.end(),
          [](const SDL_Event &queued_event) {
            return queued_event.type == SDL_EVENT_FINGER_MOTION;
          });
      if (motion != pending_touch_events_.end()) {
        pending_touch_events_.erase(motion);
      } else {
        pending_touch_overflowed_ = true;
        return;
      }
    }
    pending_touch_events_.push_back(event);
  }

  void EnsureVirtualGamepad() {
    if (virtual_joystick_ || Clock::now() < next_setup_attempt_ ||
        !(SDL_WasInit(SDL_INIT_GAMEPAD) & SDL_INIT_GAMEPAD) ||
        !(SDL_WasInit(SDL_INIT_EVENTS) & SDL_INIT_EVENTS)) {
      return;
    }

    SDL_VirtualJoystickDesc desc;
    SDL_INIT_INTERFACE(&desc);
    desc.type = SDL_JOYSTICK_TYPE_GAMEPAD;
    desc.naxes = SDL_GAMEPAD_AXIS_COUNT;
    desc.nbuttons = SDL_GAMEPAD_BUTTON_COUNT;
    desc.axis_mask = (1u << SDL_GAMEPAD_AXIS_COUNT) - 1u;
    desc.button_mask = (1u << SDL_GAMEPAD_BUTTON_COUNT) - 1u;
    desc.name = "MCLA Touch Controls";

    joystick_id_ = SDL_AttachVirtualJoystick(&desc);
    if (joystick_id_ == 0) {
      LogSetupError("could not attach virtual gamepad");
      return;
    }

    virtual_joystick_ = SDL_OpenJoystick(joystick_id_);
    if (!virtual_joystick_) {
      SDL_DetachVirtualJoystick(joystick_id_);
      joystick_id_ = 0;
      LogSetupError("could not open virtual gamepad");
      return;
    }

    SDL_SetJoystickVirtualAxis(virtual_joystick_, SDL_GAMEPAD_AXIS_LEFT_TRIGGER,
                               SDL_JOYSTICK_AXIS_MIN);
    SDL_SetJoystickVirtualAxis(virtual_joystick_,
                               SDL_GAMEPAD_AXIS_RIGHT_TRIGGER,
                               SDL_JOYSTICK_AXIS_MIN);

    {
      std::lock_guard<std::mutex> guard(g_dialog_mutex);
      g_dialog = this;
      event_watch_installed_ =
          SDL_AddEventWatch(&TouchControlsDialog::WatchEvent, nullptr);
      if (!event_watch_installed_) {
        g_dialog = nullptr;
      }
    }
    if (!event_watch_installed_) {
      SDL_DetachVirtualJoystick(joystick_id_);
      SDL_CloseJoystick(virtual_joystick_);
      virtual_joystick_ = nullptr;
      joystick_id_ = 0;
      LogSetupError("could not monitor touch input");
    }
  }

  void LogSetupError(const char *action) {
    SDL_LogWarn(SDL_LOG_CATEGORY_APPLICATION, "MCLA touch controls: %s: %s",
                action, SDL_GetError());
    next_setup_attempt_ = Clock::now() + std::chrono::seconds(3);
  }

  Control HitTest(ImVec2 point) const {
    if (point.x >= layout_.toggle_min.x && point.x <= layout_.toggle_max.x &&
        point.y >= layout_.toggle_min.y && point.y <= layout_.toggle_max.y) {
      return Control::kToggle;
    }
    if (point.x >= layout_.start_center.x - layout_.start_size.x * 0.5f &&
        point.x <= layout_.start_center.x + layout_.start_size.x * 0.5f &&
        point.y >= layout_.start_center.y - layout_.start_size.y * 0.5f &&
        point.y <= layout_.start_center.y + layout_.start_size.y * 0.5f) {
      return Control::kStart;
    }
    if (DistanceSquared(point, layout_.stick_center) <=
        layout_.stick_radius * layout_.stick_radius) {
      return Control::kStick;
    }
    if (DistanceSquared(point, layout_.accelerator_center) <=
        layout_.pedal_radius * layout_.pedal_radius) {
      return Control::kAccelerator;
    }
    if (DistanceSquared(point, layout_.brake_center) <=
        layout_.pedal_radius * layout_.pedal_radius) {
      return Control::kBrake;
    }
    for (size_t i = 0; i < layout_.face_centers.size(); ++i) {
      if (DistanceSquared(point, layout_.face_centers[i]) <=
          layout_.face_radius * layout_.face_radius) {
        return static_cast<Control>(static_cast<int>(Control::kA) +
                                    static_cast<int>(i));
      }
    }
    return Control::kNone;
  }

  void HandleFingerEventLocked(const SDL_Event &event) {
    const auto &touch = event.tfinger;
    const FingerKey key{touch.touchID, touch.fingerID};
    const auto now = Clock::now();
    const ImVec2 point(touch.x * display_width_, touch.y * display_height_);
    last_touch_ = now;

    if (event.type == SDL_EVENT_FINGER_DOWN) {
      Control control = HitTest(point);
      if (control == Control::kToggle) {
        if (visible_) {
          visible_ = false;
          ReleaseAllLocked();
        } else {
          visible_ = true;
        }
      } else {
        visible_ = true;
        if (control == Control::kStick && stick_finger_) {
          control = Control::kNone;
        }
        fingers_[key] = control;
        PressControlLocked(key, control, point);
      }
      if (control == Control::kToggle) {
        fingers_[key] = Control::kToggle;
      }
      return;
    }

    const auto found = fingers_.find(key);
    if (found == fingers_.end()) {
      return;
    }
    if (event.type == SDL_EVENT_FINGER_MOTION) {
      if (found->second == Control::kStick) {
        UpdateStickLocked(point);
      }
      return;
    }

    ReleaseControlLocked(key, found->second);
    fingers_.erase(found);
  }

  void PressControlLocked(const FingerKey &key, Control control, ImVec2 point) {
    if (control == Control::kStick) {
      stick_finger_ = key;
      UpdateStickLocked(point);
      return;
    }
    if (control == Control::kAccelerator || control == Control::kBrake) {
      const int axis = control == Control::kAccelerator
                           ? SDL_GAMEPAD_AXIS_RIGHT_TRIGGER
                           : SDL_GAMEPAD_AXIS_LEFT_TRIGGER;
      int &count = trigger_counts_[axis];
      if (count++ == 0) {
        SetAxisLocked(axis, SDL_JOYSTICK_AXIS_MAX);
      }
      return;
    }
    const int button = ButtonFor(control);
    if (button >= 0) {
      int &count = button_counts_[button];
      if (count++ == 0) {
        SetButtonLocked(button, true);
      }
    }
  }

  void ReleaseControlLocked(const FingerKey &key, Control control) {
    if (control == Control::kStick) {
      if (stick_finger_ && *stick_finger_ == key) {
        stick_finger_.reset();
        stick_x_ = 0.0f;
        stick_y_ = 0.0f;
        SetAxisLocked(SDL_GAMEPAD_AXIS_LEFTX, 0);
        SetAxisLocked(SDL_GAMEPAD_AXIS_LEFTY, 0);
      }
      return;
    }
    if (control == Control::kAccelerator || control == Control::kBrake) {
      const int axis = control == Control::kAccelerator
                           ? SDL_GAMEPAD_AXIS_RIGHT_TRIGGER
                           : SDL_GAMEPAD_AXIS_LEFT_TRIGGER;
      int &count = trigger_counts_[axis];
      if (count > 0 && --count == 0) {
        SetAxisLocked(axis, SDL_JOYSTICK_AXIS_MIN);
      }
      return;
    }
    const int button = ButtonFor(control);
    if (button >= 0) {
      int &count = button_counts_[button];
      if (count > 0 && --count == 0) {
        SetButtonLocked(button, false);
      }
    }
  }

  void UpdateStickLocked(ImVec2 point) {
    float x = (point.x - layout_.stick_center.x) / layout_.stick_radius;
    float y = (point.y - layout_.stick_center.y) / layout_.stick_radius;
    const float magnitude = std::sqrt(x * x + y * y);
    if (magnitude > 1.0f) {
      x /= magnitude;
      y /= magnitude;
    }
    stick_x_ = x;
    stick_y_ = y;
    SetAxisLocked(SDL_GAMEPAD_AXIS_LEFTX,
                  static_cast<Sint16>(std::lround(x * SDL_JOYSTICK_AXIS_MAX)));
    SetAxisLocked(SDL_GAMEPAD_AXIS_LEFTY,
                  static_cast<Sint16>(std::lround(y * SDL_JOYSTICK_AXIS_MAX)));
  }

  void ReleaseAllLocked() {
    for (size_t i = 0; i < button_counts_.size(); ++i) {
      if (button_counts_[i] > 0) {
        SetButtonLocked(static_cast<int>(i), false);
      }
    }
    button_counts_.fill(0);
    for (size_t i = 0; i < trigger_counts_.size(); ++i) {
      if (trigger_counts_[i] > 0) {
        SetAxisLocked(static_cast<int>(i), SDL_JOYSTICK_AXIS_MIN);
      }
    }
    trigger_counts_.fill(0);
    SetAxisLocked(SDL_GAMEPAD_AXIS_LEFTX, 0);
    SetAxisLocked(SDL_GAMEPAD_AXIS_LEFTY, 0);
    stick_x_ = 0.0f;
    stick_y_ = 0.0f;
    stick_finger_.reset();
    fingers_.clear();
  }

  void SetAxisLocked(int axis, Sint16 value) {
    if (virtual_joystick_) {
      SDL_SetJoystickVirtualAxis(virtual_joystick_, axis, value);
    }
  }

  void SetButtonLocked(int button, bool pressed) {
    if (virtual_joystick_) {
      SDL_SetJoystickVirtualButton(virtual_joystick_, button, pressed);
    }
  }

  static int ButtonFor(Control control) {
    switch (control) {
    case Control::kStart:
      return SDL_GAMEPAD_BUTTON_START;
    case Control::kA:
      return SDL_GAMEPAD_BUTTON_SOUTH;
    case Control::kB:
      return SDL_GAMEPAD_BUTTON_EAST;
    case Control::kX:
      return SDL_GAMEPAD_BUTTON_WEST;
    case Control::kY:
      return SDL_GAMEPAD_BUTTON_NORTH;
    default:
      return -1;
    }
  }

  static ImU32 Color(bool active, int alpha = 118) {
    return active ? IM_COL32(255, 177, 66, 190) : IM_COL32(18, 24, 32, alpha);
  }

  static void DrawButton(ImDrawList *draw, ImVec2 center, float radius,
                         const char *label, bool active) {
    draw->AddCircleFilled(center, radius, Color(active));
    draw->AddCircle(center, radius, IM_COL32(255, 255, 255, 155), 0, 2.0f);
    const ImVec2 text_size = ImGui::CalcTextSize(label);
    draw->AddText(
        ImVec2(center.x - text_size.x * 0.5f, center.y - text_size.y * 0.5f),
        IM_COL32(255, 255, 255, 235), label);
  }

  static void DrawStick(ImDrawList *draw, const TouchLayout &layout,
                        float axis_x, float axis_y) {
    draw->AddCircleFilled(layout.stick_center, layout.stick_radius,
                          IM_COL32(18, 24, 32, 72));
    draw->AddCircle(layout.stick_center, layout.stick_radius,
                    IM_COL32(255, 255, 255, 155), 0, 2.0f);
    const ImVec2 knob(
        layout.stick_center.x + axis_x * layout.stick_radius * 0.72f,
        layout.stick_center.y + axis_y * layout.stick_radius * 0.72f);
    draw->AddCircleFilled(knob, layout.stick_radius * 0.42f,
                          IM_COL32(28, 39, 51, 190));
    draw->AddCircle(knob, layout.stick_radius * 0.42f,
                    IM_COL32(255, 255, 255, 185), 0, 2.0f);
  }

  static void DrawStart(ImDrawList *draw, const TouchLayout &layout,
                        bool active) {
    const ImVec2 half(layout.start_size.x * 0.5f, layout.start_size.y * 0.5f);
    const ImVec2 min(layout.start_center.x - half.x,
                     layout.start_center.y - half.y);
    const ImVec2 max(layout.start_center.x + half.x,
                     layout.start_center.y + half.y);
    draw->AddRectFilled(min, max, Color(active), 8.0f);
    draw->AddRect(min, max, IM_COL32(255, 255, 255, 155), 8.0f, 0, 2.0f);
    constexpr const char *label = "START";
    const ImVec2 text_size = ImGui::CalcTextSize(label);
    draw->AddText(ImVec2(layout.start_center.x - text_size.x * 0.5f,
                         layout.start_center.y - text_size.y * 0.5f),
                  IM_COL32(255, 255, 255, 235), label);
  }

  static void DrawToggle(ImDrawList *draw, const TouchLayout &layout,
                         bool visible) {
    const ImU32 color =
        visible ? IM_COL32(18, 24, 32, 105) : IM_COL32(255, 177, 66, 180);
    draw->AddRectFilled(layout.toggle_min, layout.toggle_max, color, 8.0f);
    draw->AddRect(layout.toggle_min, layout.toggle_max,
                  IM_COL32(255, 255, 255, 170), 8.0f, 0, 2.0f);
    const char *label = visible ? "HIDE" : "PAD";
    const ImVec2 text_size = ImGui::CalcTextSize(label);
    const ImVec2 center((layout.toggle_min.x + layout.toggle_max.x) * 0.5f,
                        (layout.toggle_min.y + layout.toggle_max.y) * 0.5f);
    draw->AddText(
        ImVec2(center.x - text_size.x * 0.5f, center.y - text_size.y * 0.5f),
        IM_COL32(255, 255, 255, 240), label);
  }

  std::mutex state_mutex_;
  std::mutex pending_touch_mutex_;
  std::deque<SDL_Event> pending_touch_events_;
  bool pending_touch_overflowed_ = false;
  static constexpr size_t kMaxPendingTouchEvents = 256;
  std::map<FingerKey, Control> fingers_;
  std::array<int, SDL_GAMEPAD_BUTTON_COUNT> button_counts_{};
  std::array<int, SDL_GAMEPAD_AXIS_COUNT> trigger_counts_{};
  std::optional<FingerKey> stick_finger_;
  SDL_Joystick *virtual_joystick_ = nullptr;
  SDL_JoystickID joystick_id_ = 0;
  bool event_watch_installed_ = false;
  bool visible_ = true;
  float display_width_ = 1.0f;
  float display_height_ = 1.0f;
  float stick_x_ = 0.0f;
  float stick_y_ = 0.0f;
  TouchLayout layout_{};
  Clock::time_point last_touch_ = Clock::now();
  Clock::time_point next_setup_attempt_{};
};

} // namespace

std::unique_ptr<rex::ui::ImGuiDialog>
CreateAndroidTouchControlsDialog(rex::ui::ImGuiDrawer *drawer) {
  return std::make_unique<TouchControlsDialog>(drawer);
}

#endif // defined(__ANDROID__)
