#define VK_NO_PROTOTYPES
#include "npu_cemu.h"
#include "borrowed_support.h"
#include "anvil_async_worker.h"
#include "buffered_timeline.h"
#include "ort_paths.h"
#include "pair_admission.h"
#include "qnn_context_cache.h"
#include <functional>
#include <map>
#include <memory>
#include <unordered_map>

#include "processing_profile.h"
#include "gpu_resources.h"

enum class SlotState { Free, Working, Ready, Consuming, Orphan };
struct Slot {
    Vulkan& vk;
    const ProcessingProfile& profile;
    Buffer input,output,forward,backward;
    GpuImage composed,quarterA,quarterB,warpedA,warpedB;
    Compute compute;
    Ort::Value inputTensor{nullptr},outputTensor{nullptr};
    VkCommandBuffer pre{},post{};
    VkFence inputFence{},composeFence{};
    SlotState state{SlotState::Free};
    cemu::npu::Completion completion{};
    uint64_t jobFrame{},jobEpoch{};
    // Written by the worker for its job and read after take(); the worker
    // mutex orders both. submitted is set before the job is handed over.
    Clock::time_point submitted{},waitStart{},waitEnd{};
    Clock::duration run{};
    bool ran{};
    Slot(Vulkan& v,const ProcessingProfile& p):vk(v),profile(p),input(v),output(v),forward(v),backward(v),composed(v),quarterA(v),quarterB(v),warpedA(v),warpedB(v),compute(v,p){}
    void create(Ort::Allocator& allocator,GpuImage& a,GpuImage& b,const fs::path& shaders) {
        input.create(profile.inputBytes,&allocator); output.create(profile.outputBytes,&allocator);
        forward.create(profile.flowBytes,nullptr,VK_BUFFER_USAGE_STORAGE_BUFFER_BIT); backward.create(profile.flowBytes,nullptr,VK_BUFFER_USAGE_STORAGE_BUFFER_BIT);
        composed.create(profile.width,profile.height);quarterA.create(profile.width/4,profile.height/4);quarterB.create(profile.width/4,profile.height/4);warpedA.create(profile.width,profile.height);warpedB.create(profile.width,profile.height);
        compute.create(input,output,a,b,composed,forward,backward,quarterA,quarterB,warpedA,warpedB,shaders);
        const std::array<int64_t,4> inShape{1,profile.height,profile.width,6},outShape{1,profile.height,profile.width,3};
        inputTensor=Ort::Value::CreateTensor<uint8_t>(allocator.GetInfo(),static_cast<uint8_t*>(input.pointer),profile.inputBytes,inShape.data(),4);
        outputTensor=Ort::Value::CreateTensor<uint8_t>(allocator.GetInfo(),static_cast<uint8_t*>(output.pointer),profile.outputBytes,outShape.data(),4);
        VkCommandBufferAllocateInfo ai{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO}; ai.commandPool=vk.pool;ai.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY;ai.commandBufferCount=1;
        check(vk.vkAllocateCommandBuffers(vk.device,&ai,&pre),"allocate preprocessing command");
        check(vk.vkAllocateCommandBuffers(vk.device,&ai,&post),"allocate compose command");
        VkFenceCreateInfo fi{VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};
        check(vk.vkCreateFence(vk.device,&fi,nullptr,&inputFence),"create input fence");
        check(vk.vkCreateFence(vk.device,&fi,nullptr,&composeFence),"create compose fence");
    }
    void bindSources(GpuImage& a,GpuImage& b) {
        const VkDescriptorImageInfo images[2]{{VK_NULL_HANDLE,a.view,VK_IMAGE_LAYOUT_GENERAL},{VK_NULL_HANDLE,b.view,VK_IMAGE_LAYOUT_GENERAL}};
        VkWriteDescriptorSet writes[2]{};
        for(unsigned i=0;i<2;++i) { writes[i].sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;writes[i].dstSet=compute.set;writes[i].dstBinding=i;writes[i].descriptorCount=1;writes[i].descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE;writes[i].pImageInfo=&images[i]; }
        vk.vkUpdateDescriptorSets(vk.device,2,writes,0,nullptr);
    }
    ~Slot() {
        if(inputFence) vk.vkDestroyFence(vk.device,inputFence,nullptr);
        if(composeFence) vk.vkDestroyFence(vk.device,composeFence,nullptr);
    }
};

struct CemuNpu {
    ProcessingProfile profile;
    Vulkan vk;
    Module rpc;
    std::unique_ptr<Ort::Env> env;
    std::unique_ptr<Ort::Session> session;
    std::unique_ptr<Ort::Allocator> allocator;
    std::array<std::unique_ptr<GpuImage>,2> history;
    std::array<std::unique_ptr<Slot>,cemu::npu::JobSlotCount> slots;
    std::string inputName,outputName;
    std::unique_ptr<cemu::npu::AsyncWorker> worker;
    cemu::npu::BufferedTimeline timeline;
    cemu::npu::PairAdmission admission{cemu::npu::MaxBufferedFrames};
    std::atomic<uint64_t> latestReal{},npuRuns{},inputWaitUs{},npuRunUs{},workerStartUs{};
    CemuNpuStats counters{};
    static uint64_t micros(Clock::time_point begin) { return uint64_t(std::chrono::duration_cast<std::chrono::microseconds>(Clock::now()-begin).count()); }
    void initialize(const CemuNpuCreateInfo& info) {
        const char* stage="borrowed Vulkan setup";
        try {
        profile=ProcessingProfile::fromHeight(info.processingHeight);
        vk.initialize(info);
        stage="RPC library verification";
        const fs::path directory(info.directory),rpcPath(info.rpcLibrary);
        if(!rpcPath.is_absolute() || rpcPath.filename()!=L"libcdsprpc.dll") throw std::runtime_error("Absolute pinned RPC library required");
        rpc.load(rpcPath,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
        wchar_t loaded[32768]{};const auto length=GetModuleFileNameW(rpc.handle,loaded,DWORD(std::size(loaded)));
        if(!length || length>=std::size(loaded) || !fs::equivalent(rpcPath,loaded)) throw std::runtime_error("RPC path mismatch");
        if(std::string(OrtGetApiBase()->GetVersionString())!="1.24.4") throw std::runtime_error("Expected pinned ORT 1.24.4");
        stage="ORT runtime and backend path verification";
        const auto backend=cemu::npu::backendName(directory,cemu::npu::modulePath(GetModuleHandleW(L"onnxruntime.dll")));
        stage="ORT environment";
        env=std::make_unique<Ort::Env>(ORT_LOGGING_LEVEL_WARNING,"cemu-npu");
        Ort::SessionOptions options;options.SetIntraOpNumThreads(1);options.SetInterOpNumThreads(1);
        options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
        options.AddConfigEntry("session.disable_cpu_ep_fallback","1");
        stage="QNN provider registration";
        const std::unordered_map<std::string,std::string> qnn{{"backend_path",backend},{"offload_graph_io_quantization","0"},
            {"enable_htp_fp16_precision","1"},{"htp_performance_mode","balanced"},{"profiling_level","off"},{"enable_htp_shared_memory_allocator","1"}};
        options.AppendExecutionProvider("QNN",qnn);
        stage="QNN session creation (wide model path, app-local backend basename)";
        session=openSession(directory,directory/L"npu"/profile.label/L"anvil-u8nhwc.onnx",rpcPath,options,qnn);
        Ort::AllocatorWithDefaultOptions names;
        inputName=session->GetInputNameAllocated(0,names).get();outputName=session->GetOutputNameAllocated(0,names).get();
        stage="QNN shared allocator";
        Ort::MemoryInfo shared("QnnHtpShared",OrtDeviceAllocator,0,OrtMemTypeDefault);
        allocator=std::make_unique<Ort::Allocator>(*session,shared);
        if(allocator->GetInfo().GetAllocatorName()!="QnnHtpShared") throw std::runtime_error("Shared allocator unavailable");
        stage="Vulkan images and shared tensor slots";
        for(auto& image:history) { image=std::make_unique<GpuImage>(vk);image->create(profile.width,profile.height); }
        for(auto& slot:slots) { slot=std::make_unique<Slot>(vk,profile);slot->create(*allocator,*history[0],*history[1],directory/L"npu"/profile.label/L"shaders"); }
        stage="asynchronous worker";
        worker=std::make_unique<cemu::npu::AsyncWorker>(slots.size());
        reset(); // Prepared OFF; no Run/dispatch on captured frames has happened.
        } catch(const std::exception& e) {throw std::runtime_error(std::string(stage)+": "+e.what());}
    }
    void verifyModel(Ort::Session& candidate) const {
        if(candidate.GetInputCount()!=1 || candidate.GetOutputCount()!=1) throw std::runtime_error("Unexpected model I/O count");
        const std::array<std::vector<int64_t>,2> shapes{{{1,profile.height,profile.width,6},{1,profile.height,profile.width,3}}};
        for(unsigned i=0;i<2;++i) {
            auto type=i?candidate.GetOutputTypeInfo(0):candidate.GetInputTypeInfo(0);auto tensor=type.GetTensorTypeAndShapeInfo();
            if(tensor.GetElementType()!=ONNX_TENSOR_ELEMENT_DATA_TYPE_UINT8 || tensor.GetShape()!=shapes[i]) throw std::runtime_error("U8 NHWC model does not match the selected processing resolution");
        }
    }
    // QNN graph preparation dominates startup (about 4 s measured for the FP16
    // model). Compile once into an embedded EP context and reuse it from
    // npu/<profile>/cache on later starts. Cache problems never fail startup:
    // the last step is the original uncached session from the source model.
    // A key whose context failed here once is marked and stays uncached, so a
    // broken cache costs at most one slower start; deleting the folder retries.
    std::unique_ptr<Ort::Session> openSession(const fs::path& directory,const fs::path& model,const fs::path& rpcPath,
                                              const Ort::SessionOptions& options,const std::unordered_map<std::string,std::string>& qnn) {
        std::error_code ignored;
        std::vector<char> source;fs::path cache,disabled;
        try {
            source=cemu::npu::readFile(model);
            cemu::npu::ContextCacheKey key;
            key.add("qnn-context-v1").add(source).add(OrtGetApiBase()->GetVersionString()).add(utf8(rpcPath.wstring()));
            for(const auto& [name,value]:std::map<std::string,std::string>(qnn.begin(),qnn.end())) key.add(name).add(value);
            for(const auto* file:{L"onnxruntime.dll",L"onnxruntime_providers_qnn.dll",L"QnnHtp.dll",L"QnnHtpPrepare.dll",L"QnnSystem.dll",
                                  L"QnnHtpV73Stub.dll",L"libQnnHtpV73Skel.so",L"QnnHtpV81Stub.dll",L"libQnnHtpV81Skel.so"}) key.addFile(directory/file);
            cache=model.parent_path()/L"cache"/cemu::npu::contextFileName(key);
            disabled=cemu::npu::disabledMarker(cache);
            if(fs::exists(disabled,ignored)) cache.clear();
        } catch(const std::exception&) {cache.clear();}
        if(!cache.empty()) {
            try {
                if(fs::is_regular_file(cache,ignored)) {
                    const auto bytes=cemu::npu::readFile(cache);
                    auto cached=std::make_unique<Ort::Session>(*env,bytes.data(),bytes.size(),options);
                    verifyModel(*cached);return cached;
                }
                Ort::AllocatorWithDefaultOptions cpu;
                void* data{};size_t size{};
                Ort::ModelCompilationOptions compile(*env,options);
                compile.SetInputModelFromBuffer(source.data(),source.size()).SetEpContextEmbedMode(true)
                    .SetOutputModelBuffer(cpu,&data,&size).SetFlags(OrtCompileApiFlags_ERROR_IF_NO_NODES_COMPILED)
                    .SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
                auto status=Ort::CompileModel(*env,compile);
                const std::unique_ptr<void,std::function<void(void*)>> compiled(data,[&cpu](void* p){if(p) cpu.Free(p);});
                if(!status.IsOK() || !data || !size) throw std::runtime_error(status.GetErrorMessage());
                auto fresh=std::make_unique<Ort::Session>(*env,data,size,options);
                verifyModel(*fresh);
                if(cemu::npu::writeFileReplacing(cache,data,size)) cemu::npu::removeStaleContexts(cache.parent_path(),cache.filename());
                return fresh;
            } catch(const std::exception&) {
                fs::remove(cache,ignored);
                cemu::npu::writeFileReplacing(disabled,"",0);
            }
        }
        auto uncached=std::make_unique<Ort::Session>(*env,model.c_str(),options);
        verifyModel(*uncached);return uncached;
    }
    void reset() {
        latestReal.store(0,std::memory_order_release);
        timeline.reset(worker->reset(),profile.width,profile.height);
        admission.reset();
    }
    bool finished(VkFence fence) {
        const auto status=vk.vkGetFenceStatus(vk.device,fence);
        if(status==VK_NOT_READY) return false;
        check(status,"vkGetFenceStatus");return true;
    }
    void submit(VkFence fence) {
        check(vk.vkEndCommandBuffer(vk.command),"vkEndCommandBuffer");
        check(vk.vkResetFences(vk.device,1,&fence),"vkResetFences");
        VkSubmitInfo si{VK_STRUCTURE_TYPE_SUBMIT_INFO};si.commandBufferCount=1;si.pCommandBuffers=&vk.command;
        const auto start=Clock::now();check(vk.vkQueueSubmit(vk.queue,1,&si,fence),"NPU vkQueueSubmit");counters.submitMs+=elapsed(start);
    }
    void poll() {
        for(auto& slot:slots) {
            if(slot->state==SlotState::Consuming && finished(slot->composeFence)) {
                double ms{};if(slot->compute.timing(6,1,&ms)) {counters.composeMs+=ms;++counters.postGpuSamples;}
                // Cemu submits all reads before the next process() call. New
                // preprocessing follows those reads on the same queue with a
                // global barrier and input fence before any new NPU writes.
                slot->state=SlotState::Free;
            }
            if(slot->state==SlotState::Orphan && finished(slot->inputFence)) slot->state=SlotState::Free;
        }
        while(auto result=worker->take()) {
            auto& slot=*slots.at(size_t(result->pair.slot));++counters.completed;
            double ms[3]{};if(slot.compute.timing(0,3,ms)) {counters.downsampleMs+=ms[0];counters.motionMs+=ms[1];counters.packMs+=ms[2];++counters.preGpuSamples;}
            if(result->error) {slot.state=SlotState::Free;std::rethrow_exception(result->error);}
            admission.completed(slot.submitted,slot.waitStart,slot.waitEnd,
                slot.ran?std::optional<cemu::npu::PairAdmission::Duration>(slot.run):std::nullopt,result->finished);
            if(result->stale || !result->executed || result->pair.current<=latestReal.load(std::memory_order_acquire)) {slot.state=SlotState::Free;++counters.stale;}
            else {slot.completion=*result;slot.state=SlotState::Ready;}
        }
    }
    void process(uint64_t frameId,CemuNpuFrame& frame) {
        // Poll before selecting the real frame. GPU input availability, not just
        // host capture count, determines whether the bounded delay must grow.
        admission.capture(Clock::now());
        poll();
        const auto next=timeline.nextReal(frameId);
        bool pending=false,ready=false;
        for(const auto& slot:slots) {
            if(slot->jobEpoch!=worker->epoch() || slot->jobFrame!=next) continue;
            pending|=slot->state==SlotState::Working;
            ready|=slot->state==SlotState::Ready;
        }
        const auto plan=timeline.begin(frameId,pending && !ready);
        const auto current=plan.captureIndex,previous=current^1;
        frame={VK_NULL_HANDLE,plan.real,-1,plan.bufferedFrames,uint32_t(plan.repeated)};
        if(plan.repeated) ++counters.heldRealFrames;
        for(size_t i=0;i<slots.size();++i) {
            auto& slot=*slots[i];if(slot.state!=SlotState::Ready) continue;
            if(slot.completion.pair.epoch!=worker->epoch() || slot.completion.pair.current<frame.realId) {slot.state=SlotState::Free;++counters.stale;continue;}
            if(slot.completion.pair.current!=frame.realId) continue;
            if(!timeline.generated(plan,slot.completion,Clock::now())) {slot.state=SlotState::Free;++counters.stale;continue;}
            vk.command=slot.post;vk.begin();
            vk.barrier(VK_ACCESS_MEMORY_READ_BIT|VK_ACCESS_MEMORY_WRITE_BIT|VK_ACCESS_HOST_WRITE_BIT,VK_ACCESS_SHADER_READ_BIT|VK_ACCESS_SHADER_WRITE_BIT,
                VK_PIPELINE_STAGE_ALL_COMMANDS_BIT|VK_PIPELINE_STAGE_HOST_BIT,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT);
            slot.compute.stamp(6,false);slot.compute.dispatch(2,0);slot.compute.stamp(7,true);
            vk.barrier(VK_ACCESS_SHADER_WRITE_BIT,VK_ACCESS_MEMORY_READ_BIT,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT);
            submit(slot.composeFence);slot.state=SlotState::Consuming;
            frame.generatedImage=slot.composed.image;frame.generatedSlot=int32_t(i);++counters.generated;
        }
        // Only the chosen display ID retires pairs. A held original keeps its
        // following midpoint eligible while the GPU/NPU producer is in flight.
        timeline.real(plan);latestReal.store(frame.realId,std::memory_order_release);
        if(frameId<2) return;
        size_t index=slots.size();for(size_t i=0;i<slots.size();++i) if(slots[i]->state==SlotState::Free) {index=i;break;}
        if(index==slots.size()) {++counters.noSlot;return;}
        // Record GPU preprocessing only for a pair the NPU can finish before its
        // real frame is shown. Pairs run in submission order on one NPU.
        std::array<Clock::time_point,cemu::npu::JobSlotCount> outstanding{};size_t waiting=0;
        for(const auto& other:slots) if(other->state==SlotState::Working) outstanding[waiting++]=other->submitted;
        std::sort(outstanding.begin(),outstanding.begin()+waiting);
        if(!admission.admit(Clock::now(),{outstanding.data(),waiting})) {++counters.noSlot;return;}
        auto& slot=*slots[index];slot.bindSources(*history[previous],*history[current]);
        vk.command=slot.pre;vk.begin();vk.vkCmdResetQueryPool(vk.command,slot.compute.queries,0,8);
        vk.barrier(VK_ACCESS_MEMORY_READ_BIT|VK_ACCESS_MEMORY_WRITE_BIT|VK_ACCESS_HOST_READ_BIT|VK_ACCESS_HOST_WRITE_BIT,
            VK_ACCESS_SHADER_READ_BIT|VK_ACCESS_SHADER_WRITE_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT|VK_PIPELINE_STAGE_HOST_BIT,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT);
        slot.compute.stamp(0,false);slot.compute.dispatch(3,0);slot.compute.stamp(1,true);
        vk.barrier(VK_ACCESS_SHADER_WRITE_BIT,VK_ACCESS_SHADER_READ_BIT,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT);
        slot.compute.stamp(2,false);slot.compute.dispatch(4,0);slot.compute.stamp(3,true);
        vk.barrier(VK_ACCESS_SHADER_WRITE_BIT,VK_ACCESS_SHADER_READ_BIT,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT);
        slot.compute.stamp(4,false);slot.compute.dispatch(1,0);slot.compute.stamp(5,true);
        vk.barrier(VK_ACCESS_SHADER_WRITE_BIT,VK_ACCESS_HOST_READ_BIT|VK_ACCESS_HOST_WRITE_BIT,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,VK_PIPELINE_STAGE_HOST_BIT);
        submit(slot.inputFence);slot.state=SlotState::Orphan;
        const auto queued=Clock::now();const auto epoch=worker->epoch();
        cemu::npu::FramePair pair{epoch,frameId-1,frameId,index,profile.width,profile.height,queued+std::chrono::milliseconds(250)};
        slot.jobFrame=frameId;slot.jobEpoch=epoch;slot.submitted=queued;
        if(worker->submit(pair,[this,index,frameId,queued](const auto& currentEpoch) {
            auto& target=*slots[index];workerStartUs.fetch_add(micros(queued),std::memory_order_relaxed);
            target.ran=false;target.waitStart=target.waitEnd=Clock::now();
            check(vk.vkWaitForFences(vk.device,1,&target.inputFence,VK_TRUE,UINT64_MAX),"NPU input GPU fence");
            target.waitEnd=Clock::now();
            inputWaitUs.fetch_add(micros(target.waitStart),std::memory_order_relaxed);
            if(!currentEpoch() || latestReal.load(std::memory_order_acquire)>=frameId) return false;
            const char* in=inputName.c_str();const char* out=outputName.c_str();const auto runStart=Clock::now();
            session->Run(Ort::RunOptions{nullptr},&in,&target.inputTensor,1,&out,&target.outputTensor,1);
            target.run=Clock::now()-runStart;target.ran=true;
            npuRunUs.fetch_add(micros(runStart),std::memory_order_relaxed);npuRuns.fetch_add(1,std::memory_order_relaxed);
            if(target.inputTensor.GetTensorRawData()!=target.input.pointer || target.outputTensor.GetTensorRawData()!=target.output.pointer) throw std::runtime_error("QNN replaced shared pointers");
            return true;
        })) {slot.state=SlotState::Working;++counters.submitted;}
        else ++counters.noSlot; // Poll the orphan's fence before recycling resources.
    }
    ~CemuNpu() {
        if(worker) worker->stop(); // Retire input fences and uncancellable Run first.
        if(vk.device && vk.vkDeviceWaitIdle) vk.vkDeviceWaitIdle(vk.device);
    }
};

static void errorText(char* destination,uint32_t size,const char* message) {
    if(destination && size) strncpy_s(destination,size,message,_TRUNCATE);
}
static int createContext(const CemuNpuCreateInfo* info,CemuNpu** out,char* error,uint32_t size) {
    if(out) *out=nullptr;
    try {
        if(!info || !out || info->size!=sizeof(*info) || info->abi!=CEMU_NPU_ABI || !info->directory || !info->rpcLibrary) throw std::runtime_error("NPU ABI mismatch");
        auto context=std::make_unique<CemuNpu>();context->initialize(*info);*out=context.release();return 0;
    } catch(const std::exception& e) {errorText(error,size,e.what());return 1;}
}
static int processFrame(CemuNpu* context,uint64_t id,CemuNpuFrame* frame,char* error,uint32_t size) {
    try {if(!context || !frame) throw std::runtime_error("Missing context/frame");context->process(id,*frame);return 0;}
    catch(const std::exception& e) {errorText(error,size,e.what());return 1;}
}
extern "C" __declspec(dllexport) int cemu_npu_get_api(uint32_t abi,CemuNpuApi* api) {
    if(!api || abi!=CEMU_NPU_ABI || api->size!=sizeof(*api)) return 1;
    api->abi=CEMU_NPU_ABI;api->create=createContext;api->destroy=[](CemuNpu* c){delete c;};
    api->reset=[](CemuNpu* c){if(c)c->reset();};
    api->captureImage=[](CemuNpu* c,uint64_t id){return c&&id?c->history[cemu::npu::BufferedTimeline::captureIndex(id)]->image:VK_NULL_HANDLE;};
    api->process=processFrame;
    api->stats=[](CemuNpu* c,CemuNpuStats* result){if(!c||!result)return;*result=c->counters;result->npuRuns=c->npuRuns.load();result->inputWaitUs=c->inputWaitUs.load();result->npuRunUs=c->npuRunUs.load();result->workerStartUs=c->workerStartUs.load();};
    return 0;
}
