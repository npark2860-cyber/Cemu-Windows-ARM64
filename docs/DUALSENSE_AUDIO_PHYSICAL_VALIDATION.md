# DualSense Audio Physical Validation

Status: physical test confirmed
Branch: `diag/botw-haptic-state-logger`

## Confirmed observation

On the user's physical DualSense over USB:

- With DSX not running, the controller speaker is silent.
- With DSX running, the controller speaker produces audio.

This strongly isolates the current failure to DualSense audio routing / output initialization rather than to Cemu's DRC PCM generation or to the physical speaker itself.

## Implication

The cheapest implementation path remains:

`Cemu g_padAudio / XAudio2 PCM -> Windows DualSense USB audio endpoint`

with the native DualSense backend responsible only for keeping the controller routed to the internal speaker and setting speaker volume.

Do not replace Cemu's PCM pipeline unless this minimal route-control approach fails.

## Gamepad-Core match

Pinned Gamepad-Core already exposes `DualSenseSettings(...)` with separate `bIsHeadset` and `bIsSpeaker` controls. Its implementation selects speaker mode when `bIsHeadset == 0 && bIsSpeaker == 1`, and the HID output buffer uses a distinct speaker audio-mode value.

Therefore the next minimal physical test is:

1. DSX fully closed.
2. Native Haptic Lab / DualSense backend sends speaker-route ON and a non-zero speaker volume.
3. Call `UpdateOutput()`.
4. Play a normal Windows test sound to the DualSense render endpoint.
5. If audio is heard, mark native speaker routing PASS and integrate the same initialization into Cemu.

## Decision

DSX is now a diagnostic A/B reference only. The target runtime remains fully native ARM64 with no DSX dependency.
