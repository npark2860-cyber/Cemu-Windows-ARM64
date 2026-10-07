#include "motion_vulkan.hpp"
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#ifdef _WIN32
#include <windows.h>
#else
#include <dlfcn.h>
#endif
namespace {
struct Vulkan {
    void *library{};
    PFN_vkGetInstanceProcAddr get{};
    VkInstance instance{};
    VkDevice device{};
    VkQueue queue{};
    uint32_t family{};
    VkPhysicalDeviceMemoryProperties memory{};
    PFN_vkGetDeviceProcAddr get_device{};
    ~Vulkan() {
        if (device)
            reinterpret_cast<PFN_vkDestroyDevice>(get_device(device, "vkDestroyDevice"))(device,
                                                                                         nullptr);
        if (instance)
            reinterpret_cast<PFN_vkDestroyInstance>(get(instance, "vkDestroyInstance"))(instance,
                                                                                        nullptr);
#ifdef _WIN32
        if (library)
            FreeLibrary(static_cast<HMODULE>(library));
#else
        if (library)
            dlclose(library);
#endif
    }
    void open() {
#ifdef _WIN32
        library = LoadLibraryW(L"vulkan-1.dll");
        if (library)
            get = reinterpret_cast<PFN_vkGetInstanceProcAddr>(
                GetProcAddress(static_cast<HMODULE>(library), "vkGetInstanceProcAddr"));
#else
        library = dlopen("libvulkan.so.1", RTLD_NOW | RTLD_LOCAL);
        if (library)
            get = reinterpret_cast<PFN_vkGetInstanceProcAddr>(
                dlsym(library, "vkGetInstanceProcAddr"));
#endif
        if (!get)
            throw std::runtime_error("Vulkan loader unavailable");
        VkApplicationInfo app{VK_STRUCTURE_TYPE_APPLICATION_INFO};
        app.apiVersion = VK_API_VERSION_1_1;
        VkInstanceCreateInfo info{VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};
        info.pApplicationInfo = &app;
        if (reinterpret_cast<PFN_vkCreateInstance>(get(nullptr, "vkCreateInstance"))(
                &info, nullptr, &instance) != VK_SUCCESS)
            throw std::runtime_error("Cannot create Vulkan instance");
        auto enumerate = reinterpret_cast<PFN_vkEnumeratePhysicalDevices>(
            get(instance, "vkEnumeratePhysicalDevices"));
        uint32_t n = 0;
        if (enumerate(instance, &n, nullptr) != VK_SUCCESS || !n)
            throw std::runtime_error("No Vulkan devices");
        std::vector<VkPhysicalDevice> devices(n);
        if (enumerate(instance, &n, devices.data()) != VK_SUCCESS)
            throw std::runtime_error("Cannot enumerate GPUs");
        auto families = reinterpret_cast<PFN_vkGetPhysicalDeviceQueueFamilyProperties>(
            get(instance, "vkGetPhysicalDeviceQueueFamilyProperties"));
        for (auto physical : devices) {
            uint32_t count = 0;
            families(physical, &count, nullptr);
            std::vector<VkQueueFamilyProperties> properties(count);
            families(physical, &count, properties.data());
            for (uint32_t f = 0; f < count; ++f)
                if (properties[f].queueFlags & VK_QUEUE_COMPUTE_BIT) {
                    float priority = 1;
                    VkDeviceQueueCreateInfo qc{VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO};
                    qc.queueFamilyIndex = f;
                    qc.queueCount = 1;
                    qc.pQueuePriorities = &priority;
                    VkDeviceCreateInfo dc{VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO};
                    dc.queueCreateInfoCount = 1;
                    dc.pQueueCreateInfos = &qc;
                    if (reinterpret_cast<PFN_vkCreateDevice>(get(instance, "vkCreateDevice"))(
                            physical, &dc, nullptr, &device) != VK_SUCCESS)
                        continue;
                    family = f;
                    get_device = reinterpret_cast<PFN_vkGetDeviceProcAddr>(
                        get(instance, "vkGetDeviceProcAddr"));
                    reinterpret_cast<PFN_vkGetDeviceQueue>(get_device(device, "vkGetDeviceQueue"))(
                        device, f, 0, &queue);
                    reinterpret_cast<PFN_vkGetPhysicalDeviceMemoryProperties>(
                        get(instance, "vkGetPhysicalDeviceMemoryProperties"))(physical, &memory);
                    return;
                }
        }
        throw std::runtime_error("No usable compute queue");
    }
};
std::vector<uint8_t> read(const char *path, size_t bytes) {
    std::ifstream f(path, std::ios::binary | std::ios::ate);
    if (!f || f.tellg() != std::streamoff(bytes))
        throw std::runtime_error(std::string("Incorrect file size: ") + path);
    std::vector<uint8_t> b(bytes);
    f.seekg(0);
    if (!f.read(reinterpret_cast<char *>(b.data()), bytes))
        throw std::runtime_error("Incomplete file");
    return b;
}
uint32_t dimension(const char *text) {
    std::string s(text);
    size_t used = 0;
    auto n = std::stoul(s, &used);
    if (used != s.size() || !n || n > 4096)
        throw std::runtime_error("Invalid dimension");
    return uint32_t(n);
}
} // namespace
int main(int argc, char **argv) {
    if (argc != 11) {
        std::cerr << "Usage: hexscale-interpolate BACKEND MODEL PREVIOUS.rgba CURRENT.rgba "
                     "FLOW.f32 OUTPUT.rgba WIDTH HEIGHT FLOW_WIDTH FLOW_HEIGHT\nFlow: interleaved "
                     "float32 x/y, forward previous-to-current displacement in full-resolution "
                     "pixels. Model: batch-1 6-channel prealigned RGB -> 3-channel RGB residual.\n";
        return 2;
    }
    try {
        uint32_t w = dimension(argv[7]), h = dimension(argv[8]), cw = dimension(argv[9]),
                 ch = dimension(argv[10]);
        if (cw > 1024 || ch > 1024)
            throw std::runtime_error("Coarse flow is limited to 1024x1024");
        hexscale::Frame previous{w, h, read(argv[3], size_t(w) * h * 4)},
            current{w, h, read(argv[4], size_t(w) * h * 4)}, output;
        auto bytes = read(argv[5], size_t(cw) * ch * sizeof(hexscale::Motion));
        std::vector<hexscale::Motion> flow(size_t(cw) * ch), smooth, dense;
        std::memcpy(flow.data(), bytes.data(), bytes.size());
        Vulkan gpu;
        gpu.open();
        std::string error;
        if (!hexscale::smooth_motion_vulkan(gpu.device, gpu.queue, gpu.family, gpu.memory,
                                            gpu.get_device, flow, cw, ch, smooth, error) ||
            !hexscale::expand_motion(smooth, cw, ch, w, h, dense))
            throw std::runtime_error(error);
        hexscale::qnn::Runtime model;
        if (!model.open(argv[1]) || !model.load(argv[2]))
            throw std::runtime_error(model.error());
        if (!hexscale::interpolate_frame(model, previous, current, dense, output, error))
            throw std::runtime_error(error);
        std::ofstream file(argv[6], std::ios::binary);
        if (!file.write(reinterpret_cast<char *>(output.rgba.data()), output.rgba.size()))
            throw std::runtime_error("Cannot write output");
        std::cout << "Generated midpoint frame using Vulkan motion smoothing and QNN residual "
                     "synthesis\n";
        return 0;
    } catch (const std::exception &e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
}
