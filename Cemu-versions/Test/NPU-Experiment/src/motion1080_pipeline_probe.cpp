#include "motion1080_vulkan_support.h"
#include "anvil_async_worker.h"
#include <memory>
#include <cmath>

constexpr uint32_t width = 1920, height = 1080;
constexpr size_t pixels = size_t(width) * height;
constexpr size_t inputBytes = pixels * 6, outputBytes = pixels * 3, rgbaBytes = pixels * 4;
constexpr size_t flowBytes = 120 * 68 * 16;
constexpr size_t diagnosticBytes = inputBytes + outputBytes + rgbaBytes * 2 + flowBytes * 2;
constexpr double residualScale = 0.00330072408542037;
uint8_t expectedInput(size_t pixel, unsigned channel, unsigned phase) {
    return uint8_t(((size_t(channel) * pixels + pixel) * 7 + 11 + phase * 31) % 251);
}
void saveBytes(const fs::path& path, const void* pointer, size_t bytes) {
    std::ofstream file(path, std::ios::binary);
    file.write(static_cast<const char*>(pointer), bytes);
    if (!file) throw std::runtime_error("Could not save evidence bytes");
}

struct GpuImage {
    Vulkan& vk;
    VkImage image{};
    VkImageView view{};
    VkDeviceMemory memory{};
    explicit GpuImage(Vulkan& v) : vk(v) {}
    GpuImage(const GpuImage&) = delete;
    void create(uint32_t imageWidth = width, uint32_t imageHeight = height) {
        VkFormatProperties properties{};
        vk.vkGetPhysicalDeviceFormatProperties(vk.physical, VK_FORMAT_R8G8B8A8_UNORM, &properties);
        constexpr auto required = VK_FORMAT_FEATURE_STORAGE_IMAGE_BIT | VK_FORMAT_FEATURE_TRANSFER_SRC_BIT;
        if ((properties.optimalTilingFeatures & required) != required) throw Unsupported("RGBA8 storage image/transfer source unavailable");
        VkImageCreateInfo info{VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO};
        info.imageType = VK_IMAGE_TYPE_2D; info.format = VK_FORMAT_R8G8B8A8_UNORM;
        info.extent = {imageWidth, imageHeight, 1}; info.mipLevels = 1; info.arrayLayers = 1;
        info.samples = VK_SAMPLE_COUNT_1_BIT; info.tiling = VK_IMAGE_TILING_OPTIMAL;
        info.usage = VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT;
        info.sharingMode = VK_SHARING_MODE_EXCLUSIVE; info.initialLayout = VK_IMAGE_LAYOUT_UNDEFINED;
        check(vk.vkCreateImage(vk.device, &info, nullptr, &image), "vkCreateImage");
        VkMemoryRequirements requirements{}; vk.vkGetImageMemoryRequirements(vk.device, image, &requirements);
        uint32_t type = UINT32_MAX;
        for (uint32_t i = 0; i < vk.memoryProperties.memoryTypeCount; ++i)
            if ((requirements.memoryTypeBits & (1u << i)) && (vk.memoryProperties.memoryTypes[i].propertyFlags & VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT)) { type = i; break; }
        if (type == UINT32_MAX) throw Unsupported("No local memory for image");
        VkMemoryDedicatedAllocateInfo dedicated{VK_STRUCTURE_TYPE_MEMORY_DEDICATED_ALLOCATE_INFO}; dedicated.image = image;
        VkMemoryAllocateInfo allocation{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};
        allocation.allocationSize = requirements.size; allocation.memoryTypeIndex = type; allocation.pNext = &dedicated;
        check(vk.vkAllocateMemory(vk.device, &allocation, nullptr, &memory), "image allocation");
        check(vk.vkBindImageMemory(vk.device, image, memory, 0), "vkBindImageMemory");
        VkImageViewCreateInfo vi{VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO};
        vi.image = image; vi.viewType = VK_IMAGE_VIEW_TYPE_2D; vi.format = info.format;
        vi.subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1};
        check(vk.vkCreateImageView(vk.device, &vi, nullptr, &view), "vkCreateImageView");
    }
    ~GpuImage() {
        if (view) vk.vkDestroyImageView(vk.device, view, nullptr);
        if (image) vk.vkDestroyImage(vk.device, image, nullptr);
        if (memory) vk.vkFreeMemory(vk.device, memory, nullptr);
    }
};

struct Compute {
    Vulkan& vk;
    VkDescriptorSetLayout setLayout{};
    VkDescriptorPool pool{};
    VkDescriptorSet set{};
    VkPipelineLayout layout{};
    std::array<VkShaderModule, 5> modules{};
    std::array<VkPipeline, 5> pipelines{};
    VkQueryPool queries{};
    explicit Compute(Vulkan& v) : vk(v) {}
    void create(Buffer& input, Buffer& output, GpuImage& a, GpuImage& b, GpuImage& composed, Buffer& forward, Buffer& backward, GpuImage& quarterA, GpuImage& quarterB, GpuImage& warpedA, GpuImage& warpedB, const fs::path& shaderDirectory) {
        std::array<VkDescriptorSetLayoutBinding, 11> bindings{};
        for (uint32_t i = 0; i < bindings.size(); ++i) {
            bindings[i].binding = i; bindings[i].descriptorCount = 1; bindings[i].stageFlags = VK_SHADER_STAGE_COMPUTE_BIT;
            bindings[i].descriptorType = (i == 2 || i == 3 || i == 5 || i == 6) ? VK_DESCRIPTOR_TYPE_STORAGE_BUFFER : VK_DESCRIPTOR_TYPE_STORAGE_IMAGE;
        }
        VkDescriptorSetLayoutCreateInfo si{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO};
        si.bindingCount = uint32_t(bindings.size()); si.pBindings = bindings.data();
        check(vk.vkCreateDescriptorSetLayout(vk.device, &si, nullptr, &setLayout), "vkCreateDescriptorSetLayout");
        const std::array<VkDescriptorPoolSize, 2> sizes{{{VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, 7}, {VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 4}}};
        VkDescriptorPoolCreateInfo pi{VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO};
        pi.maxSets = 1; pi.poolSizeCount = uint32_t(sizes.size()); pi.pPoolSizes = sizes.data();
        check(vk.vkCreateDescriptorPool(vk.device, &pi, nullptr, &pool), "vkCreateDescriptorPool");
        VkDescriptorSetAllocateInfo ai{VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO}; ai.descriptorPool = pool; ai.descriptorSetCount = 1; ai.pSetLayouts = &setLayout;
        check(vk.vkAllocateDescriptorSets(vk.device, &ai, &set), "vkAllocateDescriptorSets");
        std::array<VkDescriptorImageInfo, 11> images{};
        std::array<VkDescriptorBufferInfo, 11> buffers{};
        const std::array<std::pair<unsigned,GpuImage*>,7> imageBindings{{{0,&a},{1,&b},{4,&composed},{7,&quarterA},{8,&quarterB},{9,&warpedA},{10,&warpedB}}};
        for(auto [binding,image]:imageBindings) images[binding]={VK_NULL_HANDLE,image->view,VK_IMAGE_LAYOUT_GENERAL};
        buffers[2]={input.buffer,0,inputBytes}; buffers[3]={output.buffer,0,outputBytes};
        buffers[5]={forward.buffer,0,flowBytes}; buffers[6]={backward.buffer,0,flowBytes};
        std::array<VkWriteDescriptorSet, 11> writes{};
        for (uint32_t i = 0; i < writes.size(); ++i) {
            writes[i].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET; writes[i].dstSet = set; writes[i].dstBinding = i;
            writes[i].descriptorCount = 1; writes[i].descriptorType = bindings[i].descriptorType;
            if (i==2 || i==3 || i==5 || i==6) writes[i].pBufferInfo=&buffers[i];
            else writes[i].pImageInfo=&images[i];
        }
        vk.vkUpdateDescriptorSets(vk.device, uint32_t(writes.size()), writes.data(), 0, nullptr);
        VkPushConstantRange push{VK_SHADER_STAGE_COMPUTE_BIT, 0, 4};
        VkPipelineLayoutCreateInfo li{VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};
        li.setLayoutCount = 1; li.pSetLayouts = &setLayout; li.pushConstantRangeCount = 1; li.pPushConstantRanges = &push;
        check(vk.vkCreatePipelineLayout(vk.device, &li, nullptr, &layout), "vkCreatePipelineLayout");
        const std::array<const wchar_t*, 5> shaderNames{L"motion1080-generate.spv", L"motion1080-pack.spv", L"motion1080-compose.spv", L"motion1080-downsample.spv", L"motion1080-flow.spv"};
        for (size_t i = 0; i < modules.size(); ++i) {
            const auto file = shaderDirectory / shaderNames[i];
            const auto bytes = fs::file_size(file);
            if (!bytes || bytes % 4 || bytes > 1024 * 1024) throw std::runtime_error("Invalid SPIR-V file size");
            std::vector<uint32_t> words(size_t(bytes / 4));
            std::ifstream stream(file, std::ios::binary); stream.read(reinterpret_cast<char*>(words.data()), bytes);
            if (!stream || words[0] != 0x07230203) throw std::runtime_error("Invalid SPIR-V header");
            VkShaderModuleCreateInfo mi{VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO}; mi.codeSize = size_t(bytes); mi.pCode = words.data();
            check(vk.vkCreateShaderModule(vk.device, &mi, nullptr, &modules[i]), "vkCreateShaderModule");
            VkComputePipelineCreateInfo ci{VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO}; ci.layout = layout;
            ci.stage.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO; ci.stage.stage = VK_SHADER_STAGE_COMPUTE_BIT;
            ci.stage.module = modules[i]; ci.stage.pName = "main";
            check(vk.vkCreateComputePipelines(vk.device, VK_NULL_HANDLE, 1, &ci, nullptr, &pipelines[i]), "vkCreateComputePipelines");
        }
        VkQueryPoolCreateInfo qi{VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO}; qi.queryType = VK_QUERY_TYPE_TIMESTAMP; qi.queryCount = 12;
        check(vk.vkCreateQueryPool(vk.device, &qi, nullptr, &queries), "vkCreateQueryPool");
        vk.begin();
        std::array<VkImageMemoryBarrier, 7> barriers{};
        const std::array<VkImage, 7> handles{a.image, b.image, composed.image, quarterA.image, quarterB.image, warpedA.image, warpedB.image};
        for (size_t i = 0; i < handles.size(); ++i) {
            auto& barrier = barriers[i]; barrier.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
            barrier.dstAccessMask = VK_ACCESS_SHADER_READ_BIT | VK_ACCESS_SHADER_WRITE_BIT;
            barrier.oldLayout = VK_IMAGE_LAYOUT_UNDEFINED; barrier.newLayout = VK_IMAGE_LAYOUT_GENERAL;
            barrier.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED; barrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
            barrier.image = handles[i]; barrier.subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1};
        }
        vk.vkCmdPipelineBarrier(vk.command, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, 0, 0, nullptr, 0, nullptr, uint32_t(barriers.size()), barriers.data());
        vk.submitAndWait();
    }
    void dispatch(unsigned pipeline, unsigned phase) {
        vk.vkCmdBindPipeline(vk.command, VK_PIPELINE_BIND_POINT_COMPUTE, pipelines[pipeline]);
        vk.vkCmdBindDescriptorSets(vk.command, VK_PIPELINE_BIND_POINT_COMPUTE, layout, 0, 1, &set, 0, nullptr);
        vk.vkCmdPushConstants(vk.command, layout, VK_SHADER_STAGE_COMPUTE_BIT, 0, 4, &phase);
        if (pipeline == 1) vk.vkCmdDispatch(vk.command, uint32_t((pixels / 2 + 255) / 256), 1, 1);
        else if (pipeline == 2) vk.vkCmdDispatch(vk.command, uint32_t((pixels / 4 + 255) / 256), 1, 1);
        else if (pipeline == 3) vk.vkCmdDispatch(vk.command, 30, 17, 1);
        else if (pipeline == 4) vk.vkCmdDispatch(vk.command, 15, 9, 2);
        else vk.vkCmdDispatch(vk.command, (width + 15) / 16, (height + 15) / 16, 1);
    }
    void stamp(unsigned index, bool end) { vk.vkCmdWriteTimestamp(vk.command, end ? VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT : VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, queries, index); }
    std::array<double, 6> times() {
        std::array<uint64_t, 12> ticks{};
        check(vk.vkGetQueryPoolResults(vk.device, queries, 0, 12, sizeof(ticks), ticks.data(), sizeof(uint64_t), VK_QUERY_RESULT_64_BIT | VK_QUERY_RESULT_WAIT_BIT), "vkGetQueryPoolResults");
        const uint64_t mask = vk.timestampBits == 64 ? UINT64_MAX : ((uint64_t(1) << vk.timestampBits) - 1);
        std::array<double, 6> values{};
        for (size_t i = 0; i < 6; ++i) values[i] = double((ticks[2 * i + 1] - ticks[2 * i]) & mask) * vk.timestampPeriod / 1000000.0;
        return values;
    }
    ~Compute() {
        if (queries) vk.vkDestroyQueryPool(vk.device, queries, nullptr);
        for (auto pipeline : pipelines) if (pipeline) vk.vkDestroyPipeline(vk.device, pipeline, nullptr);
        for (auto module : modules) if (module) vk.vkDestroyShaderModule(vk.device, module, nullptr);
        if (layout) vk.vkDestroyPipelineLayout(vk.device, layout, nullptr);
        if (pool) vk.vkDestroyDescriptorPool(vk.device, pool, nullptr);
        if (setLayout) vk.vkDestroyDescriptorSetLayout(vk.device, setLayout, nullptr);
    }
};

double readback(Vulkan& vk, Buffer& input, Buffer& output, GpuImage& composed, Buffer& diagnostic, GpuImage& warpedA, Buffer& forward, Buffer& backward) {
    const auto start = Clock::now(); vk.begin();
    vk.barrier(VK_ACCESS_HOST_WRITE_BIT | VK_ACCESS_SHADER_WRITE_BIT, VK_ACCESS_TRANSFER_READ_BIT, VK_PIPELINE_STAGE_HOST_BIT | VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT);
    const VkBufferCopy ci{0, 0, inputBytes}, co{0, inputBytes, outputBytes};
    vk.vkCmdCopyBuffer(vk.command, input.buffer, diagnostic.buffer, 1, &ci);
    vk.vkCmdCopyBuffer(vk.command, output.buffer, diagnostic.buffer, 1, &co);
    VkBufferImageCopy imageCopy{}; imageCopy.bufferOffset = inputBytes + outputBytes;
    imageCopy.imageSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1}; imageCopy.imageExtent = {width, height, 1};
    vk.vkCmdCopyImageToBuffer(vk.command, composed.image, VK_IMAGE_LAYOUT_GENERAL, diagnostic.buffer, 1, &imageCopy);
    imageCopy.bufferOffset += rgbaBytes;
    vk.vkCmdCopyImageToBuffer(vk.command, warpedA.image, VK_IMAGE_LAYOUT_GENERAL, diagnostic.buffer, 1, &imageCopy);
    const VkBufferCopy cf{0,inputBytes+outputBytes+rgbaBytes*2,flowBytes}, cb{0,inputBytes+outputBytes+rgbaBytes*2+flowBytes,flowBytes};
    vk.vkCmdCopyBuffer(vk.command,forward.buffer,diagnostic.buffer,1,&cf);
    vk.vkCmdCopyBuffer(vk.command,backward.buffer,diagnostic.buffer,1,&cb);
    vk.barrier(VK_ACCESS_TRANSFER_WRITE_BIT, VK_ACCESS_HOST_READ_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_HOST_BIT);
    vk.submitAndWait(); return elapsed(start);
}

// Native consumption oracle. Full motion/input oracle is in the independent CPU reader.
void validateReadback(const uint8_t* bytes, unsigned phase, Report& report) {
    unsigned maximum{}; const auto* warped=bytes+inputBytes+outputBytes+rgbaBytes;
    for(size_t p=0;p<pixels;++p) {
        const auto mask=warped[p*4+3]; if(mask!=0 && mask!=255) throw std::runtime_error("Invalid confidence mask");
        for(unsigned c=0;c<3;++c) {
            if(warped[p*4+c]!=bytes[p*6+c]) throw std::runtime_error("Warped image and tensor disagree");
            const double mean=(double(bytes[p*6+c])+bytes[p*6+c+3])/2.0;
            const double residual=mask?(int(bytes[inputBytes+p*3+c])-128)*residualScale*255.0:0.0;
            const int expected=int(std::lround(std::clamp(mean+residual,0.0,255.0)));
            const unsigned error=unsigned(std::abs(int(bytes[inputBytes+outputBytes+p*4+c])-expected));
            maximum=std::max(maximum,error); if(error>1) throw std::runtime_error("Motion compose mismatch");
        }
        if(bytes[inputBytes+outputBytes+p*4+3]!=255) throw std::runtime_error("Composed alpha mismatch");
    }
    report.number("last_phase",phase); report.number("last_compose_max_error",maximum);
}

int wmain(int argc, wchar_t** argv) {
    Report report;
    fs::path directory, model, rpcPath, shaderDirectory;
    std::string mode;
    bool evidenceCreated = false;
    try {
        bool run = false;
        for (int i = 1; i < argc; ++i) {
            const std::wstring key = argv[i];
            if (key == L"--run-devices") run = true;
            else if (i + 1 < argc && (key == L"--out" || key == L"--model" || key == L"--rpc-library" || key == L"--shaders" || key == L"--mode")) {
                const fs::path value = argv[++i];
                if (key == L"--out") directory = value; else if (key == L"--model") model = value;
                else if (key == L"--rpc-library") rpcPath = value; else if (key == L"--shaders") shaderDirectory = value;
                else mode = utf8(value.wstring());
            } else throw std::runtime_error("Unknown or incomplete argument; no device started");
        }
        if (!run || directory.empty() || !fs::is_regular_file(model) || !fs::is_directory(shaderDirectory) || (mode != "Verify" && mode != "Measure") ||
            !rpcPath.is_absolute() || rpcPath.filename() != L"libcdsprpc.dll" || !fs::is_regular_file(rpcPath))
            throw std::runtime_error("Explicit --run-devices --model --out NEW_DIR --rpc-library ABSOLUTE --shaders --mode Verify|Measure required; no device started");
        if (!fs::create_directory(directory)) throw std::runtime_error("Evidence directory exists or cannot be created");
        evidenceCreated = true;
        const bool verify = mode == "Verify";
        report.str("status", "STARTED"); report.str("stage", "vulkan_capabilities"); report.str("mode", mode);
        report.str("model", utf8(model.wstring())); report.str("rpc_library", utf8(rpcPath.wstring()));
        report.boolean("cemu_executed", false); report.boolean("full_framegen_validated", false);
        report.number("completed_rounds", 0); report.boolean("application_cpu_writes_to_shared_payload", false);
        report.str("invocation", "direct_preallocated_run"); report.save(directory / L"result.json");
        Vulkan vk; vk.initialize(report);
        Module rpc; rpc.load(rpcPath, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
        wchar_t loaded[32768]{}; const auto length = GetModuleFileNameW(rpc.handle, loaded, DWORD(std::size(loaded)));
        if (!length || length >= std::size(loaded) || !fs::equivalent(rpcPath, loaded)) throw std::runtime_error("Wrong RPC DLL selected");
        Ort::Env env(verify ? ORT_LOGGING_LEVEL_VERBOSE : ORT_LOGGING_LEVEL_INFO, "motion1080-pipeline-probe");
        Ort::SessionOptions options; options.SetIntraOpNumThreads(1); options.SetInterOpNumThreads(1);
        options.SetLogSeverityLevel(verify ? 0 : 1);
        if (verify) Ort::ThrowOnError(Ort::GetApi().SetSessionLogVerbosityLevel(options, 1));
        options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
        options.AddConfigEntry("session.disable_cpu_ep_fallback", "1");
        const auto prefix = directory / L"ort-profile"; options.EnableProfiling(prefix.c_str());
        options.AppendExecutionProvider("QNN", {{"backend_path", "QnnHtp.dll"}, {"offload_graph_io_quantization", "0"}, {"enable_htp_fp16_precision", "1"},
            {"htp_performance_mode", "balanced"}, {"profiling_level", "off"}, {"enable_htp_shared_memory_allocator", "1"}});
        report.str("stage", "qnn_session"); report.save(directory / L"result.json");
        const auto sessionStart = Clock::now(); Ort::Session session(env, model.c_str(), options);
        report.number("session_create_ms", elapsed(sessionStart));
        report.str("backend", "QnnHtp.dll"); report.boolean("cpu_fallback_disabled", true); report.boolean("ort_profiling_enabled", true);
        report.str("qnn_profiling_level", "off"); report.str("performance_mode", "balanced"); report.str("ort_version", OrtGetApiBase()->GetVersionString());
        report.boolean("verbose_logging", verify); report.raw("input_shape", "[1,1080,1920,6]"); report.raw("output_shape", "[1,1080,1920,3]");
        report.str("dtype", "uint8"); report.number("input_bytes", inputBytes); report.number("output_bytes", outputBytes);
        if (session.GetInputCount() != 1 || session.GetOutputCount() != 1) throw std::runtime_error("Unexpected I/O count");
        const std::array<int64_t, 4> inputShape{1, 1080, 1920, 6}, outputShape{1, 1080, 1920, 3};
        for (int i = 0; i < 2; ++i) {
            auto type = i ? session.GetOutputTypeInfo(0) : session.GetInputTypeInfo(0); auto tensor = type.GetTensorTypeAndShapeInfo();
            const auto& expected = i ? outputShape : inputShape;
            if (tensor.GetElementType() != ONNX_TENSOR_ELEMENT_DATA_TYPE_UINT8 || tensor.GetShape() != std::vector<int64_t>(expected.begin(), expected.end()))
                throw std::runtime_error("Expected pinned 1080p UINT8 NHWC ANVIL model");
        }
        Ort::MemoryInfo sharedInfo("QnnHtpShared", OrtDeviceAllocator, 0, OrtMemTypeDefault);
        Ort::Allocator allocator(session, sharedInfo);
        if (allocator.GetInfo().GetAllocatorName() != "QnnHtpShared") throw std::runtime_error("Wrong shared allocator");
        report.str("stage", "import_and_pipelines"); report.save(directory / L"result.json");
        Buffer input(vk), output(vk), diagnostic(vk), forward(vk), backward(vk);
        input.create(inputBytes, &allocator); output.create(outputBytes, &allocator); diagnostic.create(diagnosticBytes, nullptr);
        forward.create(flowBytes,nullptr,VK_BUFFER_USAGE_STORAGE_BUFFER_BIT|VK_BUFFER_USAGE_TRANSFER_SRC_BIT); backward.create(flowBytes,nullptr,VK_BUFFER_USAGE_STORAGE_BUFFER_BIT|VK_BUFFER_USAGE_TRANSFER_SRC_BIT);
        report.number("input_import_bytes", input.allocationSize); report.number("output_import_bytes", output.allocationSize);
        report.number("input_aligned_offset", input.offset); report.number("output_aligned_offset", output.offset);
        report.number("input_memory_flags", vk.memoryProperties.memoryTypes[input.memoryType].propertyFlags);
        report.number("output_memory_flags", vk.memoryProperties.memoryTypes[output.memoryType].propertyFlags);
        GpuImage a(vk), b(vk), composed(vk), quarterA(vk), quarterB(vk), warpedA(vk), warpedB(vk); a.create(); b.create(); composed.create(); quarterA.create(480,270); quarterB.create(480,270); warpedA.create(); warpedB.create();
        Compute compute(vk); compute.create(input, output, a, b, composed, forward, backward, quarterA, quarterB, warpedA, warpedB, shaderDirectory);
        auto inputTensor = Ort::Value::CreateTensor<uint8_t>(allocator.GetInfo(), static_cast<uint8_t*>(input.pointer), inputBytes, inputShape.data(), inputShape.size());
        auto outputTensor = Ort::Value::CreateTensor<uint8_t>(allocator.GetInfo(), static_cast<uint8_t*>(output.pointer), outputBytes, outputShape.data(), outputShape.size());
        report.str("input_allocator", inputTensor.GetTensorMemoryInfo().GetAllocatorName()); report.str("output_allocator", outputTensor.GetTensorMemoryInfo().GetAllocatorName());
        Ort::AllocatorWithDefaultOptions names;
        auto inputName = session.GetInputNameAllocated(0, names), outputName = session.GetOutputNameAllocated(0, names);
        const std::array<const char*, 1> inputNames{inputName.get()}, outputNames{outputName.get()};
        cemu::npu::AsyncWorker worker(3);
        const unsigned count = verify ? 4 : 34;
        report.number("first_runs", verify ? 0 : 1); report.number("warmup_runs", verify ? 0 : 3); report.number("measured_runs", verify ? 0 : 30);
        std::ostringstream samples; samples << std::setprecision(12) << '[';
        for (unsigned round = 0; round < count; ++round) {
            const unsigned phase = round % 4;
            report.str("stage", "gpu_npu_gpu_round_" + std::to_string(round)); report.save(directory / L"result.json");
            const auto totalStart = Clock::now(); const auto prepareStart = Clock::now();
            vk.begin(); vk.vkCmdResetQueryPool(vk.command, compute.queries, 0, 12);
            vk.barrier(VK_ACCESS_MEMORY_READ_BIT | VK_ACCESS_MEMORY_WRITE_BIT | VK_ACCESS_HOST_READ_BIT | VK_ACCESS_HOST_WRITE_BIT,
                VK_ACCESS_SHADER_WRITE_BIT | VK_ACCESS_TRANSFER_WRITE_BIT, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT | VK_PIPELINE_STAGE_HOST_BIT,
                VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT | VK_PIPELINE_STAGE_TRANSFER_BIT);
            vk.vkCmdFillBuffer(vk.command, output.buffer, 0, outputBytes, 0xfdfdfdfd);
            // Isolate timestamp spans in this deliberately serialized baseline.
            // The poison operation stays in wall time, outside the image-generation span.
            vk.barrier(VK_ACCESS_TRANSFER_WRITE_BIT, VK_ACCESS_SHADER_WRITE_BIT,
                VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT);
            compute.stamp(0, false); compute.dispatch(0, phase); compute.stamp(1, true);
            vk.barrier(VK_ACCESS_SHADER_WRITE_BIT, VK_ACCESS_SHADER_READ_BIT,
                VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT);
            compute.stamp(2, false); compute.dispatch(3, phase); compute.stamp(3, true);
            vk.barrier(VK_ACCESS_SHADER_WRITE_BIT,VK_ACCESS_SHADER_READ_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT);
            compute.stamp(4,false); compute.dispatch(4,phase); compute.stamp(5,true);
            vk.barrier(VK_ACCESS_SHADER_WRITE_BIT,VK_ACCESS_SHADER_READ_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT);
            compute.stamp(6,false); compute.dispatch(1,phase); compute.stamp(7,true);
            vk.barrier(VK_ACCESS_SHADER_WRITE_BIT | VK_ACCESS_TRANSFER_WRITE_BIT, VK_ACCESS_HOST_READ_BIT | VK_ACCESS_HOST_WRITE_BIT,
                VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT | VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_HOST_BIT);
            const auto pre = vk.submitAndWait(); const double prepareMs = elapsed(prepareStart);
            struct InferenceTiming { Clock::time_point start{},end{}; };
            // Own per-job timing even if a GPU error unwinds this loop before Run ends.
            const auto inference=std::make_shared<InferenceTiming>();
            cemu::npu::FramePair ticket{worker.epoch(),round,round+1,0,width,height,Clock::now()+std::chrono::seconds(5)};
            const auto enqueueStart=Clock::now();
            auto execute=[&,inference](const cemu::npu::AsyncWorker::StillCurrent& current) {
                // Producer fence is complete in this standalone harness. In Cemu the
                // callback must retire the slot's input fence before this check.
                if(!current()) return false;
                inference->start=Clock::now();
                session.Run(Ort::RunOptions{nullptr},inputNames.data(),&inputTensor,1,outputNames.data(),&outputTensor,1);
                inference->end=Clock::now(); return true;
            };
            while(!worker.submit(ticket,execute)) {
                if(elapsed(enqueueStart)>10) throw std::runtime_error("Worker submission unexpectedly unavailable");
                std::this_thread::yield();
            }
            const double enqueueMs=elapsed(enqueueStart);
            // Independent producer work touches only source images; all in-flight
            // NPU tensors and warped images remain unchanged until consumption ends.
            const auto producerStart=Clock::now(); vk.begin();
            vk.barrier(VK_ACCESS_MEMORY_READ_BIT|VK_ACCESS_MEMORY_WRITE_BIT,VK_ACCESS_SHADER_WRITE_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT);
            compute.stamp(10,false); compute.dispatch(0,(phase+1)%4); compute.stamp(11,true); vk.submitAndWait();
            const auto producerEnd=Clock::now(); const auto pollStart=Clock::now();
            std::optional<cemu::npu::Completion> completion;
            while(!(completion=worker.take())) std::this_thread::sleep_for(std::chrono::milliseconds(1));
            const double harnessPollMs=elapsed(pollStart);
            if(completion->error) std::rethrow_exception(completion->error);
            if(completion->stale || !completion->executed) throw std::runtime_error("Worker result expired or was invalidated");
            const double npuMs=std::chrono::duration<double,std::milli>(inference->end-inference->start).count();
            const double overlapMs=std::max(0.0,std::chrono::duration<double,std::milli>(std::min(producerEnd,inference->end)-std::max(producerStart,inference->start)).count());
            if (inputTensor.GetTensorRawData() != input.pointer || outputTensor.GetTensorRawData() != output.pointer) throw std::runtime_error("Run replaced shared tensor pointer");
            const auto composeStart = Clock::now(); vk.begin();
            vk.barrier(VK_ACCESS_HOST_WRITE_BIT, VK_ACCESS_SHADER_READ_BIT, VK_PIPELINE_STAGE_HOST_BIT, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT);
            compute.stamp(8, false); compute.dispatch(2, phase); compute.stamp(9, true);
            const auto post = vk.submitAndWait(); const double composeMs = elapsed(composeStart), totalMs = elapsed(totalStart);
            const auto gpu = compute.times();
            if (round) samples << ',';
            samples << "{\"round\":" << round << ",\"phase\":" << phase << ",\"measured\":" << (!verify && round >= 4 ? "true" : "false")
                << ",\"synthetic_gpu_ms\":" << gpu[0] << ",\"pack_gpu_ms\":" << gpu[3] << ",\"compose_gpu_ms\":" << gpu[4]
                << ",\"prepare_wall_ms\":" << prepareMs << ",\"npu_wall_ms\":" << npuMs << ",\"compose_wall_ms\":" << composeMs
                << ",\"serial_wall_ms\":" << totalMs << ",\"pre_submit_ms\":" << pre.submitMs << ",\"pre_fence_ms\":" << pre.waitMs
                << ",\"post_submit_ms\":" << post.submitMs << ",\"post_fence_ms\":" << post.waitMs
                << ",\"downsample_gpu_ms\":" << gpu[1] << ",\"motion_gpu_ms\":" << gpu[2] << ",\"lookahead_gpu_ms\":" << gpu[5]
                << ",\"worker_submit_wall_ms\":" << enqueueMs << ",\"producer_overlap_ms\":" << overlapMs << ",\"harness_completion_poll_ms\":" << harnessPollMs << '}';
            if (verify || round + 1 == count) {
                const double readbackMs = readback(vk, input, output, composed, diagnostic, warpedA, forward, backward);
                report.number("last_diagnostic_readback_ms", readbackMs);
                const auto* bytes = static_cast<const uint8_t*>(diagnostic.mapped);
                const auto suffix = verify ? std::to_wstring(phase) : L"final";
                saveBytes(directory / (L"diagnostic-" + suffix + L".bin"), bytes, diagnosticBytes);
                validateReadback(bytes, phase, report);
                if (verify) {
                    std::vector<uint8_t> referenceInput(inputBytes), referenceOutput(outputBytes);
                    std::copy(bytes,bytes+inputBytes,referenceInput.begin()); // CPU reader independently verifies this aligned input before accepting the run.
                    auto hostMemory = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
                    auto hostInput = Ort::Value::CreateTensor<uint8_t>(hostMemory, referenceInput.data(), inputBytes, inputShape.data(), inputShape.size());
                    auto hostOutput = Ort::Value::CreateTensor<uint8_t>(hostMemory, referenceOutput.data(), outputBytes, outputShape.data(), outputShape.size());
                    session.Run(Ort::RunOptions{nullptr}, inputNames.data(), &hostInput, 1, outputNames.data(), &hostOutput, 1);
                    saveBytes(directory / (L"reference-" + suffix + L".bin"), referenceOutput.data(), outputBytes);
                    if (!std::equal(referenceOutput.begin(), referenceOutput.end(), bytes + inputBytes)) throw std::runtime_error("Shared GPU path differs from ordinary-memory QNN reference");
                }
            }
            report.number("completed_rounds", round + 1);
        }
        samples << ']'; report.raw("samples", samples.str());
        auto profile = session.EndProfilingAllocated(names); report.str("ort_profile", profile.get());
        report.boolean("async_worker",true); report.boolean("motion_alignment",true); report.number("phase_cycle",4); report.boolean("gpu_texture_input_and_compose", true); report.boolean("diagnostic_readback_outside_timing", true);
        report.boolean("application_copy_free_gpu_npu_handoff", true);
        report.str("timing_scope", "Standalone synthetic image generation, quarter-resolution bidirectional block matching, midpoint warp/NHWC pack, worker-thread QNN Run and GPU residual compose. Independent next-image generation overlaps the host NPU call. Includes benchmark completion polling and serialized GPU fences. Excludes real Cemu rendering, present, game quality and sustained contention. Host-call overlap is not proof of simultaneous device execution.");
        report.str("status", "MOTION1080_COMPLETED_VERIFICATION_PENDING"); report.str("stage", "completed"); report.save(directory / L"result.json");
        return 0;
    } catch (const Unsupported& e) {
        report.str("status", "UNSUPPORTED"); report.str("reason", e.what());
        if (evidenceCreated) report.save(directory / L"result.json"); std::cerr << "UNSUPPORTED: " << e.what() << std::endl; return 2;
    } catch (const std::exception& e) {
        report.str("status", "FAILED"); report.str("reason", e.what());
        if (evidenceCreated) report.save(directory / L"result.json"); std::cerr << "FAILED: " << e.what() << std::endl; return 1;
    }
}
