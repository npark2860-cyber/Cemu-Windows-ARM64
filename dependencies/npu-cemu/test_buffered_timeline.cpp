#include "buffered_timeline.h"
#include <iostream>
#include <array>
#include <vector>
using namespace cemu::npu;
using namespace std::chrono_literals;
int checks{};
void require(bool value,const char* message) {++checks;if(!value)throw std::runtime_error(message);}
Completion done(uint64_t epoch,uint64_t current) {
    Completion result;result.executed=true;result.pair={epoch,current-1,current,0,1920,1080,Clock::now()+1s};return result;
}
// Replay host captures with a GPU input fence two source ticks behind, followed
// by one tick of inference. This reproduces the observed pre-inference expiry.
// The legacy one-frame selection expires every pair; adaptive selection must
// keep the same pairs alive without ever inserting a midpoint behind its real.
unsigned replay(unsigned gpuTicks,unsigned npuTicks,bool adaptive) {
    struct Job {uint64_t id;unsigned submitted,started{};bool executed{},cancelled{};};
    BufferedTimeline timeline;timeline.reset(12,1920,1080);
    std::vector<Job> jobs;
    std::array<uint64_t,NativeHistorySize> originals{};
    uint64_t displayed{};
    unsigned generated{},holds{};
    for(unsigned tick=1;tick<=240;++tick) {
        originals[nativeHistoryIndex(tick)]=tick;
        for(auto& job:jobs) {
            if(job.cancelled || job.executed || job.started || tick<job.submitted+gpuTicks) continue;
            if(job.id<=displayed) job.cancelled=true;
            else job.started=tick;
        }
        for(auto& job:jobs)
            if(job.started && tick>=job.started+npuTicks) job.executed=true;
        const auto next=timeline.nextReal(tick);
        bool pending=false;
        for(const auto& job:jobs) if(job.id==next && !job.cancelled && !job.executed) pending=true;
        auto plan=timeline.begin(tick,adaptive && pending);
        require(plan.real>=displayed && plan.real<=displayed+1,"originals neither reverse nor skip");
        require(tick-plan.real<=MaxBufferedFrames,"bounded latency during GPU delays");
        require(originals[plan.displayIndex]==plan.real,"native output still belongs to the selected real frame");
        holds+=plan.repeated;
        for(auto& job:jobs) {
            if(!job.executed || job.cancelled || job.id!=plan.real) continue;
            const bool accepted=timeline.generated(plan,done(12,job.id),Clock::now());
            if(accepted) {require(job.id>displayed,"generated frame precedes its new real");++generated;}
            job.cancelled=true;
        }
        timeline.real(plan);displayed=plan.real;
        if(tick>=2) jobs.push_back({tick,tick});
    }
    require(holds<=MaxBufferedFrames,"delay grows at most twice after warmup");
    return generated;
}
int main() {
    try {
        BufferedTimeline timeline;timeline.reset(7,1920,1080);
        auto first=timeline.begin(1);
        require(first.real==1 && first.captureIndex==0 && first.displayIndex==0,"initial passthrough");
        require(timeline.real(first),"first real advances timeline");
        auto second=timeline.begin(2);
        require(second.real==1 && second.captureIndex==1 && second.displayIndex==0,"second tick preserves buffered real1");
        require(!timeline.real(second),"warmup duplicate does not advance timeline");
        auto third=timeline.begin(3);auto pair12=done(7,2);
        require(third.real==2 && third.captureIndex==0 && third.displayIndex==1,"third tick outputs buffered real2");
        require(timeline.generated(third,pair12,Clock::now()),"mid1.5 before real2");
        require(!timeline.generated(third,pair12,Clock::now()),"duplicate midpoint rejected");
        require(timeline.real(third),"real2 after mid1.5");
        auto fourth=timeline.begin(4);auto pair23=done(7,3);
        require(timeline.real(fourth),"missing NPU completion releases real3");
        require(!timeline.generated(fourth,pair23,Clock::now()),"late mid2.5 rejected after real3");
        auto fifth=timeline.begin(5);
        require(!timeline.generated(fifth,pair23,Clock::now()),"late job cannot be inserted next tick");
        require(timeline.generated(fifth,done(7,4),Clock::now()),"fresh next pair can recover after a miss");
        require(timeline.real(fifth),"real4 advances after recovery");
        timeline.reset(8,1920,1080);timeline.real(timeline.begin(1));timeline.real(timeline.begin(2));auto resetThird=timeline.begin(3);
        require(!timeline.generated(resetThird,pair12,Clock::now()),"OFF/ON or resize rejects old epoch");
        require(timeline.generated(resetThird,done(8,2),Clock::now()),"new epoch can warm up");
        bool gap=false;try{timeline.begin(8);}catch(const std::invalid_argument&){gap=true;}
        require(gap,"missing capture IDs require reset");
        bool zero=false;try{BufferedTimeline::captureIndex(0);}catch(const std::invalid_argument&){zero=true;}
        require(zero,"zero ID rejected");
        require(replay(2,1,false)==0,"legacy GPU-lag replay reproduces zero generated frames");
        require(replay(2,1,true)>230,"adaptive buffering admits delayed GPU input before NPU inference");
        require(replay(1,1,true)>230,"two-tick producer recovers without three-frame delay");
        require(replay(4,1,true)==0,"excess latency falls back without presenting old midpoints");
        // A missing job must never hold the real stream indefinitely.
        timeline.reset(14,1280,720);
        for(uint64_t id=1;id<=1000;++id) {
            const auto plan=timeline.begin(id,false);
            require(plan.real==(id==1?1:id-1),"no job preserves the low-delay real stream");
            timeline.real(plan);
        }
        timeline.reset(15,1280,720);
        timeline.real(timeline.begin(1));timeline.real(timeline.begin(2));
        auto hold=timeline.begin(3,true);require(hold.real==1 && hold.bufferedFrames==2,"GPU-pending job holds the last original");timeline.real(hold);
        hold=timeline.begin(4,true);require(hold.real==1 && hold.bufferedFrames==3,"second hold stays within native ring");timeline.real(hold);
        auto capped=timeline.begin(5,true);require(capped.real==2 && capped.bufferedFrames==3,"unready producer cannot grow latency beyond cap");timeline.real(capped);
        require(!timeline.generated(capped,done(15,2),Clock::now()),"completion arriving after fallback is rejected");
        timeline.reset(16,1280,720);
        auto restarted=timeline.begin(1);require(restarted.real==1 && restarted.bufferedFrames==0,"toggle/resize resets adaptive delay");timeline.real(restarted);
        auto old=done(15,2);old.pair.width=1280;old.pair.height=720;
        timeline.real(timeline.begin(2));auto next=timeline.begin(3);
        require(!timeline.generated(next,old,Clock::now()),"old epoch cannot enter new native history");
        auto wrongSize=done(16,2);require(!timeline.generated(next,wrongSize,Clock::now()),"old processing size cannot enter new epoch");
        std::cout<<"{\"status\":\"BUFFERED_TIMELINE_TESTS_PASSED\",\"checks\":"<<checks<<",\"gpu_npu_executed\":false}\n";
        return 0;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}
}
