#pragma once

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace mcla::perf {

struct DrawRateSnapshot {
  double draws_per_second = 0.0;
  double mean_frame_ms = 0.0;
};

class DrawRateWindow {
 public:
  bool RecordDraw(double monotonic_seconds, DrawRateSnapshot* snapshot) noexcept {
    if (!snapshot || !std::isfinite(monotonic_seconds)) return false;
    if (!started_) {
      started_ = true;
      window_start_seconds_ = monotonic_seconds;
      previous_draw_seconds_ = monotonic_seconds;
      last_frame_ms_ = 0.0;
      return false;
    }
    if (monotonic_seconds <= previous_draw_seconds_) return false;

    last_frame_ms_ = (monotonic_seconds - previous_draw_seconds_) * 1000.0;
    previous_draw_seconds_ = monotonic_seconds;
    ++frame_intervals_;
    const double elapsed = monotonic_seconds - window_start_seconds_;
    if (elapsed < 1.0 || frame_intervals_ == 0) return false;

    snapshot->draws_per_second = static_cast<double>(frame_intervals_) / elapsed;
    snapshot->mean_frame_ms = 1000.0 * elapsed / static_cast<double>(frame_intervals_);
    window_start_seconds_ = monotonic_seconds;
    frame_intervals_ = 0;
    return true;
  }

  double last_frame_ms() const noexcept { return last_frame_ms_; }

 private:
  bool started_ = false;
  double window_start_seconds_ = 0.0;
  double previous_draw_seconds_ = 0.0;
  double last_frame_ms_ = 0.0;
  uint64_t frame_intervals_ = 0;
};

struct FrameTimeSummary {
  size_t sample_count = 0;
  size_t over_50ms = 0;
  double draws_per_second = 0.0;
  double mean_ms = 0.0;
  double p50_ms = 0.0;
  double p95_ms = 0.0;
  double p99_ms = 0.0;
  double max_ms = 0.0;
};

inline FrameTimeSummary SummarizeFrameTimes(std::vector<float>& samples,
                                            double elapsed_seconds) {
  samples.erase(std::remove_if(samples.begin(), samples.end(), [](float value) {
                  return !std::isfinite(value) || value <= 0.0f;
                }), samples.end());
  std::sort(samples.begin(), samples.end());

  FrameTimeSummary summary;
  summary.sample_count = samples.size();
  if (samples.empty()) return summary;
  if (std::isfinite(elapsed_seconds) && elapsed_seconds > 0.0) {
    summary.draws_per_second = static_cast<double>(samples.size()) / elapsed_seconds;
  }

  double total_ms = 0.0;
  for (float sample : samples) {
    total_ms += sample;
    if (sample > 50.0f) ++summary.over_50ms;
  }
  summary.mean_ms = total_ms / static_cast<double>(samples.size());
  const auto percentile = [&samples](double fraction) {
    const size_t index = std::min(samples.size() - 1,
        static_cast<size_t>(std::ceil(static_cast<double>(samples.size()) * fraction)) - 1);
    return static_cast<double>(samples[index]);
  };
  summary.p50_ms = percentile(0.50);
  summary.p95_ms = percentile(0.95);
  summary.p99_ms = percentile(0.99);
  summary.max_ms = static_cast<double>(samples.back());
  return summary;
}

}  // namespace mcla::perf
