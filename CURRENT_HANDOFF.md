# CURRENT HANDOFF — [Test] Generic GraphicPack Adaptive Trigger v1

GitHub is the only source of truth.

Branch: `test/se-fingerprint-index-v1`

Last runtime-validated prototype:
- code HEAD `63172d8a28e773cabbf14220e440823bd441a428`
- run `35443550198`
- bow tension PASS
- moving-aim lifecycle incomplete

The BOTW-specific Cemu-core prototype is being replaced.

Generic design:
`GX2SwapScanBuffers -> GraphicPack frame callback -> state 0..100 -> generic DualSense trigger output`

Cemu owns only:
- `.callback frame <functionSymbol>`
- `.adaptiveTrigger <right|left> bow <stateSymbol> [startZone]`
- state 0 = off, 1..100 = tension percent
- DualSense output

BOTW-specific addresses, equipped-bow lookup and bow mapping live only in:
`enhanced_sound_policies/BreathOfTheWild/EnhancedSoundExperience/patch_AdaptiveTrigger.asm`

The pack does not overwrite a BOTW instruction hook, so it avoids the known FPS++ frame-hook address collision.

The old sound-route adaptive trigger path is removed. Enhanced Sound, BNVIB, headset routing, CPU/Vulkan and fingerprint indexing are preserved.

Validation: implementation/build/runtime validation pending.

## Runtime finding — repeated bow shots

User runtime test found:
- equipping a bow produces the expected tension once;
- after one pull/fire cycle, subsequent shots lose trigger tension until another state change.

Cause:
- generic service only resent `SetBow22` when the GraphicPack state revision changed;
- the same equipped bow keeps the same 0..100 state, so the trigger effect was not re-armed after a completed pull/release cycle.

Fix:
- keep the GraphicPack state contract unchanged;
- poll DualSense trigger analog at 8 ms while the service is active;
- after a pull crosses 0.25 and returns to <= 0.05, resend the same `SetBow22` effect;
- no BOTW-specific logic added to Cemu.
