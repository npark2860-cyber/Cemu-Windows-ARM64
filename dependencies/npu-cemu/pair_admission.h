#pragma once
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <optional>
#include <span>

namespace cemu::npu {
// Decides on the render thread, before any GPU work is recorded, whether a new
// source pair can still be composed before its real frame is shown. A pair that
// cannot make it would spend GPU preprocessing on the game's queue and then
// expire unrun, or occupy the single NPU with a Run whose result arrives late
// and delays the pairs behind it.
//
// The prediction replays the worker: pairs run one at a time in submission
// order, each after its GPU input fence. It uses running averages of the
// source interval, the GPU input latency and the NPU Run time, all measured on
// this machine. Until the interval and GPU latency have samples, pairs are
// admitted as before; until a Run has been timed, it counts as free.
class PairAdmission {
public:
    using Clock = std::chrono::steady_clock;
    using Duration = std::chrono::duration<double, std::micro>;
    // deadlineFrames: source intervals between a pair's capture and the latest
    // display of its real frame (the timeline's maximum buffering).
    explicit PairAdmission(uint32_t deadlineFrames) : deadlineFrames_(deadlineFrames) {}
    // Toggle or resize: the next capture starts a new interval sequence.
    void reset() { lastCapture_.reset(); }
    // Every process() call. Gaps from pauses or toggles are not intervals.
    void capture(Clock::time_point now) {
        if (lastCapture_) {
            const Duration interval = now - *lastCapture_;
            if (interval > Duration::zero() && interval < MaxInterval) {
                interval_.add(interval.count());
                recent_[recentNext_++ % recent_.size()] = interval.count();
            }
        }
        lastCapture_ = now;
    }
    // From a taken completion. submitted: GPU input submit; waitStart/waitEnd:
    // the worker's fence wait. A wait that blocked bounds the GPU latency
    // exactly; otherwise the input was ready before the worker got to it.
    void completed(Clock::time_point submitted, Clock::time_point waitStart, Clock::time_point waitEnd,
                   std::optional<Duration> run, Clock::time_point finished) {
        const Duration blocked = waitEnd - waitStart;
        if (blocked > BlockedWait) gpu_.add(Duration(waitEnd - submitted).count());
        else gpu_.bound(Duration(waitStart - submitted).count());
        if (run) run_.add(run->count());
        lastFinished_ = std::max(lastFinished_.value_or(finished), finished);
    }
    // outstanding: submit times of admitted pairs not yet taken, oldest first.
    bool admit(Clock::time_point now, std::span<const Clock::time_point> outstanding) {
        if (!interval_.ready() || !gpu_.ready()) return true;
        const auto gpu = std::chrono::duration_cast<Clock::duration>(Duration(gpu_.value()));
        const auto run = std::chrono::duration_cast<Clock::duration>(Duration(run_.ready() ? run_.value() : 0.0));
        // A pair still outstanding cannot have finished before now.
        auto npu = lastFinished_.value_or(now);
        for (const auto submitted : outstanding) npu = std::max(std::max(npu, submitted + gpu) + run, now);
        const auto finish = std::max(npu, now + gpu) + run;
        // The real frame is shown deadlineFrames intervals after capture. Let the
        // last of them be the longest recent one, so uneven pacing keeps the
        // pairs that land before a long interval.
        const double longest = *std::max_element(recent_.begin(), recent_.end());
        const double mean = interval_.value();
        const auto window = std::chrono::duration_cast<Clock::duration>(
            Duration(mean * (double(deadlineFrames_) - Margin) + std::max(0.0, longest - mean)));
        if (finish <= now + window) { idleRejections_ = 0; return true; }
        // GPU and NPU estimates only update from admitted pairs. While the NPU
        // is idle, let one pair through now and then so a lighter scene or a
        // faster source is noticed.
        if (outstanding.empty() && ++idleRejections_ >= ProbeAfter) { idleRejections_ = 0; return true; }
        return false;
    }
private:
    // Exponential average; the first sample initializes it.
    struct Average {
        void add(double sample) { value_ = count_ ? value_ + (sample - value_) / 8.0 : sample; ++count_; }
        // An upper bound only lowers a larger estimate, or seeds an empty one.
        void bound(double limit) { if (!count_ || limit < value_) add(limit); }
        bool ready() const { return count_ > 0; }
        double value() const { return value_; }
        double value_{};
        uint64_t count_{};
    };
    static constexpr Duration MaxInterval{250000.0};
    static constexpr Duration BlockedWait{200.0};
    // A tenth of a source interval absorbs estimate error and pacing jitter.
    static constexpr double Margin = 0.1;
    static constexpr uint32_t ProbeAfter = 30;
    const uint32_t deadlineFrames_;
    std::optional<Clock::time_point> lastCapture_, lastFinished_;
    uint32_t idleRejections_{};
    std::array<double, 8> recent_{};
    size_t recentNext_{};
    Average interval_, gpu_, run_;
};
}
