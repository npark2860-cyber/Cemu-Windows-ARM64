// Deterministic model of the module's pair scheduling against the real
// BufferedTimeline and PairAdmission. One NPU serves a FIFO; every admitted
// pair first spends GPU preprocessing on the game's queue. Compares the
// predictive admission the module uses with the previous unconditional FIFO
// and with a fixed one-pair queue.
#include "buffered_timeline.h"
#include "pair_admission.h"
#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <deque>
#include <iostream>
#include <optional>
#include <vector>
using namespace cemu::npu;
using namespace std::chrono_literals;
int checks{};
void require(bool value,const char* message) {++checks;if(!value)throw std::runtime_error(message);}

#if __has_include("frame_contract.h")
constexpr size_t Slots=JobSlotCount;
constexpr uint32_t DeadlineFrames=MaxBufferedFrames;
#else
constexpr size_t Slots=3;
constexpr uint32_t DeadlineFrames=1;
#endif
enum class Policy {Fifo,OnePair,Predictive};
// Times in microseconds. jitter alternates the source interval; noise scales
// GPU and Run times by up to that fraction. firstGpu/firstRun are added to a
// slot's first GPU input and first Run (QNN registers its buffers then). Every
// stutterEvery captures one interval is stutter longer. Runs between captures
// slowFrom and slowTo take slowRun times as long (another NPU user, throttling).
struct Scenario {
    const char* name;int64_t interval,gpu,run,jitter{};double noise{};
    int64_t firstGpu{},firstRun{};unsigned stutterEvery{};int64_t stutter{};
    unsigned slowFrom{},slowTo{};double slowRun{1};
};
struct Result {unsigned preprocessed{},runs{},lateRuns{},generated{};};

Completion done(uint64_t epoch,uint64_t current) {
    Completion result;result.executed=true;result.pair={epoch,current-1,current,0,1280,720,Clock::now()+1s};return result;
}
template<class Timeline> BufferedFrame begin(Timeline& timeline,uint64_t id,bool pending) {
    if constexpr(requires {timeline.begin(id,pending);}) return timeline.begin(id,pending);
    else return timeline.begin(id);
}
template<class Timeline> uint64_t nextReal(const Timeline& timeline,uint64_t id) {
    if constexpr(requires {timeline.nextReal(id);}) return timeline.nextReal(id);
    else return id==1?1:id-1;
}
// Deterministic variation in [-1,1].
double wobble(uint64_t n) {n=n*6364136223846793005ull+1442695040888963407ull;return double((n>>33)%2001)/1000.0-1.0;}

// A popped job blocks the worker on its input fence, then is dropped unrun if
// its real frame was already displayed (as in the module's worker lambda). A
// result counts only when composed before its real. Jobs take the lowest free
// slot, as the module does.
Result simulate(const Scenario& s,Policy policy,unsigned ticks=900) {
    enum class State {Queued,Running,Done,Ready,Freed};
    struct Job {uint64_t id;size_t slot;int64_t submitted,inputReady,pop{},start{},end{};State state{State::Queued};bool ran{},firstJob{},firstRun{};};
    const auto at=[](int64_t us){return PairAdmission::Clock::time_point{}+std::chrono::microseconds(us);};
    std::vector<Job> jobs;std::deque<size_t> fifo;
    std::array<bool,Slots> busy{},used{},ranBefore{};
    BufferedTimeline timeline;timeline.reset(3,1280,720);
    PairAdmission admission(DeadlineFrames);
    Result result;
    std::optional<size_t> current;bool decided{};
    int64_t workerFree=0,now=1000000;uint64_t latestReal=0;
    for(unsigned tick=1;tick<=ticks;++tick) {
        now+=s.interval+((tick&1)?s.jitter:-s.jitter)+(s.stutterEvery && tick%s.stutterEvery==0?s.stutter:0);
        // Worker events strictly before this tick's process() call.
        for(;;) {
            if(current) {
                auto& job=jobs[*current];
                if(!decided) {
                    if(job.start>=now) break; // Still waiting on its GPU input fence.
                    decided=true;job.ran=latestReal<job.id;
                    if(job.ran) {
                        job.firstRun=!ranBefore[job.slot];ranBefore[job.slot]=true;
                        const double slow=job.id>=s.slowFrom && job.id<s.slowTo?s.slowRun:1.0;
                        job.end=job.start+int64_t(double(s.run)*slow*(1.0+s.noise*wobble(job.id)))+(job.firstRun?s.firstRun:0);
                    } else job.end=job.start;
                }
                if(job.end>=now) break;
                job.state=State::Done;workerFree=job.end;current.reset();
            }
            if(fifo.empty()) break;
            auto& job=jobs[fifo.front()];
            job.pop=std::max(workerFree,job.submitted);
            if(job.pop>=now) break;
            fifo.pop_front();job.state=State::Running;job.start=std::max(job.pop,job.inputReady);
            current=size_t(&job-jobs.data());decided=false;
        }
        admission.capture(at(now));
        // poll(): completions become Ready only while their real is still ahead.
        for(auto& job:jobs) if(job.state==State::Done) {
            std::optional<PairAdmission::Duration> run;
            if(job.ran) {++result.runs;if(job.id<=latestReal) ++result.lateRuns;}
            if(job.ran && !job.firstRun) run=PairAdmission::Duration(double(job.end-job.start));
            admission.completed(at(job.submitted),at(job.pop),at(job.start),at(job.end),job.firstJob,run);
            job.state=(job.ran && job.id>latestReal)?State::Ready:State::Freed;
            if(job.state==State::Freed) busy[job.slot]=false;
        }
        const auto next=nextReal(timeline,tick);
        bool pending=false,ready=false;
        for(const auto& job:jobs) if(job.id==next) {
            pending|=job.state==State::Queued || job.state==State::Running;
            ready|=job.state==State::Ready;
        }
        const auto plan=begin(timeline,tick,pending && !ready);
        for(auto& job:jobs) {
            if(job.state!=State::Ready) continue;
            if(job.id<plan.real) {job.state=State::Freed;busy[job.slot]=false;continue;}
            if(job.id!=plan.real) continue;
            if(timeline.generated(plan,done(3,job.id),Clock::now())) ++result.generated;
            job.state=State::Freed;busy[job.slot]=false;
        }
        timeline.real(plan);latestReal=plan.real;
        if(tick<2) continue;
        const auto free=std::find(busy.begin(),busy.end(),false);
        if(free==busy.end()) continue;
        std::vector<PairAdmission::Clock::time_point> outstanding;
        for(const auto& job:jobs) if(job.state==State::Queued || job.state==State::Running) outstanding.push_back(at(job.submitted));
        if(policy==Policy::OnePair && fifo.size()>=1) continue;
        if(policy==Policy::Predictive && !admission.admit(at(now),outstanding)) continue;
        ++result.preprocessed;
        const auto slot=size_t(free-busy.begin());busy[slot]=true;
        const bool first=!used[slot];used[slot]=true;
        jobs.push_back({tick,slot,now,now+int64_t(double(s.gpu)*(1.0+s.noise*wobble(tick+7)))+(first?s.firstGpu:0)});
        jobs.back().firstJob=first;fifo.push_back(jobs.size()-1);
    }
    return result;
}

int main() {
    try {
        // Fixed timing; the policies must agree with the FIFO where it works.
        const Scenario steady[]{
            {"720p, NPU keeps up",33333,3000,9000},
            {"1080p, NPU keeps up",33333,4600,19400},
            {"1080p, noisy timing",33333,4600,19400,3000,0.2},
            {"1080p, GPU input two frames late",33333,66000,19400},
            {"1080p, GPU late and noisy",33333,60000,19400,3000,0.2},
            {"1080p at 60 fps source",16667,4600,19400},
            {"1080p at 60 fps, late GPU input",16667,30000,19400},
            {"1080p at 60 fps, noisy",16667,4600,19400,2000,0.2},
            {"slow NPU, 2x source interval",16667,4600,34000},
            {"bursty pacing",25000,4600,19400,9000},
        };
        // Outliers and changes that the estimates must recover from.
        const Scenario changing[]{
            {.name="GPU input after the deadline",.interval=33333,.gpu=110000,.run=19400},
            {.name="slow first Run, 60 fps",.interval=16667,.gpu=4600,.run=12000,.firstRun=120000},
            {.name="slow first GPU input, 60 fps",.interval=16667,.gpu=4600,.run=12000,.firstGpu=50000},
            {.name="slow first GPU input, 30 fps",.interval=33333,.gpu=4600,.run=19400,.firstGpu=150000},
            {.name="200 ms stutter every 100, 60 fps",.interval=16667,.gpu=4600,.run=19400,.stutterEvery=100,.stutter=183333},
            {.name="60 ms stutter every 30, 60 fps",.interval=16667,.gpu=4600,.run=19400,.stutterEvery=30,.stutter=43333},
            {.name="NPU 6x slower for 200, 60 fps",.interval=16667,.gpu=4600,.run=12000,.slowFrom=300,.slowTo=500,.slowRun=6},
            {.name="NPU 6x slower for 200, 30 fps",.interval=33333,.gpu=4600,.run=19400,.slowFrom=300,.slowTo=500,.slowRun=6},
        };
        std::printf("%-34s %-17s %-17s %-17s %-17s\n","scenario (fifo/one/predictive)","preprocessed","NPU runs","late runs","generated");
        const auto run=[](const Scenario& s) {
            const auto fifo=simulate(s,Policy::Fifo),one=simulate(s,Policy::OnePair),now=simulate(s,Policy::Predictive);
            std::printf("%-34s %5u/%5u/%5u %5u/%5u/%5u %5u/%5u/%5u %5u/%5u/%5u\n",s.name,
                fifo.preprocessed,one.preprocessed,now.preprocessed,fifo.runs,one.runs,now.runs,
                fifo.lateRuns,one.lateRuns,now.lateRuns,fifo.generated,one.generated,now.generated);
            require(now.preprocessed<=fifo.preprocessed,"admission never preprocesses more pairs than the FIFO");
            require(now.generated<=now.runs && now.runs<=now.preprocessed,"every generated frame ran once on the NPU");
            return std::array{fifo,one,now};
        };
        for(const auto& s:steady) {
            const auto [fifo,one,now]=run(s);
            require(now.generated+now.generated/50+2>=fifo.generated,"admission keeps generated frames within 2% of the FIFO");
            require(now.lateRuns<=fifo.lateRuns,"admission never wastes more NPU runs than the FIFO");
        }
        for(const auto& s:changing) {
            const auto [fifo,one,now]=run(s);
            // Recovery: an outlier or a slow stretch must not lock generation
            // out. Fewer frames than the FIFO are fine only when it got them
            // by running mostly late pairs.
            require(now.generated*100>=fifo.generated*95 || now.lateRuns*10<=fifo.lateRuns,"admission recovers to within 5% of the FIFO");
            // Preprocessing for pairs never shown: at most half the FIFO's, plus probes.
            require(now.preprocessed-now.generated<=(fifo.preprocessed-fifo.generated)/2+45,"admission skips pairs that cannot be shown");
        }
        std::cout<<"{\"status\":\"NPU_SCHEDULING_TESTS_PASSED\",\"checks\":"<<checks<<",\"gpu_npu_executed\":false}\n";
        return 0;
    } catch(const std::exception& error) {std::cerr<<error.what()<<'\n';return 1;}
}
