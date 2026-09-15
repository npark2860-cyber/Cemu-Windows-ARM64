# DualSense Gamepad-Core import

Experimental integration branch: `exp/dualsense-gamepad-core-arm64`.

Upstream: https://github.com/rafaelvaloto/Dualsense-Multiplatform
Pinned revision: `9a16b81604fd711db3c445e8a8108e2b570f6477` (2026-09-10)
Integration path: `dependencies/Gamepad-Core`

## Status

- Gamepad-Core imported as a pinned git submodule.
- Existing Cemu submodule entries preserved.
- Standalone Windows ARM64 configure: PASS.
- Standalone `GamepadCore` static library build: PASS.
- Validation run: `34969683425` / job `104382726986`.
- Cemu input/rumble code has not been modified yet.

## Integration policy

- keep `main` untouched
- keep upstream revision pinned
- validate USB adaptive trigger + haptics before Cemu integration
- validate Bluetooth separately
- only then wire the backend into Cemu
