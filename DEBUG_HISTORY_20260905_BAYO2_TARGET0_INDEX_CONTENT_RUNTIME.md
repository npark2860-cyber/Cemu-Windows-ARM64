# DEBUG HISTORY — 2026-09-05 — Bayonetta 2 target0 exact index content runtime

## Scope

Observation-only analysis of user-supplied Run #15 capture `log(5).zip` for Bayonetta 2 JP target0 CPU occlusion query `0x46a92ec8`.

Run #15 code checkpoint:

- commit `8a735a583410f28d6b4c72770b120f39c001f41f`
- workflow run `33951247306`
- conclusion `SUCCESS`
- artifact `9965407406`

New marker under test:

`[BAYO2_TARGET_INDEX]`

The trace hashes the complete guest index range for each of the six producer draws. It is not a sampled hash.

## Capture validity

- `[BAYO2_TARGET_INDEX]`: 2,916 rows
- index generations observed: 486
- exactly 6 index rows for every observed generation
- completed target0 GET generations: 485
- all 485 completed generations have exactly 6 index rows
- final `gen=486` has six index rows but no completed GET before capture end and is excluded from result-class comparison

Completed result classes:

- ZERO: 459
- NONZERO: 26
- `FIRST`: 1
- `0->0`: 432
- `0->NZ`: 26
- `NZ->0`: 26
- `NZ->NZ`: 0

## Exact six-draw index signature

Every one of the 485 completed generations uses the same six draw-position index identities and the same full-range content hashes:

1. pipeline `7e005ef7a0ebc3c5`
   - index `0x1314dac0`
   - type `4` (`U16_BE`)
   - count `8394`
   - byte size `16788`
   - exact hash `499385a99b630874`
2. pipeline `bb71fa356a5b48ce`
   - index `0x13151d00`
   - type `4`
   - count `129`
   - byte size `258`
   - exact hash `18db65c38bfd4da1`
3. pipeline `bb71fa356a5b48ce`
   - index `0x13151ec0`
   - type `4`
   - count `483`
   - byte size `966`
   - exact hash `dc23544499f56815`
4. pipeline `000909ced0b17a78`
   - index `0x13152340`
   - type `4`
   - count `6`
   - byte size `12`
   - exact hash `067eea34dcd244c9`
5. pipeline `ead20dc8febd5234`
   - index `0x13152400`
   - type `4`
   - count `1560`
   - byte size `3120`
   - exact hash `e085dfaa370d1269`
6. pipeline `bb71fa356a5b48ce`
   - index `0x131530c0`
   - type `4`
   - count `504`
   - byte size `1008`
   - exact hash `9642728cfc61ecf2`

Full per-generation six-draw signature counts:

- unique signatures across all 485 completed generations: **1**
- unique ZERO signatures: **1**
- unique NONZERO signatures: **1**
- ZERO/NONZERO signature-set intersection: **1**

At every one of the six draw positions, ZERO and NONZERO have exactly one observed `(pipeline,index,type,count,size,hash)` tuple and it is the same tuple in both classes.

## Conclusion

**Exact guest index-buffer content is not the target0 completed ZERO/NONZERO discriminator.**

This closes the producer index-content branch under the captured conditions. Do not repeat address/count/type-only or full-index-byte hashing unless a later capture contradicts this result.

The remaining missing producer input class is sampled texture resource identity/content. A new observation-only texture-resource trace is the next action before any query-driver semantic behavior A/B.

## Constraints preserved

No result from this capture changes the fixed query-consumption facts:

- Bayonetta 2 uses CPU occlusion query type 0 in these captures and consumes exported `GX2QueryGetOcclusionResult()` results.
- completed ready-zero remains a real completed/consumed result.
- do not reinterpret ready-zero as NOT_READY/default zero.
- do not transplant XCX type-2 behavior or historical seed logic.
- do not reopen closed f544 depth behavior experiments.
