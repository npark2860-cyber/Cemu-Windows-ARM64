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

Do not repeat blindly:

- transfer-write -> host-read visibility barrier — Run #28
- forced mapped-memory invalidate — Run #29
- DEVICE_LOCAL intermediate query-copy destination — Run #30

Run #30 failed to repair the copied query result on both Star Fox Zero and Bayonetta 2. The current target-specific failure boundary is `vkCmdCopyQueryPoolResults`; `vkGetQueryPoolResults` returns correct values.

Do not generalize this to XCX or all Vulkan devices/titles.

## CURRENT EXPERIMENT

Non-blocking direct readback, target-gated to Star Fox Zero JP + Bayonetta 2 JP only.

Single experiment file:

- `tools/diagnostics/Apply-StarFoxDirectQueryReadbackExperiment.py`

Behavior:

- call direct `vkGetQueryPoolResults` only after existing `HasCommandBufferFinished(...)` is true
- no `VK_QUERY_RESULT_WAIT_BIT`
- `VK_SUCCESS`: consume direct value
- `VK_NOT_READY`: retain fragment/query index and retry later; do not accumulate/release/erase
- non-target titles unchanged
- XCX unchanged
- `main` unchanged

## RUN #32 — CI SUCCESS

- Run ID `34074452899`
- job `101597749211`
- head `57f2e9e7dbdfebdd450449ff264476d31fbc1e60`
- conclusion `SUCCESS`
- artifact ID `10002247263`
- artifact name `cemu-arm64-bayo2-target-query-draw-fingerprint`
- digest `sha256:156bc7f4b6b977704c6d7c41719a1f62c25dc43a5b1914dd1a927ad758fba2af`

## STAR FOX ZERO RUN #32 RUNTIME

Supplied log confirms:

- `Init Cemu 57f2e9e`
- `TitleId: 00050000-101aff00`

Parsed `[QUERY_DIRECT]`:

- logged records `404653`
- sequence counter reached `n=572838`
- all logged `vkResult=0` (`VK_SUCCESS`)
- `VK_NOT_READY=0`
- `retry=1=0`
- `retry=0=404653`
- maximum `notReadyTotal=0`
- direct nonzero `404430`
- mapped nonzero `2`
- mismatch `404428`
- selected direct `404653/404653`
- no crash/fatal/assert/VK_ERROR/device-lost record found

Classification:

- **NONBLOCKING API READINESS PASS** on Star Fox Zero.
- After `HasCommandBufferFinished(...)`, WAIT_BIT is unnecessary in this capture; every direct query read returned immediately with `VK_SUCCESS`.
- Retry path was not exercised because `VK_NOT_READY` never occurred.
- Mapped-copy failure remains, direct result selection remains correct.
- Full visual PASS is not claimed from log alone; tester visual confirmation is still required.

# NEXT ACTION

1. Confirm whether Star Fox Zero's formerly flickering scene remained visually FIXED on Run #32.
2. Reuse exact Run #32 artifact `10002247263`; **do not rebuild**.
3. Test Bayonetta 2 JP with the same artifact.
4. Capture `log.txt` through the reproduced scene.
5. Check Bayonetta 2 visual result plus `vkResult`, `retry`, `notReadyTotal`, and any stall/query-index retention symptom.
6. If Bayonetta 2 also stays FIXED and nonblocking, accept target-gated non-blocking direct readback for these two titles.
7. If either title regresses or stalls, revert behavior to protected blocking direct checkpoint `790a945780ea561518dd072d9f73c0e3e89b4700`; do not reopen barrier/invalidate/intermediate experiments.

## DO NOT ROLLBACK / DO NOT TOUCH

- retained PASS branch/head `exp-bayo2-query-direct-readback` / `5d758a096ee9409e7c25372a6caa9ad9d2378575`
- VS DEFAULT_VAL synthesize fixes
- `main`
- XCX query behavior

## New-tab startup prompt

`Cemu Windows ARM64 / Adreno 작업 계속. GitHub의 CURRENT_HANDOFF.md와 DEBUG_HISTORY_20260906_QUERY_MAPPED_DIRECT_DIVERGENCE.md부터 읽고 실제 branch/HEAD와 대조해. Star Fox Zero와 Bayonetta 2의 direct-readback FIXED 기준선은 절대 되돌리지 말고 CURRENT_HANDOFF NEXT ACTION부터 진행해. main과 XCX는 건드리지 마.`
