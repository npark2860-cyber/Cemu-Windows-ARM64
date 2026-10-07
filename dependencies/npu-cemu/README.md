# NPU frame generation module (`cemu_npu.dll`)

## Build

`cmake -DCEMU_ENABLE_NPU=ON` builds Cemu and this module together. The build downloads the pinned ONNX Runtime QNN 1.24.4 NuGet package (SHA-256 checked; `-DCEMU_NPU_ORT_PACKAGE=<nupkg>` uses a local copy) and puts `cemu_npu.dll` and the runtime DLLs it loads in `bin/`. The ANVIL models and SPIR-V shaders are committed in `bin/npu`, so `bin/` is a complete runtime folder.

The module and its CPU contract tests also build on their own:

```
cmake -S dependencies/npu-cemu -B build-npu -G Ninja
cmake --build build-npu
ctest --test-dir build-npu
```

Off Windows ARM64 only the portable tests build.

## Runtime folder

| File | Source |
| --- | --- |
| `Cemu*.exe`, `cemu_npu.dll` | This build. Keep each EXE with the `cemu_npu.dll` built with it (module ABI). |
| `onnxruntime*.dll`, `Qnn*.dll`, `libQnnHtpV*Skel.so`, `libqnnhtpv*.cat` | ONNX Runtime QNN 1.24.4 NuGet package |
| `npu/1080p`, `npu/720p` | Committed models and shaders |
| `resources/ko/cemu.mo` | Cemu's Korean catalog with `i18n/npu/ko.po` merged in |
| `rpc-path.txt` | Optional. Pins `libcdsprpc.dll`; without it Cemu uses the copy in the installed Hexagon NPU driver |
| `npu/<profile>/cache` | Created on first start: the compiled QNN context. Delete it to force a rebuild |

## Startup cache

The first start compiles the model for the NPU and saves the result in `npu/<profile>/cache`. Later starts load it instead of compiling. The file name depends on the model, the QNN options, the ONNX Runtime/QNN files and the NPU driver, so changing any of them makes a new file. A saved context that fails to load is compiled again once. If compiling fails, or the folder cannot be written, the module uses the original model as before and later starts do not compile again; deleting the folder retries. `log.txt` shows the startup time, the RPC library and what the cache did, as `[NPU] Module startup ... ms; RPC library ...; QNN context ...`.

## Pair scheduling

Each source pair spends GPU preprocessing on Cemu's graphics queue before the single NPU runs it. A pair is admitted only if the NPU can finish it before its real frame is shown, predicted from the measured source interval, GPU input latency and NPU run time (`pair_admission.h`). Each slot's first job is not timed, because QNN registers the slot's buffers on its first Run. A pair let through after a long run of rejections replaces the estimates, so generation resumes quickly after a slow stretch. Skipped pairs count as `no_slot` in `[NPU-PERF]`. `test_npu_scheduling.cpp` compares this with the previous unconditional queue across frame rates, GPU delays, slow first runs, stutters and temporary NPU slowdowns.

## Toggle

Options → Hotkeys has "Toggle NPU frame generation", F9 by default, for the keyboard or a controller button. Cemu shows a short on/off notice when it changes.
