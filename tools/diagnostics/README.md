# Cemu ARM64 Runtime Experiments

Reusable runtime experiment harness for compatibility diagnostics and performance A/B tests.

The experimental build accepts two environment variables:

- `CEMU_EXPERIMENTS`: comma-separated runtime switches.
- `CEMU_EXPERIMENT_LOG`: log filename created directly by Cemu in its normal user-data directory.

Example:

```bat
set CEMU_EXPERIMENTS=timer-udiv64,timer-stats
set CEMU_EXPERIMENT_LOG=log_PERF2_UDiv64.txt
Cemu_PERF2_UDiv64.exe
```

The supplied BAT files automatically create a clearly named executable copy from the single master `Cemu_release.exe`, set both variables, and launch that named executable. The build itself still occurs only once.

## Named logs

Each preset writes directly to its own file from process startup. There is no post-run copy/rename step.

- `00_Normal.bat` -> `Cemu_00_Normal.exe` -> `log_00_Normal.txt`
- `A_DepthClip_Feature.bat` -> `Cemu_A_DepthClipFeature.exe` -> `log_A_DepthClipFeature.txt`
- `B_DepthClip_Off.bat` -> `Cemu_B_DepthClipOff.exe` -> `log_B_DepthClipOff.txt`
- `C_Pipeline_Feedback_Off.bat` -> `Cemu_C_PipelineFeedbackOff.exe` -> `log_C_PipelineFeedbackOff.txt`
- `D_Both_PNext_Off.bat` -> `Cemu_D_BothPNextOff.exe` -> `log_D_BothPNextOff.txt`
- `E_DepthClamp_Off.bat` -> `Cemu_E_DepthClampOff.exe` -> `log_E_DepthClampOff.txt`
- `PERF_1_Timer_Stats.bat` -> `Cemu_PERF1_TimerStats.exe` -> `log_PERF1_TimerStats.txt`
- `PERF_2_UDiv64_Stats.bat` -> `Cemu_PERF2_UDiv64.exe` -> `log_PERF2_UDiv64.txt`
- `PERF_3_UDiv64_NoFence_Stats.bat` -> `Cemu_PERF3_UDiv64_NoFence.exe` -> `log_PERF3_UDiv64_NoFence.txt`
- `PERF_4_UDiv64_ARM64_ISB_Stats.bat` -> `Cemu_PERF4_UDiv64_ARM64_ISB.exe` -> `log_PERF4_UDiv64_ARM64_ISB.txt`

## Bayonetta 2 / Adreno switches

| Switch | Purpose |
|---|---|
| `depthclip-feature` | Query and enable `VkPhysicalDeviceDepthClipEnableFeaturesEXT`; use raster depth-clip pNext only when actually enabled |
| `depthclip-off` | Disable raster depth-clip pNext |
| `pipeline-feedback-off` | Disable `VkPipelineCreationFeedbackCreateInfoEXT` |
| `pipeline-pnext-off` | Remove graphics pipeline pNext entirely |
| `raster-pnext-off` | Remove rasterization pNext entirely |
| `depthclamp-off` | Disable depth clamp for diagnosis |
| `pipeline-diag` | Emit detailed pipeline failure state |

Pipeline diagnostics include:

```text
[ADRENO_DIAG] PIPELINE_FAIL ... depthClamp=... pnext=... rasterPnext=...
[ADRENO_DIAG] RT_FORMATS ...
[ADRENO_DIAG] ATTR ...
[ADRENO_DIAG] BLEND ...
```

## PPCTimer switches

| Switch | Purpose |
|---|---|
| `timer-udiv64` | When `_rdtscAcc.high == 0`, use exact 64/64 division/remainder instead of `_udiv128` |
| `timer-no-extra-fence` | Skip the extra `_mm_mfence()` inside `PPCTimer_getFromRDTSC()` |
| `timer-arm64-serialize` | On AArch64, use `isb` before the virtual counter read |
| `timer-stats` | Measure calls, high==0 ratio, slow/fast division counts, and spinlock contention |

Example stats line:

```text
[PERF] PPCTimer calls=5000000 high0=4999990 highNZ=10 contended=1234 fast64=4999990 slow128=10
```

`timer-stats` adds instrumentation overhead, so use it for path analysis rather than absolute performance measurement.

## Design rules

- No behavior experiment is active unless requested.
- Each preset has a distinct process name and distinct log filename.
- Logs are separated at creation time, not copied after shutdown.
- Switches remain composable without rebuilding.
- New driver/CPU experiments should extend this harness rather than creating one-off binaries when practical.
