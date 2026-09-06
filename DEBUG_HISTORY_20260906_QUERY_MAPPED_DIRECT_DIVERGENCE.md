# DEBUG HISTORY — Query mapped/direct divergence

Date: 2026-09-06

## Protected direct-readback baseline

Do not remove or weaken the title-gated direct-readback path until a replacement reproduces the known runtime behavior.

- Star Fox Zero JP (`00050000-101AFF00`): Run #25 fixed the original/large flicker with `vkGetQueryPoolResults` direct readback.
- User retrospective A/B recheck on Run #25 confirms a **small-object residual flicker was already present immediately after the original fix**.
- Therefore Run #25 must no longer be described as visually perfect; it is the baseline where the major flicker is fixed but the smaller residual symptom remains.
- Bayonetta 2 JP (`00050000-1011B900`): Run #26 fixed the reproduced flicker with the same direct-readback path.
- PASS experiment HEAD: `5d758a096ee9409e7c25372a6caa9ad9d2378575` on `exp-bayo2-query-direct-readback`.
- `main` remains untouched at `58954b34d147b134d7b23ee61b2057f49da2c014`.

## Run #27 — mapped/direct side-by-side capture

- Run `34013912085`
- Job `101434315915`
- Head `77c47610c3c472198f13fb399f483691411c1c8c`
- CI SUCCESS
- Star Fox Zero JP v16

Selected mapped query-result memory:

`[QUERY_MAP_META] found=1 memoryType=4 heap=0 flags=0x0000000f requested=0x0000000e fallback=0`

Actual flags `0x0f` = DEVICE_LOCAL | HOST_VISIBLE | HOST_COHERENT | HOST_CACHED.

First completed divergence:

`direct=1192 mapped=0 selected=1192 mismatch=1`

The direct query-pool value remained correct and preserved the Run #25 major-flicker fix while the mapped path remained stale/zero.

## Run #28 — TRANSFER_WRITE -> HOST_READ barrier

- Run `34017106924`
- Job `101442707298`
- Head `79fbf25ab8a255fe15ad8210bad21a9a5491c34e`
- CI SUCCESS

Exact-range `TRANSFER_WRITE -> HOST_READ` barrier after `vkCmdCopyQueryPoolResults`.

Result: **FAIL to repair mapped path**. Mapped remained zero for essentially all nonzero direct results. Two rare mapped nonzero values exactly matched direct.

Conclusion: missing transfer-to-host barrier alone is not the cause.

## Run #29 — explicit mapped-memory invalidate

- Run `34019347912`
- Job `101448913796`
- Head `7a71d5405f3d438d52dce9554eb93a0ee49a2ed2`
- CI SUCCESS
- Runtime build banner `Init Cemu 7a71d54`
- Capture `log(20260906-081927).zip`

Results:

- `[QUERY_DIRECT]`: 299,255
- `cmdFinished=1`: 299,255 / 299,255
- `vkInvalidateMappedMemoryRanges=VK_SUCCESS(0)`: 299,255 / 299,255
- `vkGetQueryPoolResults=VK_SUCCESS(0)`: 299,255 / 299,255
- direct nonzero: 299,094
- mapped nonzero: 2
- mismatch: 299,092

Result: **FAIL to repair mapped path**.

Conclusion: HOST_COHERENT + explicit invalidate still leaves mapped stale/zero almost always. Missing invalidate is closed as the explanation.

## Run #30 — DEVICE_LOCAL intermediate query copy

- Run `34021733515`
- Job `101455446048`
- Head `6532c82d1c75b983465bcac40cf36f947462e0b9`
- Runtime build banner `Init Cemu 6532c82`
- Capture `log(20260906-091505).zip`

Target path:

`vkCmdCopyQueryPoolResults -> DEVICE_LOCAL intermediate -> vkCmdCopyBuffer -> HOST_VISIBLE mapped buffer -> CPU mapped read`

Runtime observations:

- `[QUERY_INTERMEDIATE] allocated=1 size=8192`
- `[QUERY_DIRECT]`: 218,590
- direct nonzero: 218,450
- mapped nonzero: 1
- mismatch: 218,449
- one nonzero exact agreement was observed (`direct=3032 mapped=3032 mismatch=0`), but it was isolated and did not persist
- protected direct result remained selected

Result: **FAIL to repair mapped path**.

Important correction to earlier interpretation:

- User initially noticed small-object flicker while testing Run #30.
- A later A/B recheck of the original Run #25 build confirmed the same small-object flicker was already present immediately after the major flicker fix.
- Therefore **Run #30 is NOT proven to have introduced that small-object flicker**.
- Retract the previous claim that Run #30 caused a visual regression.
- Run #30 is still closed as a mapped-path repair because intermediate copy did not make mapped/direct values agree consistently.

## Run #31 — exact direct-readback restoration

- Run `34024292927`
- Job `101462397659`
- Head `be3064da39e2913719de6fc800e7f417d28a0aec`
- CI SUCCESS
- Diagnostic branch restore commit: `790a945780ea561518dd072d9f73c0e3e89b4700`
- Runtime banner `Init Cemu be3064d`
- Capture `log(20260906-102908).zip`

Run #31 removes the Run #30 intermediate allocation/copy/barriers and restores the exact direct-readback experiment script.

Runtime results:

- `[QUERY_INTERMEDIATE]`: absent
- `[QUERY_DIRECT]`: 170,384
- `vkResult=0`: 170,384 / 170,384
- direct nonzero: 170,264
- mapped nonzero: 0
- `selected == direct`: 170,384 / 170,384
- `mismatch=0`: 120, all `direct=0 / mapped=0`
- nonzero direct/mapped agreement: 0

This confirms the direct-readback workaround functions independently of the mapped path. It does **not** solve the remaining small-object flicker, which predates Run #30 and was already present in Run #25.

## Current interpretation

Two Star Fox symptoms must now be kept separate:

1. **Original/large flicker** — fixed by the title-gated direct `vkGetQueryPoolResults` path in Run #25.
2. **Small-object residual flicker** — still present in Run #25 and therefore not explained by Run #27-30 mapped-readback experiments.

The mapped result path remains independently broken (`direct>0 / mapped=0` almost always), but it is not yet proven to be the cause of the remaining small-object flicker because the active direct path bypasses mapped values for accumulation.

## NEXT ACTION

1. Preserve the exact Run #25/Run #31 direct-readback baseline and the major-flicker fix.
2. Treat the small-object flicker as a separate unresolved symptom from this point forward.
3. Do not attribute that residual flicker to Run #30.
4. Do not repeat barrier/invalidate/intermediate-copy experiments as attempts to fix the residual symptom without new evidence.
5. Establish a reproducible scene/object for the small flicker and correlate that symptom against query/draw activity while direct results remain selected.
6. Keep XCX separate; do not globalize blocking direct readback.
