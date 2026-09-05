# DEBUG HISTORY — 2026-09-05 — Bayonetta 2 target0 resource runtime

> Repository: `npark2860-cyber/Cemu-Windows-ARM64`  
> Runtime artifact baseline: Run #10 / `6b96fb4a0fceb6f1285ea6a39db82852d4ad8972`  
> Artifact ID: `9750570882`  
> Input: user-supplied `log (2).zip` / `log.txt`  
> Scope: observation-only runtime analysis. No behavior-changing conclusion is inferred.

## 1. Capture validity

This capture is valid for the target0 resource stage.

Observed marker counts:

- `[BAYO2_RESOURCE]`: 12,949 lines
- `[BAYO2_TARGET]`: 17,071 lines total
- target0 `[BAYO2_TARGET] GET`: 932 completed generations
- target0 resource watches: 58 `0->NZ` and 58 `NZ->0`
- `[BAYO2_RESOURCE]` direction rows:
  - `0->NZ`: 6,476
  - `NZ->0`: 6,473

All target0 resource watch windows covered frame offsets 1, 2 and 3 as designed.

Target0 completed GET transition distribution:

- `FIRST`: 1
- `0->0`: 810
- `0->NZ`: 58
- `NZ->NZ`: 5
- `NZ->0`: 58

This preserves the previous conclusion that target0 repeatedly oscillates between completed zero and nonzero results.

## 2. Downstream fixed-pipeline resource result

Resource filter remained exactly:

- query: `0x46a92ec8`
- pipeline: `0x4addb8b25c8fc2bf`
- VS baseHash: `0xdba0c5a2b50b7103`
- PS baseHash: `0x2360006f2b86aae5`

All 12,949 `[BAYO2_RESOURCE] DRAW` records were from that pipeline.

### Vertex buffers

- `vbCount` was always 1.
- 20 unique `(vbIdentity, vbContent, vb0 address/size/stride)` tuples were observed.
- The `0->NZ` direction contained all 20 tuples.
- The `NZ->0` direction contained the same all 20 tuples.
- Set difference between directions: 0.
- `count + baseVertex` mapped deterministically to one VB identity/content tuple across the capture.
- Across all watch frames, 110 geometry keys were shared between directions; only one rare key was exclusive to each side.

First post-transition frame only (`frameOffset=1`):

- `0->NZ`: 2,167 resource draw rows
- `NZ->0`: 2,158 resource draw rows
- both directions still contained the same 20 VB tuples
- total variation distance of the 20-tuple frequency distributions was about 0.0086

Conclusion:

**No direction-specific downstream vertex-buffer identity/content set was observed.**

The current data does not support VB identity/content changes as the discriminator between target0 completed zero and nonzero transitions.

### Uniform/constant buffers

For this fixed downstream pipeline:

- VS `cbCount = 0` for every row
- PS `cbCount = 0` for every row
- GS `cbCount = 0` for every row
- PS `varSize = 0`, `varHash = 0`
- GS `varSize = 0`, `varHash = 0`
- VS `varSize = 4096` for every row

Therefore there is no VS/PS/GS FULL_CBANK identity/content difference to compare for this pipeline.

### VS uniform-variable hash

- 4,736 unique VS variable hashes were observed.
- Every VS variable hash belonged to exactly one actual `observedFrame`; no hash occurred in two different actual frames.
- At `frameOffset=1`, the two transition directions therefore had no exact VS hash overlap.

This is not evidence that query direction selects different uniforms. The aggregate 4 KiB VS variable hash is frame-sensitive and changes with the actual frame, so direction and time cannot be separated with this field alone.

### Overlapping watch-window control

- 87 actual observed frames were simultaneously covered by opposite-direction watch windows.
- 3,172 unique draw IDs were logged under both transition labels because the three-frame windows overlapped.
- For every one of those duplicated draws, all captured pipeline/draw/VB/CB/uniform resource fields were identical.
- Inconsistencies for the same actual draw: 0.

Do not misinterpret these duplicates as independent samples. They prove only that watch labeling itself does not alter the captured state.

## 3. Fixed downstream render-state result

For pipeline `0x4addb8b25c8fc2bf`, the associated `[BAYO2_DOWNSTREAM]` records showed the same values in both directions for:

- minimal pipeline hash
- VS/GS/PS shader hashes
- primitive type
- clip state
- raster state
- depth control
- color control
- target mask
- depth attachment identity fields

`color0` alternated between two addresses, and both addresses occurred in both query-transition directions. It is not a direction-exclusive state.

## 4. Target0 query-producer draw fingerprint — stronger narrowing

The same capture contains target0 query-producing `[BAYO2_TARGET] DRAW` records for all 932 completed target0 generations.

Result classes:

- completed zero generations: 869
- completed nonzero generations: 63
- six target0 producer draws per generation in every case
- total producer draw records: 5,592

Across zero and nonzero generations:

- the same 4 pipeline hashes were used
- the same VS/PS shader sets were used
- the same primitive/clip/raster/depth/color/target-mask states were used
- the same draw counts/baseVertex/index addresses were used
- both color0 identities occurred in both result classes

After removing the rotating color0 address from the sequence key, **all 932 generations reduced to exactly one identical six-draw producer sequence**, shared by both zero and nonzero results.

Even with color0 retained, the exact producer fingerprint sets were the same in both result classes.

Conclusion:

**Target0 completed zero vs nonzero is not explained by a different producer draw sequence or a different recorded producer pipeline/shader/render-state fingerprint.**

The next useful discriminator is the resource content used by those six query-producing draws themselves.

## 5. Next experiment selected from runtime evidence

New observation-only experiment:

**target0 query-producer vertex/uniform resource trace**

Purpose:

For each of the six target0 producer draws, record the same resource fields already validated for downstream observation, keyed by query generation. Then join each generation to its completed GET result and compare zero vs nonzero directly.

Fields:

- VB count / identity / sampled content / first address-size-stride
- VS/PS/GS constant-buffer count / identity / sampled content
- VS/PS/GS uniform-variable size / hash
- pipeline / draw arguments / generation / frame / draw sequence

No query result/readiness, visibility, culling, Vulkan state, resource contents, or draw execution changes are permitted.

## 6. Implementation state

Staging branch:

`diag-bayo2-target0-producer-resource`

Base:

`4f24fca6e0cc49d64bd14bca0b5ce1e586d2b59f` (Run #11 validated code, behavior-equivalent normalization over Run #10)

New commits:

- `44483ae5519e7aebec2e8c41ea9289c9cc903897` — add `Apply-Bayo2Target0ProducerResourceTrace.py`
- `4498bfe9c80c54ea1ac4df48355f27a1bf676e95` — chain producer resource trace

Diff from `4f24fca...`:

- one new diagnostic script
- four added chaining lines in the existing target trace wrapper
- no baseline renderer/query source file is committed modified; transforms remain build-time observation instrumentation

The CI branch `diag-bayo2-target-query-draw-fingerprint` was fast-forwarded to `4498bfe...` only after staging the complete two-commit change, so only one new automatic build is intended.

Run #12:

- Run ID: `33939024628`
- Head: `4498bfe9c80c54ea1ac4df48355f27a1bf676e95`
- State at this documentation point: `queued`

Do not start another CI run while Run #12 is active.

## 7. Preserved exclusions

Do not reopen these conclusions from this capture:

- Bayo2 ready-zero is not a simple NOT_READY/default-zero result.
- Bayo2 and XCX do not use the same observed exported query-consumption path.
- downstream target0 VB identity/content is not direction-exclusive.
- target0 zero/nonzero is not explained by a different six-draw producer fingerprint.
- do not globally force ready-zero visible.
- do not add a behavior workaround before producer-resource runtime evidence.
