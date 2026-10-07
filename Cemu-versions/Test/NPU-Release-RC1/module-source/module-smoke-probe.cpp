// Device test only. The default invocation refuses to initialize GPU/NPU.
#include "../src/motion1080_vulkan_support.h"
#include "npu_cemu.h"
#include <thread>

int wmain(int argc,wchar_t** argv) {
    if(argc!=4 || std::wstring(argv[1])!=L"--run") {
        std::cerr<<"Explicit --run <1080|720> <report.json> and an agreed device test time required.\n";
        return 2;
    }
    const std::wstring mode=argv[2];
    if(mode!=L"1080" && mode!=L"720") {std::cerr<<"Select 1080 or 720.\n";return 2;}
    const uint32_t height=mode==L"720"?720u:1080u;
    Report report;
    report.number("processing_height",height);
    try {
        wchar_t executable[32768]{};
        const DWORD size=GetModuleFileNameW(nullptr,executable,DWORD(std::size(executable)));
        if(!size || size>=std::size(executable)) throw std::runtime_error("Cannot resolve probe directory");
        const auto directory=fs::path(executable).parent_path();
        std::ifstream rpcFile(directory/L"rpc-path.txt");std::string rpcLine;std::getline(rpcFile,rpcLine);
        if(!rpcLine.empty() && rpcLine.back()=='\r') rpcLine.pop_back();
        if(rpcLine.empty()) throw std::runtime_error("Missing RPC path");
        const auto rpc=fs::u8path(rpcLine).wstring();
        Vulkan vk;vk.initialize(report);
        Module module;module.load(directory/L"cemu_npu.dll",LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
        CemuNpuApi api{sizeof(CemuNpuApi)};
        const auto getApi=reinterpret_cast<CemuNpuGetApi>(GetProcAddress(module.handle,"cemu_npu_get_api"));
        if(!getApi || getApi(CEMU_NPU_ABI,&api)) throw std::runtime_error("Module ABI mismatch");
        CemuNpu* context{};
        struct Cleanup {CemuNpuApi& api;CemuNpu*& context;~Cleanup(){if(context) api.destroy(context);}} cleanup{api,context};
        const auto path=directory.wstring();
        CemuNpuCreateInfo info{sizeof(info),CEMU_NPU_ABI,vk.instance,vk.physical,vk.device,vk.queue,vk.family,vk.getInstanceProc,path.c_str(),rpc.c_str(),height};
        char error[2048]{};
        const auto start=Clock::now();
        if(api.create(&info,&context,error,sizeof(error))) throw std::runtime_error(error);
        report.number("startup_ms",elapsed(start));
        CemuNpuStats stats{};api.stats(context,&stats);
        if(stats.npuRuns || stats.submitted) throw std::runtime_error("Startup dispatched inference while OFF");
        report.boolean("startup_off_zero_runs",true);
        const auto clear=reinterpret_cast<PFN_vkCmdClearColorImage>(vk.vkGetDeviceProcAddr(vk.device,"vkCmdClearColorImage"));
        if(!clear) throw std::runtime_error("Clear function missing");
        auto frame=[&](uint64_t id) {
            const auto image=api.captureImage(context,id);
            if(!image) throw std::runtime_error("Capture image missing");
            vk.begin();
            vk.barrier(VK_ACCESS_MEMORY_READ_BIT|VK_ACCESS_MEMORY_WRITE_BIT,VK_ACCESS_TRANSFER_WRITE_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT);
            const VkClearColorValue color{{0.25f,0.5f,0.75f,1.0f}};
            const VkImageSubresourceRange range{VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1};
            clear(vk.command,image,VK_IMAGE_LAYOUT_GENERAL,&color,1,&range);
            vk.barrier(VK_ACCESS_TRANSFER_WRITE_BIT,VK_ACCESS_MEMORY_READ_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT);
            vk.submitAndWait();
            CemuNpuFrame output{};
            if(api.process(context,id,&output,error,sizeof(error))) throw std::runtime_error(error);
            if(!output.realImage) throw std::runtime_error("Real image missing");
            return output;
        };
        frame(1);api.stats(context,&stats);
        if(stats.npuRuns || stats.submitted) throw std::runtime_error("First capture should only warm history");
        frame(2);
        const auto deadline=Clock::now()+std::chrono::seconds(3);
        do {api.stats(context,&stats);if(stats.npuRuns)break;std::this_thread::sleep_for(std::chrono::milliseconds(5));} while(Clock::now()<deadline);
        // Poll completion to surface any worker exception before deciding status.
        const auto third=frame(3);api.stats(context,&stats);
        report.number("observed_npu_runs",stats.npuRuns);
        report.number("completed_jobs",stats.completed);
        report.boolean("generated_image_ready",third.generatedImage!=VK_NULL_HANDLE);
        if(!stats.npuRuns || !stats.completed) throw std::runtime_error("No completed NPU inference observed");
        api.destroy(context);context=nullptr;
        report.str("status","MODULE_STARTUP_AND_NPU_RUN_VERIFIED");
        report.boolean("cemu_executed",false);
        report.boolean("game_quality_validated",false);
        report.boolean("scaled_1440p_presentation_validated",false);
        report.save(argv[3]);std::cout<<"MODULE_STARTUP_AND_NPU_RUN_VERIFIED\n";return 0;
    } catch(const std::exception& e) {
        report.str("status","MODULE_SMOKE_FAILED");report.str("error",e.what());report.save(argv[3]);
        std::cerr<<e.what()<<'\n';return 1;
    }
}
