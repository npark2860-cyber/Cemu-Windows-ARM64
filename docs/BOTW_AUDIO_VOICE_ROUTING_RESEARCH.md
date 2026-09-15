# BOTW / Wii U Audio Voice Routing Research

Status: source-level feasibility confirmed; BOTW-specific voice identification not yet tested
Branch: `diag/botw-haptic-state-logger`
Branch HEAD before this research write: `58fe3d6e5b666ee765cafaf93b387ee0e92e0280`

## Question

Can an existing Wii U game's individual sounds be separated before the final TV mix and selectively sent to the GamePad / DualSense speaker instead of attempting post-mix audio separation?

## Conclusion

Yes. The Wii U AX audio model already has per-voice device routing, and Cemu preserves it.

This is substantially better than trying to split a final stereo mix. Individual AX voices can carry independent mix state for TV and DRC (GamePad), and Cemu's mixer uses those device-specific fields when building the two final outputs.

Therefore the preferred BOTW experiment is:

`BOTW sound -> AX voice -> identify target voice -> preserve TV mix and optionally add/replace DRC mix -> existing Cemu GamePad audio -> DualSense speaker`

No AI source separation and no new PCM transport are required for the USB path.

## Cemu source findings

### Separate devices are first-class AX concepts

`src/Cafe/OS/libs/snd_core/ax.h` defines:

- `AX_DEV_TV = 0`
- `AX_DEV_DRC = 1`
- `AX_DEV_RMT = 2`

### Routing is per AX voice

`src/Cafe/OS/libs/snd_core/ax_voice.cpp` implements:

`AXSetVoiceDeviceMix(AXVPB* vpb, sint32 device, sint32 deviceIndex, AXCHMIX_DEPR* mix)`

For TV voices it selects `internal->deviceMixTV` / `deviceMixMaskTV`.
For DRC voices it selects `internal->deviceMixDRC` / `deviceMixMaskDRC`.

The internal voice representation in `ax_internal.h` stores separate device mix masks and mix arrays for TV and DRC.

### Cemu mixes TV and DRC independently

`src/Cafe/OS/libs/snd_core/ax_mix.cpp` reads `deviceMixMaskDRC` separately while mixing voices.
`src/Cafe/OS/libs/snd_core/ax_ist.cpp` maintains separate TV and DRC output/final-mix buffers.

This proves that the split occurs before final output and is not merely a duplicated post-mix stream.

## Existing Cemu Audio Debugger is useful

Cemu already contains `AudioDebuggerWindow` (`Debug -> View audio debugger`). It is an `AX voice viewer` and refreshes active voices every 100 ms.

It already exposes per active voice:

- voice index
- playback state
- format (`adpcm`, `pcm16`, `pcm8`)
- sample base address
- current / loop / end offsets
- voice volume and delta
- SRC ratio
- LPF / biquad state
- a `deviceMix` column

Important limitation: the current `deviceMix` display is built from `internal->deviceMixTV`; it does not currently expose DRC mix in a separate column.

That means we already have most of the diagnostic infrastructure needed. A minimal diagnostic extension can add TV/DRC columns and logging rather than creating another unrelated reverse-engineering system.

## External Wii U precedent

Homebrew Wii U code uses `AXSetVoiceDeviceMix` directly to route the same voice independently to `AX_DEVICE_TYPE_TV` and `AX_DEVICE_TYPE_DRC`. Public SDL Wii U work also documents separate TV/DRC mix arrays and per-channel routing. This matches Cemu's emulated API design.

## Cheapest BOTW identification experiment

Do not start by scanning BOTW RAM.

1. Extend the existing Audio Debugger to show both TV and DRC device mix state.
2. Add optional transition logging for AX voices: voice index, sample base, format, offsets, TV mix, DRC mix, start/stop time.
3. In a quiet BOTW scene, perform one controlled action repeatedly, e.g. exactly one bow draw/release.
4. Compare voices that appear only during the repeated action.
5. Re-run with the same action to see whether sample base / offset ranges are stable enough to fingerprint that sound or sound group.
6. Only after a candidate is stable, test routing that candidate to DRC while preserving TV output.

Potential stable identifiers include sample base plus format/end range; voice index alone should not be treated as stable because AX voices can be reused.

## Routing strategies

### Duplicate

Keep original TV mix and additionally apply DRC mix to the selected voice.

Result:

`selected original BOTW effect -> TV + DualSense speaker`

This is the safest first experiment because it does not remove anything from the original mix.

### Move

Mute/remove the selected voice from TV and enable its DRC mix.

Result:

`selected original BOTW effect -> DualSense speaker only`

This is more invasive and should be attempted only after duplicate routing is proven.

## Important BOTW distinction

BOTW apparently does not normally author many GamePad-speaker-specific effects in standard TV play. That does not prevent us from using the Wii U audio architecture for enhancement.

The key opportunity is that Cemu already sees BOTW's individual AX voices before they are mixed. We can potentially route selected original BOTW sound voices to the DRC/DualSense output without synthesizing replacement WAV files.

## Decision

Per-voice TV/DRC separation feasibility: **CONFIRMED at the Wii U/Cemu audio-engine level**.

BOTW-specific stable voice fingerprints: **NOT YET CONFIRMED**.

Next lowest-cost work is to reuse/extend Cemu's existing Audio Debugger, not to implement post-mix source separation and not to start with broad game-state reverse engineering.
