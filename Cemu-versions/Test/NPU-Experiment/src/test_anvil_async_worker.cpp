#include "anvil_async_worker.h"
#include <future>
#include <iostream>
#include <latch>
#include <vector>
using namespace cemu::npu;
using namespace std::chrono_literals;
int checks{};
void require(bool value, const char* message) { ++checks; if (!value) throw std::runtime_error(message); }
FramePair pair(uint64_t epoch, uint64_t slot, uint64_t id=10) { return {epoch,id,id+1,slot,1920,1080,Clock::now()+10s}; }
Completion waitResult(AsyncWorker& worker) {
    const auto until=Clock::now()+3s;
    while (Clock::now()<until) { if(auto r=worker.take()) return *r; std::this_thread::yield(); }
    throw std::runtime_error("Worker did not finish");
}
int main() {
    try {
        {
            AsyncWorker worker(2); std::latch entered(1), release(1);
            auto p=pair(worker.epoch(),1);
            require(worker.submit(p,[&](const auto& current){ entered.count_down(); release.wait(); return current(); }),"submit first");
            entered.wait();
            auto attempts=std::async(std::launch::async,[&] {
                require(!worker.take(),"take must not wait for in-flight inference");
                require(!worker.submit(p,[](const auto&){return true;}),"slot cannot be overwritten");
                auto second=pair(worker.epoch(),2);
                // try-lock can transiently refuse; the worker is now blocked outside its mutex.
                require(worker.submit(second,[](const auto& current){return current();}),"submit while NPU blocked");
                require(!worker.submit(pair(worker.epoch(),3),[](const auto&){return true;}),"bounded total occupancy");
                worker.reset();
            });
            const bool responsive=attempts.wait_for(1s)==std::future_status::ready;
            release.count_down(); attempts.get(); require(responsive,"render operations blocked on inference");
            const auto a=waitResult(worker), b=waitResult(worker);
            require(a.stale && b.stale && !a.executed && !b.executed,"reset cancels running/queued inference after GPU ownership retires");
            require(worker.submit(pair(worker.epoch(),1),[](const auto&){return true;}),"slot reusable only after completion consumed");
            require(waitResult(worker).executed,"new generation executes");
        }
        {
            AsyncWorker worker; std::latch entered(1), release(1);
            require(worker.submit(pair(worker.epoch(),1),[&](const auto&){entered.count_down();release.wait();return true;}),"uncancellable inference accepted");
            entered.wait(); worker.reset(); release.count_down();
            auto result=waitResult(worker); require(result.executed && result.stale,"completed old inference stays discarded");
            require(worker.submit(pair(worker.epoch(),1),[](const auto&)->bool{throw std::runtime_error("simulated QNN failure");}),"error job accepted");
            require(bool(waitResult(worker).error),"error surfaced without killing worker");
            require(worker.submit(pair(worker.epoch(),1),[](const auto&){return true;}),"worker remains usable");
            require(waitResult(worker).executed,"subsequent inference succeeds");
            auto expired=pair(worker.epoch(),3); expired.deadline=Clock::now()-1ms;
            require(!worker.submit(expired,[](const auto&){return true;}),"expired input rejected");
        }
        {
            AsyncWorker worker; std::atomic<unsigned> retired{};
            std::latch entered(1), release(1);
            require(worker.submit(pair(worker.epoch(),1),[&](const auto& current){entered.count_down();release.wait();++retired;return current();}),"shutdown test accepted");
            entered.wait();
            require(worker.submit(pair(worker.epoch(),2),[&](const auto& current){++retired;return current();}),"queued ownership to retire");
            auto stopping=std::async(std::launch::async,[&]{worker.stop();});
            release.count_down(); stopping.get();
            require(retired==2,"shutdown drains ownership callbacks");
            require(!worker.submit(pair(worker.epoch(),3),[](const auto&){return true;}),"stopped worker rejects input");
        }
        {
            // Exercise stop during both idle wait and its transition into wait.
            for(unsigned i=0;i<100;++i) { AsyncWorker worker; if(i%2) std::this_thread::yield(); worker.stop(); }
            require(true,"idle/startup shutdown retires without losing the wake");
        }
        {
            PresentationGate gate; gate.reset(7,1920,1080);
            Completion r; r.pair=pair(7,1); r.executed=true;
            require(gate.real(10),"first real accepted");
            require(gate.generated(r,Clock::now()),"10.5 after real10");
            require(!gate.generated(r,Clock::now()),"duplicate midpoint rejected");
            require(gate.real(11),"real11 follows midpoint");
            require(!gate.generated(r,Clock::now()),"late10.5 cannot follow real11");
            gate.reset(8,1280,720); require(!gate.generated(r,Clock::now()),"resize generation rejects stale output");
            r.pair=pair(8,1); require(!gate.generated(r,Clock::now()),"extent mismatch rejected");
            r.pair.width=1280;r.pair.height=720;r.pair.deadline=Clock::now()-1ms;
            require(!gate.generated(r,Clock::now()),"expired output rejected");
            gate.reset(9,1920,1080); r.pair=pair(9,1,UINT64_MAX-1);
            require(gate.real(UINT64_MAX-1) && gate.generated(r,Clock::now()) && gate.real(UINT64_MAX),"timeline does not overflow");
        }
        std::cout<<"{\"status\":\"CPU_WORKER_TESTS_PASSED\",\"checks\":"<<checks<<",\"gpu_npu_executed\":false}\n";return 0;
    } catch(const std::exception& error) {std::cerr<<error.what()<<'\n';return 1;}
}
