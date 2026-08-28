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

## 6. Main-depth first-draw observation — decisive

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

따라서 f544 divergence는 단순 bookkeeping이 아니라 **실제 visibility path까지 도달**한다.

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

## 9. 현재 새 behavior A/B — SEEDED roundtrip

Branch:
`exp/bayo2-f544-seeded-roundtrip`

Patch script:
`tools/diagnostics/Apply-Bayonetta2F544SeededRoundtrip.py`

Script commit:
`62906e5ea5029aee581700b80e2e7e5a8c0af775`

Workflow HEAD:
`a2e4e70ccba4052890d8e06b06d227d41e019878`

Workflow:
`Cemu ARM64 Bayonetta2 F544 Seeded Roundtrip`

Current Run:
`33160442364`

Job:
`98813341024`

현재 진행 중.

### Corrected behavior

main rebind에서 newer small alias가 있을 때:
1. **현재 main 1280 host D24를 먼저 readback하여 guest RAM을 pitch1280/tile4 layout으로 seed**
2. `lastDynamicUpdate > mainEvent`인 256/64만 선택
3. GPU event 순서대로 각 alias의 자체 pitch/tile mapping으로 overlay
4. seeded + overlaid guest image에서 main 1280 reload
5. main `lastDynamicUpdate`를 newest alias event로 갱신

이 방식은 old A/B와 달리 **small aliases가 건드리지 않은 main 영역을 현재 main host 값으로 보존**한다.

### Safety gates
- Bayonetta 2 JP only
- `f5442800` D24/S8 only
- main exactly 1280x720 / pitch1280
- small only 256x256/pitch256 + 64x64/pitch64
- effective resolution 1280x720 only
- resized graphics pack이면 `phase=skip-resized`하고 behavior 0
- D24 transfer implementation은 exact self-test에서 검증된 것과 동일

Expected active markers:
- `[BAYO2_F544_SEEDED] phase=begin`
- `phase=seed-main`
- `phase=overlay`
- `phase=main-reload`

## 10. 현재 후보 우선순위

1. **f5442800 cross-pitch D24 normal-write coherence / exact guest-memory alias semantics**
2. seeded main + newer alias overlay가 flicker에 미치는 visual effect
3. upstream #1348 common Bayonetta render path correlation
4. generic normal-depth path only if f544 is disproven

## 11. 작업 원칙

- 한 build에 한 가설
- source/static verifier before compile
- observation fact와 user visual result 분리
- old unseeded roundtrip 반복 금지
- simple `vkCmdCopyImage` between different pitch/scale 금지
- permanent fixes rollback 금지
- Adreno-specific hack로 단정하지 않음

# NEXT ACTION

1. Run `33160442364`의 `Validate → Apply seeded → Verify seeded semantics` 단계를 먼저 확인.
2. verifier가 통과한 경우에만 ARM64 build 완료까지 진행.
3. artifact가 나오면 **Graphics resolution pack OFF / native 1280x720**로 같은 flicker scene 테스트.
4. FPS는 blocking readback 때문에 판정 대상 아님.
5. visual 판정은 세 가지로만 기록:
   - flicker 크게 개선/소멸
   - flicker 변화 없음
   - 화면 corruption/새 artifact 발생
6. runtime log에서 `seed-main → 256 overlay → 64 overlay → main-reload` 순서가 실제 반복되는지 확인.
7. seeded A/B가 flicker를 명확히 개선하면 f544 cross-pitch coherence를 root-cause 수준으로 끌어올리고 permanent design을 GPU-side / generic texture-cache 방식으로 별도 설계한다.
8. seeded A/B도 corruption이면 guest cross-pitch semantics 가정을 재검토하고 behavior fix를 더 이상 확대하지 않는다.
