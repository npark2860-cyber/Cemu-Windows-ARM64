# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

## CURRENT STATE

Repository:

- `npark2860-cyber/Cemu-Windows-ARM64`

Active branch:

- `diag-query-mapped-direct-divergence`

Accepted non-blocking experiment code checkpoint:

- `bac23bd90b3ce51b87f7a7e955aea9e90a2005ef`

CI trigger branch/head:

- `diag-bayo2-target-query-draw-fingerprint`
- `57f2e9e7dbdfebdd450449ff264476d31fbc1e60`

Protected blocking-direct fallback:

- `790a945780ea561518dd072d9f73c0e3e89b4700`

`main` is out of scope.

## VERIFIED PASS

Run #32:

- run `34074452899`
- job `101597749211`
- artifact `10002247263`
- digest `sha256:156bc7f4b6b977704c6d7c41719a1f62c25dc43a5b1914dd1a927ad758fba2af`
- CI SUCCESS

Star Fox Zero JP:

- FULL RUNTIME PASS
- formerly broken/flickering scene remained FIXED
- `404653` logged direct reads
- all `VK_SUCCESS`
- `VK_NOT_READY=0`
- `retry=1=0`

Bayonetta 2 JP:

- FULL RUNTIME PASS
- game remained in the same FIXED state
- `65236` logged direct reads
- all `VK_SUCCESS`
- `VK_NOT_READY=0`
- `retry=1=0`
- no query-retention stall/exhaustion observed

Detailed Run #32 record:

- `DEBUG_HISTORY_20260907_QUERY_NOWAIT_PASS.md`

## ACCEPTED CLASSIFICATION

For these two reproduced Adreno cases:

- `vkCmdCopyQueryPoolResults` is the failing result-copy path.
- `vkGetQueryPoolResults` returns the correct result.
- after `HasCommandBufferFinished(...)`, `VK_QUERY_RESULT_WAIT_BIT` was unnecessary in both tested titles.

Accepted replacement behavior:

- target gate: Star Fox Zero JP + Bayonetta 2 JP only
- `vkGetQueryPoolResults(... VK_QUERY_RESULT_64_BIT)`
- `VK_SUCCESS`: consume direct result
- `VK_NOT_READY`: retain fragment/query index and retry later

XCX remains separate. Do not globalize this behavior.

# NEXT ACTION

1. Promote the accepted non-blocking direct-readback behavior from the diagnostic patch script into the real Vulkan query source on a non-main branch.
2. Keep the title gate limited to Star Fox Zero JP + Bayonetta 2 JP.
3. Preserve `VK_NOT_READY` retain/retry semantics.
4. Static-verify the source diff first.
5. Run CI once for the promoted-source implementation.
6. Reuse that artifact for final smoke if needed.
7. Do not touch `main` or XCX.

## DO NOT ROLLBACK / DO NOT TOUCH

- retained PASS branch/head `exp-bayo2-query-direct-readback` / `5d758a096ee9409e7c25372a6caa9ad9d2378575`
- protected blocking fallback `790a945780ea561518dd072d9f73c0e3e89b4700`
- VS DEFAULT_VAL synthesize fixes
- `main`
- XCX query behavior
