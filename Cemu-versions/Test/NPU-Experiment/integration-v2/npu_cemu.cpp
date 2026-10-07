#define VK_NO_PROTOTYPES
#include "npu_cemu.h"
#include "borrowed_support.h"
#include "anvil_async_worker.h"
#include "buffered_timeline.h"
#include "ort_paths.h"
#include <memory>

constexpr uint32_t width=1920,height=1080;
constexpr size_t pixels=size_t(width)*height,inputBytes=pixels*6,outputBytes=pixels*3,rgbaBytes=pixels*4,flowBytes=120*68*16;
#include "gpu_resources.h"

enum class SlotState { Free, Working, Ready, Consuming, Orphan };
struct Slot {
    Vulkan& vk;
    Buffer input,output,forward,backward;
    GpuImage composed,quarterA,quarterB,warpedA,warpedB;
    Compute compute;
    Ort::Value inputTensor{nullptr},outputTensor{nullptr};
    VkCommandBuffer pre{},post{};
    VkFence inputFence{},composeFence{};
    SlotState state{SlotState::Free};
    cemu::npu::Completion completion{};
    Slot(Vulkan& v):vk(v),input(v),output(v),forward(v),backward(v),composed(v),quarterA(v),quarterB(v),warpedA(v),warpedB(v),compute(v){}
    void create(Ort::Allocator& allocator,GpuImage& a,GpuImage& b,const fs::path& shaders) {
        input.create(inputBytes,&allocator); output.create(outputBytes,&allocator);
        forward.create(flowBytes,nullptr,VK_BUFFER_USAGE_STORAGE_BUFFER_BIT); backward.create(flowBytes,nullptr,VK_BUFFER_USAGE_STORAGE_BUFFER_BIT);
        composed.create();quarterA.create(480,270);quarterB.create(480,270);warpedA.create();warpedB.create();
        compute.create(input,output,a,b,composed,forward,backward,quarterA,quarterB,warpedA,warpedB,shaders);
        const std::array<int64_t,4> inShape{1,1080,1920,6},outShape{1,1080,1920,3};
        inputTensor=Ort::Value::CreateTensor<uint8_t>(allocator.GetInfo(),static_cast<uint8_t*>(input.pointer),inputBytes,inShape.data(),4);
        outputTensor=Ort::Value::CreateTensor<uint8_t>(allocator.GetInfo(),static_cast<uint8_t*>(output.pointer),outputBytes,outShape.data(),4);
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
    Vulkan vk;
    Module rpc;
    std::unique_ptr<Ort::Env> env;
    std::unique_ptr<Ort::Session> session;
    std::unique_ptr<Ort::Allocator> allocator;
    std::array<std::unique_ptr<GpuImage>,2> history;
    std::array<std::unique_ptr<Slot>,3> slots;
    std::string inputName,outputName;
    std::unique_ptr<cemu::npu::AsyncWorker> worker;
    cemu::npu::BufferedTimeline timeline;
    std::atomic<uint64_t> latestReal{},npuRuns{},inputWaitUs{},npuRunUs{},workerStartUs{};
    CemuNpuStats counters{};
    static uint64_t micros(Clock::time_point begin) { return uint64_t(std::chrono::duration_cast<std::chrono::microseconds>(Clock::now()-begin).count()); }
    void initialize(const CemuNpuCreateInfo& info) {
        const char* stage="borrowed Vulkan setup";
        try {
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
        env=std::make_unique<Ort::Env>(ORT_LOGGING_LEVEL_WARNING,"cemu-npu-experimental");
        Ort::SessionOptions options;options.SetIntraOpNumThreads(1);options.SetInterOpNumThreads(1);
        options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
        options.AddConfigEntry("session.disable_cpu_ep_fallback","1");
        stage="QNN provider registration";
        options.AppendExecutionProvider("QNN",{{"backend_path",backend},{"offload_graph_io_quantization","0"},
            {"enable_htp_fp16_precision","1"},{"htp_performance_mode","balanced"},{"profiling_level","off"},{"enable_htp_shared_memory_allocator","1"}});
        stage="QNN session creation (wide model path, app-local backend basename)";
        session=std::make_unique<Ort::Session>(*env,(directory/L"anvil-1080p-u8nhwc.onnx").c_str(),options);
        stage="model I/O verification";
        if(session->GetInputCount()!=1 || session->GetOutputCount()!=1) throw std::runtime_error("Unexpected model I/O count");
        const std::array<std::vector<int64_t>,2> shapes{{{1,1080,1920,6},{1,1080,1920,3}}};
        for(unsigned i=0;i<2;++i) {
            auto type=i?session->GetOutputTypeInfo(0):session->GetInputTypeInfo(0);auto tensor=type.GetTensorTypeAndShapeInfo();
            if(tensor.GetElementType()!=ONNX_TENSOR_ELEMENT_DATA_TYPE_UINT8 || tensor.GetShape()!=shapes[i]) throw std::runtime_error("Pinned U8 NHWC 1080p model required");
        }
        Ort::AllocatorWithDefaultOptions names;
        inputName=session->GetInputNameAllocated(0,names).get();outputName=session->GetOutputNameAllocated(0,names).get();
        stage="QNN shared allocator";
        Ort::MemoryInfo shared("QnnHtpShared",OrtDeviceAllocator,0,OrtMemTypeDefault);
        allocator=std::make_unique<Ort::Allocator>(*session,shared);
        if(allocator->GetInfo().GetAllocatorName()!="QnnHtpShared") throw std::runtime_error("Shared allocator unavailable");
        stage="Vulkan images and shared tensor slots";
        for(auto& image:history) { image=std::make_unique<GpuImage>(vk);image->create(); }
        for(auto& slot:slots) { slot=std::make_unique<Slot>(vk);slot->create(*allocator,*history[0],*history[1],directory/L"shaders"); }
        stage="asynchronous worker";
        worker=std::make_unique<cemu::npu::AsyncWorker>(slots.size());
        reset(); // Prepared OFF; no Run/dispatch on captured frames has happened.
        } catch(const std::exception& e) {throw std::runtime_error(std::string(stage)+": "+e.what());}
    }
    void reset() {
        latestReal.store(0,std::memory_order_release);
        timeline.reset(worker->reset(),width,height);
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
            if(result->stale || !result->executed || result->pair.current<=latestReal.load(std::memory_order_acquire)) {slot.state=SlotState::Free;++counters.stale;}
            else {slot.completion=*result;slot.state=SlotState::Ready;}
        }
    }
    void process(uint64_t frameId,CemuNpuFrame& frame) {
        const auto plan=timeline.begin(frameId);
        const auto current=plan.captureIndex,previous=current^1;
        frame={history[plan.displayIndex]->image,VK_NULL_HANDLE,plan.real,-1};
        poll();
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
        // First two captures repeat real1 once to establish the one-frame delay.
        timeline.real(plan);latestReal.store(frame.realId,std::memory_order_release);
        if(frameId<2) return;
        size_t index=slots.size();for(size_t i=0;i<slots.size();++i) if(slots[i]->state==SlotState::Free) {index=i;break;}
        if(index==slots.size()) {++counters.noSlot;return;}
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
        cemu::npu::FramePair pair{epoch,frameId-1,frameId,index,width,height,queued+std::chrono::milliseconds(250)};
        if(worker->submit(pair,[this,index,frameId,queued](const auto& currentEpoch) {
            auto& target=*slots[index];workerStartUs.fetch_add(micros(queued),std::memory_order_relaxed);
            const auto waitStart=Clock::now();
            check(vk.vkWaitForFences(vk.device,1,&target.inputFence,VK_TRUE,UINT64_MAX),"NPU input GPU fence");
            inputWaitUs.fetch_add(micros(waitStart),std::memory_order_relaxed);
            if(!currentEpoch() || latestReal.load(std::memory_order_acquire)>=frameId) return false;
            const char* in=inputName.c_str();const char* out=outputName.c_str();const auto runStart=Clock::now();
            session->Run(Ort::RunOptions{nullptr},&in,&target.inputTensor,1,&out,&target.outputTensor,1);
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
