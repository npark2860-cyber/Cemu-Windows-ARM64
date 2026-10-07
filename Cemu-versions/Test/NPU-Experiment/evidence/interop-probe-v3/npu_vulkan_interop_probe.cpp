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
constexpr size_t inputBytes = 6 * 32 * 32, outputBytes = 3 * 32 * 32;
constexpr unsigned rounds = 5;
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
uint8_t pattern(unsigned round, unsigned channel, unsigned lane) {
    return uint8_t(8 + (channel * 29 + lane * 7 + round * 41) % 224);
}
uint32_t packedPattern(unsigned round, unsigned channel) {
    uint32_t value{};
    for (unsigned lane = 0; lane < 4; ++lane) value |= uint32_t(pattern(round, channel, lane)) << (8 * lane);
    return value;
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
    X(vkGetPhysicalDeviceQueueFamilyProperties) X(vkGetPhysicalDeviceExternalBufferProperties) X(vkCreateDevice) X(vkGetDeviceProcAddr)
#define DEVICE_FUNCTIONS(X) \
    X(vkDestroyDevice) X(vkGetDeviceQueue) X(vkDeviceWaitIdle) X(vkCreateBuffer) X(vkDestroyBuffer) \
    X(vkGetBufferMemoryRequirements2) X(vkAllocateMemory) X(vkFreeMemory) X(vkBindBufferMemory) \
    X(vkGetMemoryHostPointerPropertiesEXT) X(vkMapMemory) X(vkUnmapMemory) X(vkCreateCommandPool) \
    X(vkDestroyCommandPool) X(vkAllocateCommandBuffers) X(vkResetCommandBuffer) X(vkBeginCommandBuffer) \
    X(vkEndCommandBuffer) X(vkCmdFillBuffer) X(vkCmdCopyBuffer) X(vkCmdPipelineBarrier) \
    X(vkCreateFence) X(vkDestroyFence) X(vkResetFences) X(vkWaitForFences) X(vkQueueSubmit)
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
    uint32_t family{};
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
        if (externalFlags & VK_EXTERNAL_MEMORY_FEATURE_DEDICATED_ONLY_BIT) throw Unsupported("This bounded probe does not implement dedicated-only host imports");
        vkGetPhysicalDeviceMemoryProperties(physical, &memoryProperties);
        vkGetPhysicalDeviceQueueFamilyProperties(physical, &count, nullptr);
        std::vector<VkQueueFamilyProperties> queues(count); vkGetPhysicalDeviceQueueFamilyProperties(physical, &count, queues.data());
        family = UINT32_MAX;
        for (uint32_t i = 0; i < count; ++i) if (queues[i].queueCount && (queues[i].queueFlags & VK_QUEUE_COMPUTE_BIT)) { family = i; break; }
        if (family == UINT32_MAX) throw Unsupported("No compute-capable Vulkan queue");
        const float priority = 0.5f;
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
    void submitAndWait() {
        check(vkEndCommandBuffer(command), "vkEndCommandBuffer");
        check(vkResetFences(device, 1, &fence), "vkResetFences");
        VkSubmitInfo si{VK_STRUCTURE_TYPE_SUBMIT_INFO}; si.commandBufferCount = 1; si.pCommandBuffers = &command;
        check(vkQueueSubmit(queue, 1, &si, fence), "vkQueueSubmit");
        // Do not destroy pending resources or terminate another application on a slow driver.
        check(vkWaitForFences(device, 1, &fence, VK_TRUE, UINT64_MAX), "vkWaitForFences");
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
        VkBufferCreateInfo bi{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO}; bi.size = size; bi.usage = allocator ? sharedUsage : VK_BUFFER_USAGE_TRANSFER_DST_BIT;
        bi.sharingMode = VK_SHARING_MODE_EXCLUSIVE; bi.pNext = allocator ? &external : nullptr;
        check(vk.vkCreateBuffer(vk.device, &bi, nullptr, &buffer), "vkCreateBuffer");
        VkBufferMemoryRequirementsInfo2 ri{VK_STRUCTURE_TYPE_BUFFER_MEMORY_REQUIREMENTS_INFO_2}; ri.buffer = buffer;
        VkMemoryDedicatedRequirements dedicated{VK_STRUCTURE_TYPE_MEMORY_DEDICATED_REQUIREMENTS};
        VkMemoryRequirements2 requirements{VK_STRUCTURE_TYPE_MEMORY_REQUIREMENTS_2}; requirements.pNext = &dedicated;
        vk.vkGetBufferMemoryRequirements2(vk.device, &ri, &requirements);
        if (dedicated.requiresDedicatedAllocation) throw Unsupported("Dedicated buffer allocation required");
        uint32_t types = requirements.memoryRequirements.memoryTypeBits;
        VkImportMemoryHostPointerInfoEXT import{VK_STRUCTURE_TYPE_IMPORT_MEMORY_HOST_POINTER_INFO_EXT};
        if (allocator) {
            allocationSize = alignedSize(size_t(requirements.memoryRequirements.size), vk.alignment);
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
        VkMemoryAllocateInfo ai{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO}; ai.allocationSize = allocationSize; ai.memoryTypeIndex = memoryType; ai.pNext = allocator ? &import : nullptr;
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

int wmain(int argc, wchar_t** argv) {
    fs::path directory, model, rpcPath;
    Report report;
    bool evidenceCreated = false;
    try {
        bool run = false;
        for (int i = 1; i < argc; ++i) {
            const std::wstring key = argv[i];
            if (key == L"--run-devices") run = true;
            else if (i + 1 < argc && (key == L"--out" || key == L"--model" || key == L"--rpc-library")) {
                const fs::path value = argv[++i];
                if (key == L"--out") directory = value; else if (key == L"--model") model = value; else rpcPath = value;
            } else throw std::runtime_error("Unknown or incomplete argument; no device started");
        }
        if (!run || directory.empty() || !fs::is_regular_file(model) || !rpcPath.is_absolute() || rpcPath.filename() != L"libcdsprpc.dll" || !fs::is_regular_file(rpcPath))
            throw std::runtime_error("Explicit --run-devices --out NEW_DIR --model PATH --rpc-library ABSOLUTE_PATH required; no device started");
        if (!fs::create_directory(directory)) throw std::runtime_error("Evidence directory already exists or cannot be created");
        evidenceCreated = true;
        report.str("status", "STARTED"); report.str("stage", "vulkan_capabilities");
        report.str("model", utf8(model.wstring())); report.str("rpc_library", utf8(rpcPath.wstring()));
        report.boolean("qnn_initialized", false); report.boolean("application_copy_free_gpu_npu_handoff", false);
        report.boolean("cemu_executed", false); report.boolean("full_framegen_validated", false);
        report.number("completed_rounds", 0);
        report.save(directory / L"result.json");
        Vulkan vk;
        vk.initialize(report);
        report.str("stage", "qnn_shared_allocator"); report.save(directory / L"result.json");
        Module rpc;
        rpc.load(rpcPath, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
        wchar_t loadedPath[32768]{};
        const auto length = GetModuleFileNameW(rpc.handle, loadedPath, DWORD(std::size(loadedPath)));
        if (!length || length >= std::size(loadedPath) || !fs::equivalent(rpcPath, loadedPath)) throw std::runtime_error("Wrong RPC DLL selected");
        Ort::Env env(ORT_LOGGING_LEVEL_INFO, "qnn-vulkan-interop-probe");
        Ort::SessionOptions options;
        options.SetIntraOpNumThreads(1); options.SetInterOpNumThreads(1);
        options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
        options.AddConfigEntry("session.disable_cpu_ep_fallback", "1");
        const auto prefix = directory / L"ort-profile"; options.EnableProfiling(prefix.c_str());
        options.AppendExecutionProvider("QNN", {{"backend_path", "QnnHtp.dll"}, {"offload_graph_io_quantization", "0"},
            {"htp_performance_mode", "balanced"}, {"profiling_level", "off"}, {"enable_htp_shared_memory_allocator", "1"}});
        Ort::Session session(env, model.c_str(), options);
        report.boolean("qnn_initialized", true); report.str("backend", "QnnHtp.dll"); report.boolean("cpu_fallback_disabled", true);
        report.str("ort_version", OrtGetApiBase()->GetVersionString());
        if (session.GetInputCount() != 1 || session.GetOutputCount() != 1) throw std::runtime_error("Unexpected graph I/O count");
        const std::array<int64_t, 4> inputShape{1, 6, 32, 32}, outputShape{1, 3, 32, 32};
        for (int i = 0; i < 2; ++i) {
            auto type = i ? session.GetOutputTypeInfo(0) : session.GetInputTypeInfo(0);
            auto tensor = type.GetTensorTypeAndShapeInfo();
            const auto& expected = i ? outputShape : inputShape;
            if (tensor.GetElementType() != ONNX_TENSOR_ELEMENT_DATA_TYPE_UINT8 || tensor.GetShape() != std::vector<int64_t>(expected.begin(), expected.end()))
                throw std::runtime_error("Expected the fixed UINT8 32x32 averaging model");
        }
        Ort::MemoryInfo sharedInfo("QnnHtpShared", OrtDeviceAllocator, 0, OrtMemTypeDefault);
        Ort::Allocator allocator(session, sharedInfo);
        if (allocator.GetInfo().GetAllocatorName() != "QnnHtpShared") throw std::runtime_error("Wrong allocator");
        report.str("stage", "import_qnn_memory"); report.save(directory / L"result.json");
        Buffer input(vk), output(vk), readback(vk);
        input.create(inputBytes, &allocator); output.create(outputBytes, &allocator); readback.create(inputBytes + outputBytes, nullptr);
        report.number("input_shared_backing_bytes", input.allocation->size()); report.number("output_shared_backing_bytes", output.allocation->size());
        report.number("input_import_bytes", input.allocationSize); report.number("output_import_bytes", output.allocationSize);
        report.number("input_aligned_offset", input.offset); report.number("output_aligned_offset", output.offset);
        report.number("input_memory_type", input.memoryType); report.number("output_memory_type", output.memoryType);
        report.number("input_memory_flags", vk.memoryProperties.memoryTypes[input.memoryType].propertyFlags);
        report.number("output_memory_flags", vk.memoryProperties.memoryTypes[output.memoryType].propertyFlags);
        report.str("import_handle_type", "HOST_ALLOCATION_BIT_EXT");
        auto inputTensor = Ort::Value::CreateTensor<uint8_t>(allocator.GetInfo(), static_cast<uint8_t*>(input.pointer), inputBytes, inputShape.data(), inputShape.size());
        auto outputTensor = Ort::Value::CreateTensor<uint8_t>(allocator.GetInfo(), static_cast<uint8_t*>(output.pointer), outputBytes, outputShape.data(), outputShape.size());
        report.str("input_allocator", inputTensor.GetTensorMemoryInfo().GetAllocatorName());
        report.str("output_allocator", outputTensor.GetTensorMemoryInfo().GetAllocatorName());
        Ort::AllocatorWithDefaultOptions names;
        auto inputName = session.GetInputNameAllocated(0, names), outputName = session.GetOutputNameAllocated(0, names);
        Ort::IoBinding binding(session); binding.BindInput(inputName.get(), inputTensor); binding.BindOutput(outputName.get(), outputTensor);
        std::vector<uint8_t> previousOutput;
        std::ostringstream roundJson; roundJson << std::setprecision(12) << '[';
        for (unsigned round = 0; round < rounds; ++round) {
            report.str("stage", "gpu_npu_gpu_round_" + std::to_string(round)); report.save(directory / L"result.json");
            const auto roundStart = Clock::now();
            vk.begin();
            vk.barrier(VK_ACCESS_HOST_READ_BIT | VK_ACCESS_HOST_WRITE_BIT, VK_ACCESS_TRANSFER_WRITE_BIT, VK_PIPELINE_STAGE_HOST_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT);
            for (unsigned channel = 0; channel < 6; ++channel) vk.vkCmdFillBuffer(vk.command, input.buffer, channel * 1024, 1024, packedPattern(round, channel));
            // Poison the output on GPU every round. A stale or skipped NPU output cannot pass.
            vk.vkCmdFillBuffer(vk.command, output.buffer, 0, outputBytes, 0xfdfdfdfd);
            vk.barrier(VK_ACCESS_TRANSFER_WRITE_BIT, VK_ACCESS_HOST_READ_BIT | VK_ACCESS_HOST_WRITE_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_HOST_BIT);
            vk.submitAndWait();
            const double gpuWriteMs = elapsed(roundStart);
            binding.SynchronizeInputs();
            const auto npuStart = Clock::now();
            session.Run(Ort::RunOptions{nullptr}, binding); binding.SynchronizeOutputs();
            const double npuMs = elapsed(npuStart);
            const auto gpuReadStart = Clock::now();
            vk.begin();
            vk.barrier(VK_ACCESS_HOST_WRITE_BIT, VK_ACCESS_TRANSFER_READ_BIT, VK_PIPELINE_STAGE_HOST_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT);
            VkBufferCopy copyInput{0, 0, inputBytes}, copyOutput{0, inputBytes, outputBytes};
            vk.vkCmdCopyBuffer(vk.command, input.buffer, readback.buffer, 1, &copyInput);
            vk.vkCmdCopyBuffer(vk.command, output.buffer, readback.buffer, 1, &copyOutput);
            vk.barrier(VK_ACCESS_TRANSFER_WRITE_BIT, VK_ACCESS_HOST_READ_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_HOST_BIT);
            vk.submitAndWait();
            const double gpuReadMs = elapsed(gpuReadStart);
            const auto* data = static_cast<const uint8_t*>(readback.mapped);
            for (size_t i = 0; i < inputBytes; ++i)
                if (data[i] != pattern(round, unsigned(i / 1024), unsigned(i % 4))) throw std::runtime_error("GPU input pattern mismatch");
            unsigned maxTwiceError{};
            const auto* actualOutput = data + inputBytes;
            for (size_t i = 0; i < outputBytes; ++i) {
                const unsigned channel = unsigned(i / 1024), lane = unsigned(i % 4);
                const int sum = int(pattern(round, channel, lane)) + int(pattern(round, channel + 3, lane));
                const unsigned error = unsigned(std::abs(int(actualOutput[i]) * 2 - sum));
                maxTwiceError = std::max(maxTwiceError, error);
                if (error > 2) throw std::runtime_error("GPU-read NPU output differs from arithmetic oracle");
            }
            if (!previousOutput.empty() && std::equal(previousOutput.begin(), previousOutput.end(), actualOutput)) throw std::runtime_error("Output did not change with GPU input");
            previousOutput.assign(actualOutput, actualOutput + outputBytes);
            std::ofstream raw(directory / (L"gpu-readback-round-" + std::to_wstring(round) + L".bin"), std::ios::binary);
            raw.write(reinterpret_cast<const char*>(data), inputBytes + outputBytes);
            if (!raw) throw std::runtime_error("Could not save GPU diagnostic readback");
            if (round) roundJson << ',';
            roundJson << "{\"round\":" << round << ",\"gpu_write_and_fence_ms\":" << gpuWriteMs << ",\"npu_run_ms\":" << npuMs
                << ",\"gpu_diagnostic_readback_ms\":" << gpuReadMs << ",\"max_oracle_error\":" << double(maxTwiceError) / 2 << '}';
            report.number("completed_rounds", round + 1);
            std::cout << "Round " << round << " verified through GPU diagnostic readback." << std::endl;
        }
        roundJson << ']'; report.raw("rounds", roundJson.str());
        auto profile = session.EndProfilingAllocated(names); report.str("ort_profile", profile.get());
        report.str("status", "INTEROP_ROUNDTRIP_COMPLETED_PROFILE_VERIFICATION_PENDING"); report.str("stage", "completed");
        report.boolean("application_copy_free_gpu_npu_handoff", true);
        report.boolean("application_cpu_writes_to_shared_payload", false);
        report.boolean("diagnostic_gpu_readback_used", true);
        report.str("scope", "Small NCHW UINT8 averaging graph; five changing GPU-generated patterns. Serialized host-mediated completion. GPU readback is diagnostic only. Does not prove absence of internal driver copies, Vulkan compute/image conversion, 1080p performance, or portable cache coherency beyond this experiment.");
        report.save(directory / L"result.json");
        return 0;
    } catch (const Unsupported& e) {
        report.str("status", "UNSUPPORTED"); report.str("reason", e.what());
        if (evidenceCreated) report.save(directory / L"result.json");
        std::cout << "UNSUPPORTED: " << e.what() << std::endl; return 2;
    } catch (const std::exception& e) {
        report.str("status", "FAILED"); report.str("reason", e.what());
        if (evidenceCreated) report.save(directory / L"result.json");
        std::cerr << "FAILED: " << e.what() << std::endl; return 1;
    }
}
