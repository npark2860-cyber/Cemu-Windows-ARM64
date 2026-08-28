# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> 갱신: 2026-08-28 KST  
> 장기 확정 사실은 `TECH_BIBLE.md`, 실험 누적은 `DEBUG_HISTORY.md`를 본다.

## 1. 현재 최우선 목표

**Bayonetta 2 JP Vulkan 원거리/배경 폴리곤 플리커링 원인 규명**

증상:
- 멀리 있는 폴리곤/오브젝트가 거리에서 깜빡이거나 나타났다 사라진다.
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

upstream `cemu-project/Cemu` Issue #1348에는 RTX 3060 Ti에서도 Bayonetta 2 flicker가 남아 있다. 사용자 exact scene과 동일 근본원인은 미확정이지만 ARM64/Adreno 전용이라고 전제하지 않는다.

## 2. 저장소 / 보호 기준점

Repository:
`npark2860-cyber/Cemu-Windows-ARM64`

주 문서 브랜치:
`runtime-experiments-arm64`

일반 진단/호환성 code-changing baseline:
`fa17d834bfebd9a41c598b1b1b702000d0ff4618`

문서-only `[skip ci]` commit은 baseline 뒤에 붙으므로 branch HEAD와 code baseline을 구분한다.

절대 rollback 금지:
- VS producer-side `DEFAULT_VAL` synthesize/linkage fix
- AArch64 generated-code cache / I-cache coherency fix
- known-good pre-e834 Vulkan compatibility behavior
- 77/77 Runtime Diagnostics 구조

## 3. 이미 끝난 Bayonetta 2 실험 — 반복 금지

개선 0 / 크게 하향:
- Position Invariance (`invariant gl_Position`)
- Vulkan viewport depth-range clamp
- Vulkan `depthBiasClamp`
- Force Maximum LOD / LOD 일반 설정
- native Vulkan `negativeOneToOne` / shader `(z+w)/2` 제거
- RT simple/strong/pre-begin barrier
- forced render-pass split
- depthclip
- pipeline pNext
- VS auxHash pipeline key
- `f4c24000` `0x11↔0x1a` actual alias conversion
- `f4c24000` depth↔color format conversion
- nested/overlapping GX2 occlusion-query resume/duplicate 경로

새 직접 증거 없이 반복하지 않는다.

## 4. Alias synchronization trace — 완료

Branch: `diag-bayo2-alias-sync`  
Base: `fa17d834bfebd9a41c598b1b1b702000d0ff4618`  
HEAD: `fd5f6376959d739cb50e5dfd79ef64716a40cb60`  
Run: `33119155975` — SUCCESS  
Log: `log(20260828-002909).txt`

결과:
- `[BAYO2_ALIAS_REL]` 10
- `[BAYO2_ALIAS_COPY]` 1024
- actual copy 1024/1024 = `0x1a` non-depth `640x368 → 640x360`, `image-copy`
- `0x11→0x1a` 0
- `0x1a→0x11` 0
- depth↔color 0
- `format-conversion` 0

따라서 의심했던 R24/D24↔RGBA8/depth-color conversion handoff는 캡처된 flicker session에서 실행되지 않았다.

주 gameplay depth attachment:
- addr `f5442800`
- format `0x11`
- stencil=1
- Vulkan depth format `129` = `VK_FORMAT_D24_UNORM_S8_UINT`

## 5. Native negativeOneToOne A/B — 완료, negative

Branch: `exp/vk-native-negative-one-to-one`  
Base: `fa17d834bfebd9a41c598b1b1b702000d0ff4618`  
Patch: `601eac82108db1626254c025aaff1efc83a0ccc5`  
Workflow HEAD: `66ab7c76af02f7bff76747ea6dcbb6f28b6a6c13`  
Run: `33131685028` — SUCCESS  
Log: `log(20260828-014616).txt`

Runtime validity:
- `VK_EXT_depth_clip_control: supported`
- `negativeOneToOne=1 shaderZRemap=0`
- same VS hashes의 GLSL이 이전 build 대비 일관되게 55 bytes 짧아 실제 `(z+w)/2` 제거 확인
- 새 SPIR-V/device-lost 회귀 없음

User visual result:
- **플리커링 그대로 / 개선 0**

결론:
- shader-side Z remap/clip-space conversion 자체는 주원인에서 강하게 하향.

## 6. Occlusion-query observation trace — 완료, 주 가설 탈락

Branch:
`diag-bayo2-occlusion-query`

Base:
`fa17d834bfebd9a41c598b1b1b702000d0ff4618`

Trace script commit:
`1c39f202f286f2ad953accbca4f3ae5825f778e7`

Workflow HEAD / runtime build:
`83beb12a5738afa35d198a7cfc9f9a8ca6108e9b`

Run:
`33137618598`

User log:
`log(20260828-034828).txt`

Runtime:
- Cemu `83beb12`
- JP `00050000-1011B900`, v1
- Adreno X1-85 / Vulkan 1.3
- same graphics-pack test context

Trace markers are sampled: first 256 then every 1000.
Observed highest sampled counters:
- `GX2_BEGIN n=78000`, event `155999`
- `GX2_END n=78000`, event `156000`

Therefore session executed **at least 78,000 GX2 occlusion BEGIN/END pairs**.

Critical result across full uploaded log:
- `NESTED_RESUME` = **0**
- `ACTIVE_INSERT` = **0**
- `ACTIVE_IN_FLIGHT` = **0**
- `DUPLICATE_APPEND` = **0**

`activeBefore`/`inFlight`가 수십까지 증가하는 것은 overlapping live GX2 query 증거가 아니다. Source에서 `list_activeGX2Queries2`는 query가 END된 후에도 renderer query result가 GPU에서 회수되어 `latestQueryFinishedEventId`가 해당 end event를 넘을 때까지 binding을 보존한다. 따라서 list size에는 ended-but-not-yet-retired binding이 포함된다.

`LatteQuery_EndOcclusionQuery()`의 suspicious resume path는 `list_activeGX2Queries2` 안에 **queryEnded=false인 다른 query가 있을 때만** 실행된다. 이번 runtime에서는 그 조건이 한 번도 true가 아니었다.

결론:
- Bayonetta 2가 occlusion query를 매우 많이 사용한다는 사실은 확정.
- 하지만 우리가 의심한 nested/overlap resume + premature in-flight append/duplicate bookkeeping 경로는 문제 장면에서 **0회**.
- 이 경로를 flicker 원인으로 수정하지 않는다.
- 동일 trace 반복 금지.

## 7. 정상 depth-state 정적 확인

Vulkan과 OpenGL 모두 Wii U `DB_DEPTH_CONTROL`에서 동일하게:
- `Z_ENABLE`
- `Z_WRITE_ENABLE`
- `Z_FUNC`

를 읽고 compare 의미도:
`NEVER, LESS, EQUAL, LEQUAL, GREATER, NOTEQUAL, GEQUAL, ALWAYS`
순서로 동일 매핑한다.

따라서 단순 API compare mapping 차이는 소스상 보이지 않는다.

Vulkan pipeline hash에는 `DB_DEPTH_CONTROL`이 이미 포함된다. 따라서 고유 성공 pipeline별 depth state를 관찰하면 상태 혼선 없이 분류 가능하다.

현재 generic log는 `ATTACHMENT_USE`로 `f5442800` D24 depth가 gameplay 전반에서 반복 사용되는 것을 확인하지만, 정상 성공 draw의 `Z_ENABLE/Z_WRITE/Z_FUNC`를 함께 출력하지 않는다.

## 8. 현재 후보 우선순위

1. **정상 gameplay draw의 depth test/write/compare + `f5442800` D24 attachment correlation**
2. upstream #1348과 현재 장면의 common render path
3. same-format `f4c24000 0x1a 640x368→640x360` sync — direct correlation 생길 때만 재상승
4. 기타 visibility/culling path — depth-state 결과 뒤에 검토

낮음/반복 금지:
- nested occlusion resume/duplicate
- native negativeOneToOne / shader Z remap
- Position Invariance
- viewport clamp
- depthBiasClamp
- LOD
- barrier/split/depthclip/pNext/auxHash
- `f4c24000` format/depth-class conversion

## 9. Tekken 1P→2P — 별도 트랙

- physical controller → Cemu player0 → VPAD0
- KPAD 0–3 disconnected
- 게임에서는 2P side
- x64에서도 동일

Bayonetta graphics와 섞지 않는다.

## 10. 작업 원칙

- source/static verification → 최소 observation/A-B → 필요한 경우에만 CI 1회
- 이미 끝난 실험 반복 금지
- 한 build에 다른 가설 혼합 금지
- 화면 관찰과 로그 fact 분리
- generic upstream 가능성이 있으면 Adreno-specific hack보다 공통 원인을 우선
- VS `DEFAULT_VAL` rollback 금지
- GitHub Actions는 새 runtime evidence가 필요할 때만 실행

# NEXT ACTION

1. `fa17d83`에서 전용 **Bayonetta 2 main-depth state observation** branch를 준비한다.
2. behavior는 변경하지 않는다.
3. JP Bayonetta 2 + Vulkan에서 active FBO depth view의 base `physAddress == f5442800`인 draw만 대상.
4. 각 고유/변경 state에 대해 최소한 다음을 기록:
   - pipeline hash
   - VS/PS/GS base hash
   - raw `DB_DEPTH_CONTROL`
   - `Z_ENABLE`
   - `Z_WRITE_ENABLE`
   - `Z_FUNC`
   - stencil enable/back stencil 여부
   - primitive type
   - FBO key / depth addr / depth format / size
5. 매 draw 로그 폭증을 피하기 위해 fingerprint 변화/unique state 위주 + 제한된 sampling을 사용한다.
6. 기존 `ATTACHMENT_USE f5442800`와 timestamp를 대조 가능하게 한다.
7. 정적 anchor/diff/observation-only 검증 후 workflow를 준비한다.
8. **새 CI 실행 전에는 명시적 승인 필요.**

## New-tab startup prompt

`Cemu ARM64 Bayonetta 2 flicker 분석을 이어간다. GitHub의 CURRENT_HANDOFF.md, TECH_BIBLE.md, DEBUG_HISTORY.md를 먼저 읽고 runtime-experiments-arm64 문서 HEAD와 code baseline fa17d83을 구분해라. 이미 끝난 Position Invariance, viewport clamp, depthBiasClamp, LOD, barrier variants, forced split, depthclip, pipeline pNext, VS auxHash, f4c24000 conversion, native negativeOneToOne, nested occlusion resume/duplicate 실험을 반복하지 마. Occlusion trace build 83beb12 / log(20260828-034828).txt에서 GX2 occlusion BEGIN/END는 최소 78000쌍 이상이었지만 NESTED_RESUME/ACTIVE_INSERT/ACTIVE_IN_FLIGHT/DUPLICATE_APPEND는 모두 0이었다. 현재 NEXT ACTION은 f5442800 D24 depth를 쓰는 정상 gameplay draw의 고유 depth-state/pipeline correlation observation이다.`