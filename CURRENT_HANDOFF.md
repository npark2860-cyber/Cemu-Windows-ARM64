# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> 갱신: 2026-08-28 KST  
> 장기 확정 사실은 `TECH_BIBLE.md`, 누적 실험은 `DEBUG_HISTORY.md`를 본다.  
> 이 문서는 현재 상태와 NEXT ACTION만 정확히 유지한다.

## 1. 현재 최우선 목표

**Bayonetta 2 JP Vulkan 원거리/배경 폴리곤 플리커링 원인 규명**

증상:
- 멀리 있는 폴리곤/오브젝트가 깜빡이거나 나타났다 사라진다.
- 가까워지면 상대적으로 안정된다.
- 현재 주 타겟은 crash가 아니다.

환경:
- Windows 11 ARM64
- Snapdragon X Elite / Adreno X1-85
- Vulkan 1.3
- Bayonetta 2 JP `00050000-1011B900`, v1
- driver `f22d572733`
- compiler `E031.50.36.00`
- driver branch `pp165`

upstream `cemu-project/Cemu` Issue #1348에는 RTX 3060 Ti/x64에서도 유사한 Bayonetta 2 flicker가 있다. 사용자 exact scene과 동일 근본원인은 미확정이므로 ARM64/Adreno 전용이라고 전제하지 않는다.

## 2. 저장소 / 보호 기준점

Repository:
`npark2860-cyber/Cemu-Windows-ARM64`

주 문서 브랜치:
`runtime-experiments-arm64`

일반 진단/호환성 code-changing baseline:
`fa17d834bfebd9a41c598b1b1b702000d0ff4618`

절대 rollback 금지:
- VS producer-side `DEFAULT_VAL` synthesize/linkage fix
- AArch64 generated-code cache / I-cache coherency fix
- known-good pre-e834 Vulkan compatibility behavior
- 77/77 Runtime Diagnostics 구조

## 3. 완료/하향 실험 — 반복 금지

개선 0 / 크게 하향:
- Position Invariance (`invariant gl_Position`)
- Vulkan viewport depth-range clamp
- Vulkan `depthBiasClamp`
- Force Maximum LOD / LOD 일반 설정
- native Vulkan `negativeOneToOne` / shader `(z+w)/2` 제거
- RT simple/strong/pre-begin barriers
- forced render-pass split
- depthclip
- pipeline pNext
- VS auxHash pipeline key
- `f4c24000` `0x11↔0x1a` actual alias conversion
- `f4c24000` depth↔color format conversion
- nested/overlapping GX2 occlusion-query resume/duplicate 경로

**재실험 금지 — invalid behavior A/B:**
- `f5442800` guest-RAM roundtrip (`256/64 GPU readback → same guest RAM → main 1280 reload`)

## 4. `f5442800` multi-pitch D24 — confirmed runtime structure

동일 guest physical start `f5442800`, 동일 D24/S8 (`0x11`), tile4에 서로 다른 세 base texture가 실제 depth attachment로 존재하고 GPU write를 받는다:

- `1280x720`, pitch `1280`
- `256x256`, pitch `256`
- `64x64`, pitch `64`

Static source:
- zero-offset + same-subIndex인데 pitch가 다르면 compatible relation 생성 안 됨
- 이 zero-offset incompatible case는 `TrackDataOverlap()`에도 내려가지 않음
- normal GPU dynamic sync는 `list_compatibleRelations`만 순회
- depth clear는 별도 경로로 same physical address depth texture 전부를 순회해 clear를 전파함

Clear가 pitch와 무관하게 전파되는 것은 uniform clear value라 layout 변환이 필요 없기 때문이다. Normal draw 결과는 cross-pitch/tiled remapping이 필요하므로 같은 단순 전파를 하지 않는다.

## 5. f544 alias observation trace — completed

Branch:
`diag-bayo2-f544-depth-alias`

Runtime HEAD:
`2334cb517180dc887221b7177ef1cc190f639fb3`

Run:
`33141337691` — SUCCESS

User log:
`log(20260828-050332).txt`

Runtime:
- 세 pair 모두 `result=untracked-zero-offset-incompatible`
- runtime에서도 원인은 pitch mismatch 하나로 확인
- main 1280 rebind 1462회 전부 `newerAlias=1`
- 동시에 항상 `rels=0 / sameAddrOverlaps=0 / reloadDynamic=0`
- newest other는 항상 64x64 depth
- 1461/1462 stale-main rebind는 직전 256 + 64 write가 직접 확인됨

확정:
1. Cemu host texture-cache에는 same-address / multi-pitch D24 representation divergence가 실제 존재한다.
2. small depth pass 뒤 main representation이 더 오래된 `lastDynamicUpdate` 상태로 다시 bind된다.

## 6. f544 guest-RAM roundtrip — INVALID / never repeat

Branch:
`exp/bayo2-f544-guest-roundtrip`

Runtime HEAD:
`001df98b74e4d469ff69cd0b9c1010d7e1b07792`

Run:
`33145985810` — SUCCESS

User native-resolution log:
`log(20260828-063425).txt`

Runtime:
- `phase=begin` = 1662
- 256 + 64 `alias-to-guest` = 3324
- D24 main upload = 1662
- main reload = 1662
- failure/device-lost/pipeline failure = 0

User visual result:
- **화면이 어마어마하게 망가짐**

Correct interpretation:
- roundtrip path itself executed correctly according to its markers
- but 256/64 differently pitched/tiled complete surfaces를 same guest RAM에 순차 canonicalize한 뒤 main 1280으로 재해석하는 의미가 Wii U hardware와 동일하다는 검증이 없음
- therefore this is an **invalid causal A/B**, not root-cause confirmation
- `001df98` 추가 테스트 금지

Static audit after failure:
- Vulkan `D24_UNORM_S8_UINT` depth aspect는 `X8_D24_UNORM_PACK32`; depth low24 handling은 Vulkan packed-format rule과 일치
- experimental writer는 `LatteTextureLoader_GetInput()`을 사용하므로 Cemu AddrLib tiled address calculation 자체는 재사용함
- 따라서 현재까지 단순 D24 bit-order 또는 단순 linear-vs-tiled 실수는 확인되지 않음
- 남은 강한 문제는 cross-pitch complete-surface canonicalization semantics 자체와 custom D24 transfer의 미검증 세부사항

## 7. Main-depth first-draw observation — NEW decisive result

Branch:
`diag-bayo2-main-depth-state`

Trace script commits:
- `bdcf57df8047ff9ede4f477c33a4c517fc7342b2`
- `212a43668645cbc5342746787141dc7ebe66b2d1`

Workflow/runtime HEAD:
`ebb857a856a21b9e855c3af1f8cc72786216d4c8`

Workflow:
`Cemu ARM64 Bayonetta2 Main Depth First Draw Trace`

Run:
`33149747614` — **SUCCESS**

Artifact:
- ID `9678056157`
- `cemu-arm64-bayo2-main-depth-first-draw-trace`
- sha256 `115c1e2b66e74755f1bd3fe39c8fe721bdaf2e29118e6de82553af5f5bc68abd`

User log:
`log(20260828-081104).txt`

Trace marker:
`[BAYO2_MAIN_DEPTH_FIRST_DRAW]`

### Runtime counts

Markers: **1407**

All 1407/1407:
- current main depth = `f5442800`, 1280x720, pitch1280
- newest alias = 64x64, pitch64
- `newestAliasEvent > selfEvent`
- `priorDepthAffects=1`
- `zEnable=1`
- `zWrite=1`
- `zFunc=3`
- `stencilEnable=0`
- `backStencil=0`
- `DB_DEPTH_CONTROL=0x0000001e`
- primitive=3
- instances=1
- first draw sequence=1
- GS=0
- PS=`d4c548cae60718a8`, aux `0x79`

`zFunc=3` enum mapping = **LEQUAL**.

Event gap `newestAliasEvent - selfEvent`:
- +13: 1394
- +16: 13

Stable pipeline families:
- pipeline `7ff7d63e0f004b21`, VS `8eddd84f36abdb3e`: 1060
- pipeline `511397ecc55e3522`, VS `472453acc0a35728`: 347

No runtime regression:
- pipeline fail 0
- GLSL fail 0
- SPIR-V fail 0
- device lost 0
- normal title stop

### Render-pass semantic connection

Baseline Vulkan render-pass creation uses:
- depth `loadOp = VK_ATTACHMENT_LOAD_OP_LOAD`
- depth `storeOp = VK_ATTACHMENT_STORE_OP_STORE`
- stencil LOAD/STORE as applicable

Therefore observed chain is now:

1. small f544 depth representation receives newer GPU writes
2. main 1280 host D24 remains older and no relation/overlap/reload sync occurs
3. main render pass resumes and **LOADs the old main VkImage contents**
4. first actual draw has depth test enabled
5. compare is **LEQUAL** and previous depth therefore participates in pass/fail visibility
6. draw also has depth write enabled

### Correct conclusion

This is stronger than a cache bookkeeping anomaly.

**Confirmed:** the stale main f544 host depth reaches actual renderer-visible depth-test semantics and is consumed by gameplay draws.

Still not fully confirmed:
- Wii U hardware semantics require the 64/256 differently pitched render results to be transformed into the 1280 representation in exactly the way hypothesized
- therefore original distant flicker root cause is not yet declared proven

However f544 cross-pitch depth coherence is now the **strongest live correctness candidate**.

## 8. Current candidate ranking

1. **f5442800 cross-pitch D24 normal-write coherence / correct alias semantics**
2. exact cross-pitch/tile mapping semantics needed between 64/256 and 1280 depth views
3. upstream #1348 common Bayonetta render path correlation
4. generic normal-draw depth state outside f544 only if f544 is later disproven

## 9. Work rules

- one hypothesis per build
- source/static verification before CI
- observation fact and visual result remain separate
- no repeat of ruled-out experiments
- no rollback of permanent fixes
- no more guest-RAM full canonicalization roundtrip
- do not use simple `vkCmdCopyImage` between differently scaled/pitched surfaces as a fake fix
- do not claim Adreno-specific until generic path is excluded

# NEXT ACTION

**No new CI yet.**

1. Continue static audit of `001df98` custom D24 readback/writeback to separate transfer implementation risk from alias-semantics risk.
2. Verify `TextureDecoder_D24_S8` decode byte/endian behavior against experimental `HWFMT_8_24` writer; determine whether writer is an exact inverse for one identical surface.
3. Do not test cross-pitch sync again until a **same-surface D24 self-roundtrip validation** or equivalent semantics-preserving proof exists.
4. If identical-surface D24 transfer is statically or experimentally validated, design the next causal test to modify only the minimal physical overlap region rather than canonicalizing complete 256/64 surfaces into main RAM.
5. If identical-surface D24 transfer is not inverse-correct, fix/validate that transfer independently; do not mix it with Bayonetta alias behavior.
6. Append this first-draw result to `DEBUG_HISTORY.md` before the next behavior build.

## New-tab startup prompt

`Cemu ARM64 Bayonetta 2 flicker 분석을 이어간다. GitHub CURRENT_HANDOFF.md, TECH_BIBLE.md, DEBUG_HISTORY.md를 source of truth로 읽고 code baseline fa17d83을 유지해라. 끝난 Position Invariance, viewport clamp, depthBiasClamp, LOD, barrier variants, forced split, depthclip, pNext, VS auxHash, f4c24000 conversion, native negativeOneToOne, nested occlusion-query 실험을 반복하지 마. f5442800에는 1280x720/pitch1280, 256x256/pitch256, 64x64/pitch64 D24 reps가 있고 small writes 뒤 main은 relation 없이 stale로 재bind된다. guest-RAM full roundtrip 001df98은 1662회 실행되며 화면을 대규모 파괴해 invalid A/B로 폐기됐다. 최신 observation build ebb857a / Run 33149747614 / log(20260828-081104).txt에서는 main return first draw 1407/1407이 priorDepthAffects=1, Z_ENABLE=1, Z_WRITE=1, Z_FUNC=LEQUAL이었고 Vulkan depth loadOp도 LOAD라 stale main depth가 실제 visibility test에 사용됨이 확정됐다. NEXT ACTION은 새 CI 없이 D24 self-roundtrip inverse correctness와 cross-pitch alias semantics를 정적으로 분리 검증하는 것이다.`