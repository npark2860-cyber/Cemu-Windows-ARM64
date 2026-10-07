# NPU v1 failure and v2 preparation

2026-09-29. User observed almost no NPU utilization while running Cemu-npu-exp-v1.

Observed game log snapshot: `cemu-npu-v1-startup-failure-20260929-104104.log`.

- 10:30:50.701: `Startup unavailable: Exception during initialization: No mapping for the Unicode character exists in the target multi-byte code page.`
- NPU submissions, completions, and runs stayed zero. NPU toggle was reset OFF by the error path.
- Actual swapchain extents included 1429x992 and 2560x1440, both unsupported by v1's fixed 1920x1080 output gate.

The module provided a UTF-8 absolute `backend_path` to ORT QNN 1.24.4. The Windows QNN loader constructs `std::filesystem::path(char*)`; for an absolute name it calls `LoadLibraryExA`. The same UTF-8 Korean absolute path raises exactly the logged exception when constructed with this machine's ACP 949. The native CPU regression reproduced this in `npu-path-cpu-tests-v2.log` (7 passing checks, no GPU/NPU execution).

Primary source: https://github.com/microsoft/onnxruntime/blob/v1.24.4/onnxruntime/core/providers/qnn/builder/qnn_backend_manager.cc#L2094-L2112

v2 verifies that the loaded ORT DLL belongs to the experiment runtime directory and that QnnHtp.dll is beside it, then supplies the ASCII basename. ORT's relative-name branch builds a wide absolute path from its own runtime directory and uses LoadLibraryExW. Model loading retains a wide path. No global working-directory/PATH/code-page mutation is required. Per-stage initialization error messages and on-screen failure notifications were added.

User then requested 1080p processing scaled to 1440p. v2 keeps the model/history/tensors at 1920x1080. GPU capture scales 2560x1440 to 1920x1080; both buffered real and generated images scale back to 2560x1440 with linear filtering. Every blit uses the actual source/destination image dimensions; the format must support linear filtering. Overlay rendering stays after image scaling. OFF returns the original output. This approach may reduce sharpness compared with native 1440p real frames and does not automatically lower the game's render resolution.

Build/CPU verification:

- CemuBin Release ARM64 incremental build exit 0.
- Native ARM64 module and headless module probe built.
- Unicode regression 7 checks passed; buffered timeline 17 checks passed.
- Diagnostics-free Release source guard passed; git diff --check passed.
- Separate v2 manifest pins 48 package files, model, RPC and device drivers.
- v1 package verification still passes; GPU LSFG baseline SHA256 remains ced1fa7b1291dd29fec78188165651634e6e8a9a07025afc2904e35b63737504.

At preparation time no v2 Cemu/GPU/NPU process had been started. A device time slot was requested for the headless module initialization/OFF-zero-runs/actual-inference smoke check. That result, if run, belongs in a separate timestamped session record; it does not validate game quality or scaled presentation.
