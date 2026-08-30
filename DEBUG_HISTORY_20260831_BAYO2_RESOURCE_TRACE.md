# DEBUG HISTORY — 2026-08-31 — Bayonetta 2 targeted query → downstream → target0 resource trace

> Repository: `npark2860-cyber/Cemu-Windows-ARM64`  
> Docs branch: `runtime-experiments-arm64`  
> Purpose: preserve only confirmed implementation/CI state after `DEBUG_HISTORY_20260829_QUERY_COMPARE.md`. Runtime conclusions are recorded only when supported by an actual runtime log.

## 1. Starting point retained from query correlation

Bayonetta 2 JP clean Graphic-Packs-OFF correlation capture established:

- title `00050000-1011B900`, v1
- CPU occlusion query type0 only
- completed GET results matched finished sample sums
- no `GET_NOT_READY`, missing snapshot, or repeat-generation evidence
- narrow query draw lifetimes: median 1 draw, p90 5, p95 7, max 18
- severe visual flicker remained unchanged with all Bayonetta graphic packs OFF
- aggregate zero/nonzero transition density did not track perceived flicker severity
- a small persistent subset of query slots repeatedly oscillated across independent captures

Persistent target slots selected for the next observation stage:

- target0 `0x46a92ec8`
- target1 `0x46a936c8`
- target2 `0x46a93bc8`
- target3 `0x46a93a08`
- target4 `0x46a93708`

Do not reinterpret ready-zero as premature/default-zero. Do not globally force zero visible. Do not transplant the historical XCX workaround into Bayonetta 2.

## 2. Targeted query → draw fingerprint observation

Branch chain:
`diag-bayo2-target-query-draw-fingerprint`

Observation-only trace added by:
- `058725bc6193c48b47bfebe09ff981af4b6987b1` — `diagnostics: add Bayo2 targeted query draw fingerprint trace`
- `d99686273030af52cb45f03a43a1dbb4f91b48d7` — workflow wiring
- `8603b8fee3218d5680ffb149efd76e738dc4e2aa` — helper anchor correction
- `b7c2d7327d3ae9b2bba8421594a8f1c8ef7cc088` — draw-callsite anchor correction
- `b9200e2b637470cd8902379b535b7c978ce6f973` — instrumentation compile/materialization correction

Trace scope:
- automatic `[BAYO2_TARGET]` logging
- query pointer/generation and GET transition/result
- frame/draw sequence
- pipeline `stateHash` / `minimalStateHash`
- VS/GS/PS baseHash/auxHash
- primitive/draw parameters
- clip/raster/depth/color state
- color0/depth attachment identity fields
- no query result/readiness/culling/visibility/pipeline-state/draw-execution semantic changes

CI progression:

1. Run `33241228167` — FAILED before C++ build
   - apply anchor mismatch in targeted Vulkan helper insertion
2. Run `33241366205` — FAILED before C++ build
   - first/continued draw callsite anchor count mismatch
3. Run `33241470467` — FAILED during actual `Build Cemu once`
   - Configure succeeded; targeted instrumentation still had a C++ compile issue
4. Run `33244548809` — **SUCCESS**
   - HEAD `b9200e2b637470cd8902379b535b7c978ce6f973`
   - artifact id `9712845853`
   - artifact `cemu-arm64-bayo2-target-query-draw-fingerprint`
   - digest `sha256:80930256843efff9b230e14c2cfea568353a9c8aae1d79106f8113f6336ef4b3`

This confirms the targeted query/draw observation instrumentation became build-ready. This section does not assert a runtime conclusion that is not present in the repository docs/logs.

## 3. Downstream draw observation stage

Subsequent observation-only downstream trace commits:

- `83b57aa7b89c54208f8583bbfa87e44eac9164dd` — `diagnostics: add Bayo2 downstream draw trace`
- `b1694fc46ba56de381fd5e9e6ec37bbb93ec3f48` — `diagnostics: chain Bayo2 downstream trace`

CI:
- Run `33247256523` — **SUCCESS**
- HEAD `b1694fc46ba56de381fd5e9e6ec37bbb93ec3f48`
- artifact id `9713651612`
- artifact `cemu-arm64-bayo2-target-query-draw-fingerprint`
- digest `sha256:cfd1cdccfa21894c2091174792e602993f0cc01e6ade22aa1c4815876160833c`

This confirms the downstream observation stage compiled, collected, and uploaded successfully. Detailed runtime conclusions are intentionally not reconstructed here without the corresponding runtime log as source.

## 4. Current active experiment — target0 resource identity/content trace

Current observation target:
`0x46a92ec8` (target0)

Branch:
`diag-bayo2-target0-resource-identity`

Current branch HEAD:
`725aae2f63d6b3e766c37efe26c46341059dae83`

Commits:
- `e19a3a4e92de0ad044226b248cf1e6b89f8fff9e` — `diagnostics: add Bayo2 target0 resource identity trace`
- `725aae2f63d6b3e766c37efe26c46341059dae83` — `diagnostics: chain Bayo2 target0 resource trace`

Script:
`tools/diagnostics/Apply-Bayo2Target0ResourceIdentityTrace.py`

Intended observation scope:
- target0-associated vertex-buffer guest address/size/stride identities
- sampled vertex-buffer content hashes
- stage uniform/constant-buffer identities/content hashes
- uniform variable ranges
- correlation with the already-instrumented target0 query/draw path
- no intended modification of query values, query readiness, visibility, culling, render state, resource contents, or draw execution

### Current CI state — NOT BUILD-READY

Run:
`33286935862` — **FAILURE**

Job:
`99191642306`

Head SHA:
`725aae2f63d6b3e766c37efe26c46341059dae83`

Confirmed successful before compile failure:
- checkout
- known-good Adreno compatibility patch chain
- PS `DEFAULT_VAL` fix
- AArch64 generated-code cache fix
- FSR patch
- runtime harness
- VS auxHash diagnostics
- RT/perf diagnostics
- generic Diagnostic Edition
- query-consumption trace validate/apply/observation-only verification
- Bayo2 frame/draw correlation validate/apply/observation-only verification
- targeted query/draw fingerprint validate/apply/observation-only verification
- target0 resource trace validate/apply/observation-only verification
- release/toolchain/vcpkg/NuGet setup
- CMake `Configure`

Failure:
- `Build Cemu once` — **FAILED during actual C++ compilation**
- executable collection skipped
- artifact upload skipped
- run artifacts count = **0**

Important: the exact compiler diagnostic text from Job `99191642306` has **not yet been recovered into the handoff**. Do not guess the failing field/type/line.

Therefore:
- there is no usable target0 resource artifact yet
- there is no target0 resource runtime log/result yet
- this experiment remains observation-only and unfinished

## 5. NEXT ACTION — start here in the next tab

1. Fetch the exact compiler error text from GitHub Actions Job `99191642306` for Run `33286935862`.
2. Inspect only the source line generated by `Apply-Bayo2Target0ResourceIdentityTrace.py` that the compiler identifies.
3. Make the minimum compile-only correction inside the approved `[BAYO2_RESOURCE]` observation instrumentation.
4. Do not alter query values/results/readiness, visibility, culling, render state, resource contents, draw execution, or the XCX workaround.
5. Static verify the resource observation checker still passes and that the target remains exactly `0x46a92ec8`.
6. Re-run the existing workflow only after the compile correction.
7. Call the experiment build-ready only if Build, Collect, and Upload all succeed and an artifact exists.
8. Only then request a clean Bayo2 JP runtime capture with Graphic Packs OFF and diagnostics toggles OFF.

No behavior-changing A/B is authorized at this handoff point.

## 6. Runtime capture rules to preserve after a successful build

When an artifact eventually exists:

- Stop emulation → close Cemu → reopen
- Bayonetta 2 Graphic Packs all OFF
- Runtime Diagnostics OFF
- Master/Preset OFF
- launch Bayonetta 2 JP v1
- reproduce the same severe-flicker scene
- keep camera mostly static for roughly 10–15 seconds while flicker is visible
- stop/close and upload full `log.txt`
- `[BAYO2_TARGET]` / resource observation markers are automatic; do not enable a checkbox for them
- user visual statement (`same` / `better` / `worse`) may be recorded separately; never invent video↔log synchronization

## 7. Non-regression / do-not-repeat list

Never roll back:
- VS producer-side `DEFAULT_VAL` synthesize/linkage fix
- AArch64 generated-code cache / I-cache coherency fix
- known-good pre-e834 Vulkan compatibility behavior
- Runtime Diagnostics 77/77 coverage

Do not repeat closed/downgraded experiments:
- Position Invariance
- viewport depth-range clamp
- `depthBiasClamp`
- Force Maximum LOD / LOD general
- native `negativeOneToOne` / shader `(z+w)/2` removal
- RT barrier variants / forced render-pass split
- depthclip
- pipeline pNext
- VS auxHash pipeline key
- `f4c24000` conversions
- nested/duplicate query bookkeeping
- f544 seeded/unseeded Bayonetta primary-cause experiments
- XCX `IT_SET_PREDICATION` observation
- Bayo2 global ready-zero force-visible

The next tab must continue from section 5, not restart the targeted query trace or downstream trace stages.