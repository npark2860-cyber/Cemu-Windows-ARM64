# DualSense Native USB Speaker Init — Physical Validation

Status: PASS / CLOSED
Branch: `exp/dualsense-gamepad-core-arm64`
Validated commit: `638d19309f94acde70e9a0496c5a3bbe3027c25d`
CI: run `35084659609` — PASS

## What was tested

The ARM64 Haptic Lab was updated with a native DualSense USB speaker-route control using pinned Gamepad-Core.

The test path is:

`Gamepad-Core DualSenseSettings(...) -> internal speaker route/volume -> UpdateOutput() -> DualSense USB HID output`

The user physically tested the resulting ARM64 build on a DualSense over USB.

## Result

PASS.

The DualSense internal speaker route can be enabled natively without DSX. The user reported that the result worked successfully and that the controller-local audio produced a clearly different and much stronger spatial/physical impression than ordinary TV-only playback.

This closes the previous dependency on the diagnostic DSX initialization workaround.

## Confirmed architecture

- Cemu remains the PCM/audio owner.
- Windows USB audio endpoint remains the transport for DRC/GamePad PCM.
- Gamepad-Core only needs to initialize the DualSense speaker route/volume over HID on connect/reconnect.
- No separate custom PCM engine is needed for the USB speaker baseline.
- DSX is no longer required for speaker initialization in the target design.

## Do not retest unless regression

This native USB speaker-route proof is CLOSED. Do not repeat the basic route-enable experiment unless later integration changes cause a regression.

## Next integration target

Integrate the proven one-time speaker route/volume initialization into the Cemu-side DualSense connection/reconnection path, then combine it with BOTW semantic AX voice duplication so selected local sounds can be sent to DRC/DualSense while TV output remains intact for the first proof.
