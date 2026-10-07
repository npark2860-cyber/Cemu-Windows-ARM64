Enhanced Sound Cue Capture V2 — Windows ARM64
source_head=b18d8faae5a4b2316974ef4907e0739a9e3a5c2b

Based on the validated Fingerprint Catalog V2 source.
This build does not change routing policy; it only records source/cue identities seen by EnhancedSoundSourceTracker.

Output:
- enhanced_sound_cue_capture.csv in the Cemu working directory.
- Delete any old CSV before a focused capture.

Recommended capture order with 2-3 seconds idle between groups:
1. Fire weapon: 3-5 swings
2. Ice weapon: 3-5 swings
3. Electric weapon: 3-5 swings
4. Ancient weapon: 3-5 swings
5. Remote Bomb: create / throw / detonate
6. Magnesis: activate / grab / move / release
7. Stasis: activate / target / release
8. Cryonis: create / destroy
9. Camera: open / focus / capture
10. Sheikah Slate rune menu: open / switch / close

CSV fields include candidate_count, source_path, track_name and current route_match.
