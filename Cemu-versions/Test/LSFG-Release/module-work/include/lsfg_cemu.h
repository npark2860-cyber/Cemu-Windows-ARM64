/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef LSFG_CEMU_H
#define LSFG_CEMU_H
#include <stddef.h>
#include <stdint.h>
#include <vulkan/vulkan_core.h>

#ifdef __cplusplus
#define LSFG_CEMU_NOEXCEPT noexcept
extern "C" {
#else
#define LSFG_CEMU_NOEXCEPT
#endif

#define LSFG_CEMU_ABI_VERSION 1u
typedef struct LsfgCemu LsfgCemu;
typedef struct LsfgCemuContext LsfgCemuContext;
typedef enum LsfgCemuStatus {
  LSFG_CEMU_OK = 0,
  LSFG_CEMU_DISABLED = 1,
  LSFG_CEMU_INVALID_ARGUMENT = -1,
  LSFG_CEMU_UNSUPPORTED = -2,
  LSFG_CEMU_DLL_ERROR = -3,
  LSFG_CEMU_VULKAN_ERROR = -4,
  LSFG_CEMU_TIMEOUT = -5,
  LSFG_CEMU_BUSY = -6,
  LSFG_CEMU_DEVICE_LOST = -7,
  LSFG_CEMU_OUT_OF_MEMORY = -8,
  LSFG_CEMU_INTERNAL_ERROR = -9,
  LSFG_CEMU_NEEDS_RESET = -10
} LsfgCemuStatus;

/* Caller-owned, optional on every call. vk_result_valid distinguishes actual
 * Vulkan results from validation/C++ errors. No exception or allocation crosses
 * ABI. */
typedef struct LsfgCemuError {
  LsfgCemuStatus status;
  VkBool32 vk_result_valid;
  VkResult vk_result;
  char message[512];
} LsfgCemuError;

typedef struct LsfgCemuCreateInfo {
  uint32_t struct_size;
  uint32_t abi_version;
  VkInstance instance;
  VkPhysicalDevice physical_device;
  VkDevice device;
  VkQueue queue;
  uint32_t queue_family_index;
  PFN_vkGetInstanceProcAddr get_instance_proc_addr;
  PFN_vkGetDeviceProcAddr get_device_proc_addr;
  const wchar_t *lossless_dll_path; /* copied UTF-16 path, resources only */
  uint64_t gpu_wait_timeout_ns;     /* 1 ns..60 seconds; never UINT64_MAX */
  /* Host assertions about features actually enabled on this existing device. */
  VkBool32 timeline_semaphore_enabled;
  VkBool32 shader_storage_image_extended_formats_enabled;
} LsfgCemuCreateInfo;

typedef struct LsfgCemuContextInfo {
  uint32_t struct_size;
  uint32_t width;
  uint32_t height;
  VkFormat format; /* only VK_FORMAT_R8G8B8A8_UNORM, SDR */
} LsfgCemuContextInfo;

typedef struct LsfgCemuGenerateInfo {
  uint32_t struct_size;
  VkImage previous_image;
  VkImage current_image;
  VkImage output_image;
  /* Identifiers are content sequence numbers, not swapchain image indices.
   * For continuity next.previous_frame_id must equal last.current_frame_id. */
  uint64_t previous_frame_id;
  uint64_t current_frame_id;
  /* Optional borrowed fence proving input/output readiness. Never reset or
   * destroyed by LSFG. No incoming binary semaphore is consumed by this API. */
  VkFence input_ready_fence;
} LsfgCemuGenerateInfo;

typedef struct LsfgCemuStats {
  uint32_t struct_size;
  VkBool32 enabled;
  uint32_t live_contexts;
  uint32_t initialized_contexts;
  VkBool32 shader_extraction_pass;
  uint64_t shader_modules;
  uint64_t compute_pipelines;
  uint64_t recorded_dispatches;
  uint64_t completed_generations; /* includes warmup */
  uint64_t warmup_generations;
  uint64_t generated_outputs;
  uint64_t queue_submissions; /* successful module-owned submissions */
  uint64_t history_resets;
  VkBool32 host_objects_reused;
} LsfgCemuStats;

/* All APIs require external host serialization. Hold the host queue lock for
 * every enabled generate/drain/destroy; do not concurrently submit on that
 * queue. create/context creation and enable/reset are CPU-only. Initial state
 * is OFF. */
LsfgCemuStatus lsfg_cemu_create(const LsfgCemuCreateInfo *, LsfgCemu **,
                                LsfgCemuError *) LSFG_CEMU_NOEXCEPT;
LsfgCemuStatus lsfg_cemu_set_enabled(LsfgCemu *, VkBool32,
                                     LsfgCemuError *) LSFG_CEMU_NOEXCEPT;
LsfgCemuStatus lsfg_cemu_create_context(LsfgCemu *, const LsfgCemuContextInfo *,
                                        LsfgCemuContext **,
                                        LsfgCemuError *) LSFG_CEMU_NOEXCEPT;
/* Additive host-integration API. Prepare while OFF on the render/queue thread.
 * Module prepare creates shaders/pipelines. Context prepare allocates resources
 * and completes their initialization, but never consumes a host frame. The
 * first real frame pair still needs history warmup. GPU waits remain finite. */
LsfgCemuStatus lsfg_cemu_prepare(LsfgCemu *, LsfgCemuError *) LSFG_CEMU_NOEXCEPT;
LsfgCemuStatus lsfg_cemu_prepare_context(LsfgCemuContext *,
                                         LsfgCemuError *) LSFG_CEMU_NOEXCEPT;
/* GENERAL -> GENERAL for all three host images. Input TRANSFER_SRC, output
 * TRANSFER_DST; 2D single sample/mip/layer, same context extent, no aliasing of
 * output with inputs/memory. Host retains ownership. See integration contract.
 * OK means all module GPU work completed and output is available for host use.
 * DISABLED does nothing, does not inspect info, signal/wait or change history.
 */
LsfgCemuStatus lsfg_cemu_generate(LsfgCemuContext *,
                                  const LsfgCemuGenerateInfo *,
                                  LsfgCemuError *) LSFG_CEMU_NOEXCEPT;
/* CPU-only request; next enabled generate recreates history and warms 3 times.
 */
LsfgCemuStatus lsfg_cemu_reset_history(LsfgCemuContext *,
                                       LsfgCemuError *) LSFG_CEMU_NOEXCEPT;
/* After submitted timeout/error retain all images/objects. Drain is finite;
 * success permits reset/destroy, but output of failed generate is not valid. */
LsfgCemuStatus lsfg_cemu_drain(LsfgCemuContext *, uint64_t timeout_ns,
                               LsfgCemuError *) LSFG_CEMU_NOEXCEPT;
/* On failure *context is unchanged. Module destroy returns BUSY with live
 * contexts. */
LsfgCemuStatus lsfg_cemu_destroy_context(LsfgCemuContext **,
                                         LsfgCemuError *) LSFG_CEMU_NOEXCEPT;
LsfgCemuStatus lsfg_cemu_destroy(LsfgCemu **,
                                 LsfgCemuError *) LSFG_CEMU_NOEXCEPT;
LsfgCemuStatus lsfg_cemu_get_stats(const LsfgCemu *, LsfgCemuStats *,
                                   LsfgCemuError *) LSFG_CEMU_NOEXCEPT;
const char *lsfg_cemu_status_string(LsfgCemuStatus) LSFG_CEMU_NOEXCEPT;

#ifdef __cplusplus
}
#endif
#undef LSFG_CEMU_NOEXCEPT
#endif
