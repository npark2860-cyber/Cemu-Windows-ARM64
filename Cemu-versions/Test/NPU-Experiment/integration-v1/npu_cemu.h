#pragma once
#include <stdint.h>
#include <vulkan/vulkan.h>

// Experimental ABI. All calls except the private QNN worker run on Cemu's render
// thread. Borrowed device/queue are never destroyed. No worker queue submission.
#define CEMU_NPU_ABI 1u
struct CemuNpu;
struct CemuNpuCreateInfo {
    uint32_t size, abi;
    VkInstance instance;
    VkPhysicalDevice physical;
    VkDevice device;
    VkQueue queue;
    uint32_t family;
    PFN_vkGetInstanceProcAddr getInstanceProc;
    const wchar_t* directory;
    const wchar_t* rpcLibrary;
};
struct CemuNpuFrame {
    VkImage realImage, generatedImage;
    uint64_t realId;
    int32_t generatedSlot;
};
struct CemuNpuStats {
    uint64_t submitted, completed, stale, noSlot, generated;
    uint64_t npuRuns, inputWaitUs, npuRunUs, workerStartUs;
    double submitMs, downsampleMs, motionMs, packMs, composeMs;
    uint64_t preGpuSamples, postGpuSamples;
};
struct CemuNpuApi {
    uint32_t size, abi;
    int (*create)(const CemuNpuCreateInfo*, CemuNpu**, char*, uint32_t);
    void (*destroy)(CemuNpu*); // Shutdown only, after Cemu has drained its GPU uses.
    void (*reset)(CemuNpu*); // Invalidate epoch without joining or freeing resources.
    VkImage (*captureImage)(CemuNpu*, uint64_t frameId);
    // The capture copy must already have been submitted to the borrowed queue.
    // Returned GPU work is queued on that same queue; Cemu must submit its image
    // consumption before calling process again. No inference/fence waits here.
    int (*process)(CemuNpu*, uint64_t frameId, CemuNpuFrame*, char*, uint32_t);
    void (*stats)(CemuNpu*, CemuNpuStats*);
};
using CemuNpuGetApi = int (*)(uint32_t, CemuNpuApi*);
