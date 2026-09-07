# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> 현재 상태만 기록한다. 상세 근거는 `DEBUG_HISTORY_20260906_QUERY_MAPPED_DIRECT_DIVERGENCE.md`를 우선한다.

## CURRENT STATE

Repository:

- `npark2860-cyber/Cemu-Windows-ARM64`

Active branch:

- `diag-query-mapped-direct-divergence`

Current experiment code checkpoint:

- `bac23bd90b3ce51b87f7a7e955aea9e90a2005ef`
- `diagnostics: try nonblocking direct query readback`

CI trigger branch/head:

- `diag-bayo2-target-query-draw-fingerprint`
- `57f2e9e7dbdfebdd450449ff264476d31fbc1e60`

Protected blocking-direct fallback checkpoint:

- `790a945780ea561518dd072d9f73c0e3e89b4700`

`main` is out of scope and must not be modified.

## IMMUTABLE VERIFIED PASS

Do not regress:

- Star Fox Zero JP (`00050000-101AFF00`): Run #25 FIXED by title-gated `vkGetQueryPoolResults` direct readback.
- Bayonetta 2 JP (`00050000-1011B900`): Run #26 FIXED by the same path.
- retained PASS branch/head: `exp-bayo2-query-direct-readback` / `5d758a096ee9409e7c25372a6caa9ad9d2378575`
- XCX remains separate.

## CLOSED INVESTIGATION PATHS

The following do not repair the reproduced mapped/direct divergence and must not be repeated blindly:

- transfer-write -> host-read visibility barrier — Run #28
- forced mapped-memory invalidate — Run #29
- DEVICE_LOCAL intermediate query-copy destination — Run #30

Result memory is HOST_COHERENT (`flags=0x0f`, fallback=0).

Run #30 DEVICE_LOCAL intermediate contains both required transfer barriers yet fails on both reproduced titles:

- Star Fox Zero: 336166 logged records, 335993 mismatch, mapped nonzero only 2
- Bayonetta 2: 23034 explicit mismatch records
- common mismatch: `cmdFinished=1`, `vkResult=0`, `direct>0`, `mapped=0`

Therefore, for these two reproduced Adreno cases, the current failure boundary is the `vkCmdCopyQueryPoolResults` result-copy path itself. `vkGetQueryPoolResults` returns correct values.

Do not generalize this to XCX or all Vulkan devices/titles.

## CURRENT EXPERIMENT

Non-blocking direct readback, target-gated to Star Fox Zero JP + Bayonetta 2 JP only.

Single changed experiment file:

- `tools/diagnostics/Apply-StarFoxDirectQueryReadbackExperiment.py`

Behavior:

- direct `vkGetQueryPoolResults` is still called only after existing command-buffer-finished check
- remove only direct-call `VK_QUERY_RESULT_WAIT_BIT`
- `VK_SUCCESS`: consume direct value
- `VK_NOT_READY`: retain fragment/query index, do not accumulate/release/erase, return not-ready and retry later
- log `retry` and `notReadyTotal`
- non-target titles unchanged
- XCX unchanged
- `main` unchanged

## RUN #32

- Run ID `34074452899`
- job `101597749211`
- head `57f2e9e7dbdfebdd450449ff264476d31fbc1e60`

Already verified SUCCESS before compile:

- all patch/trace application and validation stages
- existing observation-only checks
- ARM64 toolchain setup
- vcpkg/NuGet setup

Last GitHub state recorded here:

- `Configure`: IN PROGRESS
- `Build Cemu once`: pending
- artifact: not yet claimed

Do not trigger another CI run while Run #32 is healthy/in progress.

# NEXT ACTION

1. Check Run #32 to completion.
2. If CI SUCCESS, use its artifact; do not rebuild.
3. Test Star Fox Zero JP first.
4. Verify visual FIXED state plus `[QUERY_DIRECT] retry=1/0` and `notReadyTotal` behavior.
5. If Star Fox passes, test Bayonetta 2 JP with the same artifact.
6. Both must reproduce the protected Run #25/#26 FIXED behavior before accepting non-blocking direct readback.
7. If either regresses, preserve/revert to protected blocking direct behavior; do not reopen barrier/invalidate/intermediate experiments.

## DO NOT ROLLBACK / DO NOT TOUCH

- retained PASS branch/head `exp-bayo2-query-direct-readback` / `5d758a096ee9409e7c25372a6caa9ad9d2378575`
- VS DEFAULT_VAL synthesize fixes
- `main`
- XCX query behavior

## New-tab startup prompt

`Cemu Windows ARM64 / Adreno 작업 계속. GitHub의 CURRENT_HANDOFF.md와 DEBUG_HISTORY_20260906_QUERY_MAPPED_DIRECT_DIVERGENCE.md부터 읽고 실제 branch/HEAD와 대조해. Star Fox Zero와 Bayonetta 2의 direct-readback FIXED 기준선은 절대 되돌리지 말고 CURRENT_HANDOFF NEXT ACTION부터 진행해. main과 XCX는 건드리지 마.`
