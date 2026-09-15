# BOTW Haptic State Logger

Branch: `diag/botw-haptic-state-logger`
Base: `1ec1f91977ebd2032178bf065730ed17a08ef243` (`exp/dualsense-gamepad-core-arm64`, USB output flag fix)

## Purpose

Find stable BOTW state signals for semantic DualSense haptics without attempting a full game reverse engineering pass.

Target vertical slice:

1. Bow
2. Horse
3. Master Cycle

## v0.1

The existing `Debug -> Logging window` is extended with a **Haptic State Logger** panel.

Controls:

- REC
- STOP
- Idle
- Bow
- Horse
- Master Cycle
- Combat

Sampling target: ~60 Hz (`16 ms` wx timer).

CSV fields:

- sample index
- elapsed time in ms
- Wii U title ID
- active action marker
- left stick X/Y
- right stick X/Y
- ZL/ZR analog values
- A/B/X/Y
- L/R
- ZL/ZR digital state
- Plus/Minus

Output directory:

`<Cemu user data>/haptic_diagnostics/`

## Test protocol

Use repeated A/B action blocks rather than long unstructured play sessions.

Suggested first session:

1. REC, Idle: 5 seconds standing still.
2. Bow: draw/hold/release a bow five times.
3. Idle: 5 seconds.
4. Horse: mount, stand, walk, trot, gallop, stop, dismount.
5. Idle: 5 seconds.
6. Master Cycle: mount, idle, accelerate, cruise, brake, dismount.
7. STOP.

## Next stage

v0.1 establishes synchronized human-labeled action windows and controller input timing.

v0.2 will use those windows to drive selective memory-diff candidate collection. It must not dump all guest RAM every frame.

v0.3 will apply watchpoints to the reduced candidate set and record the PPC writer/instruction path, allowing stable Cemu `HapticEvent` hooks to be derived.
