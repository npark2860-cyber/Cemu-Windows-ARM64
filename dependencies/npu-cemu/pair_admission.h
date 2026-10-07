#pragma once
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <optional>
#include <span>
#include <utility>

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
                // A hitch (shader compilation, loading) does not lengthen the
                // intervals after it. Clamping keeps one from stretching the
                // window, while a real frame rate drop is followed within a few
                // frames.
                double sample = interval.count();
                if (interval_.ready()) sample = std::min(sample, MaxStep * interval_.value());
                interval_.add(sample);
                recent_[recentNext_++ % recent_.size()] = sample;
            }
        }
        lastCapture_ = now;
    }
    // From a taken completion. submitted: GPU input submit; waitStart/waitEnd:
    // the worker's fence wait. A wait that blocked measures the GPU latency;
    // otherwise the input was ready before the worker got to it, which bounds
    // the latency from above. firstJob: the slot's first job, whose GPU input is
    // not a sample. run: the NPU Run time; empty if it did not run or was the
    // slot's first Run (QNN registers the slot's shared buffers then, and the
    // first Run after start also wakes the NPU).
    void completed(Clock::time_point submitted, Clock::time_point waitStart, Clock::time_point waitEnd,
                   Clock::time_point finished, bool firstJob, std::optional<Duration> run) {
        lastFinished_ = std::max(lastFinished_.value_or(finished), finished);
        // A probe is the only recent sample of what admission has been
        // rejecting, so it replaces the estimates instead of nudging them.
        const bool probe = std::exchange(probing_, false);
        if (!firstJob) {
            if (waitEnd - waitStart > BlockedWait) gpu_.add(Duration(waitEnd - submitted).count(), probe);
            else gpu_.bound(Duration(waitStart - submitted).count());
        }
        if (run) run_.add(run->count(), probe);
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
        if (finish <= now + window()) { idleRejections_ = 0; return true; }
        // GPU and NPU estimates only update from admitted pairs. While the NPU
        // is idle, let one pair through now and then so a lighter scene, a
        // faster source or the end of NPU contention is noticed.
        if (outstanding.empty() && ++idleRejections_ >= ProbeAfter) { idleRejections_ = 0; probing_ = true; return true; }
        return false;
    }
private:
    // Time from capture until the real frame is shown. With one frame of
    // buffering that is the next interval alone, and uneven pacing (a game
    // between 30 and 60 fps on a 60 Hz display alternates short and long
    // intervals) decides each pair: allow the second longest recent interval,
    // so the pairs before long intervals still run while one hitch does not
    // count. Over several frames of buffering the intervals average out.
    Clock::duration window() const {
        const double mean = interval_.value();
        double result = mean * double(deadlineFrames_);
        if (deadlineFrames_ == 1) {
            auto sorted = recent_;
            std::nth_element(sorted.begin(), sorted.end() - 2, sorted.end());
            result += std::max(0.0, sorted[sorted.size() - 2] - mean);
        }
        return std::chrono::duration_cast<Clock::duration>(Duration(result));
    }
    // Exponential average; the first sample initializes it.
    struct Average {
        void add(double sample, bool replace = false) { value_ = count_ && !replace ? value_ + (sample - value_) / 8.0 : sample; ++count_; }
        // An upper bound lowers a larger estimate to it, or seeds an empty one.
        void bound(double limit) { if (!count_ || limit < value_) add(limit, true); }
        bool ready() const { return count_ > 0; }
        double value() const { return value_; }
        double value_{};
        uint64_t count_{};
    };
    static constexpr Duration MaxInterval{250000.0};
    static constexpr Duration BlockedWait{200.0};
    static constexpr double MaxStep = 1.5;
    static constexpr uint32_t ProbeAfter = 30;
    const uint32_t deadlineFrames_;
    std::optional<Clock::time_point> lastCapture_, lastFinished_;
    uint32_t idleRejections_{};
    bool probing_{};
    std::array<double, 8> recent_{};
    size_t recentNext_{};
    Average interval_, gpu_, run_;
};
}
