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

These hashes are useful identifiers for signature/factory tracing, but are not guest code addresses.

The public decompilation defines `ActionFactory` as a hash followed by a create-function pointer. On Wii U both fields are 32-bit, so a future diagnostic can resolve these three factory entries by looking for the exact CRC32 hashes and validating the adjacent executable guest pointer. This is a deterministic signature lookup, not behavioral full-RAM scanning. From the resolved factory/constructed object we can work toward the Wii U vtable and the exact `enter_` / `leave_` methods.

### Horse game-data state

Public reverse-engineering identifies live horse-related game-data keys, including:

- `Horse_IsRide`
- `Horse_ActiveIndex`
- `Horse_CurrentChargeNum`
- `Horse_CurrentExtraChargeNum`
- `Horse_IsOnChargePenalty`

`Horse_IsRide` is a high-value next target because it expresses the semantic state directly. Public save-format data gives its GameData hash as decimal `1962685922`, i.e. `0x74FC35E2`.

The preferred next step is to locate the Wii U v208 GameData/query path for this exact key/hash rather than scan all RAM for values. A second deterministic option is to locate the literal `Horse_IsRide` string in the loaded RPX data, find PPC references to it, and trace the handle initialization/read path.

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

The diagnostic logging breakpoint writes the PPC LR to Cemu `log.txt` for every hit. The physical v0.2 test should therefore preserve both the CSV and `log.txt`: the CSV establishes time/state correlation, while the LR values provide direct caller landmarks for narrowing the real Wii U functions.

The probe code is deliberately isolated to the diagnostic UI. No Vulkan or production haptic path is modified. Breakpoint probing is temporary diagnostic instrumentation and must not become the final runtime haptic implementation.

Expected validation:

1. Idle should not produce sustained Bow/Master Cycle hits.
2. Bow draw/hold/release should strongly correlate with Bow probe hits.
3. Master Cycle riding/acceleration should strongly correlate with Master Cycle probe hits.
4. If a probe has excessive false positives, it is only a landmark and must not be promoted to a semantic event.
5. Compare repeated LR values in `log.txt` to find stable Wii U caller functions.

### v0.3 candidate

Priority order:

1. Resolve action-factory entries from the exact semantic hashes above and use them to map Wii U action/vtable functions.
2. Resolve Horse state through `Horse_IsRide` (`0x74FC35E2`) / `PlayerRideHorse` query or GameData access path.
3. Replace coarse Bow/Master Cycle landmark probes with exact Action `enter_` / `leave_` or equivalent state functions.

Do not fall back to broad RAM scanning unless semantic/query/factory tracing fails.

## Final architecture target

The diagnostic probes are temporary. Once the semantic locations are established, replace breakpoint-based probes with a low-overhead event/state adapter:

`BOTW semantic state -> Cemu HapticEvent/HapticState -> Haptic mixer -> Native DualSense backend`

Target first vertical slice:

- Bow tension/release
- Horse gait/speed
- Master Cycle engine/acceleration
