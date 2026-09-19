# NEXT ACTION — Generic GraphicPack Adaptive Trigger v1

Work only on `test/se-fingerprint-index-v1`. Do not create a branch.

After implementation commit:
1. Verify the single CI build.
2. Use the bundled GraphicPack from the artifact.
3. Runtime-test BOTW v208:
   - weak/strong bow tension changes;
   - moving while aiming remains active;
   - no valid bow releases trigger;
   - FPS++ coexistence.
4. Promote nothing until user runtime PASS.

Do not restore BOTW addresses, actor IDs or weapon tables to Cemu core.
Do not reconnect adaptive-trigger lifecycle to sound_routes.ini.
Do not rerun old run `35443550198`.
