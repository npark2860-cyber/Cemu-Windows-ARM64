#pragma once
#include <stdint.h>
#include <vulkan/vulkan.h>
#include "frame_contract.h"

// Versioned NPU frame-generation ABI. All calls except the private QNN worker run on Cemu's render
// thread. Borrowed device/queue are never destroyed. No worker queue submission.
#define CEMU_NPU_ABI 3u
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
    uint32_t processingHeight; // Exactly 1080 or 720; immutable for this context.
};
struct CemuNpuFrame {
    // The host retains output-resolution originals in a NativeHistorySize ring.
    // Return the exact original ID to display, independently of processing size.
    VkImage generatedImage;
    uint64_t realId;
    int32_t generatedSlot;
    uint32_t bufferedFrames;
    uint32_t repeatedReal;
};
struct CemuNpuStats {
    // noSlot counts pairs skipped before GPU preprocessing: no free slot, or the
    // NPU could not finish the pair before its real frame is shown.
    uint64_t submitted, completed, stale, noSlot, generated;
    uint64_t npuRuns, inputWaitUs, npuRunUs, workerStartUs;
    double submitMs, downsampleMs, motionMs, packMs, composeMs;
    uint64_t preGpuSamples, postGpuSamples;
    uint64_t heldRealFrames;
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
