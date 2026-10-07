#pragma once
#include "anvil_async_worker.h"

namespace cemu::npu {
struct BufferedFrame {
    uint64_t captured{},real{};
    size_t captureIndex{},displayIndex{};
};
// One source frame of buffering. Completion must belong to the real frame being
// released now, never to a real frame already released on an earlier tick.
class BufferedTimeline {
public:
    static size_t captureIndex(uint64_t id) {
        if(!id) throw std::invalid_argument("Capture ID zero");
        return size_t((id-1)%2);
    }
    void reset(uint64_t epoch,uint32_t width,uint32_t height) {
        lastInput_=0;gate_.reset(epoch,width,height);
    }
    BufferedFrame begin(uint64_t id) {
        if(!id || lastInput_==UINT64_MAX || id!=lastInput_+1) throw std::invalid_argument("Non-consecutive capture ID; reset required");
        const auto current=captureIndex(id);lastInput_=id;
        return {id,id==1?1:id-1,current,id==1?current:current^1};
    }
    bool generated(const BufferedFrame& frame,const Completion& completion,Clock::time_point now) {
        return completion.pair.current==frame.real && gate_.generated(completion,now);
    }
    bool real(const BufferedFrame& frame) {return gate_.real(frame.real);}
private:
    uint64_t lastInput_{};
    PresentationGate gate_;
};
}
