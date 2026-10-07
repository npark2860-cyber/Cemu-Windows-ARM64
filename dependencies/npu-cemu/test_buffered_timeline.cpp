#include "buffered_timeline.h"
#include <iostream>
using namespace cemu::npu;
using namespace std::chrono_literals;
int checks{};
void require(bool value,const char* message) {++checks;if(!value)throw std::runtime_error(message);}
Completion done(uint64_t epoch,uint64_t current) {
    Completion result;result.executed=true;result.pair={epoch,current-1,current,0,1920,1080,Clock::now()+1s};return result;
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
        std::cout<<"{\"status\":\"BUFFERED_TIMELINE_TESTS_PASSED\",\"checks\":"<<checks<<",\"gpu_npu_executed\":false}\n";
        return 0;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}
}
