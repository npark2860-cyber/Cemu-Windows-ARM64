#pragma once
#include <cstdint>
#include <cstddef>
#include <stdexcept>

namespace cemu::npu {
// Bound source-frame latency and memory. The extra job slots cover composition
// still in flight on the borrowed queue while delayed pairs await presentation.
inline constexpr uint32_t MaxBufferedFrames = 3;
inline constexpr size_t NativeHistorySize = MaxBufferedFrames + 1;
inline constexpr size_t JobSlotCount = MaxBufferedFrames + 2;
inline size_t nativeHistoryIndex(uint64_t id) {
    if (!id) throw std::invalid_argument("Native frame ID zero");
    return size_t((id - 1) % NativeHistorySize);
}
}
