# BOTW Sound Resource Catalog for DualSense Routing

Status: research catalog
Branch: `diag/botw-haptic-state-logger`
Source of truth for Cemu state: repository branch/HEAD

## Why this matters

BOTW already exposes useful semantic grouping through its sound resources. Instead of identifying every sound from runtime voice addresses first, we can use known `.bars` group names and contained BFWAV names to narrow the target set, then validate a small number of candidates in Cemu's AX audio debugger.

Cemu graphic packs can also redirect files placed under a graphic pack `content/` directory to `vol/content/`, so modified BOTW `.bars` resources can be tested without altering the base game files.

## Primary public catalog sources

- `leoetlino/botw`, especially `Sound/ResourceList/BarslistInfo.yml`
- The Sounds Resource BOTW sound-effect dump, which preserves many original group/file names
- BOTW heap dump references showing `Sound/Resource/M_SceneStatic.bars` loaded in the audio heap
- ZeldaMods BOTW sound-modding documentation / BarsTool

The Sounds Resource dump is from the Switch build, but the naming is useful as a catalog; actual Wii U assets must still be validated before replacement because Wii U BFWAV encoding/sample rate differs.

## High-confidence targets

### Bow — highest-priority proof target

A particularly useful finding is that the generic bow draw/release sounds are grouped in:

`Sound/Resource/M_SceneStatic.bars`

Known contained names include:

- `Bow_Draw0`
- `Bow_Draw1`
- `Bow_Draw2`
- `Bow_Draw3`
- `Bow_Draw4`
- `Bow_Draw5`
- `Bow_Release1`
- `Bow_Release2`
- `Bow_Release3`
- `Bow_Release5`

This is better than starting from `Weapon_Bow_*` because the latter groups are heavily focused on equip/un-equip/material sounds.

Other bow-related groups:

- `Weapon_Bow_Wood.bars`
  - `Pl_Equip_Bow00/01/02`
  - `Pl_UnEquip_Bow00/01/02`
  - `Wood_Land1/2/3`
- `Weapon_Bow_Metal.bars`
  - metal equip/un-equip/land sounds
- `Weapon_Bow_071.bars`
  - `Weapon_Bow_071_hold`
- `Weapon_Bow_023.bars`
  - ancient/guardian bow-specific sounds

Arrow groups:

- `Arrow.bars`
- `AncientArrow.bars`
- `BombArrow_A.bars`
- `ElectricArrow.bars`
- `FireArrow.bars`
- `IceArrow.bars`
- `BrightArrow.bars`

Elemental/ancient arrow groups have explicit `Charge`, `Charge_Complete`, `Shoot`, `Head`, `Splash`, and related loop sounds. This makes them excellent later semantic-audio targets.

### Master Cycle Zero — strongest category isolation

`BarslistInfo.yml` maps `GameROMMotorcycle` to:

- `GameROMMotorcycle.bars`
- `D_GameROMMotorcycle.bars`
- `D_GameROMMotorcycle_Mt.bars`

The extracted sound catalog contains many uniquely named motorcycle signals, including:

- `MotorcycleEngine`
- `MotorcycleEngineIdling`
- `MotorcycleEngineOffThrottle`
- `Motorcycle_EngineStart*`
- `Motorcycle_EngineAdd*`
- `Motorcycle_ThrottleOff`
- `Motorcycle_ChassisSkidding`
- `Motorcycle_HitCrash`
- `Motorcycle_WheelieStartEngine`
- `Motorcycle_WheelLandFall*`
- terrain/water/friction loops

This category is ideal for later mapping to trigger/haptic state because the audio names already encode throttle, idle, skid, crash, jump and terrain state.

### Horse

`BarslistInfo.yml` maps normal horse actors to:

- `Horse.bars`
- `HorseBase.bars`

Known sounds include:

`Horse.bars`:

- `Horse_Move_Soothe00/01`
- `Horse_SpursWeak00..03`
- `Pl_HorseSpurs00`
- `Pl_HorseWldSpurs00`
- gear-change vocal cues
- multiple breath/snort/cry cues
- warp in/out cues

`HorseBase.bars`:

- `Horse_JumpWind`
- `Horse_ReinBridle01..03`
- `Horse_ShakeWithShoe00`
- eating sounds

Hoof/terrain-contact sounds may live in shared terrain/player resources rather than only these two groups, so do not assume `Horse.bars` contains every riding sound.

### Spear

Generic spear swing sounds are directly grouped in:

`Spear.bars`

Known entries:

- `Spear_Swing1..5`
- `Spear_SwingFast1..2`

Material/special variants are layered with groups such as:

- `Weapon_Spear_Metal.bars`
- `Weapon_Spear_Wood.bars`
- `Weapon_Spear_WoodWithMetal.bars`
- `Spear_Guardian.bars`

This is a clean candidate for the broad `spear` semantic category.

### Heavy / two-handed / blunt

BOTW's internal naming uses `Lsword` for the two-handed/heavy weapon family.

Useful groups:

- `LSword.bars`
  - `LSword_AttackCharging*`
  - `LSword_DownSwingAttackStart/End`
  - `LSword_Swing1..5`
  - `LSword_SwingFast1..5`
- `Weapon_Lsword_MetalHeavy.bars`
- `Weapon_Lsword_Axe.bars`
- `Weapon_Goron_Knuckle.bars`

This should cover much of the project's intended heavy/blunt category, though hammer-specific groups still need a targeted pass.

### Magic / elemental weapons

`Rod.bars` exists as a shared base and is referenced by elemental sword/rod actors.

Known mappings include:

- `Weapon_Sword_Fire` -> `Weapon_Sword_Fire.bars`, `Rod.bars`
- `Weapon_Sword_Ice` -> `Weapon_Sword_Ice.bars`, `Rod.bars`
- `Weapon_Sword_Elec` -> `Weapon_Sword_Elec.bars`, `Rod.bars`
- stronger variants such as Meteo / Blizzard / Voltage reuse these families

This is a strong basis for the broad `magic/elemental weapon` semantic category.

### Ascending currents / wind

`BarslistInfo.yml` contains dedicated resources such as:

- `AscendingCurrent_FlightTraining.bars`
- `AscendingCurrent_DLC_United.bars`
- `AscendingCurrent_InRemains.bars`
- `AscendingCurrent_PlayerKago.bars`
- `WindGenerator.bars`

These are useful later for Revali's Gale / updraft-related speaker+haptic effects, but the exact player-created updraft path still needs runtime confirmation.

### Climbing

Climbing has not yet been isolated to one high-confidence `.bars` group. There are relevant player/static cues such as `HoldOn_Stone01` in `M_SceneStatic.bars`, but climbing surface/contact audio may be distributed across player and terrain sound resources. Do not hard-code a climbing resource yet.

## Cemu-side confirmation

Cemu already keeps per-voice TV and DRC routing separately (`deviceMixTV`, `deviceMixDRC`) and mixes DRC independently.

Cemu's existing Audio Debugger already exposes active voice index, sample base, current/loop/end offsets, volume, format and TV `deviceMix`. The debugger should be extended to display DRC mix as well before runtime routing tests.

Graphic pack file replacement is confirmed in `GraphicPack2.cpp`: files under a pack's `content/` directory are redirected to `vol/content/`. Therefore a test resource can be packaged as:

`graphicPacks/<pack>/content/Sound/Resource/M_SceneStatic.bars`

without replacing the base game file.

## Cheapest proof sequence

### Proof A — resource identity only

Use `M_SceneStatic.bars` first.

1. Extract/inspect the Wii U `M_SceneStatic.bars`.
2. Confirm `Bow_Draw*` and `Bow_Release*` entries exist with the expected names.
3. Replace **one** release sound with an unmistakable short test tone while preserving Wii U BFWAV format/channel count/sample-rate requirements.
4. Install only that modified `.bars` through a graphic pack `content/Sound/Resource/` redirect.
5. Fire a normal bow once.

Pass condition: only the intended bow release cue changes.

This proves the file mapping without touching Cemu audio routing.

### Proof B — original sound to DRC

After Proof A:

1. Restore the original sound resource.
2. Identify the corresponding AX voice while firing the bow.
3. Enable/copy that voice's DRC mix while leaving the TV mix unchanged.
4. Route Cemu GamePad audio to the DualSense endpoint.

Pass condition: the original BOTW bow release is heard through the DualSense speaker while the TV sound remains intact.

### Proof C — move to graphic-pack PPC patch

Only after the Cemu-side forced DRC test is stable, determine whether the same routing change can be expressed as a BOTW PPC patch in the graphic pack. The preferred final BOTW solution is:

- resource replacement only where useful;
- PPC patch for semantic TV/DRC routing;
- minimal/no BOTW-specific hacks in Cemu core.

## Current best first target

`M_SceneStatic.bars -> Bow_Release1/2/3/5`

Reason:

- exact archive name is confirmed from BOTW heap data;
- exact inner sound names are publicly cataloged;
- bow release is short and easy to recognize;
- it maps directly to an intended DualSense trigger/haptic event;
- one-shot audio is easier to validate than continuous engine/terrain loops.

## Safety / compatibility notes

- Switch sound dumps are useful for names, not binary replacement files.
- Wii U BOTW BFWAV assets use Wii U format/sample-rate conventions; do not drop Switch WAV/BFWAV data directly into the Wii U game.
- Preserve original channel count and valid BARS metadata when replacing a BFWAV.
- Keep the first test to one sound only so any regression is attributable.
