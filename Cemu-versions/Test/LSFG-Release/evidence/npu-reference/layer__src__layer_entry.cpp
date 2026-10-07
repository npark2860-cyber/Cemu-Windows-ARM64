#include "frame_transport.hpp"
#include <cstdlib>
#include <cstring>
#include <memory>
#include <mutex>
#include <unordered_map>
#include <vulkan/vk_layer.h>
#include <vulkan/vulkan.h>
namespace {
template <class T> void *key(T h) { return h ? *reinterpret_cast<void **>(h) : nullptr; }
struct Instance {
    VkInstance handle{};
    PFN_vkGetInstanceProcAddr get{};
};
struct Swapchain {
    VkExtent2D size{};
    VkFormat format{};
    bool capture{};
    std::vector<VkImage> images;
};
struct Device {
    VkDevice handle{};
    VkPhysicalDevice physical{};
    std::shared_ptr<Instance> instance;
    PFN_vkGetDeviceProcAddr get{};
    bool single_family{};
    VkPhysicalDeviceMemoryProperties memory{};
    std::vector<VkQueueFamilyProperties> families;
    std::unordered_map<VkQueue, uint32_t> queues;
    std::unordered_map<VkSwapchainKHR, Swapchain> swaps;
    std::mutex mutex;
    template <class T> T fn(const char *name) { return reinterpret_cast<T>(get(handle, name)); }
};
std::mutex mutex;
std::unordered_map<void *, std::shared_ptr<Instance>> instances;
std::unordered_map<void *, std::shared_ptr<Device>> devices;
std::shared_ptr<Instance> instance_for(void *k) {
    std::lock_guard lock(mutex);
    auto it = instances.find(k);
    return it == instances.end() ? nullptr : it->second;
}
std::shared_ptr<Device> device_for(void *k) {
    std::lock_guard lock(mutex);
    auto it = devices.find(k);
    return it == devices.end() ? nullptr : it->second;
}
bool enabled() {
    auto *e = std::getenv("HEXSCALE_PROCESS_FRAMES");
    return e && std::strcmp(e, "1") == 0;
}
#define FN(d, n) (d).fn<PFN_##n>(#n)
// Synchronous baseline: each submission completes before its resources are released.
struct Copy {
    Device &d;
    VkCommandPool pool{};
    VkBuffer buffer{};
    VkDeviceMemory memory{};
    VkFence fence{};
    void *mapped{};
    VkCommandBuffer command{};
    explicit Copy(Device &device) : d(device) {}
    ~Copy() {
        if (mapped)
            FN(d, vkUnmapMemory)(d.handle, memory);
        if (fence)
            FN(d, vkDestroyFence)(d.handle, fence, nullptr);
        if (buffer)
            FN(d, vkDestroyBuffer)(d.handle, buffer, nullptr);
        if (memory)
            FN(d, vkFreeMemory)(d.handle, memory, nullptr);
        if (pool)
            FN(d, vkDestroyCommandPool)(d.handle, pool, nullptr);
    }
    bool create(uint32_t family, size_t bytes) {
        VkBufferCreateInfo b{VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO};
        b.size = bytes;
        b.usage = VK_BUFFER_USAGE_TRANSFER_SRC_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT;
        b.sharingMode = VK_SHARING_MODE_EXCLUSIVE;
        if (FN(d, vkCreateBuffer)(d.handle, &b, nullptr, &buffer) != VK_SUCCESS)
            return false;
        VkMemoryRequirements req;
        FN(d, vkGetBufferMemoryRequirements)(d.handle, buffer, &req);
        uint32_t type = UINT32_MAX;
        for (uint32_t i = 0; i < d.memory.memoryTypeCount; ++i)
            if ((req.memoryTypeBits & (1u << i)) &&
                (d.memory.memoryTypes[i].propertyFlags &
                 (VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)) ==
                    (VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)) {
                type = i;
                break;
            }
        if (type == UINT32_MAX)
            return false;
        VkMemoryAllocateInfo a{VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO};
        a.allocationSize = req.size;
        a.memoryTypeIndex = type;
        if (FN(d, vkAllocateMemory)(d.handle, &a, nullptr, &memory) != VK_SUCCESS ||
            FN(d, vkBindBufferMemory)(d.handle, buffer, memory, 0) != VK_SUCCESS ||
            FN(d, vkMapMemory)(d.handle, memory, 0, bytes, 0, &mapped) != VK_SUCCESS)
            return false;
        VkCommandPoolCreateInfo p{VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO};
        p.queueFamilyIndex = family;
        p.flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;
        if (FN(d, vkCreateCommandPool)(d.handle, &p, nullptr, &pool) != VK_SUCCESS)
            return false;
        VkCommandBufferAllocateInfo c{VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO};
        c.commandPool = pool;
        c.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
        c.commandBufferCount = 1;
        if (FN(d, vkAllocateCommandBuffers)(d.handle, &c, &command) != VK_SUCCESS)
            return false;
        VkFenceCreateInfo f{VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};
        return FN(d, vkCreateFence)(d.handle, &f, nullptr, &fence) == VK_SUCCESS;
    }
    VkResult submit(VkQueue queue, VkImage image, VkExtent2D size, bool upload, uint32_t count,
                    const VkSemaphore *waits, bool &submitted) {
        submitted = false;
        VkResult r = FN(d, vkResetFences)(d.handle, 1, &fence);
        if (r != VK_SUCCESS)
            return r;
        r = FN(d, vkResetCommandBuffer)(command, 0);
        if (r != VK_SUCCESS)
            return r;
        VkCommandBufferBeginInfo begin{VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};
        begin.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
        r = FN(d, vkBeginCommandBuffer)(command, &begin);
        if (r != VK_SUCCESS)
            return r;
        VkImageMemoryBarrier barrier{VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER};
        barrier.oldLayout = VK_IMAGE_LAYOUT_PRESENT_SRC_KHR;
        barrier.newLayout =
            upload ? VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL : VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;
        barrier.srcQueueFamilyIndex = barrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
        barrier.image = image;
        barrier.subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1};
        barrier.dstAccessMask = upload ? VK_ACCESS_TRANSFER_WRITE_BIT : VK_ACCESS_TRANSFER_READ_BIT;
        FN(d, vkCmdPipelineBarrier)(command, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,
                                    VK_PIPELINE_STAGE_TRANSFER_BIT, 0, 0, nullptr, 0, nullptr, 1,
                                    &barrier);
        VkBufferImageCopy region{};
        region.imageSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1};
        region.imageExtent = {size.width, size.height, 1};
        if (upload)
            FN(d, vkCmdCopyBufferToImage)(command, buffer, image,
                                          VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 1, &region);
        else
            FN(d, vkCmdCopyImageToBuffer)(command, image, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,
                                          buffer, 1, &region);
        barrier.oldLayout = barrier.newLayout;
        barrier.newLayout = VK_IMAGE_LAYOUT_PRESENT_SRC_KHR;
        barrier.srcAccessMask = barrier.dstAccessMask;
        barrier.dstAccessMask = 0;
        FN(d, vkCmdPipelineBarrier)(command, VK_PIPELINE_STAGE_TRANSFER_BIT,
                                    VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT, 0, 0, nullptr, 0, nullptr,
                                    1, &barrier);
        if (!upload) {
            VkMemoryBarrier host{VK_STRUCTURE_TYPE_MEMORY_BARRIER};
            host.srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT;
            host.dstAccessMask = VK_ACCESS_HOST_READ_BIT;
            FN(d, vkCmdPipelineBarrier)(command, VK_PIPELINE_STAGE_TRANSFER_BIT,
                                        VK_PIPELINE_STAGE_HOST_BIT, 0, 1, &host, 0, nullptr, 0,
                                        nullptr);
        }
        r = FN(d, vkEndCommandBuffer)(command);
        if (r != VK_SUCCESS)
            return r;
        std::vector<VkPipelineStageFlags> stages(count, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT);
        VkSubmitInfo info{VK_STRUCTURE_TYPE_SUBMIT_INFO};
        info.waitSemaphoreCount = count;
        info.pWaitSemaphores = waits;
        info.pWaitDstStageMask = stages.data();
        info.commandBufferCount = 1;
        info.pCommandBuffers = &command;
        r = FN(d, vkQueueSubmit)(queue, 1, &info, fence);
        if (r != VK_SUCCESS)
            return r;
        submitted = true;
        return FN(d, vkWaitForFences)(d.handle, 1, &fence, VK_TRUE, UINT64_MAX);
    }
};
} // namespace
extern "C" VKAPI_ATTR PFN_vkVoidFunction VKAPI_CALL hexscale_vkGetInstanceProcAddr(VkInstance,
                                                                                   const char *);
extern "C" VKAPI_ATTR PFN_vkVoidFunction VKAPI_CALL hexscale_vkGetDeviceProcAddr(VkDevice,
                                                                                 const char *);
VKAPI_ATTR VkResult VKAPI_CALL hexscale_vkCreateInstance(const VkInstanceCreateInfo *info,
                                                         const VkAllocationCallbacks *allocator,
                                                         VkInstance *result) {
    auto *link = reinterpret_cast<VkLayerInstanceCreateInfo *>(const_cast<void *>(info->pNext));
    while (link && (link->sType != VK_STRUCTURE_TYPE_LOADER_INSTANCE_CREATE_INFO ||
                    link->function != VK_LAYER_LINK_INFO))
        link = reinterpret_cast<VkLayerInstanceCreateInfo *>(const_cast<void *>(link->pNext));
    if (!link || !link->u.pLayerInfo)
        return VK_ERROR_INITIALIZATION_FAILED;
    auto get = link->u.pLayerInfo->pfnNextGetInstanceProcAddr;
    link->u.pLayerInfo = link->u.pLayerInfo->pNext;
    auto create = reinterpret_cast<PFN_vkCreateInstance>(get(nullptr, "vkCreateInstance"));
    if (!create)
        return VK_ERROR_INITIALIZATION_FAILED;
    auto r = create(info, allocator, result);
    if (r == VK_SUCCESS) {
        auto state = std::make_shared<Instance>();
        state->handle = *result;
        state->get = get;
        std::lock_guard lock(mutex);
        instances[key(*result)] = state;
    }
    return r;
}
VKAPI_ATTR void VKAPI_CALL hexscale_vkDestroyInstance(VkInstance instance,
                                                      const VkAllocationCallbacks *allocator) {
    auto state = instance_for(key(instance));
    if (!state)
        return;
    {
        std::lock_guard lock(mutex);
        instances.erase(key(instance));
    }
    reinterpret_cast<PFN_vkDestroyInstance>(state->get(instance, "vkDestroyInstance"))(instance,
                                                                                       allocator);
}
VKAPI_ATTR VkResult VKAPI_CALL hexscale_vkCreateDevice(VkPhysicalDevice physical,
                                                       const VkDeviceCreateInfo *info,
                                                       const VkAllocationCallbacks *allocator,
                                                       VkDevice *result) {
    auto instance = instance_for(key(physical));
    if (!instance)
        return VK_ERROR_INITIALIZATION_FAILED;
    auto *link = reinterpret_cast<VkLayerDeviceCreateInfo *>(const_cast<void *>(info->pNext));
    while (link && (link->sType != VK_STRUCTURE_TYPE_LOADER_DEVICE_CREATE_INFO ||
                    link->function != VK_LAYER_LINK_INFO))
        link = reinterpret_cast<VkLayerDeviceCreateInfo *>(const_cast<void *>(link->pNext));
    if (!link || !link->u.pLayerInfo)
        return VK_ERROR_INITIALIZATION_FAILED;
    auto get = link->u.pLayerInfo->pfnNextGetDeviceProcAddr;
    auto gipa = link->u.pLayerInfo->pfnNextGetInstanceProcAddr;
    link->u.pLayerInfo = link->u.pLayerInfo->pNext;
    auto create = reinterpret_cast<PFN_vkCreateDevice>(gipa(instance->handle, "vkCreateDevice"));
    if (!create)
        return VK_ERROR_INITIALIZATION_FAILED;
    auto r = create(physical, info, allocator, result);
    if (r != VK_SUCCESS)
        return r;
    auto d = std::make_shared<Device>();
    d->handle = *result;
    d->physical = physical;
    d->instance = instance;
    d->get = get;
    d->single_family = info->queueCreateInfoCount == 1;
    reinterpret_cast<PFN_vkGetPhysicalDeviceMemoryProperties>(
        gipa(instance->handle, "vkGetPhysicalDeviceMemoryProperties"))(physical, &d->memory);
    auto families = reinterpret_cast<PFN_vkGetPhysicalDeviceQueueFamilyProperties>(
        gipa(instance->handle, "vkGetPhysicalDeviceQueueFamilyProperties"));
    uint32_t count = 0;
    families(physical, &count, nullptr);
    d->families.resize(count);
    families(physical, &count, d->families.data());
    std::lock_guard lock(mutex);
    devices[key(*result)] = d;
    return r;
}
VKAPI_ATTR void VKAPI_CALL hexscale_vkDestroyDevice(VkDevice device,
                                                    const VkAllocationCallbacks *allocator) {
    auto d = device_for(key(device));
    if (!d)
        return;
    {
        std::lock_guard lock(mutex);
        devices.erase(key(device));
    }
    FN(*d, vkDestroyDevice)(device, allocator);
}
VKAPI_ATTR void VKAPI_CALL hexscale_vkGetDeviceQueue(VkDevice device, uint32_t family,
                                                     uint32_t index, VkQueue *queue) {
    auto d = device_for(key(device));
    if (!d)
        return;
    FN(*d, vkGetDeviceQueue)(device, family, index, queue);
    std::lock_guard lock(d->mutex);
    d->queues[*queue] = family;
}
VKAPI_ATTR void VKAPI_CALL hexscale_vkGetDeviceQueue2(VkDevice device,
                                                      const VkDeviceQueueInfo2 *info,
                                                      VkQueue *queue) {
    auto d = device_for(key(device));
    if (!d)
        return;
    FN(*d, vkGetDeviceQueue2)(device, info, queue);
    if (!info->flags) {
        std::lock_guard lock(d->mutex);
        d->queues[*queue] = info->queueFamilyIndex;
    }
}
VKAPI_ATTR VkResult VKAPI_CALL hexscale_vkCreateSwapchainKHR(VkDevice device,
                                                             const VkSwapchainCreateInfoKHR *info,
                                                             const VkAllocationCallbacks *allocator,
                                                             VkSwapchainKHR *swap) {
    auto d = device_for(key(device));
    if (!d)
        return VK_ERROR_INITIALIZATION_FAILED;
    auto copy = *info;
    bool capture = enabled() &&
                   (d->single_family || info->imageSharingMode == VK_SHARING_MODE_CONCURRENT) &&
                   info->imageColorSpace == VK_COLOR_SPACE_SRGB_NONLINEAR_KHR && !info->pNext &&
                   !info->flags && info->imageArrayLayers == 1 &&
                   hexscale::frames::extent(info->imageExtent.width, info->imageExtent.height);
    capture = capture && (info->imageFormat == VK_FORMAT_R8G8B8A8_UNORM ||
                          info->imageFormat == VK_FORMAT_B8G8R8A8_UNORM ||
                          info->imageFormat == VK_FORMAT_R8G8B8A8_SRGB ||
                          info->imageFormat == VK_FORMAT_B8G8R8A8_SRGB);
    auto caps = reinterpret_cast<PFN_vkGetPhysicalDeviceSurfaceCapabilitiesKHR>(
        d->instance->get(d->instance->handle, "vkGetPhysicalDeviceSurfaceCapabilitiesKHR"));
    VkSurfaceCapabilitiesKHR surface{};
    const auto usage = VK_IMAGE_USAGE_TRANSFER_SRC_BIT | VK_IMAGE_USAGE_TRANSFER_DST_BIT;
    capture = capture && caps && caps(d->physical, info->surface, &surface) == VK_SUCCESS &&
              (surface.supportedUsageFlags & usage) == usage;
    if (capture)
        copy.imageUsage |= usage;
    auto r = FN(*d, vkCreateSwapchainKHR)(device, &copy, allocator, swap);
    if (r != VK_SUCCESS && capture) {
        capture = false;
        r = FN(*d, vkCreateSwapchainKHR)(device, info, allocator, swap);
    }
    if (r == VK_SUCCESS) {
        Swapchain state{info->imageExtent, info->imageFormat, capture, {}};
        uint32_t count = 0;
        auto images = FN(*d, vkGetSwapchainImagesKHR);
        if (images(device, *swap, &count, nullptr) == VK_SUCCESS) {
            state.images.resize(count);
            if (images(device, *swap, &count, state.images.data()) != VK_SUCCESS)
                state.capture = false;
        } else
            state.capture = false;
        std::lock_guard lock(d->mutex);
        d->swaps[*swap] = std::move(state);
    }
    return r;
}
VKAPI_ATTR void VKAPI_CALL hexscale_vkDestroySwapchainKHR(VkDevice device, VkSwapchainKHR swap,
                                                          const VkAllocationCallbacks *allocator) {
    auto d = device_for(key(device));
    if (!d)
        return;
    {
        std::lock_guard lock(d->mutex);
        d->swaps.erase(swap);
    }
    FN(*d, vkDestroySwapchainKHR)(device, swap, allocator);
}
VKAPI_ATTR VkResult VKAPI_CALL hexscale_vkQueuePresentKHR(VkQueue queue,
                                                          const VkPresentInfoKHR *info) {
    auto d = device_for(key(queue));
    if (!d)
        return VK_ERROR_INITIALIZATION_FAILED;
    auto next = FN(*d, vkQueuePresentKHR);
    if (!next)
        return VK_ERROR_EXTENSION_NOT_PRESENT;
    if (!enabled() || !info || info->pNext || info->swapchainCount != 1)
        return next(queue, info);
    bool consumed = false;
    VkResult failure = VK_SUCCESS;
    try {
        std::lock_guard lock(d->mutex);
        auto q = d->queues.find(queue);
        auto s = d->swaps.find(info->pSwapchains[0]);
        if (q != d->queues.end() && q->second < d->families.size() &&
            (d->families[q->second].queueFlags & VK_QUEUE_GRAPHICS_BIT) && s != d->swaps.end() &&
            s->second.capture && info->pImageIndices[0] < s->second.images.size()) {
            auto &state = s->second;
            size_t bytes = size_t(state.size.width) * state.size.height * 4;
            Copy copy(*d);
            if (copy.create(q->second, bytes)) {
                failure =
                    copy.submit(queue, state.images[info->pImageIndices[0]], state.size, false,
                                info->waitSemaphoreCount, info->pWaitSemaphores, consumed);
                if (failure == VK_SUCCESS) {
                    hexscale::Frame input{state.size.width, state.size.height,
                                          std::vector<uint8_t>(bytes)},
                        output;
                    std::memcpy(input.rgba.data(), copy.mapped, bytes);
                    bool bgra = state.format == VK_FORMAT_B8G8R8A8_UNORM ||
                                state.format == VK_FORMAT_B8G8R8A8_SRGB;
                    if (bgra)
                        for (size_t i = 0; i < bytes; i += 4)
                            std::swap(input.rgba[i], input.rgba[i + 2]);
                    if (hexscale::frames::request(input, input.width, input.height, output)) {
                        if (bgra)
                            for (size_t i = 0; i < bytes; i += 4)
                                std::swap(output.rgba[i], output.rgba[i + 2]);
                        std::memcpy(copy.mapped, output.rgba.data(), bytes);
                        bool submitted = false;
                        failure = copy.submit(queue, state.images[info->pImageIndices[0]],
                                              state.size, true, 0, nullptr, submitted);
                    }
                }
            }
        }
    } catch (const std::exception &) {
    }
    if (failure != VK_SUCCESS)
        return failure;
    auto present = *info;
    if (consumed) {
        present.waitSemaphoreCount = 0;
        present.pWaitSemaphores = nullptr;
    }
    return next(queue, &present);
}
namespace {
PFN_vkVoidFunction hook(const char *name) {
#define HOOK(n)                                                                                    \
    if (std::strcmp(name, #n) == 0)                                                                \
    return reinterpret_cast<PFN_vkVoidFunction>(hexscale_##n)
    HOOK(vkGetInstanceProcAddr);
    HOOK(vkGetDeviceProcAddr);
    HOOK(vkCreateInstance);
    HOOK(vkDestroyInstance);
    HOOK(vkCreateDevice);
    HOOK(vkDestroyDevice);
    HOOK(vkGetDeviceQueue);
    HOOK(vkGetDeviceQueue2);
    HOOK(vkCreateSwapchainKHR);
    HOOK(vkDestroySwapchainKHR);
    HOOK(vkQueuePresentKHR);
#undef HOOK
    return nullptr;
}
} // namespace
extern "C" VKAPI_ATTR PFN_vkVoidFunction VKAPI_CALL
hexscale_vkGetInstanceProcAddr(VkInstance instance, const char *name) {
    if (!name)
        return nullptr;
    if (!instance)
        return std::strcmp(name, "vkCreateInstance") == 0
                   ? reinterpret_cast<PFN_vkVoidFunction>(hexscale_vkCreateInstance)
               : std::strcmp(name, "vkGetInstanceProcAddr") == 0
                   ? reinterpret_cast<PFN_vkVoidFunction>(hexscale_vkGetInstanceProcAddr)
                   : nullptr;
    auto state = instance_for(key(instance));
    if (!state)
        return nullptr;
    auto next = state->get(instance, name);
    if (auto found = hook(name))
        return next ? found : nullptr;
    return next;
}
extern "C" VKAPI_ATTR PFN_vkVoidFunction VKAPI_CALL hexscale_vkGetDeviceProcAddr(VkDevice device,
                                                                                 const char *name) {
    if (!device || !name)
        return nullptr;
    auto d = device_for(key(device));
    if (!d)
        return nullptr;
    auto next = d->get(device, name);
    if (auto found = hook(name))
        return next ? found : nullptr;
    return next;
}
extern "C" VKAPI_ATTR VkResult VKAPI_CALL
vkNegotiateLoaderLayerInterfaceVersion(VkNegotiateLayerInterface *info) {
    if (!info || info->loaderLayerInterfaceVersion < 2)
        return VK_ERROR_INITIALIZATION_FAILED;
    info->loaderLayerInterfaceVersion = 2;
    info->pfnGetInstanceProcAddr = hexscale_vkGetInstanceProcAddr;
    info->pfnGetDeviceProcAddr = hexscale_vkGetDeviceProcAddr;
    info->pfnGetPhysicalDeviceProcAddr = nullptr;
    return VK_SUCCESS;
}
