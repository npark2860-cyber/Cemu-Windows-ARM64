# 2026-09-08 — Lean ARM64 diagnostics final pre-build review

Repository: `npark2860-cyber/Cemu-Windows-ARM64`

Development branch: `exp/release-arm64-diagnostics-lean`

Reviewed HEAD before this document commit: `b3e11e4bd24587b664eb269c2c752edc5d1a250c`

Build/CI remains prohibited until the user explicitly requests a build.

## Mandatory pre-build fixes

### 1. Safe UI semantics

Current `Diagnostics master` uses `RuntimeDiagnostics::SetAll(true)` when checked. That can enable every diagnostic including `DumpEveryShader`, which is contrary to the user-mandated anti-heavy-log principle.

Before build:

- remove the all-on master behavior, or convert it to a global gate that does not alter individual selections;
- preferably provide a `Disable all` action rather than a one-click `Enable all` action;
- if `Full` preset remains, label it clearly as very heavy and keep it non-default;
- add a safe `Adreno Triage` preset that enables only failure/event-oriented diagnostics and never `DumpEveryShader`.

### 2. Incident block integrity

Shader compilation is asynchronous and may fail on more than one compiler thread. `[ADRENO_INCIDENT] BEGIN/END` blocks must not interleave.

Before build:

- serialize incident dumps with a dedicated mutex;
- assign a monotonic `incident=<id>` to every incident line;
- suppress duplicate incident expansion by a stable failure key, or enforce a bounded first-N policy;
- repeated duplicates should become compact one-line count updates rather than another 64-draw dump.

### 3. Shader-origin and direct shader-to-pipeline attribution

`RendererShaderVk::CompileInternal()` has two materially different paths:

1. precompiled SPIR-V cache -> `vkCreateShaderModule`;
2. generated GLSL -> glslang -> SPIR-V -> `vkCreateShaderModule`.

A shader failure must say which path produced the rejected module.

Before build, include:

- `source=spirv_cache` or `source=fresh_compile`;
- cache key/file identity when the cached path was used;
- `isRenderThread` / async compiler context;
- shader short ID plus full base/aux hash;
- direct related pipeline state hash(es), using the existing shader dependency relationship rather than relying only on the most recent draw ring.

The last point is important because an asynchronously compiled shader can fail before any related draw is recorded.

### 4. Resource I/O context

Cemu already exposes file path at open time and file position/handle/size at read time. A bounded resource breadcrumb should be attached to incidents.

Minimum useful form:

- guest path/container path;
- file handle;
- file offset;
- bytes requested/read;
- monotonic sequence/timestamp.

Tracking must occur only while relevant incident diagnostics are enabled. It must not emit per-read logs by default.

Archive-entry attribution such as `data000.cpk -> ui_shop.dat` is optional. Generic Cemu diagnostics should first record `data000.cpk + offset`; Bayonetta-specific CPK TOC resolution can be performed offline or through an optional mapping layer. Do not hard-code Bayonetta archive knowledge into generic Cemu runtime diagnostics.

### 5. Image-layout/barrier history attached to incidents

`ImageLayoutTransition` currently provides a selectable log probe, but Adreno triage needs failure-local history rather than an independent log stream.

Before build, add a bounded in-memory layout/barrier breadcrumb, active only when incident diagnostics are enabled, containing at least:

- image identity;
- old/new layout;
- aspect;
- mip/layer range;
- src/dst access masks where available;
- src/dst pipeline stages where available;
- frame/draw or global sequence.

On incident, dump the most recent relevant transitions in chronological order. This is especially important on Adreno because image layout specificity, render-pass/subpass behavior and GMEM interactions are unusually important.

### 6. Device-lost path must not make normal Vulkan queries after loss

The current common incident dumper calls `vkGetPhysicalDeviceProperties2()` when the incident is emitted. That is acceptable for normal shader/pipeline failures but should not be relied on after `VK_ERROR_DEVICE_LOST`.

Before build:

- cache the device/driver/feature fingerprint while the Vulkan device is healthy;
- device-lost incident output must use only cached data plus safe local state;
- do not add post-loss Vulkan calls merely for diagnostics.

`VK_EXT_device_fault` remains deferred because enabling it may require changing device-extension state even while diagnostics are nominally OFF. It should not be added until a design preserves the baseline-runtime contract.

## High-value optional addition

### Mapped-memory flush breadcrumb

Cemu uses `vkFlushMappedMemoryRanges()` in Vulkan memory/upload paths, including uniform data and upload reservations. For Windows ARM64/Adreno UMA cases where shader/pipeline state is correct but GPU-visible data is stale or corrupted, a small incident-only breadcrumb could record:

- memory object class/identity;
- offset/size;
- coherent vs non-coherent path;
- `nonCoherentAtomSize` alignment facts;
- frame/draw/global sequence.

This is valuable but lower priority than resource and layout history. Add it only if the implementation stays observation-only and switch-gated.

## Not required for first build

- full live Shader Inspector window;
- shader highlight/isolation rendering changes;
- automatic CPK parsing inside generic Cemu;
- unconditional Vulkan Adreno Layer integration;
- unconditional `VK_EXT_device_fault` enablement;
- screenshot/frame-capture automation.

These can be added later if the incident bundle still leaves ambiguity.

## Desired incident shape

A single incident should be sufficient for first-pass diagnosis:

`resource I/O -> layout/barrier -> draw -> descriptor/FBO -> pipeline -> VS/PS/GS -> shader source/cache origin -> submit/fence -> failure`

The incident should use one stable incident ID and deterministic shader/pipeline identifiers so assistant-side analysis requires no manual cross-log reconstruction.

## Validation still required before claiming readiness

A source-only review cannot replace an actual patch-chain dry run. The local sandbox cannot currently clone GitHub (`Could not resolve host: github.com`), so `Apply-LeanReleaseDiagnostics.py` has not yet been executed end-to-end against a clean checkout in this session.

When environment access permits, before any compile:

1. apply `Apply-LeanReleaseDiagnostics.py` to a clean release baseline checkout;
2. require all patch anchors to succeed;
3. run `Verify-LeanDiagnostics.py`;
4. run `git diff --check`;
5. verify no generated source references `RuntimeExperiments`;
6. verify protected Star Fox Zero / Bayonetta 2 direct-query code and FSR workflow remain untouched.

Only after the user explicitly says to build should CI/compiler validation start.
