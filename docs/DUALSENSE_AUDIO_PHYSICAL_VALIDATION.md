# DualSense Audio Physical Validation

Status: USB PCM transport PASS; fresh-connection speaker route reset CONFIRMED
Branch: `diag/botw-haptic-state-logger`

## Confirmed observation

On the user's physical DualSense over USB:

1. Initially, with DSX not running, the controller speaker was silent.
2. Starting DSX caused the controller speaker to produce audio.
3. DSX was then closed.
4. Cemu was launched after DSX had been closed.
5. Cemu audio played normally through the DualSense internal speaker.
6. The DualSense was then disconnected/reconnected by USB with DSX not launched.
7. After the fresh USB connection, Cemu audio was again silent on the controller speaker.

This physically confirms that DSX is **not** required as the ongoing PCM transport, but it does perform an initialization that enables/routes audio to the DualSense internal speaker. That route state survives DSX process exit but is reset by a fresh controller connection.

## Confirmed architecture

The USB audio path is physically validated:

`Wii U DRC/GamePad audio -> Cemu g_padAudio -> Windows audio backend -> DualSense USB audio endpoint -> DualSense internal speaker`

Therefore Cemu's existing GamePad audio pipeline should be preserved. A separate custom PCM engine is not needed for the USB baseline.

The missing native behavior is now isolated to connection-time DualSense speaker initialization.

## Native implementation target

On each DualSense USB connection/reconnection:

1. select internal speaker routing;
2. set a usable non-zero speaker volume;
3. submit the DualSense output state once (and again only if required by later hardware validation).

Cemu continues to own all PCM transport.

The likely Gamepad-Core path is its existing `DualSenseSettings(...)` support with `bIsHeadset = 0`, `bIsSpeaker = 1`, a non-zero `AudioVolume`, followed by `UpdateOutput()`.

A minimal Haptic Lab test should validate this without DSX before production integration.

## Decision

- USB Cemu -> DualSense speaker PCM transport: **PASS**.
- Speaker route reset on fresh USB connection: **CONFIRMED**.
- Missing component: **one-time native speaker route/volume initialization on connect/reconnect**.
- DSX: diagnostic A/B reference only.
- Target runtime: fully native ARM64 with no DSX dependency.
- Do not replace Cemu's existing DRC audio pipeline.
