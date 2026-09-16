# TOTK Common BNVIB Analysis

Status: confirmed from user-owned extracted TOTK data
Branch: `diag/botw-sound-source-tracer`

## Source sample

Uploaded diagnostic archive:

- `TOTK_Common_BNVIB_extracted.zip`
- SHA-256: `20094dcac2e7f6bf93a4631150b050fcdc19d3a657056c88981d66b1c6b7205e`

The archive was extracted from TOTK `Common.bnvib.sarc.zs` and contains 46 `.bnvib` files plus a summary CSV/README.

Observed file types:

- 32 `Normal` (`0x04`)
- 14 `Loop` (`0x0C`)
- 0 `Loop + Wait` (`0x10`) in this sample set

All parsed files use:

- magic byte `0x03`
- stored sample-rate field `200`
- 4 bytes per vibration sample

CTCaer Joy-Con Toolkit treats the stored rate as `1000 / rate_field` milliseconds per sample, therefore `200` means **200 samples/sec = 5 ms/sample**.

## Confirmed BNVIB header layout

### Normal (`0x04`)

```text
0x00  u8   type = 0x04
0x04  u8   magic = 0x03
0x06  u16  rate field (LE)
0x08  u32  vibration-data byte size (LE)
0x0C       4-byte samples
```

### Loop (`0x0C`)

```text
0x00  u8   type = 0x0C
0x04  u8   magic = 0x03
0x06  u16  rate field (LE)
0x08  u32  loop start sample index (LE)
0x0C  u32  loop end sample index (LE)
0x10  u32  vibration-data byte size (LE)
0x14       4-byte samples
```

This matches SwitchBrew structural documentation and the actual uploaded files exactly.

## Most important result: the 4-byte sample is directly useful

CTCaer Joy-Con Toolkit source shows that a BNVIB sample is interpreted in this order:

```text
byte 0 = low-band amplitude
byte 1 = low-band frequency code
byte 2 = high-band amplitude
byte 3 = high-band frequency code
```

The toolkit reads the amplitude bytes as a linear normalized value (`byte / 255.0`) before converting them through the Joy-Con packet amplitude LUT.

For frequency, the BNVIB byte is the pre-packet logarithmic frequency code. The physical frequency can be recovered with the standard Switch relation:

```text
frequency_hz = 10 * 2^(frequency_code / 32)
```

This is independently sanity-checked by the included `Simple240Hz.bnvib`:

```text
sample bytes: FF 93 00 A1
low amplitude = 255 / 255 = 1.0
low frequency code = 0x93 = 147
10 * 2^(147/32) = 241.466 Hz
```

That is consistent with the file name `Simple240Hz`.

### Consequence for this project

BNVIB is **not** just a Joy-Con raw packet dump. It is a much better donor format for DualSense conversion:

```text
BNVIB sample
  -> normalized low amplitude
  -> physical low frequency
  -> normalized high amplitude
  -> physical high frequency
  -> DualSense renderer
```

We do not need to pass through Nintendo's Joy-Con amplitude-packet LUT unless reproducing Joy-Con transport itself. For DualSense, the BNVIB normalized amplitudes and decoded frequencies should be preserved directly as the source timeline.

## Common BNVIB inventory summary

Duration range in this set is roughly 20 ms to 4.915 s.

Notable files for the planned Haptic Explorer include:

### Very short / impact-like candidates

- `UiRollOver.bnvib` — 20 ms
- `PresetKott.bnvib` — 30 ms
- `WaveSquareUpShort.bnvib` — 30 ms
- `Simple240Hz.bnvib` — 50 ms
- `PresetZa_nvibEdit.bnvib` — 75 ms
- `PresetKott_nvibEdit.bnvib` — 125 ms
- `PresetZaZaFast_nvibEdit.bnvib` — 130 ms
- `PresetPetit_nvibEdit.bnvib` — 135 ms
- `PresetDott.bnvib` — 155 ms
- `PresetGyuru_nvibEdit.bnvib` — 155 ms
- `PresetNyo_nvibEdit.bnvib` — 155 ms
- `PresetDoka.bnvib` — 205 ms
- `PresetDon.bnvib` — 260 ms

### Longer one-shot candidates

- `PresetDoon.bnvib` — 580 ms
- `PresetKattan.bnvib` — 610 ms
- `PresetGatan_nvibEdit.bnvib` — 795 ms
- `PresetByeenS2_nvibEdit.bnvib` — 815 ms
- `PresetByeen.bnvib` — 930 ms
- `PresetBofuhn.bnvib` — 1000 ms
- `PresetPicakon.bnvib` — 1030 ms
- `PresetSpon.bnvib` — 1090 ms
- `PresetDoDon.bnvib` — 1185 ms
- `PresetDoonBiri.bnvib` — 1330 ms
- `PresetDohoon.bnvib` — 1345 ms
- `PresetSpicakon.bnvib` — 1470 ms
- `PresetBiyoon.bnvib` — 1515 ms
- `PresetDooon.bnvib` — 1905 ms

### Loop / texture candidates

- `UIFadeIn.bnvib`
- `PresetJiiiLv_nvibEdit.bnvib`
- `PresetJiriJiriLv.bnvib`
- `PresetBuBuBuLv.bnvib`
- `PresetDoDoDoLv.bnvib`
- `PresetGoGoGoFastLv.bnvib`
- `PresetGoroGoro.bnvib`
- `WaveBigBallRotateLv.bnvib`
- `PresetGohWithAttackLv.bnvib`
- `PresetGoGoGoLv.bnvib`
- `PresetGataGataLv.bnvib`

`PresetGohWithAttackLv.bnvib` is especially interesting by name because it appears intended as a repeating base texture with an attack/accent component, but semantic use must be confirmed by physical testing rather than inferred from the name alone.

## Frequency ranges observed in active samples

Across this Common set, active low-band frequencies are approximately:

- **128.84 Hz to 348.96 Hz**

Active high-band frequencies are approximately:

- **257.68 Hz to 388.88 Hz**

Several patterns intentionally use only one band:

- `Simple240Hz*`: low only
- `PresetBuBuBuLv`: low only
- `PresetDoDoDoLv`: low only
- `PresetGoGoGoLv`: low only
- `PresetJiiiLv_nvibEdit`: high only
- `PresetJiriJiriLv`: high only

This is useful for validating that a DualSense renderer preserves the character difference between low-only, high-only and dual-band effects.

## Duplicate observation

The only exact byte-for-byte duplicate in this 46-file set is:

- `PresetNyo_nvibEdit.bnvib`
- `PresetGyuru_nvibEdit.bnvib`

The explorer should therefore identify exact duplicates by SHA-256 and allow them to share one physical-test result while preserving both original names.

## Haptic Explorer direction

The preferred workflow is now:

```text
TOTK BNVIB library
        ↓
BNVIB parser / normalized timeline
        ↓
Haptic Explorer list
        ↓
[Play] on physical DualSense
        ↓
user experience tags + notes
        ↓
BOTW event candidate / confirmed mapping
        ↓
Cemu ARM64 runtime integration
```

The first Haptic Explorer should show at least:

- original path/name
- SHA-256
- Normal / Loop / LoopWait
- duration
- sample count
- loop range
- low/high amplitude graph
- low/high frequency graph
- Play / Stop
- strength scalar
- loop toggle/count
- automatic name-based candidate tags
- user feeling tags / memo
- BOTW target event
- mapping state: `unreviewed`, `auto-candidate`, `tested`, `confirmed`, `rejected`

### Mapping rule

File/path naming is the first automatic hint, but never the final authority.

Example:

```text
TOTK name/path -> automatic candidate
              -> physical DualSense playback
              -> human confirmation
              -> BOTW mapping
```

Original BNVIB data must remain unchanged. Per-BOTW strength or trimming belongs in mapping metadata, for example:

```json
{
  "botw_event": "Spear_SwingFast1",
  "source_bnvib": ".../PresetX.bnvib",
  "gain": 0.62,
  "status": "confirmed"
}
```

## External implementation reference

CTCaer `jc_toolkit` is useful as an implementation reference because it already:

- parses BNVIB normal/loop/loop-wait types;
- interprets the 4-byte BNVIB sample fields;
- converts BNVIB amplitude/frequency values into Joy-Con raw rumble packet data;
- supports gain, frequency/pitch adjustment and physical BNVIB playback.

The project is MIT licensed. Reuse should still be limited to the minimal formulas/data structures needed, with attribution where source is copied rather than independently reimplemented.

## Next implementation step

Do **not** start by embedding these 46 files into Cemu.

First build a standalone `Haptic Explorer` / decoder against this Common sample set and physically validate:

1. `Simple240Hz.bnvib` as a known-frequency reference.
2. one low-only loop.
3. one high-only loop.
4. one short impact.
5. one dual-band long effect.

Only after the renderer has a consistent physical interpretation should BOTW semantic mapping begin.
