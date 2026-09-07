# DEBUG HISTORY — Run #32 non-blocking direct readback PASS

Date: 2026-09-07

## Scope

Target titles only:

- Star Fox Zero JP (`00050000-101AFF00`)
- Bayonetta 2 JP (`00050000-1011B900`)

Do not apply this conclusion to XCX or unrelated titles/devices.

## Build

- Run #32: `34074452899`
- job: `101597749211`
- head: `57f2e9e7dbdfebdd450449ff264476d31fbc1e60`
- artifact: `10002247263`
- digest: `sha256:156bc7f4b6b977704c6d7c41719a1f62c25dc43a5b1914dd1a927ad758fba2af`
- CI: SUCCESS

## Experiment

After the existing `HasCommandBufferFinished(...)` gate:

- call `vkGetQueryPoolResults` with `VK_QUERY_RESULT_64_BIT` only
- no `VK_QUERY_RESULT_WAIT_BIT`
- `VK_SUCCESS`: consume direct result
- `VK_NOT_READY`: retain fragment/query index and retry later
- title gate remains Star Fox Zero JP + Bayonetta 2 JP only

## Star Fox Zero JP — FULL PASS

Runtime log:

- `Init Cemu 57f2e9e`
- `404653` logged direct-readback records
- sequence counter reached `n=572838`
- all logged calls: `VK_SUCCESS`
- `VK_NOT_READY=0`
- `retry=1=0`
- `notReadyTotal=0`

Tester confirmation:

- formerly broken/flickering scene remained FIXED
- behavior unchanged from the protected blocking-direct build

Classification: **FULL RUNTIME PASS**.

## Bayonetta 2 JP — FULL PASS

Runtime log:

- `Init Cemu 57f2e9e`
- `65236` logged direct-readback records
- sequence counter reached `n=138505`
- all logged calls: `VK_SUCCESS`
- `VK_NOT_READY=0`
- `retry=1=0`
- `notReadyTotal=0`
- no query-retention stall/exhaustion symptom observed

Tester confirmation:

- game remained in the same FIXED state as the protected direct-readback build
- removing `VK_QUERY_RESULT_WAIT_BIT` caused no visible regression

Classification: **FULL RUNTIME PASS**.

## Accepted conclusion

For these two reproduced Adreno cases:

- `vkCmdCopyQueryPoolResults` remains the failing result-copy path.
- `vkGetQueryPoolResults` returns the correct value.
- after `HasCommandBufferFinished(...)`, `VK_QUERY_RESULT_WAIT_BIT` was unnecessary in both captured runs.

Accepted replacement behavior:

`HasCommandBufferFinished(...)` -> `vkGetQueryPoolResults(... VK_QUERY_RESULT_64_BIT)` -> consume on `VK_SUCCESS`, retain/retry on `VK_NOT_READY`.

## Next action

Promote this exact target-gated non-blocking direct-readback behavior from the diagnostic patch script into real source on a non-main branch, preserving the `VK_NOT_READY` retain/retry semantics. Do not touch `main` or XCX.
