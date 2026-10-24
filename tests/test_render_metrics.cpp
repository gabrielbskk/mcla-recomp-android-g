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
  mcla::perf::DrawRateWindow window;
  mcla::perf::DrawRateSnapshot snapshot;
  bool ready = false;
  for (int frame = 0; frame <= 60; ++frame) {
    ready = window.RecordDraw(frame / 60.0, &snapshot) || ready;
  }
  Check(ready, "one-second window produces a snapshot");
  Near(snapshot.draws_per_second, 60.0, "60 draw callbacks per second");
  Near(snapshot.mean_frame_ms, 1000.0 / 60.0, "one-second mean frame time");

  mcla::perf::DrawRateWindow irregular;
  mcla::perf::DrawRateSnapshot irregular_snapshot;
  irregular.RecordDraw(5.0, &irregular_snapshot);
  irregular.RecordDraw(5.2, &irregular_snapshot);
  irregular.RecordDraw(5.7, &irregular_snapshot);
  Check(irregular.RecordDraw(6.0, &irregular_snapshot), "irregular one-second window completes");
  Near(irregular_snapshot.draws_per_second, 3.0, "irregular callback rate uses elapsed time");
  Near(irregular_snapshot.mean_frame_ms, 1000.0 / 3.0, "irregular mean frame time");

  mcla::perf::DrawRateWindow invalid_times;
  mcla::perf::DrawRateSnapshot invalid_snapshot;
  Check(!invalid_times.RecordDraw(std::numeric_limits<double>::quiet_NaN(), &invalid_snapshot),
        "non-finite timestamps are ignored");
  invalid_times.RecordDraw(1.0, &invalid_snapshot);
  Check(!invalid_times.RecordDraw(1.0, &invalid_snapshot), "duplicate timestamps are ignored");
  Check(!invalid_times.RecordDraw(0.5, &invalid_snapshot), "backwards timestamps are ignored");

  std::vector<float> samples = {10.0f, 20.0f, 30.0f, 51.0f, 100.0f};
  const auto summary = mcla::perf::SummarizeFrameTimes(samples, 1.0);
  Near(summary.draws_per_second, 5.0, "sampled callback rate");
  Near(summary.mean_ms, 42.2, "mean frame time");
  Near(summary.p50_ms, 30.0, "p50 nearest-rank percentile");
  Near(summary.p95_ms, 100.0, "p95 nearest-rank percentile");
  Near(summary.p99_ms, 100.0, "p99 nearest-rank percentile");
  Near(summary.max_ms, 100.0, "maximum frame time");
  Check(summary.over_50ms == 2, "frames over 50 ms count excludes the boundary");

  std::vector<float> boundary = {50.0f, 50.1f};
  Check(mcla::perf::SummarizeFrameTimes(boundary, 1.0).over_50ms == 1,
        "exactly 50 ms is not counted as over 50 ms");
  std::vector<float> empty;
  const auto empty_summary = mcla::perf::SummarizeFrameTimes(empty, 0.0);
  Check(empty_summary.draws_per_second == 0.0 && empty_summary.mean_ms == 0.0,
        "empty samples produce zero metrics");

  std::vector<float> invalid = {std::numeric_limits<float>::quiet_NaN(), -1.0f, 16.0f};
  const auto filtered = mcla::perf::SummarizeFrameTimes(invalid, 1.0);
  Check(filtered.sample_count == 1 && filtered.over_50ms == 0,
        "invalid frame times are discarded");
  std::cout << "render metrics: PASS\n";
}
