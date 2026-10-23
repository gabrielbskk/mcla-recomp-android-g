#pragma once

#include <cstring>

namespace mcla {

struct GraphicsPresetSettings {
  const char* name;
  const char* city_lod;
  const char* traffic_lod;
  const char* traffic_distance;
  const char* pedestrians;
  const char* parked_cars;
  bool shadows;
  bool race_shadows;
  bool fast_car_shadows;
  bool foliage_shadows;
  bool foliage_impostors;
  bool fullscreen_blur;
  bool msaa;
  bool motion_blur;
  bool depth_of_field;
};

inline const GraphicsPresetSettings* ResolveGraphicsPreset(const char* name) noexcept {
  static constexpr GraphicsPresetSettings kPresets[] = {
      {"super_low", "0.25", "0.25", "100", "0", "0", false, false, true, false, true,
       false, false, false, false},
      {"low", "0.5", "0.5", "150", "0.25", "0.25", false, false, true, false, true,
       false, false, false, false},
      {"medium", "0.75", "0.75", "250", "0.5", "0.5", true, true, false, false, true,
       false, false, false, false},
      {"high", "0.75", "0.75", "325", "0.75", "0.75", true, true, false, true, true,
       true, true, true, true},
      {"ultra", "1.0", "1.0", "400", "1.0", "1.0", true, true, false, true, true,
       true, true, true, true},
  };
  if (!name) return nullptr;
  if (std::strcmp(name, "performance") == 0) name = "super_low";
  else if (std::strcmp(name, "balanced") == 0) name = "medium";
  else if (std::strcmp(name, "original") == 0) name = "ultra";
  for (const auto& preset : kPresets) {
    if (std::strcmp(name, preset.name) == 0) return &preset;
  }
  return nullptr;
}

}  // namespace mcla
