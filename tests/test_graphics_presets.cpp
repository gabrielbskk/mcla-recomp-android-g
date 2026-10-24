#include "graphics_presets.h"

#include <cmath>
#include <cstdlib>
#include <iostream>
#include <string>

namespace {
void Check(bool condition, const char* message) {
  if (!condition) {
    std::cerr << "FAIL: " << message << '\n';
    std::exit(1);
  }
}

void Near(double actual, double expected, const char* message) {
  Check(std::fabs(actual - expected) < 0.0001, message);
}

double Number(const char* value) {
  return std::strtod(value, nullptr);
}
}  // namespace

int main() {
  using mcla::ResolveGraphicsPreset;

  const auto* super_low = ResolveGraphicsPreset("super_low");
  Check(super_low && std::string(super_low->name) == "super_low", "super low preset exists");
  Near(Number(super_low->city_lod), 0.25, "super low city LOD");
  Near(Number(super_low->pedestrians), 0.0, "super low disables pedestrians");
  Near(Number(super_low->traffic_distance), 100.0, "super low traffic distance");
  Check(!super_low->shadows && !super_low->msaa && !super_low->depth_of_field,
        "super low disables heavy effects");

  const auto* low = ResolveGraphicsPreset("low");
  Check(low && std::string(low->name) == "low", "low preset remains distinct");
  Near(Number(low->city_lod), 0.5, "low city LOD");
  Near(Number(low->pedestrians), 0.25, "low pedestrian density");
  Near(Number(low->traffic_distance), 150.0, "low traffic distance");

  const auto* medium = ResolveGraphicsPreset("medium");
  Check(medium && std::string(medium->name) == "medium", "medium preset exists");
  Near(Number(medium->city_lod), 0.75, "medium city LOD");
  Near(Number(medium->pedestrians), 0.5, "medium pedestrian density");
  Near(Number(medium->traffic_distance), 250.0, "medium traffic distance");
  Check(medium->shadows && !medium->msaa && !medium->fullscreen_blur,
        "medium uses basic shadows without heavy effects");

  const auto* high = ResolveGraphicsPreset("high");
  Check(high && std::string(high->name) == "high", "high preset exists");
  Near(Number(high->pedestrians), 0.75, "high pedestrian density");
  Near(Number(high->traffic_distance), 325.0, "high traffic distance");
  Check(high->foliage_shadows && high->msaa && high->motion_blur && high->depth_of_field,
        "high enables enhanced effects");

  const auto* ultra = ResolveGraphicsPreset("ultra");
  Check(ultra && std::string(ultra->name) == "ultra", "ultra preset exists");
  Near(Number(ultra->city_lod), 1.0, "ultra city LOD");
  Near(Number(ultra->pedestrians), 1.0, "ultra pedestrian density");
  Near(Number(ultra->traffic_distance), 400.0, "ultra traffic distance");
  Check(ultra->shadows && ultra->foliage_shadows && ultra->msaa && ultra->depth_of_field,
        "ultra enables all quality effects");

  Check(ResolveGraphicsPreset("performance") == super_low, "legacy performance alias");
  Check(ResolveGraphicsPreset("balanced") == medium, "legacy balanced alias");
  Check(ResolveGraphicsPreset("original") == ultra, "legacy original alias");
  Check(ResolveGraphicsPreset("unknown") == nullptr, "invalid preset is rejected");
  Check(ResolveGraphicsPreset(nullptr) == nullptr, "null preset is rejected");
  std::cout << "graphics presets: PASS\n";
}
