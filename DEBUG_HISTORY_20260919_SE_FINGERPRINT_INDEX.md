# DEBUG_HISTORY_20260919_SE_FINGERPRINT_INDEX

## Symptom

User reported a severe BOTW FPS drop on the SE build. It was initially unclear whether the slowdown was random or location-dependent.

## Static hot-path finding

Primary suspect:
`AXApplyEnhancedSoundRoute()`
-> `EnhancedSoundSourceTracker::ResolveSourceCandidates()`
-> `BotWSoundFingerprintCatalog::FindMatches()`

Old `FindMatches()` behavior:
- hash 64 sample bytes as two 32-byte hashes;
- lock fingerprint catalog mutex;
- reverse-scan `s_entries`;
- catalog limit up to 32,768 entries;
- only then filter hash/path/duplicates.

This could create large CPU cost when many AX voices start/reuse in sound-heavy areas.

## Implemented optimization

Implementation commit:
`fb2d7afeb4deb6929b164bdf97842465b971f901`

Design:
- `s_entries` remains source of truth;
- add `FingerprintKey { hashA, hashB }`;
- add lookup-only `unordered_map<FingerprintKey, vector<Match>>`;
- add accepted entries to the hash bucket;
- remove corresponding lookup data on bounded-catalog eviction;
- `FindMatches()` checks only the matching hash bucket;
- reverse iteration preserves newest-first order;
- expectedPath filtering remains;
- duplicate `path + trackName` suppression remains;
- multiple candidate/ambiguity behavior remains.

Do not simplify to `hash -> single entry`.

## Validation and promotion

Validated Test build/code HEAD:
`9263604feff7d92cbe517cd75246ac97d15d853d`

Run:
`35425264365`

Result:
SUCCESS

Promoted to Release+SE:
`f2a5ad15b191d30eb2c870db7626518628cd90a2`

At promotion time, the optimized file blob matched between Release+SE and Test:
`9cc256faf0e4c0880a8b7eee18486c5a1bf9e127`

Later commits on both branches may be policy/handoff documentation only. Always fetch current HEAD.

## Separate discarded hypothesis

The user briefly thought DualSense headset auto-routing globally muted TV output. A temporary `g_tvAudio->Play()` workaround was added, then reverted when the user determined TV output had actually been normal.

Do not connect future FPS work to that discarded workaround without new evidence.
