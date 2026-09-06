# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> 갱신: 2026-09-06 KST
> GitHub branch / HEAD / Actions / debug history를 source of truth로 사용한다.

## Repository state

Repository: `npark2860-cyber/Cemu-Windows-ARM64`

Protected `main` remains untouched:

`58954b34d147b134d7b23ee61b2057f49da2c014`

Protected runtime-PASS branch:

- `exp-bayo2-query-direct-readback`
- HEAD `5d758a096ee9409e7c25372a6caa9ad9d2378575`

Docs branch:

`diag-bayo2-target0-resource-identity`

Diagnostic development branch:

- `diag-query-mapped-direct-divergence`
- intermediate-copy implementation commit `eb04e6f370c8bbf2ae9564e19edef8b6e8c7d266`

CI trigger branch:

- `diag-bayo2-target-query-draw-fingerprint`
- current CI implementation HEAD `6532c82d1c75b983465bcac40cf36f947462e0b9`

## Protected runtime PASS — never roll back

Star Fox Zero JP `00050000-101AFF00`:

- Run #25
- direct `vkGetQueryPoolResults`
- visual flicker FIXED

Bayonetta 2 JP `00050000-1011B900`:

- Run #26
- same direct `vkGetQueryPoolResults`
- visual flicker FIXED

The direct result remains selected until a replacement mapped path reproduces both PASS results.

## Query-consumption separation

Star Fox Zero / Bayonetta 2:

- CPU occlusion query type=0
- exported CPU query consumption active

XCX:

- GPU occlusion query type=2
- exported CPU GET consumption not observed

Do not transplant Star Fox/Bayo2 behavior to XCX without evidence.

## Run #27 — mapped/direct divergence confirmed

- Run `34013912085`
- Head `77c47610c3c472198f13fb399f483691411c1c8c`
- CI SUCCESS

Mapped result memory:

`memoryType=4 flags=0x0000000f`

= DEVICE_LOCAL | HOST_VISIBLE | HOST_COHERENT | HOST_CACHED.

Completed queries repeatedly showed:

`cmdFinished=1, direct>0, mapped=0`

while direct values preserved correct rendering.

## Run #28 — transfer->host barrier FAIL

- Run `34017106924`
- Head `79fbf25ab8a255fe15ad8210bad21a9a5491c34e`
- CI SUCCESS

Added exact-range `TRANSFER_WRITE -> HOST_READ` barrier.

Result: mapped remained zero almost always.

Conclusion: missing buffer barrier alone is not the cause.

## Run #29 — explicit invalidate FAIL

- Run `34019347912`
- Job `101448913796`
- Head `7a71d5405f3d438d52dce9554eb93a0ee49a2ed2`
- CI SUCCESS
- Runtime Star Fox Zero JP
- Capture: `log(20260906-081927).zip`

Results:

- query observations: 299,255
- command buffer finished: 299,255 / 299,255
- `vkInvalidateMappedMemoryRanges`: VK_SUCCESS 299,255 / 299,255
- direct `vkGetQueryPoolResults`: VK_SUCCESS 299,255 / 299,255
- direct nonzero: 299,094
- mapped nonzero: 2
- mismatch: 299,092

The only two nonzero mapped values exactly matched direct.

Therefore explicit invalidate does not repair the path. HOST_COHERENT cache visibility and a missing invalidate are closed as explanations under this capture.

## Current experiment — Run #30

CI:

- Run #30 ID `34021733515`
- Job `101455446048`
- Head `6532c82d1c75b983465bcac40cf36f947462e0b9`
- Status at update: IN PROGRESS

For Star Fox Zero and Bayonetta 2 only:

`vkCmdCopyQueryPoolResults`
`-> DEVICE_LOCAL intermediate buffer`
`-> TRANSFER_WRITE/TRANSFER_READ barrier`
`-> vkCmdCopyBuffer`
`-> existing HOST_VISIBLE mapped buffer`
`-> TRANSFER_WRITE/HOST_READ barrier`
`-> CPU mapped read`

The failed explicit invalidate from Run #29 is removed.

The direct `vkGetQueryPoolResults` value remains selected, preserving the known visual FIX during this experiment.

Purpose: determine whether Adreno specifically fails when `vkCmdCopyQueryPoolResults` writes directly into HOST_VISIBLE/HOST_CACHED memory, while ordinary device-local-to-host `vkCmdCopyBuffer` works.

## NEXT ACTION

1. Let Run #30 complete; do not modify source while it is building.
2. If CI fails, record the first real compile/patch diagnostic and fix only that.
3. If CI succeeds, run Star Fox Zero JP first.
4. Confirm `[QUERY_INTERMEDIATE] allocated=1`.
5. Inspect `[QUERY_DIRECT] ... path=intermediate`.
6. Success criterion: nonzero `direct=N mapped=N mismatch=0` consistently.
7. If restored, run Bayonetta 2 with the same build.
8. If both titles pass and mapped/direct agree, convert the intermediate path into the narrowest safe Adreno-compatible mapped readback fix and regression-test BOTW/XCX separately.
9. If mapped remains zero, stop repeating host-cache/barrier experiments and investigate `vkCmdCopyQueryPoolResults` execution/storage semantics directly.
10. Do not globally switch every title to blocking direct reads.

## DO NOT ROLLBACK

- Star Fox Zero Run #25 direct-readback FIX
- Bayonetta 2 Run #26 direct-readback FIX
- VS DEFAULT_VAL synthesize/linkage fixes
- AArch64 generated-code cache/I-cache fix
- known-good pre-e834 Vulkan baseline
- `main` untouched state
