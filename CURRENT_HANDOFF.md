# CURRENT HANDOFF — [Test] Clean Release+SE + Haptics + Raw Trigger

GitHub is the only source of truth.

Branch:
`test/se-fingerprint-index-v1`

Baseline composition:
- Release+SE source baseline: `240b52c853f3d8a7b111c74dd95277ba50866204`
- BNVIB haptic baseline: `cbe7a835441ec112fc829088b87d6daad74430a9`
- Generic adaptive-trigger transport only.

Hard boundary:
- Cemu contains no BOTW addresses, actor IDs, bow database, attack->tension formula, aim/fire/reload state machine, or R2 polling.
- Cemu only watches a GraphicPack command word and forwards raw SetBow22 bytes when that word changes.
- GraphicPack owns all game-specific logic and all tension calculations.

Raw command word:
- bits 0..7 = SetBow22 StartZone byte
- bits 8..15 = SetBow22 SnapBack/force byte
- bits 16..31 = event sequence
- command 0 = trigger off

The event sequence exists only so a GraphicPack can resend the same tension for the next shot without changing the tension bytes.

No BOTW adaptive-trigger GraphicPack is bundled into this binary artifact.
