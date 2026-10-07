#pragma once
#include "anvil_async_worker.h"
#include "frame_contract.h"

namespace cemu::npu {
struct BufferedFrame {
    uint64_t captured{},real{};
    size_t captureIndex{},displayIndex{};
    uint32_t bufferedFrames{};
    bool repeated{};
};
// Start one frame behind. If the next pair is still producing GPU input or
// inference, hold the last real frame to grow the delay, at most three frames.
// Never wait on the render thread, move backwards, or release a late midpoint.
// Keep the learned delay until reset, avoiding oscillation and skipped originals.
class BufferedTimeline {
public:
    static size_t captureIndex(uint64_t id) {
        if(!id) throw std::invalid_argument("Capture ID zero");
        return size_t((id-1)%2);
    }
    void reset(uint64_t epoch,uint32_t width,uint32_t height) {
        lastInput_=lastReal_=0;delay_=1;gate_.reset(epoch,width,height);
    }
    uint64_t nextReal(uint64_t id) const {
        if(!id || lastInput_==UINT64_MAX || id!=lastInput_+1) throw std::invalid_argument("Non-consecutive capture ID; reset required");
        return id>delay_?id-delay_:1;
    }
    BufferedFrame begin(uint64_t id,bool nextPairPending=false) {
        auto real=nextReal(id);
        if(nextPairPending && real>lastReal_ && lastReal_ && delay_<MaxBufferedFrames) {
            ++delay_;real=lastReal_;
        }
        const auto current=captureIndex(id);lastInput_=id;
        return {id,real,current,nativeHistoryIndex(real),uint32_t(id-real),real==lastReal_};
    }
    bool generated(const BufferedFrame& frame,const Completion& completion,Clock::time_point now) {
        return completion.pair.current==frame.real && gate_.generated(completion,now);
    }
    bool real(const BufferedFrame& frame) {
        if(!gate_.real(frame.real)) return false;
        lastReal_=frame.real;return true;
    }
private:
    uint64_t lastInput_{},lastReal_{};
    uint32_t delay_{1};
    PresentationGate gate_;
};
}
