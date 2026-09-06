# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> 갱신: 2026-09-06 KST
> GitHub branch / HEAD / Actions / debug history를 source of truth로 사용한다. 이전 대화를 추측해서 복원하지 않는다.

## 0. 먼저 읽을 문서

1. `TECH_BIBLE.md`
2. `DEBUG_HISTORY.md`
3. `DEBUG_HISTORY_20260829_QUERY_COMPARE.md`
4. `DEBUG_HISTORY_20260906_STARFOX_QUERY_FOCUS_RUNTIME.md`
5. `DEBUG_HISTORY_20260906_STARFOX_BAYO2_DIRECT_QUERY_READBACK_RUNTIME.md`
6. `DEBUG_HISTORY_20260906_QUERY_MAPPED_DIRECT_DIVERGENCE.md`
7. `CURRENT_HANDOFF.md`

## 1. Repository state

Repository: `npark2860-cyber/Cemu-Windows-ARM64`

Protected main remains untouched:

`58954b34d147b134d7b23ee61b2057f49da2c014`

Docs branch:

`diag-bayo2-target0-resource-identity`

CI branch:

`diag-bayo2-target-query-draw-fingerprint`

Protected runtime-PASS branch:

`exp-bayo2-query-direct-readback`

Protected runtime-PASS HEAD:

`5d758a096ee9409e7c25372a6caa9ad9d2378575`

Current mapped/direct diagnostic branch:

`diag-query-mapped-direct-divergence`

Current diagnostic HEAD:

`eb04e6f370c8bbf2ae9564e19edef8b6e8c7d266`

## 2. Protected runtime PASS — never roll back

Star Fox Zero JP `00050000-101AFF00`:

- Run #25
- direct `vkGetQueryPoolResults`
- visual flicker FIXED

Bayonetta 2 JP `00050000-1011B900`:

- Run #26
- same direct `vkGetQueryPoolResults`
- visual flicker FIXED

The direct result must remain selected until a replacement mapped path reproduces both PASS results.

## 3. Query-consumption separation

Star Fox Zero / Bayonetta 2:

- CPU occlusion query type=0
- exported CPU query consumption active

XCX:

- GPU occlusion query type=2
- exported `GX2QueryGetOcclusionResult()` consumption not observed

Do not transplant Star Fox/Bayo2 behavior to XCX without new evidence.

## 4. Run #27 — persistent mapped path divergence confirmed

- Run `34013912085`
- Head `77c47610c3c472198f13fb399f483691411c1c8c`
- CI SUCCESS

Mapped result memory:

`memoryType=4 flags=0x0000000f`

= DEVICE_LOCAL | HOST_VISIBLE | HOST_COHERENT | HOST_CACHED.

Completed queries showed:

`cmdFinished=1, direct>0, mapped=0`

while direct values preserved correct rendering.

## 5. Run #28 — device->host barrier FAIL

- Run `34017106924`
- Head `79fbf25ab8a255fe15ad8210bad21a9a5491c34e`
- CI SUCCESS

Added exact-range:

`TRANSFER_WRITE -> HOST_READ`

Result: mapped remained zero almost always.

Conclusion: missing buffer barrier alone is not the cause.

## 6. Run #29 — explicit invalidate FAIL

- Run `34019347912`
- Job `101448913796`
- Head `7a71d5405f3d438d52dce9554eb93a0ee49a2ed2`
- CI SUCCESS
- Runtime Star Fox Zero JP

Capture: `log(20260906-081927).zip`

Results:

- query observations: 299,255
- command buffer finished: 100%
- `vkInvalidateMappedMemoryRanges`: VK_SUCCESS 100%
- direct `vkGetQueryPoolResults`: VK_SUCCESS 100%
- direct nonzero: 299,094
- mapped nonzero: 2
- mismatch: 299,092

The two nonzero mapped values exactly matched direct.

Therefore:

- explicit invalidate does not repair the path
- HOST_COHERENT cache visibility alone is not the explanation
- bind/map offset is unlikely to be globally wrong

## 7. Current experiment — Run #30

Diagnostic commit:

`eb04e6f370c8bbf2ae9564e19edef8b6e8c7d266`

For Star Fox Zero and Bayonetta 2 only:

`vkCmdCopyQueryPoolResults`
`-> DEVICE_LOCAL intermediate buffer`
`-> TRANSFER_WRITE/TRANSFER_READ barrier`
`-> vkCmdCopyBuffer`
`-> existing HOST_VISIBLE mapped buffer`
`-> TRANSFER_WRITE/HOST_READ barrier`
`-> CPU mapped read`

The failed explicit invalidate from Run #29 is removed.

The direct `vkGetQueryPoolResults` value remains the selected runtime result, so the known FIXED visual behavior is protected.

Purpose: isolate whether Adreno fails specifically when `vkCmdCopyQueryPoolResults` writes directly into HOST_VISIBLE/HOST_CACHED memory.

## 8. NEXT ACTION

1. Trigger/build Run #30 from `eb04e6f370c8bbf2ae9564e19edef8b6e8c7d266`.
2. Run Star Fox Zero JP first.
3. Confirm `[QUERY_INTERMEDIATE] allocated=1`.
4. Inspect `[QUERY_DIRECT] ... path=intermediate`.
5. Success criterion: nonzero `direct=N mapped=N mismatch=0` consistently.
6. If PASS, test Bayonetta 2 with the same build.
7. If both PASS and mapped/direct agree, convert this into the narrowest permanent Adreno-compatible mapped path and regression-test BOTW/XCX separately.
8. If mapped still zero, stop repeating host cache/barrier experiments and investigate query-copy execution/storage behavior directly.
9. Do not globally switch every title to blocking direct reads.

## DO NOT ROLLBACK

- Star Fox Zero Run #25 direct-readback FIX
- Bayonetta 2 Run #26 direct-readback FIX
- VS DEFAULT_VAL synthesize/linkage fixes
- AArch64 generated-code cache/I-cache fix
- known-good pre-e834 Vulkan baseline
- `main` untouched state

## New-tab startup prompt

`Cemu Windows ARM64 / Adreno 작업 계속. GitHub CURRENT_HANDOFF.md와 DEBUG_HISTORY_20260906_QUERY_MAPPED_DIRECT_DIVERGENCE.md를 source of truth로 읽고 실제 branch/HEAD/Actions와 대조해. main은 58954b34d147b134d7b23ee61b2057f49da2c014로 untouched. Star Fox Zero/Bayonetta 2 direct vkGetQueryPoolResults FIXED 상태는 절대 되돌리지 마. Run #28 TRANSFER_WRITE->HOST_READ barrier와 Run #29 explicit invalidate는 mapped path를 복구하지 못했다. 현재 NEXT ACTION은 DEVICE_LOCAL intermediate query buffer -> vkCmdCopyBuffer -> HOST_VISIBLE mapped buffer 실험 Run #30이다. XCX는 별도 type=2 계열로 유지해.`
