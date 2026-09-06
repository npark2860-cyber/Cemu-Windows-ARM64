# Star Fox Zero / Bayonetta 2 sync-cadence lead — 2026-09-06

## User-visible cross-title observation

Star Fox Zero JP:

- In the opening first-person sequence, some objects flicker.
- Other objects that do **not** flicker still move in a visibly stepped / jerky cadence rather than smooth motion.
- This does not look like ordinary insufficient-performance slowdown.
- Bayonetta 2 showed the same combination: object flicker plus visibly stepped motion on otherwise visible objects.

This observation must not be conflated with the earlier note that the scene naturally contains relatively few objects.

## Existing runtime evidence

From Star Fox `log(9).zip` / Run #22 instrumentation:

- CPU occlusion query class: type=0.
- Focus query FINISH -> CPU GET matched exactly for all 4067 completed generations.
- Therefore CPU-side GX2 result copying/consumption is not currently the leading explanation for the visual cadence issue.
- `[CMD_LIFECYCLE] SUBMIT` count: 126543 over ~148.47 s of observed command-buffer activity (~852 submits/s).
- Last `[RT_STATS]` snapshot: draws=4,800,000, render-pass begin=1,174,554 (~4.09 draws per render pass).

From Bayonetta 2 Run #17 runtime (`log (2)(3).zip`):

- `[CMD_LIFECYCLE] SUBMIT` count: 23370 over ~40.79 s (~573 submits/s).
- Last `[RT_STATS]` snapshot: draws=900,000, render-pass begin=113,494 (~7.93 draws per render pass).

These values do not by themselves prove a bug, but they establish a strong common characteristic: both affected titles produce extremely fine-grained Vulkan command-buffer submission / render-pass cadence.

## Source-level common path

Current Vulkan occlusion-query implementation:

- `LatteQueryObjectVk::beginFragment()` ends the active render pass before resetting/beginning a Vulkan occlusion query.
- `LatteQueryObjectVk::endFragment()` again ends the render pass before ending/copying the Vulkan query result.
- `LatteQueryObjectVk::end()` calls both `RequestSubmitSoon()` and `RequestSubmitOnIdle()`.
- `RequestSubmitSoon()` reduces the current submit threshold to `m_recordedDrawcalls + 10`.
- Normal command-buffer threshold is initialized to 300 draws.

Thus heavy CPU-occlusion-query traffic can repeatedly force render-pass boundaries and pull command-buffer submissions forward from the normal threshold.

## Historical Star Fox clue

Historical Cemu Star Fox Zero testing reported that the game flickered without the old `GX2DrawDone` synchronization behavior and could render correctly when that synchronization was enabled.

Current Cemu differs from old versions: on Vulkan, `GX2DrawDone()` now forces the full-sync packet regardless of the user setting. The sync packet executes:

- `LatteTextureReadback_UpdateFinishedTransfers(true)`
- `LatteQuery_UpdateFinishedQueriesForceFinishAll()`

and the query force-finish path calls renderer `occlusionQuery_flush()`.

Therefore the old observation is a synchronization sensitivity clue, **not** a recommendation simply to toggle the current setting.

## Current interpretation

The leading cross-title hypothesis is broadened from only query-result correctness to a shared Vulkan synchronization/cadence issue around the CPU occlusion-query workload:

1. repeated query begin/end fragments split render passes;
2. query completion requests aggressively shorten command-buffer lifetime;
3. affected titles exhibit both object-specific flicker and global stepped object motion;
4. Star Fox historically changed behavior with stronger GPU completion synchronization.

This may unify the flicker and motion-cadence symptoms, but is not yet proven.

## Active A/B

Run #24 (`34005173179`) remains the active one-variable Star Fox direct-query-readback A/B. Do not cancel it for this new lead.

If direct query readback changes neither flicker nor motion cadence, the next experiment should target synchronization/cadence rather than another resource hash:

- trace `GX2DrawDone()` entry/return and wait duration;
- trace actual `IT_HLE_SYNC_ASYNC_OPERATIONS` execution duration;
- trace scanbuffer-swap cadence;
- correlate those with command-buffer submit/completion bursts.

Only after observation should behavior be changed, preferably with a Star-Fox-only submit-threshold / query-completion A/B.

## Do not regress

- Do not reinterpret completed READY_ZERO as NOT_READY.
- Do not reopen closed Bayo2 resource/VB/CB/uniform/index/depth bookkeeping experiments without new evidence.
- Do not modify protected main.
- Do not cancel Run #24 merely to add this observation trace.
