# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> 이 파일은 현재 상태만 유지한다. 이 탭의 상세 근거는 `DEBUG_HISTORY_20260906_QUERY_MAPPED_DIRECT_DIVERGENCE.md`를 우선한다.

## CURRENT STATE

Repository:

- `npark2860-cyber/Cemu-Windows-ARM64`

Active branch:

- `diag-query-mapped-direct-divergence`

Last verified code-changing checkpoint:

- `790a945780ea561518dd072d9f73c0e3e89b4700`
- `diagnostics: restore protected direct query readback baseline`

The branch may contain documentation-only commits after this code checkpoint. Always verify actual branch HEAD, but do not treat docs-only HEAD movement as a code change.

`main` is out of scope and must not be modified.

## IMMUTABLE VERIFIED PASS

Do not regress these results:

- Star Fox Zero JP (`00050000-101AFF00`): Run #25 FIXED by title-gated `vkGetQueryPoolResults` direct readback.
- Bayonetta 2 JP (`00050000-1011B900`): Run #26 FIXED by the same path.
- retained PASS branch/head: `exp-bayo2-query-direct-readback` / `5d758a096ee9409e7c25372a6caa9ad9d2378575`
- XCX remains separate; do not globalize blocking direct readback.

## CONFIRMED ROOT-CAUSE BOUNDARY

Star Fox Zero runtime instrumentation proves repeated cases where:

- owning command buffer is finished: `cmdFinished=1`
- direct Vulkan query read succeeds: `vkResult=0`
- `direct` is nonzero
- mapped result is still `0`
- `mismatch=1`

Therefore the reproduced failure is downstream of a completed query result and is in the normal query-copy / mapped-result path, not simply an unfinished query.

Bayonetta 2 runtime memory metadata proves:

- `memoryType=4`
- actual flags `0x0000000f`
- requested flags `0x0000000e`
- `fallback=0`

The selected query-result memory is `DEVICE_LOCAL | HOST_VISIBLE | HOST_COHERENT | HOST_CACHED`. Missing invalidate for non-coherent memory is therefore ruled out for this captured Adreno path.

## EXPERIMENTS ALREADY DONE

Do not repeat these blindly:

1. transfer-write -> host-read barrier
   - commit `79fbf25ab8a255fe15ad8210bad21a9a5491c34e`
   - Run #28 `34017106924`
   - CI SUCCESS

2. forced mapped-memory invalidate
   - commit `7a71d5405f3d438d52dce9554eb93a0ee49a2ed2`
   - Run #29 `34019347912`
   - CI SUCCESS
   - runtime memory is HOST_COHERENT, so non-coherent invalidate is not the root fix

3. DEVICE_LOCAL intermediate isolation
   - diagnostic commit `eb04e6f370c8bbf2ae9564e19edef8b6e8c7d266`
   - trigger head `6532c82d1c75b983465bcac40cf36f947462e0b9`
   - Run #30 `34021733515`
   - CI SUCCESS
   - artifact `9986265293`
   - digest `sha256:c7083f69433ae71029673d7ac21291a6f6b8543060eec4a794e0949eb0621b3b`
   - runtime result: **NOT VERIFIED**; no Run #30 runtime log is available

4. protected baseline restored
   - code checkpoint `790a945780ea561518dd072d9f73c0e3e89b4700`
   - trigger Run #31 `34024292927`
   - trigger head `be3064da39e2913719de6fc800e7f417d28a0aec`
   - CI SUCCESS
   - artifact `9987082611`
   - digest `sha256:74aef6d516965fc1ec93fc32d0a6ad2fe0358e36a439afdf1b9d2e6c344499bd`
   - Run #31 tree matches the restored protected code checkpoint tree

## CURRENT OPEN QUESTION

The remaining branch point is exactly this:

- Does `vkCmdCopyQueryPoolResults` fail only when its immediate destination is the persistent HOST_VISIBLE mapped buffer?
- Or does the query-copy result remain wrong even when the immediate destination is DEVICE_LOCAL?

Run #30 was built specifically to answer this without sacrificing the known direct-readback visual fix.

# NEXT ACTION

1. **Do not rebuild.** Reuse Run #30 artifact `9986265293`.
2. Test **Star Fox Zero JP first** with that Run #30/intermediate build.
3. Capture `log.txt` from startup through the reproduced flicker scene.
4. Confirm the startup build is the Run #30/intermediate revision, not restored Run #31.
5. Classify both:
   - whether mapped query values become nonzero
   - whether visual flicker remains fixed
6. Then test Bayonetta 2 JP with the same Run #30 artifact.
7. If the intermediate path repairs mapped values, narrow the defect to query-copy directly into host-visible mapped memory.
8. If the intermediate path still produces mapped zero, classify `vkCmdCopyQueryPoolResults` itself as the failing Adreno path and retain protected `vkGetQueryPoolResults` while investigating a non-blocking replacement.
9. Record the runtime result in `DEBUG_HISTORY_20260906_QUERY_MAPPED_DIRECT_DIVERGENCE.md` before any next code experiment.

## DO NOT ROLLBACK / DO NOT TOUCH

- Star Fox Zero + Bayonetta 2 title-gated direct-readback FIXED behavior
- PASS branch/head `exp-bayo2-query-direct-readback` / `5d758a096ee9409e7c25372a6caa9ad9d2378575`
- VS DEFAULT_VAL synthesize fixes
- `main`
- XCX query behavior; keep it separate

## New-tab startup prompt

`Cemu Windows ARM64 / Adreno 작업 계속. GitHub의 CURRENT_HANDOFF.md와 DEBUG_HISTORY_20260906_QUERY_MAPPED_DIRECT_DIVERGENCE.md를 먼저 읽고 실제 branch/HEAD와 대조해. Star Fox Zero와 Bayonetta 2의 vkGetQueryPoolResults direct readback FIXED 상태는 절대 되돌리지 말고, CURRENT_HANDOFF의 NEXT ACTION부터 진행해. main은 건드리지 마.`
