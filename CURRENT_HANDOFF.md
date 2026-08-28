# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> 갱신: 2026-08-28 KST  
> 장기 확정 사실은 `TECH_BIBLE.md`, 누적 실험은 `DEBUG_HISTORY.md`를 본다.  
> 이 문서는 현재 상태와 NEXT ACTION만 정확히 유지한다.

## 1. 현재 최우선 목표

**Bayonetta 2 JP Vulkan 원거리/배경 폴리곤 플리커링 원인 규명**

환경:
- Windows 11 ARM64
- Snapdragon X Elite / Adreno X1-85
- Vulkan 1.3
- Bayonetta 2 JP `00050000-1011B900`, v1
- driver `f22d572733`
- compiler `E031.50.36.00`
- driver branch `pp165`

증상:
- 멀리 있는 폴리곤/오브젝트가 깜빡이거나 나타났다 사라짐
- 가까워지면 상대적으로 안정
- 현재 주 타겟은 crash가 아님

upstream `cemu-project/Cemu` Issue #1348에는 RTX 3060 Ti/x64에서도 유사한 Bayonetta 2 flicker가 있으므로 ARM64/Adreno 전용이라고 전제하지 않는다.

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
- **`f5442800` cross-pitch D24 stale-main coherence as primary flicker cause — seeded A/B 0 improvement**

**재실험 금지 — invalid behavior A/B:**
- old `f5442800` unseeded guest-RAM roundtrip (`256/64 GPU readback → stale guest RAM → main 1280 reload`)
- runtime HEAD `001df98b74e4d469ff69cd0b9c1010d7e1b07792`
- 1662회 완전 실행, device-lost 0, 사용자 화면 **대규모 파괴**

## 4. `f5442800` multi-pitch D24 — confirmed runtime structure

동일 guest physical start `f5442800`, 동일 D24/S8 (`0x11`), tile4에 실제 depth attachment로 존재:

- `1280x720`, pitch `1280`
- `256x256`, pitch `256`
- `64x64`, pitch `64`

세 representation 모두 GPU write를 받는다.

Static/source fact:
- zero-offset + same-subIndex인데 pitch가 다르면 compatible relation 생성 안 됨
- 같은 branch에서 `TrackDataOverlap()`에도 내려가지 않음
- normal GPU dynamic sync는 `list_compatibleRelations`만 순회
- depth clear는 별도 same-physical-address 경로로 여러 representation에 전파

## 5. f544 alias observation trace — confirmed

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
- 원인은 pitch mismatch 하나
- main 1280 rebind 1462회 전부 `newerAlias=1`
- 동시에 항상 `rels=0 / sameAddrOverlaps=0 / reloadDynamic=0`
- newest other는 항상 64x64 depth
- 1461/1462회 직전 256 + 64 GPU write 확인

확정:
1. Cemu host texture-cache에는 same-address / multi-pitch D24 representation divergence가 실제 존재한다.
2. small depth pass 뒤 main representation이 더 오래된 상태로 다시 bind된다.

## 6. Main-depth first-draw observation — decisive structure, not visual causality

Branch:
`diag-bayo2-main-depth-state`

Runtime HEAD:
`ebb857a856a21b9e855c3af1f8cc72786216d4c8`

Run:
`33149747614` — SUCCESS

User log:
`log(20260828-081104).txt`

`[BAYO2_MAIN_DEPTH_FIRST_DRAW]` = 1407회.

1407/1407 전부:
- newest alias event > main self event
- newest alias = 64x64 / pitch64
- `priorDepthAffects=1`
- `Z_ENABLE=1`
- `Z_WRITE=1`
- `Z_FUNC=3 = LEQUAL`
- stencil off
- GS=0

Vulkan depth render pass:
- `loadOp = VK_ATTACHMENT_LOAD_OP_LOAD`
- `storeOp = VK_ATTACHMENT_STORE_OP_STORE`

Confirmed renderer chain:
1. small f544 depth representation이 더 최신 GPU write를 가짐
2. main 1280 host D24는 더 오래되고 relation sync 없음
3. main render pass가 old main VkImage depth를 LOAD
4. 첫 gameplay draw가 LEQUAL depth test로 그 prior depth를 실제 visibility 판정에 사용
5. depth write도 enabled

이 divergence가 **실제 visibility path까지 도달**하는 구조는 확정이다. 다만 Section 9 seeded A/B에서 visual improvement가 0이므로 현재 flicker의 주원인이라는 인과성은 강하게 하향한다.

## 7. D24 same-surface self-roundtrip — EXACT

Branch:
`diag-bayo2-f544-d24-self-roundtrip`

Runtime HEAD:
`eab7cbb49717525b19d8786af032ecb792735785`

Run:
`33155997608` — **SUCCESS**

User log:
`log(20260828-093344).txt`

Test condition:
- Bayonetta 2 JP
- native condition: Graphics resolution pack OFF
- cross-pitch 256/64→main logic completely removed from generated test function
- `f544 64x64/pitch64` 동일 surface 1회만 self-roundtrip

Runtime result:
`[BAYO2_F544_D24_SELFTEST] result=exact event=215433 pixels=4096 mismatch=0 depthMismatch=0 stencilMismatch=0`

따라서 4096/4096 texel의 packed D24+S8가 before/after byte-for-byte identical.

### Confirmed transfer facts

동일 surface 기준 experimental transfer path는 실측 통과:
- Vulkan D24 depth aspect `X8_D24` readback
- separate S8 stencil plane readback
- GX2 `D24 low24 | S8 high8` repack
- `LatteTextureLoader_GetInput()` 기반 tiled guest writer
- same pitch/tile reload

즉 old `001df98`의 대규모 화면 파괴를 단순 D24 bit order / endian / linear-vs-tiled corruption으로 설명할 수 없다.

## 8. Old roundtrip failure — corrected interpretation

Old invalid flow:
1. current main 1280 host depth는 guest RAM에 먼저 보존하지 않음
2. newer 256x256 depth만 guest RAM에 writeback
3. newer 64x64 depth를 같은 guest RAM에 writeback
4. **stale guest RAM 전체**를 main 1280 depth로 reload

Cemu texture가 GPU updated 상태이면 guest RAM이 최신 main host contents를 보장하지 않는다.

따라서 small aliases가 실제로 덮지 않은 main 영역도 stale RAM 값으로 되돌아가며 화면을 대규모로 파괴할 수 있다.

이 설명은 D24 same-surface exact test와 일치한다.

## 9. SEEDED f544 roundtrip — VALID NEGATIVE A/B

Branch:
`exp/bayo2-f544-seeded-roundtrip`

Patch script:
`tools/diagnostics/Apply-Bayonetta2F544SeededRoundtrip.py`

Script commit:
`62906e5ea5029aee581700b80e2e7e5a8c0af775`

Workflow/runtime HEAD:
`a2e4e70ccba4052890d8e06b06d227d41e019878`

Workflow:
`Cemu ARM64 Bayonetta2 F544 Seeded Roundtrip`

Run:
`33160442364` — **SUCCESS**

Job:
`98813341024` — **SUCCESS**

User log:
`log(20260828-105448).txt`

Test condition:
- Bayonetta 2 JP
- Graphics resolution pack OFF / native 1280x720
- Cemu startup SHA `a2e4e70`

### Corrected behavior

main rebind에서 newer small alias가 있을 때:
1. **현재 main 1280 host D24를 먼저 readback하여 guest RAM을 pitch1280/tile4 layout으로 seed**
2. `lastDynamicUpdate > mainEvent`인 256/64만 선택
3. GPU event 순서대로 각 alias의 자체 pitch/tile mapping으로 overlay
4. seeded + overlaid guest image에서 main 1280 reload
5. main `lastDynamicUpdate`를 newest alias event로 갱신

### Runtime validity

실제 로그에서 약 15.7초 동안 **940 complete cycles** 실행:
- `phase=begin` = 940
- `phase=seed-main` = 940
- `phase=overlay` = 1880
  - 매 cycle 256x256 1회
  - 매 cycle 64x64 1회
- `phase=main-reload` = 940
- `phase=skip-resized` = 0
- D24 main upload = 940
- device-lost / pipeline failure / GLSL failure = 0

대표 순서는 반복적으로 정확히:
`seed-main 1280 → overlay 256 → overlay 64 → main-reload 1280`

### User visual result

**플리커링 0 개선.**

### Conclusion

이 A/B는:
- 올바른 seeded main 보존
- exact-tested D24 transfer
- 실제 940 cycle runtime execution
- 새 corruption 없음

을 만족한 **유효한 negative behavior A/B**다.

따라서:
- `f5442800` same-address/multi-pitch host coherence gap 자체는 실제 correctness gap으로 남는다.
- stale main depth가 실제 LEQUAL visibility path에 들어가는 것도 사실이다.
- 그러나 **현재 Bayonetta 2 distant/background flicker의 주원인으로 보는 가설은 강하게 하향**한다.
- 새 직접 증거 없이는 f544 coherence 보정 실험을 반복하지 않는다.

## 10. 현재 후보 우선순위

1. **Bayonetta 2의 실제 visibility/occlusion decision path 자체** — nested/duplicate bookkeeping은 배제됐지만 query result correctness/consumption은 아직 별도 미검증
2. upstream #1348과 공통인 generic Bayonetta render/visibility path
3. normal gameplay draw의 다른 visibility 조건(cull/scissor/clip/primitive state) — observation-first
4. f544 multi-pitch D24 coherence는 correctness issue로 보존하되 현재 flicker root-cause 우선순위에서는 크게 하향

## 11. 작업 원칙

- 한 build에 한 가설
- source/static verifier before compile
- observation fact와 user visual result 분리
- old unseeded roundtrip 반복 금지
- seeded f544 coherence A/B도 새 직접 증거 없이는 반복 금지
- simple `vkCmdCopyImage` between different pitch/scale 금지
- permanent fixes rollback 금지
- Adreno-specific hack로 단정하지 않음

# NEXT ACTION

**새 빌드/CI는 아직 시작하지 않는다.**

다음 한 단계는 static analysis only:
1. `LatteQuery`의 정상 occlusion query result 완료/누적/guest-visible 반환 경로를 끝까지 읽는다.
2. 이미 배제된 nested resume / duplicate pointer anomaly는 다시 보지 않는다.
3. Bayonetta 2에서 heavy query usage가 확인된 상태이므로, query result가 0/비0 visibility decision으로 소비되는 정확한 경계를 찾는다.
4. 그 경계가 명확하면 **Bayonetta 2 only / query result force-visible** 단일 behavior A/B를 설계한다.
5. 이 A/B는 query bookkeeping, depth, texture coherence, shader를 건드리지 않고 오직 최종 visibility result 하나만 바꾸도록 제한한다.
6. 구현/새 workflow/CI는 사용자의 다음 명시적 `ㄱㄱ` 승인 후에만 진행한다.
