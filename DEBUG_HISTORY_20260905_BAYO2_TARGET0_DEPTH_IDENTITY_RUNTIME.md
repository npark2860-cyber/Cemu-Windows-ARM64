# DEBUG HISTORY — 2026-09-05 — Bayonetta 2 target0 depth identity/runtime

## Input

Run #14 depth-identity artifact runtime log supplied by user as `log(4).zip`.

Target query: `0x46a92ec8`.

## Capture validity

- `[BAYO2_TARGET_DEPTH]`: 381 rows
- completed target0 GET generations: 380
- completed generations with depth row: 380/380
- final gen 381 has a depth row but no completed GET before capture end and is excluded from result-class comparison

Completed result classes:

- ZERO: 354
- NONZERO: 26
- `FIRST`: 1
- `0->0`: 329
- `0->NZ`: 24
- `NZ->0`: 24
- `NZ->NZ`: 2

## Actual depth surface identity

All 380 completed generations, ZERO and NONZERO alike, use exactly the same recorded depth identity/state:

- `DB_HTILE_DATA_BASE = 0x00f54428`
- reconstructed raw physical address `0xf5442800`
- bound depth texture physical address `0xf5442800`
- `DB_DEPTH_SIZE = 0x00e0fc9f`
- `DB_DEPTH_INFO = 0x00020003`
- `DB_DEPTH_VIEW = 0x00000000`
- `DB_DEPTH_CONTROL = 0x00200736`
- bound depth texture present on every generation
- format 17
- tile mode 4
- swizzle 0
- 1280x720, pitch 1280
- mip 0/1, slice 0/1
- `isUpdatedOnGPU = 1`
- readback disabled
- `lastUpdateEventCounter = 8`
- `lastUpdateFrameCounter = 0`
- `reloadCount = 1`

There is no ZERO/NONZERO-exclusive actual depth surface identity.

## Dynamic bookkeeping

`dataUpdateFrame` and `accessFrame` equal the current producer frame on all 380 completed generations.

`lastUnflushedRTDrawcallIndex` equals the target0 query begin draw on 377/380 generations. Three deviations by -9 draws occur at:

- gen 11 (`NZ->0`)
- gen 92 (`0->0`)
- gen 93 (`0->0`)

Therefore this deviation is not NONZERO-specific.

`lastWriteEventCounter` is monotonic and its delta follows elapsed frame/draw work rather than query result class. Conditioned on frame gap:

### one-frame gap

- `0->0`: n=170, median delta 521, range 361..620
- `0->NZ`: n=13, median delta 516, range 456..617
- `NZ->0`: n=12, median delta 523, range 417..576
- `NZ->NZ`: n=1, delta 506

The distributions strongly overlap.

### three-frame gap

- `0->0`: n=159, median delta 1585, range 1320..2099
- `0->NZ`: n=11, median delta 1604, range 1388..1678

Again the distributions overlap.

Two-frame gaps occur only after NZ generations in this capture and therefore reflect sequence timing rather than an independent depth-state discriminator.

## Conclusion

The previously missing actual depth identity is now observed directly. Under this capture, completed ZERO/NONZERO is **not explained by a different depth surface identity or by an NZ-specific depth bookkeeping/write-history state**.

This observation does not reopen the already closed destructive/seeded `f5442800` behavior experiments. Do not retry those experiments.

Current eliminated/demoted producer discriminators now include:

- six-draw sequence / pipeline / shaders / draw args
- recorded raster/depth/color state
- producer VB identity and sampled content
- constant buffers
- PS full uniform state
- transition-specific VS uniform delta family
- actual bound depth surface identity
- observed depth write/update bookkeeping

## Next missing producer input

Proceed one variable at a time to **index-buffer content** before sampled textures or any behavior workaround.

The six target0 producer draws use fixed U16_BE index ranges in every generation:

1. `0x1314dac0`, count 8394
2. `0x13151d00`, count 129
3. `0x13151ec0`, count 483
4. `0x13152340`, count 6
5. `0x13152400`, count 1560
6. `0x131530c0`, count 504

All use index type 4 = `U16_BE`.

Next observation should exact-hash the guest index bytes (`count * 2`) for these six draws and correlate by target generation/result. No query/render/resource mutation.