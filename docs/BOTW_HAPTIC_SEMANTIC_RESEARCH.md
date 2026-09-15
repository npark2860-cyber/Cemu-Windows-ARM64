# BOTW Semantic Haptic Research

Status: diagnostic research branch only
Branch: `diag/botw-haptic-state-logger`
Target: Breath of the Wild Wii U v208 / 1.5.0

## Principle

Do not begin with blind full-RAM scanning. Use public BOTW reverse-engineering to identify semantic game states first, then use known Wii U v208 PPC sites or narrowly targeted probes to correlate those states on real hardware.

The Switch decompilation is a semantic map only. Switch code/vtable addresses are not reused as Wii U addresses.

## Public semantic references

### zeldaret/botw

Relevant game-side semantic classes/actions:

- `uking::action::PlayerBow`
- `uking::action::PlayerRideHorse`
- `uking::ai::PlayerRideHorse`
- `uking::query::IsRideHorse`
- `uking::query::CheckPlayerRideHorse`
- `uking::action::MotorcycleRiddenByPlayer`
- `uking::ai::MotorcycleRoot`

Stable semantic factory hashes found in the decompilation:

- `PlayerBow`: `0xDD0DA107`
- `PlayerRideHorse`: `0x9762FDCE`
- `MotorcycleRiddenByPlayer`: `0x7EB5D4C9`

These hashes are useful identifiers for future signature/factory tracing, but are not guest code addresses.

### Horse game-data state

Public reverse-engineering also identifies live horse-related game-data keys, including:

- `Horse_IsRide`
- `Horse_ActiveIndex`
- `Horse_CurrentChargeNum`
- `Horse_CurrentExtraChargeNum`
- `Horse_IsOnChargePenalty`

`Horse_IsRide` is a high-value next target because it expresses the semantic state directly. The preferred next step is to locate the Wii U v208 GameData/query path for this key rather than scan all RAM.

## Wii U v208 PPC references from cemu-project/cemu_graphic_packs

BOTW v208 graphic-pack module match:

- `moduleMatches = 0x6267BFD0`

### Bow

Source: `BreathOfTheWild/Cheats/ArrowDrawSpeed/patch_ArrowDrawSpeed.asm`

Known v208 sites:

- `0x024A0164`
- `0x024A019C`
- related draw-speed constant: `0x100C0150`

These are known Bow draw-speed code paths and are used only as diagnostic semantic probes in v0.2.

### Master Cycle

Source: `BreathOfTheWild/Mods/FPS++/patch_MastercycleSpeed.asm`

Known v208 site:

- `0x0209FFC0`
- related boost-speed value: `0x100136B4`

This is a known Master Cycle speed path and is used as a diagnostic semantic probe in v0.2.

Other public Master Cycle v208 patch reference:

- Spawn eligibility: `0x02A32A30` (`MotorcycleAllRegions`) — useful as a reverse-engineering landmark, not as a ridden-state signal.

## Diagnostic strategy

### v0.1 — PASS

Human marker + VPAD input timeline.

Physical test CSV established that the logger reliably correlates markers with user input. Bow ZR rising edges matched the intended five test draws exactly.

### v0.2 — current

Use Cemu's existing non-pausing logging breakpoint mechanism on the public Wii U v208 PPC sites above.

CSV adds:

- BOTW title version
- Bow probe active/hit count/last-hit age
- Master Cycle probe active/hit count/last-hit age

The probe code is deliberately isolated to the diagnostic UI. No JIT, Vulkan, performance, or production haptic path is modified.

Expected validation:

1. Idle should not produce sustained Bow/Master Cycle hits.
2. Bow draw/hold/release should strongly correlate with Bow probe hits.
3. Master Cycle riding/acceleration should strongly correlate with Master Cycle probe hits.
4. If a probe has excessive false positives, it is only a landmark and must not be promoted to a semantic event.

### v0.3 candidate

Horse state first, using `Horse_IsRide` / `PlayerRideHorse` query or GameData access path.

Do not fall back to broad RAM scanning unless semantic/query/factory tracing fails.

## Final architecture target

The diagnostic probes are temporary. Once the semantic locations are established, replace breakpoint-based probes with a low-overhead event/state adapter:

`BOTW semantic state -> Cemu HapticEvent/HapticState -> Haptic mixer -> Native DualSense backend`

Target first vertical slice:

- Bow tension/release
- Horse gait/speed
- Master Cycle engine/acceleration
