// SPDX-License-Identifier: GPL-3.0-or-later
#include "lsfg_cemu.h"
#include <windows.h>
#include <bcrypt.h>
#undef CreateSemaphore
#include "extraction/dll_reader.hpp"
#include "lsfg-vk-backend/lsfgvk.hpp"
#include "lsfg-vk-common/helpers/errors.hpp"
#include "lsfg-vk-common/vulkan/command_buffer.hpp"
#include "lsfg-vk-common/vulkan/image.hpp"
#include "lsfg-vk-common/vulkan/timeline_semaphore.hpp"
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <limits>
#include <memory>
#include <new>
#include <set>
#include <string>
#include <vector>

namespace {
constexpr uint64_t maxWait = 60'000'000'000ULL;
constexpr const char *dllHash =
    "626b196d799606cd4250b7b29e04228692ab70cf56a5d1bbb56d748c8219f0eb";
struct Failure {
  LsfgCemuStatus status;
  const char *text;
};
void Require(bool ok, const char *text,
             LsfgCemuStatus status = LSFG_CEMU_INVALID_ARGUMENT) {
  if (!ok)
    throw Failure{status, text};
}
void Check(VkResult r, const char *text) {
  if (r != VK_SUCCESS)
    throw ls::vulkan_error(r, text);
}
LsfgCemuStatus WriteError(LsfgCemuError *e, LsfgCemuStatus s, const char *text,
                          bool valid = false,
                          VkResult r = VK_SUCCESS) noexcept {
  if (e) {
    e->status = s;
    e->vk_result_valid = valid;
    e->vk_result = r;
    std::snprintf(e->message, sizeof(e->message), "%s", text ? text : "");
  }
  return s;
}
template <class F> LsfgCemuStatus Boundary(LsfgCemuError *e, F &&f) noexcept {
  try {
    const auto s = f();
    return WriteError(e, s, "");
  } catch (const Failure &x) {
    return WriteError(e, x.status, x.text);
  } catch (const ls::vulkan_error &x) {
    auto s = x.error() == VK_TIMEOUT             ? LSFG_CEMU_TIMEOUT
             : x.error() == VK_ERROR_DEVICE_LOST ? LSFG_CEMU_DEVICE_LOST
             : (x.error() == VK_ERROR_OUT_OF_HOST_MEMORY ||
                x.error() == VK_ERROR_OUT_OF_DEVICE_MEMORY)
                 ? LSFG_CEMU_OUT_OF_MEMORY
                 : LSFG_CEMU_VULKAN_ERROR;
    return WriteError(e, s, x.what(), true, x.error());
  } catch (const std::bad_alloc &) {
    return WriteError(e, LSFG_CEMU_OUT_OF_MEMORY, "host allocation failed");
  } catch (const std::exception &x) {
    return WriteError(e, LSFG_CEMU_INTERNAL_ERROR, x.what());
  } catch (...) {
    return WriteError(e, LSFG_CEMU_INTERNAL_ERROR,
                      "unknown C++ exception contained");
  }
}
struct Deadline {
  std::chrono::steady_clock::time_point end;
  explicit Deadline(uint64_t ns)
      : end(std::chrono::steady_clock::now() + std::chrono::nanoseconds(ns)) {}
  uint64_t remaining() const {
    const auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
                        end - std::chrono::steady_clock::now())
                        .count();
    return ns > 0 ? uint64_t(ns) : 0;
  }
};
std::string Sha256(const std::filesystem::path &path) {
  std::ifstream input(path, std::ios::binary | std::ios::ate);
  Require(input.good(), "cannot read supplied Lossless.dll path",
          LSFG_CEMU_DLL_ERROR);
  const auto n = input.tellg();
  Require(n > 0 && uint64_t(n) <= 512ULL * 1024 * 1024,
          "invalid/oversized Lossless.dll", LSFG_CEMU_DLL_ERROR);
  std::vector<unsigned char> bytes(static_cast<size_t>(n));
  input.seekg(0);
  input.read(reinterpret_cast<char *>(bytes.data()), n);
  Require(input.good(), "incomplete DLL read", LSFG_CEMU_DLL_ERROR);
  BCRYPT_ALG_HANDLE alg{};
  BCRYPT_HASH_HANDLE hash{};
  struct Close {
    BCRYPT_ALG_HANDLE &a;
    BCRYPT_HASH_HANDLE &h;
    ~Close() {
      if (h)
        BCryptDestroyHash(h);
      if (a)
        BCryptCloseAlgorithmProvider(a, 0);
    }
  } close{alg, hash};
  Require(BCryptOpenAlgorithmProvider(&alg, BCRYPT_SHA256_ALGORITHM, nullptr,
                                      0) >= 0,
          "SHA256 provider unavailable", LSFG_CEMU_DLL_ERROR);
  Require(BCryptCreateHash(alg, &hash, nullptr, 0, nullptr, 0, 0) >= 0 &&
              BCryptHashData(hash, bytes.data(),
                             static_cast<ULONG>(bytes.size()), 0) >= 0,
          "SHA256 failed", LSFG_CEMU_DLL_ERROR);
  unsigned char digest[32]{};
  Require(BCryptFinishHash(hash, digest, sizeof(digest), 0) >= 0,
          "SHA256 finish failed", LSFG_CEMU_DLL_ERROR);
  char hex[65]{};
  for (size_t i = 0; i < 32; ++i)
    std::snprintf(hex + i * 2, 3, "%02x", digest[i]);
  return hex;
}
template <class T>
T InstanceProc(const LsfgCemuCreateInfo &ci, const char *name) {
  auto p = reinterpret_cast<T>(ci.get_instance_proc_addr(ci.instance, name));
  Require(p != nullptr, "missing required instance dispatch",
          LSFG_CEMU_UNSUPPORTED);
  return p;
}
} // namespace

struct ContextGpu;
struct LsfgCemu {
  LsfgCemuCreateInfo ci{};
  std::filesystem::path dll;
  bool enabled{}, extracted{}, deviceLost{};
  uint32_t maxDimension{};
  std::set<LsfgCemuContext *> contexts;
  std::unique_ptr<vk::Vulkan> vulkan;
  std::unique_ptr<lsfgvk::backend::Instance> core;
  PFN_vkCmdCopyImage copyImage{};
  LsfgCemuStats totals{};
  void Initialize();
};
struct LsfgCemuContext {
  LsfgCemu *owner{};
  VkExtent2D extent{};
  bool resetRequested{true}, historyReady{}, poisoned{};
  uint64_t currentFrameId{};
  std::unique_ptr<ContextGpu> gpu;
};
struct ContextGpu {
  LsfgCemu &owner;
  VkExtent2D extent;
  std::unique_ptr<vk::Image> a, b, generated;
  std::unique_ptr<vk::TimelineSemaphore> timeline;
  std::unique_ptr<vk::CommandBuffer> copyCommand;
  lsfgvk::backend::Context *context{};
  VkFence tail{};
  bool mayPending{}, tailSubmitted{}, internalImagesInitialized{};
  uint64_t scheduled{};
  explicit ContextGpu(LsfgCemu &m, VkExtent2D e) : owner(m), extent(e) {}
  ~ContextGpu() {
    // Only reached after successful drain (or wait-confirmed device loss).
    if (context)
      owner.core->closeContext(*context);
    if (tail)
      owner.vulkan->df().DestroyFence(owner.ci.device, tail, nullptr);
  }
  void Build();
  VkResult Drain(Deadline &deadline);
  void Complete(Deadline &deadline) {
    Check(Drain(deadline), "module tail fence completion");
  }
  void CopyInputs(VkImage previous, VkImage current, bool first,
                  Deadline &deadline);
  void Schedule(Deadline &deadline);
  void Output(VkImage output, Deadline &deadline);
  void Barrier(VkImage image, VkImageLayout old, VkImageLayout next,
               VkAccessFlags src, VkAccessFlags dst) {
    VkImageMemoryBarrier b{VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER};
    b.srcAccessMask = src;
    b.dstAccessMask = dst;
    b.oldLayout = old;
    b.newLayout = next;
    b.srcQueueFamilyIndex = b.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
    b.image = image;
    b.subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1};
    owner.vulkan->df().CmdPipelineBarrier(
        copyCommand->handle(), VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,
        VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, 0, 0, nullptr, 0, nullptr, 1, &b);
  }
  void Copy(VkImage from, VkImage to) {
    VkImageCopy r{};
    r.srcSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1};
    r.dstSubresource = r.srcSubresource;
    r.extent = {extent.width, extent.height, 1};
    owner.copyImage(copyCommand->handle(), from, VK_IMAGE_LAYOUT_GENERAL, to,
                    VK_IMAGE_LAYOUT_GENERAL, 1, &r);
  }
  void SubmitCopy(Deadline &deadline) {
    copyCommand->end(*owner.vulkan);
    mayPending = true;
    copyCommand->submit(*owner.vulkan, {}, VK_NULL_HANDLE, 0, {},
                        VK_NULL_HANDLE, 0, VK_NULL_HANDLE);
    Complete(deadline);
  }
};

void LsfgCemu::Initialize() {
  if (core)
    return;
  Require(
      !deviceLost,
      "host device was lost; create a new module after host device recreation",
      LSFG_CEMU_DEVICE_LOST);
  Require(Sha256(dll) == dllHash,
          "DLL SHA256 does not match validated legacy ABI",
          LSFG_CEMU_DLL_ERROR);
  try {
    const auto resources = lsfgvk::backend::extractResourcesFromDLL(dll);
    unsigned spirv = 0;
    for (const auto &[id, bytes] : resources) {
      (void)id;
      uint32_t magic{};
      if (bytes.size() >= 4)
        std::memcpy(&magic, bytes.data(), 4);
      if (magic == 0x07230203)
        ++spirv;
    }
    Require(spirv == 98, "expected 98 legacy SPIR-V resources",
            LSFG_CEMU_DLL_ERROR);
    for (uint32_t id = 303; id <= 400; ++id) {
      const auto it = resources.find(id);
      uint32_t magic{};
      Require(it != resources.end() && it->second.size() >= 20 &&
                  it->second.size() % 4 == 0,
              "legacy shader resource ID/size mismatch", LSFG_CEMU_DLL_ERROR);
      std::memcpy(&magic, it->second.data(), 4);
      Require(magic == 0x07230203, "legacy resource magic mismatch",
              LSFG_CEMU_DLL_ERROR);
    }
  } catch (const Failure &) {
    throw;
  } catch (const std::bad_alloc &) {
    throw;
  } catch (const std::exception &) {
    throw Failure{LSFG_CEMU_DLL_ERROR, "PE resource parsing failed"};
  }
  extracted = true;
  vk::VulkanInstanceFuncs fi{};
#define LOAD_I(n) fi.n = InstanceProc<PFN_vk##n>(ci, "vk" #n)
  LOAD_I(GetPhysicalDeviceProperties2);
  LOAD_I(GetPhysicalDeviceQueueFamilyProperties);
  LOAD_I(GetPhysicalDeviceFeatures2);
  LOAD_I(GetPhysicalDeviceMemoryProperties);
#undef LOAD_I
  fi.GetDeviceProcAddr = ci.get_device_proc_addr;
  VkPhysicalDeviceProperties2 props{
      VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2};
  fi.GetPhysicalDeviceProperties2(ci.physical_device, &props);
  Require(props.properties.apiVersion >= VK_API_VERSION_1_2,
          "Vulkan 1.2 physical device required", LSFG_CEMU_UNSUPPORTED);
  maxDimension = props.properties.limits.maxImageDimension2D;
  VkPhysicalDeviceVulkan12Features v12{
      VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_2_FEATURES};
  VkPhysicalDeviceFeatures2 features{
      VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2, &v12};
  fi.GetPhysicalDeviceFeatures2(ci.physical_device, &features);
  Require(v12.timelineSemaphore &&
              features.features.shaderStorageImageExtendedFormats,
          "required Vulkan core features unsupported", LSFG_CEMU_UNSUPPORTED);
  uint32_t count = 0;
  fi.GetPhysicalDeviceQueueFamilyProperties(ci.physical_device, &count,
                                            nullptr);
  std::vector<VkQueueFamilyProperties> queues(count);
  fi.GetPhysicalDeviceQueueFamilyProperties(ci.physical_device, &count,
                                            queues.data());
  Require(ci.queue_family_index < count &&
              (queues[ci.queue_family_index].queueFlags & VK_QUEUE_COMPUTE_BIT),
          "borrowed queue family must support compute", LSFG_CEMU_UNSUPPORTED);
  auto getFormat = InstanceProc<PFN_vkGetPhysicalDeviceFormatProperties>(
      ci, "vkGetPhysicalDeviceFormatProperties");
  VkFormatProperties format{};
  getFormat(ci.physical_device, VK_FORMAT_R8G8B8A8_UNORM, &format);
  constexpr VkFormatFeatureFlags needed = VK_FORMAT_FEATURE_SAMPLED_IMAGE_BIT |
                                          VK_FORMAT_FEATURE_STORAGE_IMAGE_BIT |
                                          VK_FORMAT_FEATURE_TRANSFER_SRC_BIT |
                                          VK_FORMAT_FEATURE_TRANSFER_DST_BIT;
  Require((format.optimalTilingFeatures & needed) == needed,
          "RGBA8 image features unavailable", LSFG_CEMU_UNSUPPORTED);
  auto df = vk::initVulkanDeviceFuncs(fi, ci.device, false);
  copyImage = reinterpret_cast<PFN_vkCmdCopyImage>(
      ci.get_device_proc_addr(ci.device, "vkCmdCopyImage"));
  Require(copyImage && df.SignalSemaphore && df.WaitSemaphores,
          "required device commands unavailable", LSFG_CEMU_UNSUPPORTED);
  vulkan = std::make_unique<vk::Vulkan>(
      ci.instance, ci.device, ci.physical_device, fi, df, false, std::nullopt,
      std::nullopt, ci.queue_family_index, ci.queue);
  core = std::make_unique<lsfgvk::backend::Instance>(
      *vulkan, dll, false); // FP32, unchanged legacy shaders.
  Require(vulkan->stats().modules == 51 && vulkan->stats().pipelines == 51,
          "expected 51 shader modules/pipelines", LSFG_CEMU_DLL_ERROR);
}
void ContextGpu::Build() {
  auto &v = *owner.vulkan;
  const auto inputs = VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_STORAGE_BIT |
                      VK_IMAGE_USAGE_TRANSFER_DST_BIT;
  a = std::make_unique<vk::Image>(v, extent, VK_FORMAT_R8G8B8A8_UNORM, inputs);
  b = std::make_unique<vk::Image>(v, extent, VK_FORMAT_R8G8B8A8_UNORM, inputs);
  generated = std::make_unique<vk::Image>(v, extent, VK_FORMAT_R8G8B8A8_UNORM,
                                          VK_IMAGE_USAGE_SAMPLED_BIT |
                                              VK_IMAGE_USAGE_STORAGE_BIT |
                                              VK_IMAGE_USAGE_TRANSFER_SRC_BIT);
  timeline = std::make_unique<vk::TimelineSemaphore>(v, uint32_t(0));
  copyCommand = std::make_unique<vk::CommandBuffer>(v);
  VkFenceCreateInfo info{VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};
  Check(v.df().CreateFence(owner.ci.device, &info, nullptr, &tail),
        "create persistent tail fence");
  context = &owner.core->openContext(
      {a->handle(), b->handle()}, {generated->handle()}, timeline->handle(),
      extent.width, extent.height, false, 1.0f, false); // SDR, 2X, Quality.
}
VkResult ContextGpu::Drain(Deadline &deadline) {
  if (!mayPending)
    return owner.deviceLost ? VK_ERROR_DEVICE_LOST : VK_SUCCESS;
  auto &v = *owner.vulkan;
  if (!tailSubmitted) {
    auto r = v.df().ResetFences(owner.ci.device, 1, &tail);
    if (r != VK_SUCCESS && r != VK_ERROR_DEVICE_LOST)
      return r;
    if (r == VK_ERROR_DEVICE_LOST)
      owner.deviceLost = true;
    VkSubmitInfo submit{VK_STRUCTURE_TYPE_SUBMIT_INFO};
    r = v.df().QueueSubmit(owner.ci.queue, 1, &submit, tail);
    if (r != VK_SUCCESS && r != VK_ERROR_DEVICE_LOST)
      return r;
    if (r == VK_SUCCESS)
      ++owner.totals.queue_submissions;
    else
      owner.deviceLost = true;
    tailSubmitted = true;
  }
  const auto r = v.df().WaitForFences(owner.ci.device, 1, &tail, VK_TRUE,
                                      deadline.remaining());
  if (r == VK_SUCCESS || r == VK_ERROR_DEVICE_LOST) {
    // Lost-device spec equates wait DEVICE_LOST with SUCCESS for in-use
    // lifetime only; the generation and renderer still failed.
    mayPending = false;
    tailSubmitted = false;
    if (r == VK_ERROR_DEVICE_LOST)
      owner.deviceLost = true;
  }
  return owner.deviceLost && !mayPending ? VK_ERROR_DEVICE_LOST : r;
}
void ContextGpu::CopyInputs(VkImage previous, VkImage current, bool first,
                            Deadline &deadline) {
  auto &v = *owner.vulkan;
  copyCommand->begin(v);
  constexpr auto rw = VK_ACCESS_MEMORY_READ_BIT | VK_ACCESS_MEMORY_WRITE_BIT;
  auto fill = [&](VkImage host, VkImage internal) {
    Barrier(host, VK_IMAGE_LAYOUT_GENERAL, VK_IMAGE_LAYOUT_GENERAL, rw,
            VK_ACCESS_TRANSFER_READ_BIT);
    Barrier(
        internal, first ? VK_IMAGE_LAYOUT_UNDEFINED : VK_IMAGE_LAYOUT_GENERAL,
        VK_IMAGE_LAYOUT_GENERAL, first ? 0 : rw, VK_ACCESS_TRANSFER_WRITE_BIT);
    Copy(host, internal);
    Barrier(internal, VK_IMAGE_LAYOUT_GENERAL, VK_IMAGE_LAYOUT_GENERAL,
            VK_ACCESS_TRANSFER_WRITE_BIT, VK_ACCESS_SHADER_READ_BIT);
    Barrier(host, VK_IMAGE_LAYOUT_GENERAL, VK_IMAGE_LAYOUT_GENERAL,
            VK_ACCESS_TRANSFER_READ_BIT, rw);
  };
  if (first) {
    fill(previous, a->handle());
    fill(previous, b->handle());
    Barrier(generated->handle(), VK_IMAGE_LAYOUT_UNDEFINED,
            VK_IMAGE_LAYOUT_GENERAL, 0, VK_ACCESS_SHADER_WRITE_BIT);
  } else
    fill(current, scheduled % 2 ? b->handle() : a->handle());
  SubmitCopy(deadline);
  internalImagesInitialized = true;
}
void ContextGpu::Schedule(Deadline &deadline) {
  auto &v = *owner.vulkan;
  timeline->signal(v, scheduled * 2 + 1);
  mayPending =
      true; // prepass can have succeeded before a later recording/submit error.
  owner.core->scheduleFrames(*context);
  Complete(deadline);
  ++scheduled;
  ++owner.totals.completed_generations;
}
void ContextGpu::Output(VkImage output, Deadline &deadline) {
  auto &v = *owner.vulkan;
  copyCommand->begin(v);
  constexpr auto rw = VK_ACCESS_MEMORY_READ_BIT | VK_ACCESS_MEMORY_WRITE_BIT;
  Barrier(generated->handle(), VK_IMAGE_LAYOUT_GENERAL, VK_IMAGE_LAYOUT_GENERAL,
          VK_ACCESS_SHADER_WRITE_BIT, VK_ACCESS_TRANSFER_READ_BIT);
  Barrier(output, VK_IMAGE_LAYOUT_GENERAL, VK_IMAGE_LAYOUT_GENERAL, rw,
          VK_ACCESS_TRANSFER_WRITE_BIT);
  Copy(generated->handle(), output);
  Barrier(output, VK_IMAGE_LAYOUT_GENERAL, VK_IMAGE_LAYOUT_GENERAL,
          VK_ACCESS_TRANSFER_WRITE_BIT, rw);
  Barrier(generated->handle(), VK_IMAGE_LAYOUT_GENERAL, VK_IMAGE_LAYOUT_GENERAL,
          VK_ACCESS_TRANSFER_READ_BIT, VK_ACCESS_SHADER_WRITE_BIT);
  SubmitCopy(deadline);
}

extern "C" LsfgCemuStatus lsfg_cemu_create(const LsfgCemuCreateInfo *ci,
                                           LsfgCemu **out,
                                           LsfgCemuError *e) noexcept {
  if (out)
    *out = nullptr;
  return Boundary(e, [&] {
    Require(ci && out && ci->struct_size == sizeof(*ci) &&
                ci->abi_version == LSFG_CEMU_ABI_VERSION,
            "invalid create ABI/arguments");
    Require(ci->instance && ci->physical_device && ci->device && ci->queue &&
                ci->get_instance_proc_addr && ci->get_device_proc_addr,
            "all borrowed Vulkan handles and dispatch functions are required");
    Require(ci->lossless_dll_path && *ci->lossless_dll_path,
            "host must provide a Lossless.dll path");
    Require(ci->gpu_wait_timeout_ns > 0 && ci->gpu_wait_timeout_ns <= maxWait,
            "GPU timeout must be 1ns..60 seconds");
    Require(ci->timeline_semaphore_enabled &&
                ci->shader_storage_image_extended_formats_enabled,
            "host must enable timelineSemaphore and "
            "shaderStorageImageExtendedFormats",
            LSFG_CEMU_UNSUPPORTED);
    auto m = std::make_unique<LsfgCemu>();
    m->ci = *ci;
    m->dll = ci->lossless_dll_path;
    m->ci.lossless_dll_path = nullptr;
    *out = m.release();
    return LSFG_CEMU_OK;
  });
}
extern "C" LsfgCemuStatus lsfg_cemu_set_enabled(LsfgCemu *m, VkBool32 enable,
                                                LsfgCemuError *e) noexcept {
  return Boundary(e, [&] {
    Require(m && enable <= 1, "invalid enable arguments");
    if (m->enabled != bool(enable)) {
      m->enabled = bool(enable);
      for (auto c : m->contexts)
        c->resetRequested = true;
    }
    return LSFG_CEMU_OK;
  });
}
extern "C" LsfgCemuStatus
lsfg_cemu_create_context(LsfgCemu *m, const LsfgCemuContextInfo *info,
                         LsfgCemuContext **out, LsfgCemuError *e) noexcept {
  if (out)
    *out = nullptr;
  return Boundary(e, [&] {
    Require(m && info && out && info->struct_size == sizeof(*info),
            "invalid context arguments");
    Require(info->format == VK_FORMAT_R8G8B8A8_UNORM,
            "only SDR RGBA8_UNORM is supported", LSFG_CEMU_UNSUPPORTED);
    Require(info->width >= 128 && info->height >= 128 &&
                info->width <= INT32_MAX && info->height <= INT32_MAX,
            "extent must be at least 128 and fit signed offsets");
    auto c = std::make_unique<LsfgCemuContext>();
    c->owner = m;
    c->extent = {info->width, info->height};
    m->contexts.insert(c.get());
    *out = c.release();
    return LSFG_CEMU_OK;
  });
}
extern "C" LsfgCemuStatus lsfg_cemu_generate(LsfgCemuContext *c,
                                             const LsfgCemuGenerateInfo *info,
                                             LsfgCemuError *e) noexcept {
  return Boundary(e, [&] {
    Require(c, "null context");
    auto &m = *c->owner;
    if (!m.enabled)
      return LSFG_CEMU_DISABLED;
    Require(!m.deviceLost, "host device lost", LSFG_CEMU_DEVICE_LOST);
    Require(!c->poisoned, "failed generation requires drain and reset",
            LSFG_CEMU_NEEDS_RESET);
    Require(info && info->struct_size == sizeof(*info),
            "invalid generate arguments");
    Require(info->previous_image && info->current_image && info->output_image &&
                info->output_image != info->previous_image &&
                info->output_image != info->current_image,
            "host images required; output must not alias inputs");
    Require(info->current_frame_id > info->previous_frame_id,
            "frame IDs must increase");
    Require(!c->historyReady || c->resetRequested ||
                c->currentFrameId == info->previous_frame_id,
            "noncontinuous frame IDs require reset_history",
            LSFG_CEMU_NEEDS_RESET);
    Deadline deadline(m.ci.gpu_wait_timeout_ns);
    if (info->input_ready_fence) {
      auto wait = reinterpret_cast<PFN_vkWaitForFences>(
          m.ci.get_device_proc_addr(m.ci.device, "vkWaitForFences"));
      Require(wait != nullptr, "missing vkWaitForFences",
              LSFG_CEMU_UNSUPPORTED);
      const auto ready = wait(m.ci.device, 1, &info->input_ready_fence, VK_TRUE,
                              deadline.remaining());
      if (ready == VK_ERROR_DEVICE_LOST)
        m.deviceLost = true;
      Check(ready, "host input readiness fence");
    }
    try {
      m.Initialize();
      Require(c->extent.width <= m.maxDimension &&
                  c->extent.height <= m.maxDimension,
              "extent exceeds device maxImageDimension2D",
              LSFG_CEMU_UNSUPPORTED);
      if (c->resetRequested || !c->gpu) {
        Require(!c->gpu || !c->gpu->mayPending,
                "drain pending work before history rebuild", LSFG_CEMU_BUSY);
        c->gpu.reset();
        c->historyReady = false;
        c->gpu = std::make_unique<ContextGpu>(m, c->extent);
        c->gpu->Build();
        c->gpu->mayPending = true;
        m.core->initializeContext(*c->gpu->context);
        c->gpu->Complete(deadline);
        c->gpu->CopyInputs(info->previous_image, info->current_image, true,
                           deadline);
        for (unsigned i = 0; i < 3; ++i) {
          c->gpu->Schedule(deadline);
          ++m.totals.warmup_generations;
        }
        ++m.totals.history_resets;
        c->resetRequested = false;
      }
      c->gpu->CopyInputs(info->previous_image, info->current_image, false,
                         deadline);
      c->gpu->Schedule(deadline);
      c->gpu->Output(info->output_image, deadline);
      c->historyReady = true;
      c->currentFrameId = info->current_frame_id;
      ++m.totals.generated_outputs;
      return LSFG_CEMU_OK;
    } catch (const ls::vulkan_error &x) {
      c->poisoned = true;
      c->resetRequested = true;
      if (x.error() == VK_ERROR_DEVICE_LOST)
        m.deviceLost = true;
      throw;
    } catch (...) {
      c->poisoned = true;
      c->resetRequested = true;
      throw;
    }
  });
}
extern "C" LsfgCemuStatus lsfg_cemu_reset_history(LsfgCemuContext *c,
                                                  LsfgCemuError *e) noexcept {
  return Boundary(e, [&] {
    Require(c, "null context");
    Require(!c->gpu || !c->gpu->mayPending, "drain pending work first",
            LSFG_CEMU_BUSY);
    Require(!c->owner->deviceLost, "host device lost", LSFG_CEMU_DEVICE_LOST);
    c->resetRequested = true;
    c->poisoned = false;
    return LSFG_CEMU_OK;
  });
}
extern "C" LsfgCemuStatus lsfg_cemu_drain(LsfgCemuContext *c, uint64_t ns,
                                          LsfgCemuError *e) noexcept {
  return Boundary(e, [&] {
    Require(c && ns > 0 && ns <= maxWait, "invalid drain timeout/context");
    if (c->gpu) {
      Deadline d(ns);
      Check(c->gpu->Drain(d), "drain completion");
    }
    return LSFG_CEMU_OK;
  });
}
extern "C" LsfgCemuStatus lsfg_cemu_destroy_context(LsfgCemuContext **ptr,
                                                    LsfgCemuError *e) noexcept {
  return Boundary(e, [&] {
    Require(ptr, "null context pointer");
    if (!*ptr)
      return LSFG_CEMU_OK;
    auto c = *ptr;
    auto m = c->owner;
    if (c->gpu) {
      Deadline d(m->ci.gpu_wait_timeout_ns);
      const auto r = c->gpu->Drain(d);
      if (r != VK_ERROR_DEVICE_LOST || c->gpu->mayPending)
        Check(r, "destroy context drain");
    }
    m->contexts.erase(c);
    delete c;
    *ptr = nullptr;
    // Cleanup success on an already failed device does not certify generation.
    return LSFG_CEMU_OK;
  });
}
extern "C" LsfgCemuStatus lsfg_cemu_destroy(LsfgCemu **ptr,
                                            LsfgCemuError *e) noexcept {
  return Boundary(e, [&] {
    Require(ptr, "null module pointer");
    if (!*ptr)
      return LSFG_CEMU_OK;
    Require((*ptr)->contexts.empty(), "destroy contexts before module",
            LSFG_CEMU_BUSY);
    delete *ptr;
    *ptr = nullptr;
    return LSFG_CEMU_OK;
  });
}
extern "C" LsfgCemuStatus lsfg_cemu_get_stats(const LsfgCemu *m,
                                              LsfgCemuStats *s,
                                              LsfgCemuError *e) noexcept {
  return Boundary(e, [&] {
    Require(m && s && s->struct_size == sizeof(*s), "invalid stats arguments");
    *s = m->totals;
    s->struct_size = sizeof(*s);
    s->enabled = m->enabled;
    s->live_contexts = static_cast<uint32_t>(m->contexts.size());
    for (auto c : m->contexts)
      if (c->gpu && c->gpu->context)
        ++s->initialized_contexts;
    s->shader_extraction_pass = m->extracted;
    if (m->vulkan) {
      const auto &v = m->vulkan->stats();
      s->shader_modules = v.modules;
      s->compute_pipelines = v.pipelines;
      s->recorded_dispatches = v.dispatches;
      s->queue_submissions += v.submissions;
      s->host_objects_reused = m->vulkan->inst() == m->ci.instance &&
                               m->vulkan->dev() == m->ci.device &&
                               m->vulkan->queue() == m->ci.queue;
    }
    return LSFG_CEMU_OK;
  });
}
extern "C" const char *lsfg_cemu_status_string(LsfgCemuStatus s) noexcept {
  switch (s) {
#define STATUS(n)                                                              \
  case LSFG_CEMU_##n:                                                          \
    return #n
    STATUS(OK);
    STATUS(DISABLED);
    STATUS(INVALID_ARGUMENT);
    STATUS(UNSUPPORTED);
    STATUS(DLL_ERROR);
    STATUS(VULKAN_ERROR);
    STATUS(TIMEOUT);
    STATUS(BUSY);
    STATUS(DEVICE_LOST);
    STATUS(OUT_OF_MEMORY);
    STATUS(INTERNAL_ERROR);
    STATUS(NEEDS_RESET);
#undef STATUS
  default:
    return "UNKNOWN_STATUS";
  }
}
