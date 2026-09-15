# DualSense Audio Physical Validation

Status: physical test partially confirmed; routing persistence under test
Branch: `diag/botw-haptic-state-logger`

## Confirmed observation

On the user's physical DualSense over USB:

1. Initially, with DSX not running, the controller speaker was silent.
2. Starting DSX caused the controller speaker to produce audio.
3. After DSX was then closed, the controller speaker **continued producing audio**.

This is an important correction to the earlier interpretation. DSX does not appear to be required as a continuously running audio bridge once the speaker path has been activated.

The most likely explanations are now:

- DSX sends a DualSense HID audio-routing / speaker-enable state that remains latched in the controller after the DSX process exits; or
- a DSX-related background component remains active; or
- DSX changes a Windows/controller endpoint state that persists beyond the foreground app lifetime.

The next physical test must distinguish these cases.

## Next minimum test

1. Fully close DSX.
2. Disconnect the DualSense USB cable or power-cycle the controller.
3. Reconnect by USB.
4. Do **not** launch DSX.
5. Send a normal Windows test sound to the DualSense render endpoint.

Interpretation:

- If the speaker is silent after reconnect, but becomes active after one DSX launch and stays active after DSX exits, this strongly confirms a controller-side latched speaker-routing state.
- If the speaker is already active immediately after reconnect without DSX, investigate a persistent Windows/driver setting or a still-running DSX background service/component.

## Implication

The preferred implementation path remains:

`Cemu g_padAudio / XAudio2 PCM -> Windows DualSense USB audio endpoint`

with the native DualSense backend responsible only for the minimal speaker route / volume initialization needed after a fresh connection.

Do not replace Cemu's PCM pipeline unless this minimal route-control approach fails.

## Gamepad-Core match

Pinned Gamepad-Core already exposes `DualSenseSettings(...)` with separate `bIsHeadset` and `bIsSpeaker` controls. Its implementation selects speaker mode when `bIsHeadset == 0 && bIsSpeaker == 1`, and the HID output buffer uses a distinct speaker audio-mode value.

If the reconnect test confirms a latched controller-side route, the cheapest native implementation is likely a one-time initialization on DualSense connection/reconnection rather than continuous audio routing logic.

## Decision

DSX remains a diagnostic A/B reference only. The target runtime remains fully native ARM64 with no DSX dependency.
