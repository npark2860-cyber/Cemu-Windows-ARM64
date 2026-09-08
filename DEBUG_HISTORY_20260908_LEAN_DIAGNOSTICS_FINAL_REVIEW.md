# 2026-09-08 — Lean ARM64 diagnostics final pre-build review

Repository: `npark2860-cyber/Cemu-Windows-ARM64`

Development branch: `exp/release-arm64-diagnostics-lean`

Release baseline branch: `final-adreno-compat-arm64`

Build/CI remains prohibited until the user explicitly requests a build.

## Final review result

The six mandatory pre-build diagnostic design fixes identified in the final review are now staged in the lean release patch chain. They are not yet compile- or runtime-validated.

The final orchestrator is:

`tools/diagnostics/release/Apply-LeanReleaseDiagnostics.py`

The final generated-source verifier is:

`tools/diagnostics/release/Verify-AdrenoDiagnosticsComplete.py`

Do not claim PASS until the patch chain runs successfully against a clean release baseline and the user explicitly authorizes a build for compiler/runtime validation.

## Implemented/staged mandatory fixes

### 1. Safe UI semantics — STAGED

The historical `Diagnostics master` checkbox and all-on behavior are removed by `Apply-AdrenoSafeUI.py`.

Final intended UI behavior:

- no `RuntimeDiagnostics::SetAll(true)` path in ARM64 Diagnostics;
- `Disable all` is the only global action;
- `DumpEveryShader` remains a manual checkbox only;
- the old `Full` preset is replaced by `Adreno Triage`;
- `Adreno Triage` enables only failure-oriented probes:
  - `PipelineFailure`
  - `PipelineCacheMismatch`
  - `GLSLCompileFailure`
  - `SPIRVCompileFailure`
  - `DumpFailedShader`
  - `DeviceLostSubmitError`
- `Adreno Triage` never enables `DumpEveryShader`.

### 2. Incident block integrity — STAGED

The final incident layer provides:

- monotonic `incident=<id>`;
- a dedicated incident log mutex so asynchronous shader compiler threads cannot interleave one incident block with another;
- stable failure-key deduplication;
- a one-second repeat window;
- `repeatsSuppressed=<n>` on the next expanded occurrence;
- bounded incident output even though the in-memory rings retain deeper history.

Current bounded history/output targets:

- draw history: 64 retained / newest 24 emitted per incident;
- image-layout history: 64 retained / newest 24 emitted;
- resource history: 32 retained / newest 12 emitted.

### 3. Shader origin and direct shader-to-pipeline attribution — STAGED

`RendererShaderVk` now carries diagnostic provenance through shader-module creation.

The intended incident can distinguish:

- `source=spirv_cache`;
- `source=fresh_compile`;
- exact precompiled cache key pair;
- render-thread versus asynchronous worker compilation context;
- short shader ID plus full base/aux hash.

All shader failure phases are keyed by the exact shader:

- GLSL preprocess;
- GLSL parse;
- GLSL link;
- mapIO;
- empty SPIR-V output;
- `vkCreateShaderModule` failure.

The existing `RendererShaderVk::list_pipelineInfo` dependency relationship is copied under `RendererShaderVk::s_dependencyLock` and emitted as direct `[ADRENO_SHADER_PIPELINE]` correlation. This avoids relying only on recent draw inference when an asynchronously compiled shader fails before it is drawn.

`DumpFailedShader` still solely controls failure artifacts:

- original/generated GLSL;
- preprocessed GLSL;
- exact rejected SPIR-V bytes when module creation fails.

`DumpEveryShader` remains independent and manual-heavy only.

### 4. Resource I/O context — STAGED

The generic Cemu FSA path is instrumented only while relevant incident diagnostics are active.

Captured resource facts:

- canonical Wii U virtual path where the file was opened while diagnostics were active;
- file handle;
- starting offset;
- requested bytes;
- actual bytes read;
- monotonic sequence/timestamp.

OFF behavior:

- no resource path map is maintained;
- no file-position lookup is performed for diagnostic attribution;
- no resource breadcrumb is recorded.

If diagnostics are enabled after a file was already open, the path is explicitly reported as:

`<unknown-open-before-diagnostics>`

rather than guessed.

Generic runtime diagnostics intentionally do not hard-code Bayonetta archive knowledge. A read can therefore be reported as `/vol/content/.../data000.cpk + offset`. Mapping that offset to an entry such as `ui_shop.dat` remains an optional/offline CPK-TOC attribution step.

### 5. Image-layout/barrier history — STAGED

`VulkanRenderer::barrier_image()` feeds a bounded incident-only history containing:

- image identity;
- old/new layout;
- source/destination pipeline stages;
- source/destination access masks;
- aspect mask;
- mip range;
- layer range;
- sequence/timestamp.

This history is attached to the common incident as `[ADRENO_IMAGE_LAYOUT]` instead of requiring manual reconstruction from an unrelated log stream.

The existing dedicated `ImageLayoutTransition` checkbox remains available for a user who explicitly wants the broader transition log.

### 6. Device-lost-safe incident identity — STAGED

The common incident dumper no longer performs Vulkan property/feature enumeration/query calls when an incident is emitted.

Instead, the device/driver identity is cached while the Vulkan backend is healthy from the `vkGetPhysicalDeviceProperties2()` query that Cemu already performs in `DetermineVendor()`.

Cached incident identity includes:

- device name;
- vendor/device ID;
- raw driver version;
- API version;
- driver ID/name/info when available.

The incident also emits already-known feature/extension state from local `m_featureControl` data.

This keeps `VK_ERROR_DEVICE_LOST` triage from adding diagnostic Vulkan queries after loss.

`VK_EXT_device_fault` remains deferred because enabling it could alter device-creation extension state even when diagnostics are otherwise OFF.

## OFF-path contract

Final incident correlation uses a single atomic `g_incidentContextActive` hot-path gate.

That atomic is refreshed only when one of these existing failure switches changes:

- `PipelineFailure`
- `GLSLCompileFailure`
- `SPIRVCompileFailure`
- `DeviceLostSubmitError`
- `DumpFailedShader`

When none are enabled:

- draw incident breadcrumbs are not recorded;
- resource attribution work is skipped;
- image-layout incident breadcrumbs are not recorded;
- incident file/path state is not maintained.

No new correlation checkbox was added.

## Final verifier contract

`Verify-AdrenoDiagnosticsComplete.py` is intended to fail if the finished generated release source violates any of these rules:

- not all 77 implemented diagnostics match the 77 UI items;
- a selectable flag has no concrete runtime consumer;
- a dead/grey unsupported checkbox exists;
- `RuntimeExperiments::` survives in generated release source;
- a global all-on UI path survives;
- `DumpEveryShader` appears in a preset;
- incident correlation lacks the atomic OFF gate;
- incident history is unbounded;
- incident blocks are not serialized or lack stable IDs/deduplication;
- post-fault incident logging contains Vulkan property/feature/enumeration queries;
- shader cache-vs-fresh provenance is lost;
- shader failure phases are not keyed by base/aux hash;
- direct shader-to-pipeline dependency correlation is missing;
- failed shader artifacts are not individually gated;
- resource open/read/close attribution is missing or ungated;
- image-layout stage/access/subresource attribution is missing;
- the accepted Star Fox Zero / Bayonetta 2 direct-query workaround is missing;
- `vkGetQueryPoolResults` loader declaration is duplicated;
- the diagnostic GPU timestamp query pool is not lazy and switch-gated.

The stale source comment that mentioned `RuntimeExperiments::Enabled()` has also been removed by the final polish pass so a surviving `RuntimeExperiments::` token can be treated as a real verifier failure rather than a comment false-positive.

## Protected behavior

The final verification flow still requires preservation of:

- Star Fox Zero JP direct-query readback workaround;
- Bayonetta 2 JP direct-query readback workaround;
- title-gated `vkGetQueryPoolResults` direct path;
- XCX separate query behavior;
- known-good pre-e834 Vulkan behavior;
- VS `DEFAULT_VAL` synthesize behavior;
- AMD FidelityFX FSR1 EASU + RCAS release workflow;
- `main` untouched.

## High-value optional item — DEFERRED

Mapped-memory flush breadcrumb remains optional.

Cemu uses `vkFlushMappedMemoryRanges()` in uniform/upload paths. If later evidence shows a Windows ARM64/Adreno problem where shader/pipeline/layout state is correct but GPU-visible data is stale or corrupted, add a small incident-only breadcrumb containing:

- memory object class/identity;
- offset/size;
- coherent/non-coherent path;
- `nonCoherentAtomSize` alignment facts;
- sequence/frame/draw context where available.

Do not add this before evidence justifies it.

## Not required for first build

- full live Shader Inspector window;
- shader highlight/isolation rendering changes;
- automatic CPK parsing inside generic Cemu;
- unconditional Vulkan Adreno Layer integration;
- unconditional `VK_EXT_device_fault` enablement;
- screenshot/frame-capture automation.

## Desired incident shape

A single incident is designed to provide this first-pass chain:

`resource I/O -> image layout/barrier -> draw -> descriptor/FBO -> pipeline -> VS/PS/GS -> shader source/cache origin -> submit/fence -> failure`

All related lines use one stable incident ID so assistant-side analysis does not require manual hash/log reconstruction.

## Validation status

- six mandatory final-review fixes: **STAGED**
- final safe UI pass: **STAGED**
- final comprehensive verifier: **STAGED**
- end-to-end patch-chain execution on a clean release checkout: **NOT YET RUN**
- compiler/CI validation: **NOT RUN**
- runtime validation: **NOT RUN**

The local sandbox previously failed to clone GitHub because DNS resolution for `github.com` was unavailable. Therefore this session must not claim end-to-end patch-chain PASS merely from source/anchor review.

## Next action

Do not add more diagnostic features before the first validation unless a static blocker is discovered.

When the user explicitly says `빌드`:

1. apply the reviewed lean diagnostics to the release workflow/baseline;
2. require the final patch-chain verifier to PASS;
3. run compiler/CI validation;
4. inspect the first real failure if any;
5. preserve the protected query/FSR/pre-e834 behavior throughout.
