#include "render_metrics.h"

#include <cmath>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <vector>

namespace {
void Check(bool condition, const char* message) {
  if (!condition) {
    std::cerr << "FAIL: " << message << '\n';
    std::exit(1);
  }
}

void Near(double actual, double expected, const char* message) {
  Check(std::fabs(actual - expected) < 0.001, message);
}
}  // namespace

int main() {
  mcla::perf::PresentedFrameWindow presents;
  for (int frame = 0; frame <= 59; ++frame) {
    Check(presents.RecordPresent(frame / 60.0), "successful present timestamp is recorded");
  }
  const auto presented = presents.Snapshot(1.0);
  Check(presented.presentations == 60, "presentation count includes real present events");
  Near(presented.presented_fps, 60.0, "presented FPS uses presentation count");
  Near(presented.p50_ms, 1000.0 / 60.0, "present frame time p50");
  Near(presented.p95_ms, 1000.0 / 60.0, "present frame time p95");
  Near(presented.p99_ms, 1000.0 / 60.0, "present frame time p99");

  Check(!presents.RecordPresent(0.5), "duplicate or backwards presents are ignored");
  Check(!presents.RecordPresent(std::numeric_limits<double>::infinity()),
        "non-finite present timestamps are ignored");

  std::vector<float> samples = {10.0f, 20.0f, 30.0f, 51.0f, 100.0f};
  const auto summary = mcla::perf::SummarizeFrameTimes(samples);
  Near(summary.mean_ms, 42.2, "mean frame time");
  Near(summary.p50_ms, 30.0, "p50 nearest-rank percentile");
  Near(summary.p95_ms, 100.0, "p95 nearest-rank percentile");
  Near(summary.p99_ms, 100.0, "p99 nearest-rank percentile");
  Near(summary.max_ms, 100.0, "maximum frame time");
  Check(summary.over_50ms == 2, "frames over 50 ms count excludes the boundary");

  std::vector<float> boundary = {50.0f, 50.1f};
  Check(mcla::perf::SummarizeFrameTimes(boundary).over_50ms == 1,
        "exactly 50 ms is not counted as over 50 ms");
  std::vector<float> empty;
  const auto empty_summary = mcla::perf::SummarizeFrameTimes(empty);
  Check(empty_summary.mean_ms == 0.0, "empty samples produce zero metrics");

  std::vector<float> invalid = {std::numeric_limits<float>::quiet_NaN(), -1.0f, 16.0f};
  const auto filtered = mcla::perf::SummarizeFrameTimes(invalid);
  Check(filtered.sample_count == 1 && filtered.over_50ms == 0,
        "invalid frame times are discarded");
  std::cout << "render metrics: PASS\n";
}
