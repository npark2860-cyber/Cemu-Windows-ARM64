# CURRENT HANDOFF — [Test] Generic GraphicPack Adaptive Trigger v1

GitHub is the only source of truth.

Branch: `test/se-fingerprint-index-v1`

Last runtime-validated prototype:
- code HEAD `63172d8a28e773cabbf14220e440823bd441a428`
- run `35443550198`
- bow tension PASS
- moving-aim lifecycle incomplete

Generic separation rule:
`GraphicPack game state -> generic haptic request -> DualSense output`

Cemu binary owns only generic haptic/trigger transport:
- `.callback frame <functionSymbol>`
- `.adaptiveTrigger <right|left> bow <stateSymbol> [startZone]`
- state 0 = off, 1..100 = tension percent
- generic DualSense `SetBow22` output

Cemu binary must NOT contain:
- BOTW addresses, actor IDs, weapon tables
- aim/fire/release detection
- physical R2 polling for bow lifecycle
- BOTW-specific re-arm state machines

BOTW-specific state detection and bow mapping live only in:
`enhanced_sound_policies/BreathOfTheWild/EnhancedSoundExperience/patch_AdaptiveTrigger.asm`

## Runtime finding — repeated shots

Observed:
- first equipped-bow tension works;
- subsequent shots lost tension.

Cause:
- generic output deduplicated an unchanged 0..100 GraphicPack value, so identical persistent haptic requests were not resent.

Correction:
- do not inspect R2 in Cemu;
- every non-zero GraphicPack frame request refreshes the same generic `SetBow22` output;
- zero still means stop/off.

This preserves the architectural boundary: GraphicPack owns gameplay; Cemu owns only generic haptic transport.
