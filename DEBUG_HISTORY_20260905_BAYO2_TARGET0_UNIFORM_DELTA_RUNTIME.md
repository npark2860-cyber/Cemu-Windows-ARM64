# DEBUG HISTORY — 2026-09-05 — Bayonetta 2 target0 uniform-delta runtime

> Repository: `npark2860-cyber/Cemu-Windows-ARM64`  
> Runtime build: Run #13 / `2f5d4080082219e096bfbf593d711c69fed807ce`  
> Input: user-supplied `log(3).zip`  
> Scope: observation-only target0 producer uniform vec4 delta trace

## 1. Capture validity

Required marker is present and abundant:

- `[BAYO2_TARGET_UNIFORM]`: 140,860 rows
- `[BAYO2_TARGET_RESOURCE]`: 2,742 rows
- target0 `[BAYO2_TARGET] DRAW`: 2,742 rows
- target0 completed GET generations: 457
- exactly six target0 producer draws per completed generation

Run #13 was independently confirmed SUCCESS:

- Run ID `33945290442`
- HEAD `2f5d4080082219e096bfbf593d711c69fed807ce`

## 2. Target0 result pattern

Completed generations:

- ZERO: 431
- NONZERO: 26

Transitions:

- `FIRST`: 1
- `0->0`: 406
- `0->NZ`: 24
- `NZ->0`: 24
- `NZ->NZ`: 2

NONZERO topology:

- 22 NONZERO generations are isolated one-generation spikes: ZERO -> NZ -> ZERO
- only two two-generation NONZERO episodes exist (`152-153`, `398-399`)
- nonzero sample sums range 8,418..15,993; these are not tiny threshold values

This pattern remains compatible with severe query-result oscillation and does not look like a slow monotonic visibility crossing by itself.

## 3. VS uniform-delta result

Recurring VS:

- `e6fc4f385f9b0034`
- `93a12f899ed56598`

Both expose 256 vec4 slots (4096 bytes).

Changed-slot counts do not separate result transitions:

For VS `e6fc...`:

- `0->0`: mean 148.50 changed slots
- `0->NZ`: mean 149.46
- `NZ->0`: mean 150.00
- `NZ->NZ`: mean 142.00

The second VS has effectively the same change-count behavior.

Exactly 127 VS slots are changed in every `0->NZ` generation and also in every `NZ->0` generation. Those are ordinary continuously changing slots, not direction-specific markers.

For the 22 isolated NZ spikes, compare the changed-slot set at the NZ generation with the immediately following ZERO generation:

- mean Jaccard similarity: 0.995 for each recurring VS
- median: 1.0
- minimum: 0.9401

No vec4 slot shows a repeated exact `A -> B -> A` transient at all isolated NZ events. The maximum repeat count for any such exact transient slot is only 2 of 22 events.

Therefore no transition-specific VS vec4 slot/value pattern was found that explains completed ZERO/NONZERO.

## 4. PS uniform-delta result

Recurring PS:

- `e2b9a6e6c2a4a0f8`
- `519954498085e510`
- `902ca3422dccc182`
- `362608e302d3de4c`

PS changed-slot counts are small and similarly distributed across transition classes. No slot is changed in every `0->NZ` or every `NZ->0` generation.

More importantly, exact reconstructed full PS uniform states occur in both completed result classes:

- PS `e2b9...`: 10 of 26 NONZERO generations share an exact full PS uniform state also observed on ZERO generations
- PS `5199...`: 7 of 26 NONZERO generations share an exact state with ZERO
- PS `902c...`: 7 of 26 share an exact state with ZERO
- PS `3626...`: 7 of 26 share an exact state with ZERO

Therefore PS uniform-variable state is not a sufficient discriminator for target0 result.

## 5. Current conclusion

The following producer-side discriminators have now been demoted/closed for this capture series:

- six-draw sequence
- pipeline/shader/render-state fingerprint
- guest VB identity
- sampled guest VB content
- VS/PS/GS constant-buffer identity/content
- PS full uniform-variable state
- transition-specific VS uniform vec4 delta pattern

VS whole-state differs generation-to-generation, but the numeric delta trace does not reveal an NZ-specific transient or direction-specific slot family. Do not keep drilling the same uniform layer without new evidence.

## 6. Critical depth-trace blind spot discovered

Previous `[BAYO2_TARGET] DRAW` logged:

- `DB_DEPTH_BASE`
- `DB_DEPTH_SIZE`
- `DB_DEPTH_INFO`
- `DB_DEPTH_VIEW`

However Cemu `GX2SetDepthBuffer()` intentionally writes:

- `DB_DEPTH_BASE = 0`
- actual guest depth physical identity in `DB_HTILE_DATA_BASE = physical(imagePtr) >> 8`

`LatteRenderTarget.cpp` reconstructs the real depth physical address from:

`depthBufferPhysMem = DB_HTILE_DATA_BASE << 8`

Therefore the previous statement that the recorded `depth=00000000/...` tuple represented a stable actual depth surface identity was too strong. The actual depth address was not observed.

This is a new observation gap, not a return to the closed f544 depth-coherence experiments.

## 7. Next observation

New active marker planned/implemented:

`[BAYO2_TARGET_DEPTH]`

Record once per target0 generation:

- `DB_HTILE_DATA_BASE`
- reconstructed raw physical address
- depth size/info/view/control
- current bound `LatteMRT::GetDepthAttachment()` presence
- bound depth texture `physAddress`, format/tile/swizzle/size/pitch/view
- GPU-update/readback flags
- `lastWriteEventCounter`
- `lastUpdateEventCounter`
- update/data-update frame counters
- reload/access/unflushed-draw bookkeeping

No GPU readback and no depth-content/state mutation are authorized at this stage.

Do not mix index-buffer or texture-resource experiments into this build. First determine whether actual depth surface identity/history correlates with target0 ZERO/NONZERO.
