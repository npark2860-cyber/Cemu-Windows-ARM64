# DEBUG_HISTORY_20260919_SE_FINGERPRINT_INDEX

## Symptom

User reported a serious FPS drop in BOTW while using the SE build. It was initially unclear whether it was random or tied to a specific area.

## Static finding

The main suspected hot path was the Enhanced Sound fingerprint resolver.

Call path:
`AXApplyEnhancedSoundRoute()`
-> `EnhancedSoundSourceTracker::ResolveSourceCandidates()`
-> `BotWSoundFingerprintCatalog::FindMatches()`

The old `FindMatches()` implementation:
- hashes the first 64 bytes of the sample as two 32-byte hashes,
- locks the catalog mutex,
- reverse-scans `s_entries`,
- `s_entries` is capped at 32,768 entries,
- applies expectedPath and duplicate filtering after hash comparison.

This can become expensive when many AX voices start/reuse in sound-heavy areas.

## Safety requirement

The optimization must not change matching semantics.

Do NOT use a simple:
`hash -> single entry`

because:
- identical sample hashes may legitimately map to multiple path/track candidates,
- ambiguity handling is intentional,
- expectedPath filtering must remain,
- duplicate `path + trackName` suppression must remain.

## Implemented test optimization

Branch:
`test/se-fingerprint-index-v1`

Implementation commit:
`fb2d7afeb4deb6929b164bdf97842465b971f901`

Design:
- keep `s_entries` unchanged as source of truth,
- add `FingerprintKey { hashA, hashB }`,
- add `unordered_map<FingerprintKey, vector<Match>> s_lookupIndex`,
- populate lookup index when a unique source entry is accepted,
- remove index entry when the bounded catalog evicts an entry,
- `FindMatches()` now looks up only the hash bucket,
- iterate bucket in reverse order to preserve newest-first behavior,
- retain expectedPath filtering,
- retain duplicate `path + trackName` suppression,
- return multiple matches exactly as before.

## Build validation

Test workflow change produced:
- Test HEAD: `9263604feff7d92cbe517cd75246ac97d15d853d`
- Run: `35425264365`
- Result: SUCCESS
- Artifact: `cemu-arm64-test-se-fingerprint-index-v1`

## Promotion

User explicitly requested promotion and asked that the test branch remain for haptic work.

Promoted to:
`Release+SE`

Promotion commit:
`f2a5ad15b191d30eb2c870db7626518628cd90a2`

At handoff, Release+SE and Test use the same optimized fingerprint file blob:
`9cc256faf0e4c0880a8b7eee18486c5a1bf9e127`

No post-promotion Release+SE artifact build has been run yet.

## Separate resolved misunderstanding

The user briefly suspected DualSense headset auto-detection was globally muting TV audio. A temporary TV `Play()` workaround was added, then the user determined the original behavior had actually been fine. The workaround was reverted.

Do not connect future FPS diagnosis to that reverted TV workaround without new evidence.
