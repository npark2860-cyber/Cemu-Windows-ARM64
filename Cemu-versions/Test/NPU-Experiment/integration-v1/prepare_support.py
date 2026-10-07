"""Derive isolated borrowed-device helpers from the pinned, tested probe."""
from pathlib import Path
root = Path(__file__).resolve().parent
lab = root.parent
code = (lab/'src/motion1080_vulkan_support.h').read_text(encoding='utf-8')
code = code.replace('// Dedicated snapshot of the verified revision-5 helper; original probe stays frozen.',
                    '// Borrowed-device integration snapshot. Standalone probes remain unchanged.')
code = code.replace('X(vkCreateFence)', 'X(vkGetFenceStatus) X(vkCreateFence)')
start = code.index('    void initialize(Report& report) {')
end = code.index('    uint32_t coherentType', start)
code = code[:start] + '''    void initialize(const CemuNpuCreateInfo& info) {
        instance=info.instance; physical=info.physical; device=info.device;
        queue=info.queue; family=info.family; getInstanceProc=info.getInstanceProc;
        if(!instance || !physical || !device || !queue || !getInstanceProc) throw Unsupported("Missing borrowed Vulkan objects");
#define LOAD_INSTANCE(name) name=reinterpret_cast<PFN_##name>(getInstanceProc(instance,#name)); if(!name) throw Unsupported(#name " missing");
        INSTANCE_FUNCTIONS(LOAD_INSTANCE)
#undef LOAD_INSTANCE
#define LOAD_DEVICE(name) name=reinterpret_cast<PFN_##name>(vkGetDeviceProcAddr(device,#name)); if(!name) throw Unsupported(#name " missing");
        DEVICE_FUNCTIONS(LOAD_DEVICE)
#undef LOAD_DEVICE
        VkPhysicalDeviceProperties properties{}; vkGetPhysicalDeviceProperties(physical,&properties);
        if(properties.vendorID!=0x5143) throw Unsupported("Native Qualcomm Adreno required");
        uint32_t count{}; vkGetPhysicalDeviceQueueFamilyProperties(physical,&count,nullptr);
        std::vector<VkQueueFamilyProperties> queues(count); vkGetPhysicalDeviceQueueFamilyProperties(physical,&count,queues.data());
        if(family>=count || !(queues[family].queueFlags&VK_QUEUE_COMPUTE_BIT)) throw Unsupported("Borrowed queue has no compute support");
        timestampBits=queues[family].timestampValidBits; timestampPeriod=properties.limits.timestampPeriod;
        if(!timestampBits || timestampBits>64 || timestampPeriod<=0) throw Unsupported("GPU timestamps unavailable");
        VkPhysicalDeviceExternalMemoryHostPropertiesEXT host{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_EXTERNAL_MEMORY_HOST_PROPERTIES_EXT};
        VkPhysicalDeviceProperties2 properties2{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2}; properties2.pNext=&host;
        vkGetPhysicalDeviceProperties2(physical,&properties2); alignment=size_t(host.minImportedHostPointerAlignment); alignedSize(1,alignment);
        VkPhysicalDeviceExternalBufferInfo externalInfo{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_EXTERNAL_BUFFER_INFO};
        externalInfo.usage=sharedUsage; externalInfo.handleType=hostHandle;
        VkExternalBufferProperties external{VK_STRUCTURE_TYPE_EXTERNAL_BUFFER_PROPERTIES};
        vkGetPhysicalDeviceExternalBufferProperties(physical,&externalInfo,&external);
        if(!(external.externalMemoryProperties.externalMemoryFeatures&VK_EXTERNAL_MEMORY_FEATURE_IMPORTABLE_BIT)) throw Unsupported("Shared host import unavailable");
        vkGetPhysicalDeviceMemoryProperties(physical,&memoryProperties);
        VkCommandPoolCreateInfo pi{VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO}; pi.flags=VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT; pi.queueFamilyIndex=family;
        check(vkCreateCommandPool(device,&pi,nullptr,&pool),"vkCreateCommandPool");
        VkCommandBufferAllocateInfo ai{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO}; ai.commandPool=pool; ai.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY; ai.commandBufferCount=1;
        check(vkAllocateCommandBuffers(device,&ai,&command),"vkAllocateCommandBuffers");
        VkFenceCreateInfo fi{VK_STRUCTURE_TYPE_FENCE_CREATE_INFO}; check(vkCreateFence(device,&fi,nullptr,&fence),"vkCreateFence");
    }
''' + code[end:]
code = code.replace('        if (device && vkDestroyDevice) vkDestroyDevice(device, nullptr);\n','')
code = code.replace('        if (instance && vkDestroyInstance) vkDestroyInstance(instance, nullptr);\n','')
(root/'borrowed_support.h').write_text(code,encoding='utf-8')

probe = (lab/'src/motion1080_pipeline_probe.cpp').read_text(encoding='utf-8')
resources = probe[probe.index('struct GpuImage {'):probe.index('double readback(')]
resources = resources.replace('VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT;',
                              'VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT;')
resources = resources.replace('qi.queryCount = 12;', 'qi.queryCount = 8;')
start = resources.index('    std::array<double, 6> times() {')
end = resources.index('    ~Compute()',start)
resources = resources[:start]+'''    bool timing(unsigned first,unsigned count,double* values) {
        std::array<uint64_t,8> ticks{};
        const auto status=vk.vkGetQueryPoolResults(vk.device,queries,first,count*2,count*2*sizeof(uint64_t),ticks.data(),sizeof(uint64_t),VK_QUERY_RESULT_64_BIT);
        if(status==VK_NOT_READY) return false;
        check(status,"vkGetQueryPoolResults");
        const uint64_t mask=vk.timestampBits==64?UINT64_MAX:((uint64_t(1)<<vk.timestampBits)-1);
        for(unsigned i=0;i<count;++i) values[i]=double((ticks[i*2+1]-ticks[i*2])&mask)*vk.timestampPeriod/1e6;
        return true;
    }
''' + resources[end:]
(root/'gpu_resources.h').write_text(resources,encoding='utf-8')
(root/'anvil_async_worker.h').write_bytes((lab/'src/anvil_async_worker.h').read_bytes())
print('Prepared separate borrowed-device resources; frozen probes unchanged.')
