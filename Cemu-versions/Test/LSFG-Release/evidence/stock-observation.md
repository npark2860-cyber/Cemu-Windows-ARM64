# Stock Release baseline observation

- Executable: copied from `C:/Emulators/Cemu_arm64/Cemu.exe`.
- SHA-256: `d2d77ee6961d9f834740ae450653a9f9235da27f43f3b82ed35ca7b2acc56abb`.
- Log identifies build `d359c53`, Vulkan on Adreno X1-85.
- BOTW JP v208 base, update and DLC mounted. Log confirms save path is inside this test's portable MLC.
- Native window observation showed actual outdoor gameplay: Link beside a shrine, scene and HUD visible. Instantaneous FPS readings were about 34–36; this is not a performance benchmark.
- Normal close requested with Alt+F4 through the computer-use API. Process exited with code 0 after 83.91 seconds. No watchdog or forced termination was used.
- Result: short launch, rendering and graceful-exit smoke check PASS. Long-duration stability, LSFG OFF/ON, image quality and pacing remain NOT RUN.
