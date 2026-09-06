# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> 이 파일은 현재 상태만 유지한다. 상세 근거는 `DEBUG_HISTORY_20260906_QUERY_MAPPED_DIRECT_DIVERGENCE.md`를 우선한다.

## CURRENT STATE

Repository:

- `npark2860-cyber/Cemu-Windows-ARM64`

Active branch:

- `diag-query-mapped-direct-divergence`

Last verified code-changing checkpoint:

- `790a945780ea561518dd072d9f73c0e3e89b4700`
- `diagnostics: restore protected direct query readback baseline`

Later branch movement is documentation-only unless GitHub proves otherwise.

`main` is out of scope and must not be modified.

## IMMUTABLE VERIFIED PASS

Do not regress:

- Star Fox Zero JP (`00050000-101AFF00`): Run #25 FIXED by title-gated `vkGetQueryPoolResults` direct readback.
- Bayonetta 2 JP (`00050000-1011B900`): Run #26 FIXED by the same path.
- retained PASS branch/head: `exp-bayo2-query-direct-readback` / `5d758a096ee9409e7c25372a6caa9ad9d2378575`
- XCX remains separate; do not globalize blocking direct readback.

## CONFIRMED ROOT-CAUSE BOUNDARY

Star Fox Zero mapped/direct instrumentation proved completed queries can return:

- `cmdFinished=1`
- `vkResult=0`
- `direct > 0`
- `mapped=0`
- `mismatch=1`

Bayonetta 2 memory metadata proved the query-result allocation is:

- `memoryType=4`
- actual flags `0x0000000f` = `DEVICE_LOCAL | HOST_VISIBLE | HOST_COHERENT | HOST_CACHED`
- requested flags `0x0000000e`
- `fallback=0`

Therefore unfinished-query and non-coherent-invalidate explanations are ruled out for the captured target path.

## EXPERIMENTS ALREADY DONE

1. transfer-write -> host-read barrier
   - commit `79fbf25ab8a255fe15ad8210bad21a9a5491c34e`
   - Run #28 `34017106924`
   - CI SUCCESS

2. forced mapped-memory invalidate
   - commit `7a71d5405f3d438d52dce9554eb93a0ee49a2ed2`
   - Run #29 `34019347912`
   - CI SUCCESS
   - captured memory is HOST_COHERENT; invalidate is not root fix

3. DEVICE_LOCAL intermediate isolation
   - diagnostic commit `eb04e6f370c8bbf2ae9564e19edef8b6e8c7d266`
   - trigger head `6532c82d1c75b983465bcac40cf36f947462e0b9`
   - Run #30 `34021733515`
   - artifact `9986265293`
   - digest `sha256:c7083f69433ae71029673d7ac21291a6f6b8543060eec4a794e0949eb0621b3b`
   - implementation includes:
     - `vkCmdCopyQueryPoolResults` -> DEVICE_LOCAL intermediate
     - `TRANSFER_WRITE -> TRANSFER_READ` barrier
     - `vkCmdCopyBuffer` -> mapped host buffer
     - `TRANSFER_WRITE -> HOST_READ` barrier
   - Star Fox Zero JP runtime: **FAILED TO REPAIR MAPPED PATH**
   - expected build confirmed: `Init Cemu 6532c82`, `[QUERY_INTERMEDIATE] allocated=1`
   - parsed logged query records: `336166`
   - all parsed `vkResult=0`
   - direct nonzero `335995`
   - mismatch `335993`
   - mapped nonzero among logged records only `2`
   - conclusion: moving the immediate destination to DEVICE_LOCAL does not repair the systematic zero-result copy path

4. protected baseline restored
   - code checkpoint `790a945780ea561518dd072d9f73c0e3e89b4700`
   - Run #31 `34024292927`
   - artifact `9987082611`
   - digest `sha256:74aef6d516965fc1ec93fc32d0a6ad2fe0358e36a439afdf1b9d2e6c344499bd`
   - CI SUCCESS

## CURRENT CLASSIFICATION

The failure boundary is now narrowed past:

- query completion
- host-coherent memory selection
- explicit host visibility barrier
- explicit invalidate
- direct query-copy destination being HOST_VISIBLE

Run #30 still fails systematically even when `vkCmdCopyQueryPoolResults` writes into DEVICE_LOCAL memory first and all transfer dependencies are explicit.

The remaining leading suspect for these reproduced titles is the Adreno `vkCmdCopyQueryPoolResults` result-copy path itself, while `vkGetQueryPoolResults` returns correct values.

Bayonetta 2 Run #30 confirmation is still required before closing this line for both reproduced titles.

# NEXT ACTION

1. **Do not rebuild.** Reuse Run #30 artifact `9986265293`.
2. Test **Bayonetta 2 JP** with this exact Run #30 build.
3. Capture `log.txt` through the previously reproduced scene.
4. Verify the log contains:
   - `Init Cemu 6532c82`
   - `[QUERY_INTERMEDIATE] allocated=1`
   - title `000500001011b900`
5. Parse direct/mapped/mismatch results.
6. If Bayonetta 2 reproduces Star Fox's intermediate-path failure, close the mapped-copy investigation for these two titles.
7. Then implement one new variable only: **non-blocking direct readback**.
   - call `vkGetQueryPoolResults` without `VK_QUERY_RESULT_WAIT_BIT` only after `HasCommandBufferFinished(...)` is true
   - on `VK_SUCCESS`, consume the direct value
   - on `VK_NOT_READY`, keep the fragment/query index and retry later; do not block and do not release it
8. Static verify first, then CI only once.
9. Re-test Star Fox Zero and Bayonetta 2 before considering any broader rollout.

## DO NOT ROLLBACK / DO NOT TOUCH

- Star Fox Zero + Bayonetta 2 title-gated direct-readback FIXED behavior
- PASS branch/head `exp-bayo2-query-direct-readback` / `5d758a096ee9409e7c25372a6caa9ad9d2378575`
- VS DEFAULT_VAL synthesize fixes
- `main`
- XCX query behavior

## New-tab startup prompt

`Cemu Windows ARM64 / Adreno 작업 계속. GitHub의 CURRENT_HANDOFF.md와 DEBUG_HISTORY_20260906_QUERY_MAPPED_DIRECT_DIVERGENCE.md부터 읽고 실제 branch/HEAD와 대조해. Star Fox Zero와 Bayonetta 2의 vkGetQueryPoolResults direct readback FIXED 상태는 절대 되돌리지 말고 CURRENT_HANDOFF NEXT ACTION부터 진행해. main과 XCX는 건드리지 마.`
