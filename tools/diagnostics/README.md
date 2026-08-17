# Cemu ARM64 Runtime Experiments

This folder contains a reusable runtime experiment harness for compatibility diagnostics and performance A/B tests.

The build is patched by `Apply-RuntimeExperiments.ps1`. With no environment variable set, the experimental binary keeps the existing runtime behavior.

## Usage

Set `CEMU_EXPERIMENTS` before launching Cemu. Multiple switches can be combined with commas.

```bat
set CEMU_EXPERIMENTS=depthclip-feature
Cemu_release.exe
```

Clear the variable to return to the default behavior:

```bat
set CEMU_EXPERIMENTS=
```

## Bayonetta 2 / Adreno pipeline presets

| Preset | `CEMU_EXPERIMENTS` | Purpose |
|---|---|---|
| A | `depthclip-feature` | Query and enable `VkPhysicalDeviceDepthClipEnableFeaturesEXT`, then use the raster depth-clip pNext only when the feature is actually enabled |
| B | `depthclip-off` | Disable the raster depth-clip pNext path |
| C | `pipeline-feedback-off` | Disable `VkPipelineCreationFeedbackCreateInfoEXT` in the graphics pipeline pNext chain |
| D | `depthclip-off,pipeline-feedback-off` | Disable both suspected pNext paths |
| E | `depthclip-off,pipeline-feedback-off,depthclamp-off` | D plus disable depth clamp; diagnostic only, not intended as a final fix |
| Full pipeline pNext off | `pipeline-pnext-off` | Remove the graphics pipeline pNext chain entirely; useful for future driver diagnostics |
| Full raster pNext off | `raster-pnext-off` | Remove the current rasterization pNext path |

Cemu logs the active list as:

```text
[EXPERIMENT] Active: depthclip-feature
```

Preset A also logs whether the driver exposes the actual feature:

```text
[EXPERIMENT] depthClipEnable feature: supported/enabled
```

## PPCTimer performance experiments

| Switch | Purpose |
|---|---|
| `timer-udiv64` | If `_rdtscAcc.high == 0`, use exact 64/64 division and remainder instead of `_udiv128` |
| `timer-no-extra-fence` | Skip the extra `_mm_mfence()` inside `PPCTimer_getFromRDTSC()` |
| `timer-arm64-serialize` | On AArch64, use `isb` before the virtual counter read instead of the existing extra fence |
| `timer-stats` | Measure PPCTimer calls, `high == 0` ratio, slow/fast division counts, and spinlock contention; logs every 5,000,000 calls |

Recommended first measurements:

```bat
set CEMU_EXPERIMENTS=timer-stats
Cemu_release.exe

set CEMU_EXPERIMENTS=timer-udiv64,timer-stats
Cemu_release.exe

set CEMU_EXPERIMENTS=timer-udiv64,timer-no-extra-fence,timer-stats
Cemu_release.exe

set CEMU_EXPERIMENTS=timer-udiv64,timer-arm64-serialize,timer-stats
Cemu_release.exe
```

Example stats line:

```text
[PERF] PPCTimer calls=5000000 high0=4999990 highNZ=10 contended=1234 fast64=4999990 slow128=10
```

`timer-stats` intentionally adds instrumentation overhead. Use it to understand the hot path, not as a benchmark result itself.

## Design rules

- No experiment is active by default.
- Each switch changes one narrow behavior so results remain attributable.
- Switches can be combined without rebuilding.
- New driver or CPU experiments should be added here instead of creating one-off binaries whenever practical.
