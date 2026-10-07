#pragma once
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <deque>
#include <exception>
#include <functional>
#include <mutex>
#include <optional>
#include <stdexcept>
#include <thread>
#include <unordered_set>

namespace cemu::npu {
using Clock = std::chrono::steady_clock;
struct FramePair {
    uint64_t epoch{}, previous{}, current{}, slot{};
    uint32_t width{}, height{};
    Clock::time_point deadline{};
};
struct Completion {
    FramePair pair;
    bool executed{}, stale{};
    std::exception_ptr error;
    Clock::time_point started{}, finished{};
};

// No Vulkan/ORT dependencies. The caller owns resources through take() and all
// subsequent GPU consumers. reset() invalidates results; it does not free slots.
class AsyncWorker {
public:
    using StillCurrent = std::function<bool()>;
    // Always invoked, even after reset. Wait for the producer GPU fence first;
    // then check current() before NPU Run. Return true only when inference ran.
    using Execute = std::function<bool(const StillCurrent&)>;
    explicit AsyncWorker(size_t capacity = 3) : capacity_(capacity) {
        if (!capacity_) throw std::invalid_argument("Zero worker capacity");
        thread_ = std::thread([this] { loop(); });
    }
    AsyncWorker(const AsyncWorker&) = delete;
    ~AsyncWorker() { stop(); }
    uint64_t epoch() const { return epoch_.load(std::memory_order_acquire); }
    uint64_t reset() { return epoch_.fetch_add(1, std::memory_order_acq_rel) + 1; }
    bool submit(FramePair pair, Execute execute) {
        // Submission never waits for inference or a contended queue lock.
        std::unique_lock lock(mutex_, std::try_to_lock);
        if (!lock || stopping_.load() || pair.epoch != epoch() || pair.current <= pair.previous ||
            pair.current - pair.previous != 1 || !pair.width || !pair.height || !execute ||
            Clock::now() > pair.deadline || occupied_.size() >= capacity_ || occupied_.contains(pair.slot)) return false;
        pending_.push_back({pair, std::move(execute)});
        try { occupied_.insert(pair.slot); }
        catch (...) { pending_.pop_back(); throw; }
        lock.unlock(); wake_.notify_one(); return true;
    }
    std::optional<Completion> take() {
        std::unique_lock lock(mutex_, std::try_to_lock);
        if (!lock || completed_.empty()) return std::nullopt;
        auto result = std::move(completed_.front()); completed_.pop_front();
        occupied_.erase(result.pair.slot);
        result.stale |= result.pair.epoch != epoch() || Clock::now() > result.pair.deadline;
        return result;
    }
    void stop() {
        // Change the wait predicate under its mutex to avoid a lost shutdown wake.
        { std::lock_guard lock(mutex_); stopping_.store(true, std::memory_order_release); }
        wake_.notify_one();
        if (thread_.joinable()) thread_.join(); // Shutdown only, never a per-frame/toggle operation.
    }
private:
    struct Task { FramePair pair; Execute execute; };
    void loop() {
        for (;;) {
            Task task;
            {
                std::unique_lock lock(mutex_);
                wake_.wait(lock, [&] { return stopping_.load() || !pending_.empty(); });
                if (pending_.empty()) return;
                task = std::move(pending_.front()); pending_.pop_front();
            }
            Completion result; result.pair = task.pair; result.started = Clock::now();
            const StillCurrent current = [this, pair = task.pair] {
                return !stopping_.load(std::memory_order_acquire) && pair.epoch == epoch() && Clock::now() <= pair.deadline;
            };
            try { result.executed = task.execute(current); }
            catch (...) { result.error = std::current_exception(); }
            result.finished = Clock::now(); result.stale = !current();
            {
                std::lock_guard lock(mutex_); completed_.push_back(std::move(result));
            }
        }
    }
    const size_t capacity_;
    std::atomic<uint64_t> epoch_{1};
    std::atomic<bool> stopping_{false};
    std::mutex mutex_;
    std::condition_variable wake_;
    std::deque<Task> pending_;
    std::deque<Completion> completed_;
    std::unordered_set<uint64_t> occupied_;
    std::thread thread_;
};

// Source IDs are represented as (real index, midpoint flag), avoiding 2*id overflow.
// This gate rejects a midpoint once its following real frame has been displayed.
class PresentationGate {
public:
    void reset(uint64_t epoch, uint32_t width, uint32_t height) {
        epoch_ = epoch; width_ = width; height_ = height; last_.reset();
    }
    bool generated(const Completion& result, Clock::time_point now) {
        const auto& pair = result.pair;
        const Position position{pair.previous, true};
        if (!result.executed || result.stale || result.error || pair.epoch != epoch_ || pair.width != width_ || pair.height != height_ ||
            pair.current <= pair.previous || pair.current - pair.previous != 1 || now > pair.deadline || !later(position)) return false;
        last_ = position; return true;
    }
    bool real(uint64_t id) {
        const Position position{id, false};
        if (!later(position)) return false;
        last_ = position; return true;
    }
private:
    struct Position { uint64_t real; bool midpoint; };
    bool later(Position p) const {
        return !last_ || p.real > last_->real || (p.real == last_->real && p.midpoint && !last_->midpoint);
    }
    uint64_t epoch_{};
    uint32_t width_{}, height_{};
    std::optional<Position> last_;
};
}
