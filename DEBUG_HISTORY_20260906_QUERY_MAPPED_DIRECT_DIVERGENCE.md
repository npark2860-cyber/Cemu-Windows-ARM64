# DEBUG HISTORY — Query mapped/direct divergence

Date: 2026-09-06~07

## Immutable runtime PASS baseline

Do not regress or remove the title-gated direct-readback path until a replacement reproduces both runtime PASS results.

- Star Fox Zero JP (`00050000-101AFF00`): Run #25 FIXED by `vkGetQueryPoolResults` direct readback.
- Bayonetta 2 JP (`00050000-1011B900`): Run #26 FIXED by the same direct-readback path.
- retained PASS branch/head: `exp-bayo2-query-direct-readback` / `5d758a096ee9409e7c25372a6caa9ad9d2378575`.
- `main` is out of scope and must not be modified.
- XCX remains separate. Do not globalize the direct-readback path.

## Diagnostic branches

Active investigation branch:

- `diag-query-mapped-direct-divergence`

CI trigger branch:

- `diag-bayo2-target-query-draw-fingerprint`

Protected blocking-direct baseline code checkpoint:

- `790a945780ea561518dd072d9f73c0e3e89b4700`
- `diagnostics: restore protected direct query readback baseline`

Current non-blocking experiment code checkpoint on active branch:

- `bac23bd90b3ce51b87f7a7e955aea9e90a2005ef`
- `diagnostics: try nonblocking direct query readback`

Equivalent CI-trigger commit:

- `57f2e9e7dbdfebdd450449ff264476d31fbc1e60`
- identical experiment-script blob: `2f47eaf88f812cb89893d172efa863c61563cbd4`

## Confirmed runtime divergence

Star Fox Zero JP runtime capture from Cemu `77c4761` repeatedly showed:

- `cmdFinished=1`
- `vkResult=0` (`VK_SUCCESS`)
- `direct > 0`
- `mapped=0`
- `selected=direct`
- `mismatch=1`

This rules out “query simply not finished when the CPU read it” for the reproduced target failure.

## Confirmed result-memory properties

Bayonetta 2 JP runtime capture from Cemu `7a71d54`:

`[QUERY_MAP_META] found=1 memoryType=4 heap=0 flags=0x0000000f requested=0x0000000e fallback=0`

Interpretation:

- actual `0x0f` = `DEVICE_LOCAL | HOST_VISIBLE | HOST_COHERENT | HOST_CACHED`
- requested `0x0e` = `HOST_VISIBLE | HOST_COHERENT | HOST_CACHED`
- `fallback=0`
- `nonCoherentAtomSize=1`

Therefore missing non-coherent invalidation is not the cause of the captured failure.

## Experiments already completed — do not repeat

### 1. Transfer-write -> host-read visibility barrier

- commit `79fbf25ab8a255fe15ad8210bad21a9a5491c34e`
- Run #28 `34017106924`
- CI SUCCESS
- did not establish a repair.

### 2. Forced mapped-memory invalidate

- commit `7a71d5405f3d438d52dce9554eb93a0ee49a2ed2`
- Run #29 `34019347912`
- CI SUCCESS
- Bayonetta 2 capture proves result memory is HOST_COHERENT; invalidate is not the root fix.

### 3. DEVICE_LOCAL intermediate isolation

- diagnostic commit `eb04e6f370c8bbf2ae9564e19edef8b6e8c7d266`
- trigger Run #30 head `6532c82d1c75b983465bcac40cf36f947462e0b9`
- Run ID `34021733515`
- CI SUCCESS
- artifact `9986265293`
- digest `sha256:c7083f69433ae71029673d7ac21291a6f6b8543060eec4a794e0949eb0621b3b`

Implementation for target titles:

1. `vkCmdCopyQueryPoolResults` -> DEVICE_LOCAL intermediate
2. explicit `TRANSFER_WRITE -> TRANSFER_READ` barrier
3. `vkCmdCopyBuffer` -> existing mapped host buffer
4. explicit `TRANSFER_WRITE -> HOST_READ` barrier
5. protected direct result remains selected for behavior safety

#### Star Fox Zero JP Run #30 runtime — FAILED TO REPAIR

Expected build confirmed:

- `Init Cemu 6532c82`
- title `00050000101aff00`
- `[QUERY_INTERMEDIATE] allocated=1`

Parsed `[QUERY_DIRECT]` records:

- records `336166`
- all parsed `vkResult=0`
- direct nonzero `335995`
- mismatch `335993`
- mapped nonzero only `2`

DEVICE_LOCAL intermediate did not repair the systematic copied result.

#### Bayonetta 2 JP Run #30 runtime — FAILED TO REPAIR

Expected build/path confirmed:

- `Init Cemu 6532c82`
- title `000500001011b900`
- `path=intermediate`

Explicit mismatch records in the supplied capture:

- mismatch `23034`
- mismatch pattern consistently:
  - `cmdFinished=1`
  - `vkResult=0`
  - `direct > 0`
  - `mapped=0`

Bayonetta 2 therefore reproduces the same DEVICE_LOCAL-intermediate failure as Star Fox Zero.

### Conclusion of mapped-copy investigation for these two titles

The reproduced failure boundary is narrowed past:

- query completion
- HOST_COHERENT memory selection
- explicit host visibility barrier
- explicit invalidate
- immediate query-copy destination being HOST_VISIBLE
- an intermediate DEVICE_LOCAL destination plus explicit transfer dependencies

For Star Fox Zero JP and Bayonetta 2 JP, `vkGetQueryPoolResults` returns the correct completed query value while the `vkCmdCopyQueryPoolResults` result-copy path systematically fails to deliver that value in the tested Adreno configuration.

Treat the Adreno `vkCmdCopyQueryPoolResults` path as the current target-specific failure boundary. Do not generalize this conclusion to every title/device; XCX remains a separate path.

### 4. Protected blocking-direct baseline restoration

- active code checkpoint `790a945780ea561518dd072d9f73c0e3e89b4700`
- trigger Run #31 head `be3064da39e2913719de6fc800e7f417d28a0aec`
- Run ID `34024292927`
- CI SUCCESS
- artifact `9987082611`
- digest `sha256:74aef6d516965fc1ec93fc32d0a6ad2fe0358e36a439afdf1b9d2e6c344499bd`

This is the protected fallback if the non-blocking replacement does not reproduce both runtime PASS results.

## Current experiment — non-blocking direct query readback

One variable only was changed in `tools/diagnostics/Apply-StarFoxDirectQueryReadbackExperiment.py`.

Target gate remains only:

- Star Fox Zero JP
- Bayonetta 2 JP

Behavior:

- call `vkGetQueryPoolResults` only after existing `HasCommandBufferFinished(...)` is true
- direct call flags changed from `VK_QUERY_RESULT_64_BIT | VK_QUERY_RESULT_WAIT_BIT` to `VK_QUERY_RESULT_64_BIT`
- on `VK_SUCCESS`: consume direct result exactly as the protected FIXED path does
- on `VK_NOT_READY`:
  - do not accumulate the fragment
  - do not release the query index
  - do not erase the fragment
  - break out of finished-fragment processing
  - `getResult()` returns false while retained fragments remain
  - retry on a later consumer call
- non-target titles retain their mapped-buffer behavior unchanged
- XCX is untouched
- `main` is untouched

New runtime log fields:

- `retry=1` for `VK_NOT_READY`
- `retry=0` for consumed/fallback result
- `notReadyTotal=<count>`

Active commit:

- `bac23bd90b3ce51b87f7a7e955aea9e90a2005ef`

CI trigger commit:

- `57f2e9e7dbdfebdd450449ff264476d31fbc1e60`

Diff from previous active handoff is one file only:

- `tools/diagnostics/Apply-StarFoxDirectQueryReadbackExperiment.py`

## Run #32 build status

- Run #32 ID `34074452899`
- job `101597749211`
- head `57f2e9e7dbdfebdd450449ff264476d31fbc1e60`
- workflow `Cemu ARM64 Bayo2 Target Query Draw Fingerprint Trace`

Verified successful before compilation:

- checkout
- baseline behavior application
- PS DEFAULT_VAL compatibility fix
- AArch64 generated-code cache flush fix
- FSR application
- runtime experiment harness
- VS/RT diagnostic transforms
- query-consumption trace validation/application
- correlation trace validation/application
- targeted fingerprint trace validation/application
- existing observation-only validations
- clang-cl/MSVC ARM64/Ninja/CMake setup
- vcpkg bootstrap / NuGet setup

At the last recorded GitHub state, Run #32 is in `Configure`; build/artifact/runtime result is not yet claimed.

## NEXT ACTION

1. Complete classification of Run #32 CI result. Do not start another build unless Run #32 itself fails for a code reason.
2. If Run #32 produces the artifact, test **Star Fox Zero JP first**.
3. Confirm startup identifies the Run #32 build/head and capture `log.txt` through the formerly flickering scene.
4. Check:
   - visual FIXED state retained
   - `[QUERY_DIRECT] retry=1` count/rate
   - eventual retry -> `VK_SUCCESS`
   - no query-index exhaustion/stall
5. If Star Fox Zero passes, test Bayonetta 2 JP with the exact same artifact.
6. Only if both reproduce their Run #25/#26 FIXED behavior may this non-blocking direct path replace the protected blocking-direct baseline for these two titles.
7. If either regresses, revert the experiment to protected commit `790a945780ea561518dd072d9f73c0e3e89b4700` behavior; do not reopen already-eliminated mapped-copy experiments.
8. Do not modify `main`; do not mix XCX into this experiment.
