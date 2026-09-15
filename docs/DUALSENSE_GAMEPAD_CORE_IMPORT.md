# DualSense Gamepad-Core import

Experimental integration branch: `exp/dualsense-gamepad-core-arm64`.

Upstream candidate: https://github.com/rafaelvaloto/Dualsense-Multiplatform

Goal: validate a native Windows ARM64 DualSense backend before touching Cemu's existing input/rumble path.

Integration policy:
- keep `main` untouched
- pin upstream revision
- validate standalone Windows ARM64 build first
- validate USB adaptive trigger + haptics
- validate Bluetooth separately
- only then wire into Cemu
