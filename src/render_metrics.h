#pragma once

#include <algorithm>
#include <array>
#include <atomic>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace mcla::perf {

struct FrameTimeSummary {
  size_t sample_count = 0;
  size_t over_50ms = 0;
  double mean_ms = 0.0;
  double p50_ms = 0.0;
  double p95_ms = 0.0;
  double p99_ms = 0.0;
  double max_ms = 0.0;
};

inline FrameTimeSummary SummarizeFrameTimes(std::vector<float>& samples) {
  samples.erase(std::remove_if(samples.begin(), samples.end(), [](float value) {
                  return !std::isfinite(value) || value <= 0.0f;
                }), samples.end());
  std::sort(samples.begin(), samples.end());

  FrameTimeSummary summary;
  summary.sample_count = samples.size();
  if (samples.empty()) return summary;
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

struct PresentedFrameSnapshot {
  size_t presentations = 0;
  double presented_fps = 0.0;
  double mean_ms = 0.0;
  double p50_ms = 0.0;
  double p95_ms = 0.0;
  double p99_ms = 0.0;
  double max_ms = 0.0;
  size_t over_50ms = 0;
};

// Record only successful vkQueuePresentKHR results. One producer is expected:
// Vulkan externally synchronizes presentation on the present queue.
class PresentedFrameWindow {
 public:
  static constexpr size_t kCapacity = 4096;

  bool RecordPresent(double monotonic_seconds) noexcept {
    if (!std::isfinite(monotonic_seconds)) return false;
    const double previous = last_present_seconds_.load(std::memory_order_relaxed);
    if (previous >= monotonic_seconds) return false;
    if (previous < 0.0) start_seconds_.store(monotonic_seconds, std::memory_order_relaxed);

    const uint64_t sequence = sequence_.load(std::memory_order_relaxed);
    const size_t slot = static_cast<size_t>(sequence % kCapacity);
    const double interval_ms = previous < 0.0 ? 0.0 : (monotonic_seconds - previous) * 1000.0;
    intervals_ms_[slot].store(static_cast<float>(interval_ms), std::memory_order_relaxed);
    timestamps_seconds_[slot].store(monotonic_seconds, std::memory_order_release);
    sequence_.store(sequence + 1, std::memory_order_release);
    last_present_seconds_.store(monotonic_seconds, std::memory_order_relaxed);
    return true;
  }

  PresentedFrameSnapshot Snapshot(double monotonic_seconds) const {
    PresentedFrameSnapshot snapshot;
    if (!std::isfinite(monotonic_seconds)) return snapshot;
    const uint64_t end = sequence_.load(std::memory_order_acquire);
    const uint64_t begin = end > kCapacity ? end - kCapacity : 0;
    const double started = start_seconds_.load(std::memory_order_relaxed);
    if (started < 0.0 || monotonic_seconds <= started) return snapshot;

    const double elapsed = std::min(1.0, monotonic_seconds - started);
    const double cutoff = monotonic_seconds - 1.0;
    std::vector<float> frame_times;
    frame_times.reserve(static_cast<size_t>(end - begin));
    for (uint64_t sequence = begin; sequence < end; ++sequence) {
      const size_t slot = static_cast<size_t>(sequence % kCapacity);
      const double timestamp = timestamps_seconds_[slot].load(std::memory_order_acquire);
      if (timestamp < cutoff || timestamp > monotonic_seconds) continue;
      ++snapshot.presentations;
      const float interval_ms = intervals_ms_[slot].load(std::memory_order_relaxed);
      if (interval_ms > 0.0f) frame_times.push_back(interval_ms);
    }
    if (elapsed > 0.0) {
      snapshot.presented_fps = static_cast<double>(snapshot.presentations) / elapsed;
    }
    const FrameTimeSummary summary = SummarizeFrameTimes(frame_times);
    snapshot.mean_ms = summary.mean_ms;
    snapshot.p50_ms = summary.p50_ms;
    snapshot.p95_ms = summary.p95_ms;
    snapshot.p99_ms = summary.p99_ms;
    snapshot.max_ms = summary.max_ms;
    snapshot.over_50ms = summary.over_50ms;
    return snapshot;
  }

 private:
  std::array<std::atomic<double>, kCapacity> timestamps_seconds_{};
  std::array<std::atomic<float>, kCapacity> intervals_ms_{};
  std::atomic<uint64_t> sequence_{0};
  std::atomic<double> start_seconds_{-1.0};
  std::atomic<double> last_present_seconds_{-1.0};
};

}  // namespace mcla::perf
