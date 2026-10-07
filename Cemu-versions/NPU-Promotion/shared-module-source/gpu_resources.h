struct GpuImage {
    Vulkan& vk;
    VkImage image{};
    VkImageView view{};
    VkDeviceMemory memory{};
    explicit GpuImage(Vulkan& v) : vk(v) {}
    GpuImage(const GpuImage&) = delete;
    void create(uint32_t imageWidth, uint32_t imageHeight) {
        VkFormatProperties properties{};
        vk.vkGetPhysicalDeviceFormatProperties(vk.physical, VK_FORMAT_R8G8B8A8_UNORM, &properties);
        constexpr auto required = VK_FORMAT_FEATURE_STORAGE_IMAGE_BIT | VK_FORMAT_FEATURE_TRANSFER_SRC_BIT;
        if ((properties.optimalTilingFeatures & required) != required) throw Unsupported("RGBA8 storage image/transfer source unavailable");
        VkImageCreateInfo info{VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO};
        info.imageType = VK_IMAGE_TYPE_2D; info.format = VK_FORMAT_R8G8B8A8_UNORM;
        info.extent = {imageWidth, imageHeight, 1}; info.mipLevels = 1; info.arrayLayers = 1;
        info.samples = VK_SAMPLE_COUNT_1_BIT; info.tiling = VK_IMAGE_TILING_OPTIMAL;
        info.usage = VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT;
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
    const ProcessingProfile& profile;
    VkDescriptorSetLayout setLayout{};
    VkDescriptorPool pool{};
    VkDescriptorSet set{};
    VkPipelineLayout layout{};
    std::array<VkShaderModule, 5> modules{};
    std::array<VkPipeline, 5> pipelines{};
    VkQueryPool queries{};
    Compute(Vulkan& v,const ProcessingProfile& p) : vk(v),profile(p) {}
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
        buffers[2]={input.buffer,0,profile.inputBytes}; buffers[3]={output.buffer,0,profile.outputBytes};
        buffers[5]={forward.buffer,0,profile.flowBytes}; buffers[6]={backward.buffer,0,profile.flowBytes};
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
        VkQueryPoolCreateInfo qi{VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO}; qi.queryType = VK_QUERY_TYPE_TIMESTAMP; qi.queryCount = 8;
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
        if (pipeline == 1) vk.vkCmdDispatch(vk.command, uint32_t((profile.pixels / 2 + 255) / 256), 1, 1);
        else if (pipeline == 2) vk.vkCmdDispatch(vk.command, uint32_t((profile.pixels / 4 + 255) / 256), 1, 1);
        else if (pipeline == 3) vk.vkCmdDispatch(vk.command, (profile.width/4+15)/16, (profile.height/4+15)/16, 1);
        else if (pipeline == 4) vk.vkCmdDispatch(vk.command, (profile.flowWidth+7)/8, (profile.flowHeight+7)/8, 2);
        else vk.vkCmdDispatch(vk.command, (profile.width + 15) / 16, (profile.height + 15) / 16, 1);
    }
    void stamp(unsigned index, bool end) { vk.vkCmdWriteTimestamp(vk.command, end ? VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT : VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, queries, index); }
    bool timing(unsigned first,unsigned count,double* values) {
        std::array<uint64_t,8> ticks{};
        const auto status=vk.vkGetQueryPoolResults(vk.device,queries,first,count*2,count*2*sizeof(uint64_t),ticks.data(),sizeof(uint64_t),VK_QUERY_RESULT_64_BIT);
        if(status==VK_NOT_READY) return false;
        check(status,"vkGetQueryPoolResults");
        const uint64_t mask=vk.timestampBits==64?UINT64_MAX:((uint64_t(1)<<vk.timestampBits)-1);
        for(unsigned i=0;i<count;++i) values[i]=double((ticks[i*2+1]-ticks[i*2])&mask)*vk.timestampPeriod/1e6;
        return true;
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

