#pragma once
// Dedicated snapshot of the verified revision-5 helper; original probe stays frozen.
#define VK_NO_PROTOTYPES
#include <vulkan/vulkan.h>
#include <onnxruntime_cxx_api.h>
#include <windows.h>
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;
using Clock = std::chrono::steady_clock;
constexpr VkBufferUsageFlags sharedUsage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | VK_BUFFER_USAGE_TRANSFER_SRC_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT;
constexpr auto hostHandle = VK_EXTERNAL_MEMORY_HANDLE_TYPE_HOST_ALLOCATION_BIT_EXT;
double elapsed(Clock::time_point t) { return std::chrono::duration<double, std::milli>(Clock::now() - t).count(); }
std::string utf8(const std::wstring& s) {
    const int n = WideCharToMultiByte(CP_UTF8, 0, s.data(), int(s.size()), nullptr, 0, nullptr, nullptr);
    std::string r(n, '\0');
    WideCharToMultiByte(CP_UTF8, 0, s.data(), int(s.size()), r.data(), n, nullptr, nullptr);
    return r;
}
std::string quoted(const std::string& s) {
    std::ostringstream r; r << '"';
    for (unsigned char c : s) {
        if (c == '"' || c == '\\') r << '\\' << c;
        else if (c < 32) r << "\\u" << std::hex << std::setw(4) << std::setfill('0') << unsigned(c);
        else r << c;
    }
    r << '"'; return r.str();
}
struct Report {
    std::vector<std::pair<std::string, std::string>> fields;
    void raw(const std::string& key, const std::string& value) {
        for (auto& field : fields) if (field.first == key) { field.second = value; return; }
        fields.emplace_back(key, value);
    }
    void str(const std::string& key, const std::string& value) { raw(key, quoted(value)); }
    void boolean(const std::string& key, bool value) { raw(key, value ? "true" : "false"); }
    template<class T> void number(const std::string& key, T value) { std::ostringstream s; s << std::setprecision(12) << value; raw(key, s.str()); }
    void save(const fs::path& path) const {
        std::ofstream out(path); out << "{\n";
        for (size_t i = 0; i < fields.size(); ++i) out << "  " << quoted(fields[i].first) << ": " << fields[i].second << (i + 1 < fields.size() ? ",\n" : "\n");
        out << "}\n"; if (!out) throw std::runtime_error("Could not save report");
    }
};
struct Unsupported : std::runtime_error { using std::runtime_error::runtime_error; };
void check(VkResult r, const char* operation) {
    if (r != VK_SUCCESS) throw std::runtime_error(std::string(operation) + " failed, VkResult " + std::to_string(r));
}
size_t alignedSize(size_t value, size_t alignment) {
    if (!alignment || (alignment & (alignment - 1)) || alignment > 16 * 1024 * 1024 || value > 16 * 1024 * 1024)
        throw Unsupported("Unsupported alignment or allocation size");
    return (value + alignment - 1) & ~(alignment - 1);
}
struct Module {
    HMODULE handle{};
    Module() = default;
    Module(const Module&) = delete;
    Module& operator=(const Module&) = delete;
    void load(const fs::path& path, DWORD flags) {
        handle = LoadLibraryExW(path.c_str(), nullptr, flags);
        if (!handle) throw std::runtime_error("DLL load failed: " + utf8(path.wstring()) + ", Win32 " + std::to_string(GetLastError()));
    }
    ~Module() { if (handle) FreeLibrary(handle); }
};

#define INSTANCE_FUNCTIONS(X) \
    X(vkDestroyInstance) X(vkEnumeratePhysicalDevices) X(vkGetPhysicalDeviceProperties) \
    X(vkEnumerateDeviceExtensionProperties) X(vkGetPhysicalDeviceProperties2) X(vkGetPhysicalDeviceMemoryProperties) \
    X(vkGetPhysicalDeviceFormatProperties) X(vkGetPhysicalDeviceQueueFamilyProperties) X(vkGetPhysicalDeviceExternalBufferProperties) X(vkCreateDevice) X(vkGetDeviceProcAddr)
#define DEVICE_FUNCTIONS(X) \
    X(vkDestroyDevice) X(vkGetDeviceQueue) X(vkDeviceWaitIdle) X(vkCreateBuffer) X(vkDestroyBuffer) \
    X(vkGetBufferMemoryRequirements2) X(vkAllocateMemory) X(vkFreeMemory) X(vkBindBufferMemory) \
    X(vkGetMemoryHostPointerPropertiesEXT) X(vkMapMemory) X(vkUnmapMemory) X(vkCreateCommandPool) \
    X(vkDestroyCommandPool) X(vkAllocateCommandBuffers) X(vkResetCommandBuffer) X(vkBeginCommandBuffer) \
    X(vkEndCommandBuffer) X(vkCmdFillBuffer) X(vkCmdCopyBuffer) X(vkCmdPipelineBarrier) \
    X(vkCreateFence) X(vkDestroyFence) X(vkResetFences) X(vkWaitForFences) X(vkQueueSubmit) X(vkCreateImage) X(vkDestroyImage) X(vkGetImageMemoryRequirements) X(vkBindImageMemory) X(vkCreateImageView) X(vkDestroyImageView) X(vkCmdCopyImageToBuffer) X(vkCreateShaderModule) X(vkDestroyShaderModule) X(vkCreateDescriptorSetLayout) X(vkDestroyDescriptorSetLayout) X(vkCreateDescriptorPool) X(vkDestroyDescriptorPool) X(vkAllocateDescriptorSets) X(vkUpdateDescriptorSets) X(vkCreatePipelineLayout) X(vkDestroyPipelineLayout) X(vkCreateComputePipelines) X(vkDestroyPipeline) X(vkCmdBindPipeline) X(vkCmdBindDescriptorSets) X(vkCmdPushConstants) X(vkCmdDispatch) X(vkCreateQueryPool) X(vkDestroyQueryPool) X(vkCmdResetQueryPool) X(vkCmdWriteTimestamp) X(vkGetQueryPoolResults)
struct Vulkan {
    Module loader;
    PFN_vkGetInstanceProcAddr getInstanceProc{};
#define DECLARE(name) PFN_##name name{};
    INSTANCE_FUNCTIONS(DECLARE)
    DEVICE_FUNCTIONS(DECLARE)
#undef DECLARE
    VkInstance instance{};
    VkPhysicalDevice physical{};
    VkDevice device{};
    VkQueue queue{};
    VkCommandPool pool{};
    VkCommandBuffer command{};
    VkFence fence{};
    VkPhysicalDeviceMemoryProperties memoryProperties{};
    size_t alignment{};
    uint32_t family{}, timestampBits{}; float timestampPeriod{};
    void initialize(Report& report) {
        loader.load(L"vulkan-1.dll", LOAD_LIBRARY_SEARCH_SYSTEM32);
        getInstanceProc = reinterpret_cast<PFN_vkGetInstanceProcAddr>(GetProcAddress(loader.handle, "vkGetInstanceProcAddr"));
        if (!getInstanceProc) throw Unsupported("Vulkan loader entry point missing");
        auto version = reinterpret_cast<PFN_vkEnumerateInstanceVersion>(getInstanceProc(nullptr, "vkEnumerateInstanceVersion"));
        uint32_t apiVersion = VK_API_VERSION_1_0;
        if (version) check(version(&apiVersion), "vkEnumerateInstanceVersion");
        report.number("loader_api_version", apiVersion);
        if (apiVersion < VK_API_VERSION_1_1) throw Unsupported("Vulkan 1.1 required");
        auto createInstance = reinterpret_cast<PFN_vkCreateInstance>(getInstanceProc(nullptr, "vkCreateInstance"));
        if (!createInstance) throw Unsupported("vkCreateInstance missing");
        VkApplicationInfo app{VK_STRUCTURE_TYPE_APPLICATION_INFO};
        app.pApplicationName = "Cemu standalone QNN memory import probe"; app.apiVersion = VK_API_VERSION_1_1;
        VkInstanceCreateInfo info{VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO}; info.pApplicationInfo = &app;
        check(createInstance(&info, nullptr, &instance), "vkCreateInstance");
#define LOAD_INSTANCE(name) name = reinterpret_cast<PFN_##name>(getInstanceProc(instance, #name)); if (!name) throw Unsupported(#name " missing");
        INSTANCE_FUNCTIONS(LOAD_INSTANCE)
#undef LOAD_INSTANCE
        uint32_t count{}; check(vkEnumeratePhysicalDevices(instance, &count, nullptr), "vkEnumeratePhysicalDevices");
        if (!count) throw Unsupported("No Vulkan physical device");
        std::vector<VkPhysicalDevice> devices(count);
        check(vkEnumeratePhysicalDevices(instance, &count, devices.data()), "vkEnumeratePhysicalDevices");
        unsigned matches{};
        VkPhysicalDeviceProperties properties{};
        std::ostringstream inventory; inventory << '[';
        unsigned deviceIndex{};
        for (auto candidate : devices) {
            VkPhysicalDeviceProperties candidateProperties{}; vkGetPhysicalDeviceProperties(candidate, &candidateProperties);
            if (deviceIndex) inventory << ',';
            inventory << "{\"index\":" << deviceIndex++ << ",\"name\":" << quoted(candidateProperties.deviceName)
                << ",\"vendor_id\":" << candidateProperties.vendorID << ",\"device_id\":" << candidateProperties.deviceID
                << ",\"driver_version_raw\":" << candidateProperties.driverVersion << ",\"api_version\":" << candidateProperties.apiVersion << '}';
            // The D3D12 translation adapter also contains "Adreno" in its name.
            // The captured native Qualcomm adapter reports vendor ID 0x5143.
            if (candidateProperties.vendorID == 0x5143 && std::string(candidateProperties.deviceName).find("Adreno") != std::string::npos) {
                physical = candidate; properties = candidateProperties; ++matches;
            }
        }
        inventory << ']'; report.raw("vulkan_devices", inventory.str()); report.number("matching_adreno_devices", matches);
        if (matches != 1) throw Unsupported("Expected exactly one native Qualcomm Adreno device");
        report.str("gpu_name", properties.deviceName); report.number("gpu_vendor_id", properties.vendorID);
        report.number("gpu_device_id", properties.deviceID); report.number("gpu_driver_version_raw", properties.driverVersion);
        report.number("gpu_api_version", properties.apiVersion);
        if (properties.apiVersion < VK_API_VERSION_1_1) throw Unsupported("Selected GPU does not support Vulkan 1.1");
        check(vkEnumerateDeviceExtensionProperties(physical, nullptr, &count, nullptr), "vkEnumerateDeviceExtensionProperties");
        std::vector<VkExtensionProperties> extensions(count);
        check(vkEnumerateDeviceExtensionProperties(physical, nullptr, &count, extensions.data()), "vkEnumerateDeviceExtensionProperties");
        auto has = [&](const char* name) { return std::any_of(extensions.begin(), extensions.end(), [&](const auto& e) { return std::string(e.extensionName) == name; }); };
        report.boolean("external_memory_host", has(VK_EXT_EXTERNAL_MEMORY_HOST_EXTENSION_NAME));
        report.boolean("external_memory_win32", has("VK_KHR_external_memory_win32"));
        report.boolean("external_semaphore_win32", has("VK_KHR_external_semaphore_win32"));
        if (!has(VK_EXT_EXTERNAL_MEMORY_HOST_EXTENSION_NAME)) throw Unsupported("VK_EXT_external_memory_host is not advertised by the active GPU driver");
        VkPhysicalDeviceExternalMemoryHostPropertiesEXT host{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_EXTERNAL_MEMORY_HOST_PROPERTIES_EXT};
        VkPhysicalDeviceProperties2 properties2{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2}; properties2.pNext = &host;
        vkGetPhysicalDeviceProperties2(physical, &properties2);
        alignment = size_t(host.minImportedHostPointerAlignment);
        alignedSize(1, alignment);
        report.number("min_imported_host_pointer_alignment", alignment);
        VkPhysicalDeviceExternalBufferInfo externalInfo{VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_EXTERNAL_BUFFER_INFO};
        externalInfo.usage = sharedUsage; externalInfo.handleType = hostHandle;
        VkExternalBufferProperties external{VK_STRUCTURE_TYPE_EXTERNAL_BUFFER_PROPERTIES};
        vkGetPhysicalDeviceExternalBufferProperties(physical, &externalInfo, &external);
        const auto externalFlags = external.externalMemoryProperties.externalMemoryFeatures;
        report.number("host_buffer_external_features", externalFlags);
        report.number("shared_buffer_usage", sharedUsage);
        if (!(externalFlags & VK_EXTERNAL_MEMORY_FEATURE_IMPORTABLE_BIT)) throw Unsupported("Host allocation import is not supported for storage/transfer buffers");
        report.boolean("external_buffer_dedicated_only", (externalFlags & VK_EXTERNAL_MEMORY_FEATURE_DEDICATED_ONLY_BIT) != 0);
        vkGetPhysicalDeviceMemoryProperties(physical, &memoryProperties);
        vkGetPhysicalDeviceQueueFamilyProperties(physical, &count, nullptr);
        std::vector<VkQueueFamilyProperties> queues(count); vkGetPhysicalDeviceQueueFamilyProperties(physical, &count, queues.data());
        family = UINT32_MAX;
        for (uint32_t i = 0; i < count; ++i) if (queues[i].queueCount && (queues[i].queueFlags & VK_QUEUE_COMPUTE_BIT)) { family = i; break; }
        if (family == UINT32_MAX) throw Unsupported("No compute-capable Vulkan queue");
        timestampBits = queues[family].timestampValidBits; timestampPeriod = properties.limits.timestampPeriod; if (!timestampBits || timestampBits > 64 || timestampPeriod <= 0) throw Unsupported("Selected queue has no usable GPU timestamps"); report.number("timestamp_valid_bits", timestampBits); report.number("timestamp_period_ns", timestampPeriod); const float priority = 0.5f;
        VkDeviceQueueCreateInfo qi{VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO}; qi.queueFamilyIndex = family; qi.queueCount = 1; qi.pQueuePriorities = &priority;
        const char* extension = VK_EXT_EXTERNAL_MEMORY_HOST_EXTENSION_NAME;
        VkDeviceCreateInfo di{VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO}; di.queueCreateInfoCount = 1; di.pQueueCreateInfos = &qi;
        di.enabledExtensionCount = 1; di.ppEnabledExtensionNames = &extension;
        check(vkCreateDevice(physical, &di, nullptr, &device), "vkCreateDevice");
#define LOAD_DEVICE(name) name = reinterpret_cast<PFN_##name>(vkGetDeviceProcAddr(device, #name)); if (!name) throw Unsupported(#name " missing");
        DEVICE_FUNCTIONS(LOAD_DEVICE)
#undef LOAD_DEVICE
        vkGetDeviceQueue(device, family, 0, &queue);
        VkCommandPoolCreateInfo pi{VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO}; pi.flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT; pi.queueFamilyIndex = family;
        check(vkCreateCommandPool(device, &pi, nullptr, &pool), "vkCreateCommandPool");
        VkCommandBufferAllocateInfo ai{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO}; ai.commandPool = pool; ai.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY; ai.commandBufferCount = 1;
        check(vkAllocateCommandBuffers(device, &ai, &command), "vkAllocateCommandBuffers");
        VkFenceCreateInfo fi{VK_STRUCTURE_TYPE_FENCE_CREATE_INFO}; check(vkCreateFence(device, &fi, nullptr, &fence), "vkCreateFence");
    }
    uint32_t coherentType(uint32_t bits) const {
        constexpr auto required = VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT;
        for (uint32_t i = 0; i < memoryProperties.memoryTypeCount; ++i)
            if ((bits & (1u << i)) && (memoryProperties.memoryTypes[i].propertyFlags & required) == required) return i;
        throw Unsupported("No compatible host-visible coherent memory type; non-coherent interop is not attempted");
    }
    void begin() {
        check(vkResetCommandBuffer(command, 0), "vkResetCommandBuffer");
        VkCommandBufferBeginInfo bi{VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO}; bi.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
        check(vkBeginCommandBuffer(command, &bi), "vkBeginCommandBuffer");
    }
    void barrier(VkAccessFlags src, VkAccessFlags dst, VkPipelineStageFlags from, VkPipelineStageFlags to) {
        VkMemoryBarrier b{VK_STRUCTURE_TYPE_MEMORY_BARRIER}; b.srcAccessMask = src; b.dstAccessMask = dst;
        vkCmdPipelineBarrier(command, from, to, 0, 1, &b, 0, nullptr, 0, nullptr);
    }
    struct Submission { double submitMs{}, waitMs{}; }; Submission submitAndWait() {
        check(vkEndCommandBuffer(command), "vkEndCommandBuffer");
        check(vkResetFences(device, 1, &fence), "vkResetFences");
        VkSubmitInfo si{VK_STRUCTURE_TYPE_SUBMIT_INFO}; si.commandBufferCount = 1; si.pCommandBuffers = &command;
        const auto submitStart = Clock::now(); check(vkQueueSubmit(queue, 1, &si, fence), "vkQueueSubmit"); const auto submitMs = elapsed(submitStart); const auto waitStart = Clock::now();
        // Do not destroy pending resources or terminate another application on a slow driver.
        check(vkWaitForFences(device, 1, &fence, VK_TRUE, UINT64_MAX), "vkWaitForFences"); return {submitMs, elapsed(waitStart)};
    }
    ~Vulkan() {
        if (device && vkDeviceWaitIdle) vkDeviceWaitIdle(device);
        if (fence && vkDestroyFence) vkDestroyFence(device, fence, nullptr);
        if (pool && vkDestroyCommandPool) vkDestroyCommandPool(device, pool, nullptr);
        if (device && vkDestroyDevice) vkDestroyDevice(device, nullptr);
        if (instance && vkDestroyInstance) vkDestroyInstance(instance, nullptr);
    }
};

// Declare these buffers after the QNN allocator. Vulkan import must be released before RPC backing memory.
struct Buffer {
    Vulkan& vk;
    VkBuffer buffer{};
    VkDeviceMemory memory{};
    std::optional<Ort::MemoryAllocation> allocation;
    void* pointer{};
    void* mapped{};
    size_t offset{}, allocationSize{};
    uint32_t memoryType{};
    explicit Buffer(Vulkan& v) : vk(v) {}
    Buffer(const Buffer&) = delete;
    Buffer& operator=(const Buffer&) = delete;
    void create(size_t size, Ort::Allocator* allocator) {
        VkExternalMemoryBufferCreateInfo external{VK_STRUCTURE_TYPE_EXTERNAL_MEMORY_BUFFER_CREATE_INFO}; external.handleTypes = hostHandle;
        VkBufferCreateInfo bi{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO}; bi.size = allocator ? alignedSize(size, vk.alignment) : size; bi.usage = allocator ? sharedUsage : VK_BUFFER_USAGE_TRANSFER_DST_BIT;
        bi.sharingMode = VK_SHARING_MODE_EXCLUSIVE; bi.pNext = allocator ? &external : nullptr;
        check(vk.vkCreateBuffer(vk.device, &bi, nullptr, &buffer), "vkCreateBuffer");
        VkBufferMemoryRequirementsInfo2 ri{VK_STRUCTURE_TYPE_BUFFER_MEMORY_REQUIREMENTS_INFO_2}; ri.buffer = buffer;
        VkMemoryDedicatedRequirements dedicated{VK_STRUCTURE_TYPE_MEMORY_DEDICATED_REQUIREMENTS};
        VkMemoryRequirements2 requirements{VK_STRUCTURE_TYPE_MEMORY_REQUIREMENTS_2}; requirements.pNext = &dedicated;
        vk.vkGetBufferMemoryRequirements2(vk.device, &ri, &requirements);
        uint32_t types = requirements.memoryRequirements.memoryTypeBits;
        VkImportMemoryHostPointerInfoEXT import{VK_STRUCTURE_TYPE_IMPORT_MEMORY_HOST_POINTER_INFO_EXT};
        if (allocator) {
            allocationSize = size_t(requirements.memoryRequirements.size);
            if (allocationSize != alignedSize(allocationSize, vk.alignment)) throw Unsupported("Dedicated buffer size is incompatible with host import alignment");
            allocation.emplace(allocator->GetAllocation(allocationSize + vk.alignment - 1));
            if (!allocation->get()) throw std::runtime_error("QNN shared allocation failed");
            const uintptr_t base = reinterpret_cast<uintptr_t>(allocation->get());
            const uintptr_t aligned = (base + vk.alignment - 1) & ~(uintptr_t(vk.alignment) - 1);
            pointer = reinterpret_cast<void*>(aligned); offset = size_t(aligned - base);
            if (offset + allocationSize > allocation->size()) throw std::runtime_error("Import exceeds shared backing allocation");
            VkMemoryHostPointerPropertiesEXT hostProperties{VK_STRUCTURE_TYPE_MEMORY_HOST_POINTER_PROPERTIES_EXT};
            const auto result = vk.vkGetMemoryHostPointerPropertiesEXT(vk.device, hostHandle, pointer, &hostProperties);
            if (result == VK_ERROR_INVALID_EXTERNAL_HANDLE) throw Unsupported("GPU rejects this QNN RPC host allocation");
            check(result, "vkGetMemoryHostPointerPropertiesEXT");
            types &= hostProperties.memoryTypeBits;
            import.handleType = hostHandle; import.pHostPointer = pointer;
        } else allocationSize = size_t(requirements.memoryRequirements.size);
        memoryType = vk.coherentType(types);
        // Each buffer already has separate backing storage. Explicitly describe the sole
        // resource, satisfying the Qualcomm driver's dedicated-allocation requirement.
        VkMemoryDedicatedAllocateInfo dedicatedInfo{VK_STRUCTURE_TYPE_MEMORY_DEDICATED_ALLOCATE_INFO};
        dedicatedInfo.buffer = buffer; dedicatedInfo.pNext = allocator ? &import : nullptr;
        VkMemoryAllocateInfo ai{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO}; ai.allocationSize = allocationSize; ai.memoryTypeIndex = memoryType; ai.pNext = &dedicatedInfo;
        const auto allocationResult = vk.vkAllocateMemory(vk.device, &ai, nullptr, &memory);
        if (allocator && allocationResult == VK_ERROR_INVALID_EXTERNAL_HANDLE) throw Unsupported("QNN host pointer import was rejected at allocation");
        check(allocationResult, "vkAllocateMemory");
        check(vk.vkBindBufferMemory(vk.device, buffer, memory, 0), "vkBindBufferMemory");
        if (!allocator) check(vk.vkMapMemory(vk.device, memory, 0, allocationSize, 0, &mapped), "vkMapMemory");
    }
    ~Buffer() {
        if (mapped) vk.vkUnmapMemory(vk.device, memory);
        if (buffer) vk.vkDestroyBuffer(vk.device, buffer, nullptr);
        if (memory) vk.vkFreeMemory(vk.device, memory, nullptr);
        // allocation member frees RPC memory after the Vulkan objects above.
    }
};


