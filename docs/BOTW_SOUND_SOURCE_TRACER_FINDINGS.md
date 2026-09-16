# BOTW Sound Source Tracer Findings

Status: active diagnostic record
Branch: `diag/botw-sound-source-tracer`
Source of truth: repository branch/HEAD + physical CSV logs

## Purpose

This document records the findings that led from the original AX voice viewer to the current BOTW sound-source tracer and defines the next tracer architecture.

The target is not merely to list active AX voices. The useful output is:

```text
timestamp -> AX voice -> original BOTW sound resource -> track/cue name -> TV/DRC route
```

That output allows a player action such as a sword swing, Link vocalization, damage reaction, horse action, or Master Cycle state to be identified from one controlled in-game reproduction instead of manually searching sound archives.

## Confirmed runtime findings

### v1 — FS range to AX voice correlation

The first tracer recorded sound-resource file opens/reads and correlated the resulting Wii U virtual-memory ranges with AX sample-base addresses.

Confirmed working examples included resource/track identification such as weapon equip/un-equip sounds.

Limitation: many short runtime effects were copied out of the original BARS read buffer into separate audio heaps such as `0xAA...`, so direct address-range matching lost the source identity.

### v2 — copied BFWAV fingerprint recovery

v2 parsed BARS/BFWAV channel data after successful FS reads, stored fingerprints of the original encoded sample bytes, and matched later AX sample buffers against those fingerprints.

This proved that copied sample buffers can be traced back to the Nintendo-authored BARS resource and track even when the runtime address no longer overlaps the original FS destination.

Confirmed examples from physical BOTW logs included:

- `Spear.bars`
  - `Spear_Swing1`
  - `Spear_Swing2`
  - `Spear_SwingFast1`
- `LSword.bars`
  - `LSword_Swing1` and later additional swing/charge variants
- `ReactionHit.bars`
- `GameROMMotorcycle.bars`
- `Horse.bars`
- player movement/landing cues

At this point `ReactionHit.bars`, previously only a candidate name, became runtime-confirmed.

### v3 — blank-track recovery and fragmented BARS reads

v3 added two important fixes:

1. If a BARS path was known but `track_name` was blank, the tracer retried fingerprint matching constrained to the already-known BARS path.
2. If a BARS archive arrived across multiple FS reads, the tracer accumulated the ranges and registered the logical archive once sufficient data was present.

The physical v3 log showed that every `start` event for which a BARS path was resolved also received a track name in that test session. Important examples included:

- `ReactionHit.bars`: resolved track names
- `Weapon_Sword_Metal.bars`: resolved track names
- `Horse.bars`: resolved track names
- `GameROMMotorcycle.bars`: resolved track names
- `Spear.bars`: swing variants resolved
- `LSword.bars`: swing/charging variants resolved

Therefore the specific v2 defect "BARS path known but track name blank" is considered closed unless a regression appears.

## Remaining unexplained voices after v3

A large remaining class of AX voices has neither `bars_path` nor `track_name`.

This is no longer primarily a BARS track-parser problem. The important question is how those resources enter memory.

Several repeatable sample addresses appeared tightly synchronized with weapon attacks, for example values such as:

```text
0xa9f64a20
0xaa189660
0xaa5b1c60
```

These are useful fingerprints, but their semantic identity must not be inferred solely from timing.

## Linkle mod finding — PlayerVoice is inside TitleBG.pack

A local Linkle mod archive was analyzed as a diagnostic/reference sample. No third-party audio assets are committed to this repository.

Verified archive hashes for reproducibility:

```text
BreathOfTheWild_Linkle.zip
SHA-256 ae9cb068fc2f3e71347d6b151e8076301cc04e03ee5e3ec35d17c1b4843d0a83

BreathOfTheWild_LinkleMod/content/Pack/TitleBG.pack
SHA-256 ebb2e9681de9aac5991cfb6d2a10f1025bdc5c0d73a7f16a32b4fee775af1b64

TitleBG.pack::Sound/Resource/PlayerVoice.bars
SHA-256 8aed11b65f4523636152343e921ff88e6f08fe0391291d30a63f4503ebc7dc09
```

The pack is a SARC archive. It contains 410 entries, including 35 `.bars` resources.

Most importantly:

```text
BreathOfTheWild_LinkleMod/content/Pack/TitleBG.pack
└─ Sound/Resource/PlayerVoice.bars
```

`PlayerVoice.bars` details from the analyzed sample:

- size: 2,336,032 bytes
- BARS track count: 267
- all 267 AMTA names parsed successfully
- all names follow the `PVxxx_xx` form
- example names include `PV507_01`, `PV001_00`, `PV500_02`, `PV305_00`

This confirms that Player Voice data can be embedded inside a pack rather than opened as a standalone filesystem `.bars` file.

Other BARS resources found in the same `TitleBG.pack` include examples such as:

- `Arrow.bars`
- `AncientArrow.bars`
- `BombArrow_A.bars`
- `ElectricArrow.bars`
- `FireArrow.bars`
- `IceArrow.bars`
- `BrightArrow.bars`
- `ExpressionSound.bars`
- `PlayerShockWave.bars`
- `M_SceneStatic.bars`
- multiple Event BARS resources

## Why v1-v3 could not identify PlayerVoice.bars

The current tracer's filesystem catalog starts from files opened/read through Wii U FS APIs and treats `.bars`, `.bfwav`, and `.bfstp` paths as direct source resources.

For packed resources the real load chain is instead:

```text
FSOpen / FSRead: /Pack/TitleBG.pack
        ↓
SARC parser / resource manager
        ↓
Sound/Resource/PlayerVoice.bars
        ↓
embedded BFWAV
        ↓
runtime audio heap copy
        ↓
AX voice
```

Therefore `PlayerVoice.bars` itself never needs to appear as an FS open path. A tracer that only catalogs standalone sound files cannot discover it, even though its samples later reach AX correctly.

This explains why physical v3 sessions could produce repeatable unidentified attack-synchronized voices while logging zero standalone `PlayerVoice.bars` opens.

## v4 design — packed SARC/BARS discovery

The next tracer revision should extend source discovery rather than further modifying AX matching.

Target pipeline:

```text
FS read of *.pack / known SARC
    ↓
detect SARC magic
    ↓
parse SFAT/SFNT entries
    ↓
locate embedded Sound/Resource/*.bars entries
    ↓
register embedded BARS with existing BARS/BFWAV fingerprint catalog
    ↓
AX sample fingerprint match
    ↓
source path + track name
```

Preferred diagnostic path format:

```text
/vol/content/Pack/TitleBG.pack::Sound/Resource/PlayerVoice.bars
```

Expected final output example:

```text
event=start
voice=<AX index>
sample_base=<runtime heap address>
bars_path=/vol/content/Pack/TitleBG.pack::Sound/Resource/PlayerVoice.bars
track_name=PV305_00
```

The existing v2/v3 sample fingerprint code should be reused. v4 should only add a new catalog source for packed BARS and avoid creating a second independent sound matcher.

## v4 implementation requirements

- Detect SARC safely from completed pack reads.
- Support big-endian SARC used by Wii U resources.
- Parse SARC header, SFAT nodes, SFNT names, and data offsets with strict range validation.
- Enumerate embedded `.bars` entries without copying the entire pack when the data is already contiguous and accessible.
- Feed each complete embedded BARS region into the same BARS/BFWAV fingerprint registration used by standalone files.
- Preserve the parent pack path in the diagnostic source name.
- Keep ambiguity handling conservative: if the same fingerprint resolves to multiple semantic sources, leave it unresolved instead of guessing.
- Bound cached pack/catalog state so normal gameplay cannot grow diagnostic memory indefinitely.
- Keep this feature on the diagnostic branch until physical validation is complete.

## v4 physical pass conditions

The first proof should be deliberately narrow.

1. Delete the previous `botw_sound_source_trace.csv` before testing.
2. Boot BOTW with the v4 tracer.
3. Reproduce clearly audible Link voice actions several times, separated by idle gaps.
4. Confirm that at least one previously source-less AX voice resolves through `TitleBG.pack` to `PlayerVoice.bars` and a `PVxxx_xx` track.
5. Repeat with a weapon swing to verify that pack discovery does not regress already-resolved standalone BARS resources.

Primary PASS condition:

```text
runtime AX voice -> TitleBG.pack::Sound/Resource/PlayerVoice.bars -> PVxxx_xx
```

Once that is demonstrated on the physical Wii U BOTW build running in Cemu ARM64, Player Voice source identification can be considered solved for the DualSense-routing project.

## Architectural consequence

The tracer should now be thought of as a generic source correlator with multiple catalog inputs:

```text
standalone FS BARS ─┐
                    ├─> common BARS/BFWAV fingerprint catalog -> AX voice
SARC/pack BARS ─────┘
```

This is preferable to special-casing `PlayerVoice.bars`. The same SARC path can recover other currently unidentified BOTW effects and will likely reduce the remaining `bars_path = blank` population substantially.

## Distribution / legal boundary

Do not commit or redistribute the Linkle audio assets, Nintendo BARS/BFWAV contents, or extracted `TitleBG.pack` resources. The repository should contain only tracer code, structural metadata, hashes, and user-generated diagnostic logs where appropriate.
