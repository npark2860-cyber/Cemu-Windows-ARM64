# NEXT ACTION — Generic GraphicPack Adaptive Trigger v1

Work only on `test/se-fingerprint-index-v1`. Do not create a branch.

Validation target:
1. Build the corrected generic haptic-refresh implementation once.
2. Runtime-test several consecutive shots without changing bows.
3. Verify first shot still has tension.
4. Verify weak/strong bow changes still change tension.
5. Verify moving while aiming remains active.
6. Verify no valid bow releases trigger.
7. Verify FPS++ coexistence.

Hard boundary:
- no R2/input polling in Cemu for bow behavior;
- no aim/fire/release state machine in Cemu;
- no BOTW addresses, actor IDs or weapon tables in Cemu core;
- all gameplay-specific detection stays in the GraphicPack.

Do not rerun old prototype run `35443550198`.
