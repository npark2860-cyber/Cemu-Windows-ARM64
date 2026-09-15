# DualSense Audio Physical Validation

Status: USB PCM transport PASS; fresh-connection speaker routing still to validate
Branch: `diag/botw-haptic-state-logger`

## Confirmed observation

On the user's physical DualSense over USB:

1. Initially, with DSX not running, the controller speaker was silent.
2. Starting DSX caused the controller speaker to produce audio.
3. DSX was then closed.
4. Cemu was launched after DSX had been closed.
5. Cemu audio played normally through the DualSense internal speaker.

This confirms that DSX is **not** required as the ongoing PCM transport once the controller speaker path has been activated.

## Confirmed architecture

The USB audio path is physically validated:

`Wii U DRC/GamePad audio -> Cemu g_padAudio -> Windows audio backend -> DualSense USB audio endpoint -> DualSense internal speaker`

Therefore Cemu's existing GamePad audio pipeline should be preserved. A separate custom PCM engine is not needed for the USB baseline.

## Remaining unknown

The only remaining Stage 1 USB-audio question is what initialization is required after a fresh DualSense connection.

Most likely:

- DSX sends a HID audio-routing / speaker-enable command and usable speaker volume;
- that state remains latched in the controller after DSX exits.

Still possible:

- a DSX background component remains active;
- Windows retains a route state beyond the foreground DSX process.

## Next minimum test

1. Fully close DSX.
2. Disconnect the DualSense USB cable or fully power-cycle the controller.
3. Reconnect by USB.
4. Do not launch DSX.
5. Launch Cemu with Wii U GamePad audio assigned to the DualSense endpoint.
6. Check whether the controller speaker is already active.

Interpretation:

- Silent after reconnect, then works after one DSX launch: speaker-route initialization is the missing step.
- Already works after reconnect without DSX: investigate persistent Windows/controller state or a DSX background component.

## Gamepad-Core match

Pinned Gamepad-Core already exposes `DualSenseSettings(...)` with separate `bIsHeadset` and `bIsSpeaker` controls. Its implementation selects speaker mode when `bIsHeadset == 0 && bIsSpeaker == 1`, and its HID output buffer uses a distinct speaker audio-mode value.

If the reconnect test confirms route reset, the cheapest native implementation is a one-time speaker-route/volume initialization on DualSense connect/reconnect, while Cemu continues to own PCM transport.

## Decision

- USB Cemu -> DualSense speaker PCM transport: **PASS**.
- DSX: diagnostic A/B reference only.
- Target runtime: fully native ARM64 with no DSX dependency.
- Do not replace Cemu's existing DRC audio pipeline.
