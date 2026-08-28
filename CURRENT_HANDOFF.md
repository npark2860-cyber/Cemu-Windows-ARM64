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

## 4. f4c24000 alias synchronization trace — 완료

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

의심했던 R24/D24↔RGBA8/depth-color conversion handoff는 캡처된 flicker session에서 실행되지 않았다.

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

Branch: `diag-bayo2-occlusion-query`  
Base: `fa17d834bfebd9a41c598b1b1b702000d0ff4618`  
Trace script: `1c39f202f286f2ad953accbca4f3ae5825f778e7`  
Workflow/runtime build: `83beb12a5738afa35d198a7cfc9f9a8ca6108e9b`  
Run: `33137618598`  
Log: `log(20260828-034828).txt`

Observed highest sampled counters:
- `GX2_BEGIN n=78000`, event `155999`
- `GX2_END n=78000`, event `156000`

따라서 session에서 **최소 78,000 GX2 occlusion BEGIN/END pair**가 실행됨.

Full log critical result:
- `NESTED_RESUME` = 0
- `ACTIVE_INSERT` = 0
- `ACTIVE_IN_FLIGHT` = 0
- `DUPLICATE_APPEND` = 0

`activeBefore/inFlight`가 수십까지 올라간 것은 live overlap이 아니라 ended-but-not-yet-retired GX2 binding이 list에 남는 구조 때문.

결론:
- Bayonetta는 occlusion query를 매우 많이 사용한다.
- 그러나 의심한 nested live query resume + premature in-flight append/duplicate path는 문제 장면에서 **0회**.
- 그 코드를 Bayonetta fix로 수정하지 않는다.
- 동일 trace 반복 금지.

## 7. 새 최우선 증거 — `f5442800` multi-pitch D24 depth alias

동일 최신 log `log(20260828-034828).txt`에서 기존 “main depth 하나” 가정이 깨졌다.

같은 guest physical start `f5442800`, 같은 `0x11` D24/S8 depth에 **서로 다른 3개 base texture representation이 동시에 존재**한다:

1. `1280x720`, pitch `1280`, depth, view id 2
   - created 12:41:31.856
2. `256x256`, pitch `256`, depth, view id 181
   - created 12:41:50.204
3. `64x64`, pitch `64`, depth, view id 184
   - created 12:41:50.204

세 texture 모두 session 종료까지 동시에 살아 있고 DELETE 시:
- `gpuUpdated=1`
- `reloads=1`

즉 시간차로 같은 메모리를 재사용한 것이 아니라 **동시에 host cache에 존재하며 모두 GPU-side update를 받았다.**

### 실제 FBO 사용도 확인

Generic FBO/attachment log를 size와 대조하면 같은 `f5442800` depth가 실제로 다음처럼 교대로 bind된다:

- `fbo=...dc5eecc1 / ...dc5f7541` → effective `2560x1440` → base `1280x720` depth
- `fbo=...328d9b01` → `64x64` → `64x64` depth
- `fbo=...328d5c01` → `256x256` → `256x256` depth

대표 순서:
- 12:41:55.006 main 2560x1440
- 12:41:55.271 64x64
- 12:41:55.522 main 2560x1440
- 12:41:56.086 256x256
- 12:41:56.369 main 2560x1440

작은 surface는 단순 dormant cache entry가 아니라 실제 depth attachment로 사용된다.

### Source coherence gap

`LatteTexture_CreateMapping()`:
- 같은 시작주소의 기존 texture를 overlapping candidate로 찾는다.
- pitch가 다르면 `LatteTexture_CanTextureBeRepresentedAsView()`가 `VIEW_NOT_COMPATIBLE`이고 별도 base texture를 만든다.

새 texture 생성 후:
- `LatteTexture_GatherTextureRelations(newTexture)`
- `LatteTexture_UpdateTextureFromDynamicChanges(newTexture)`

을 호출하지만, `GatherTextureRelations()`의 zero-offset branch는:
- addrStart 동일
- subIndex 동일
일 때 pitch/format/tile이 compatible하면 `LatteTexture_TrackTextureRelation()`
- **compatible하지 않으면 빈 else로 종료**
- 이 경우 `LatteTexture_TrackDataOverlap()`로도 내려가지 않는다.

따라서 `1280 / 256 / 64` pitch 조합은 runtime에서 같은 zero-offset/subIndex 경로라면:
- compatible relation 없음
- same-address data-overlap tracking도 없음

이 가능성이 높다. 다음 trace에서 subIndex/tile까지 runtime 확정한다.

### GPU dynamic synchronization도 relation-only

`LatteTexture_MarkDynamicTextureAsChanged()`:
- 현재 slice `lastDynamicUpdate = eventCounter`
- `LatteTexture_MarkConnectedTexturesForReloadFromDynamicTextures()` 호출

그러나 `MarkConnectedTextures...()`는 **`list_compatibleRelations`만 순회**한다.

`LatteTexture_UpdateTextureFromDynamicChanges()`도 **`list_compatibleRelations`만 순회**하여 `LatteTexture_SyncSlice()`를 수행한다.

따라서 pitch-incompatible same-start representation은 relation이 없으면 일반 GPU draw write가 다른 representation을 stale/reload 대상으로 표시하지 못한다.

### Clear path는 별도 partial coherence가 존재

중요한 반대 증거도 있다. `LatteRenderTarget_itHLEClearColorDepthStencil()`의 depth clear는:
- `LatteTC_LookupTexturesByPhysAddr(depthBufferMPTR)`로 같은 physical start의 depth textures를 찾고
- requested `depthBufferPitch`보다 큰 texture는 skip
- 같은/더 작은 pitch texture에는 clear를 적용한다.

즉 Cemu는 **depth clear에서는 multi-pitch same-address alias를 명시적으로 일부 처리**한다.

해석:
- 큰 depth clear → 작은 representation도 같이 clear 가능
- 작은 depth clear → 큰 representation 전체는 clear하지 않음
- 일반 draw GPU writes → relation 없는 다른 pitch representation에 전파되지 않음

따라서 현재 strongest hypothesis는:
**same guest memory의 multi-pitch D24 depth surfaces 사이에서 clear에는 일부 coherence가 있으나 일반 render write에는 coherence가 없어, surface switching 시 host depth image가 guest-memory 의미보다 stale할 수 있다.**

아직 root cause 확정은 아니다. 각 pass가 항상 clear되어 이전 내용이 필요 없는 경우 false positive일 수 있으므로 clear/write/bind chronology를 observation-only로 확인해야 한다.

최신 upstream `cemu-project/Cemu`에도 `CreateMapping / GatherTextureRelations / UpdateTextureFromDynamicChanges / depth clear` 로직은 동일하다. 따라서 generic Cemu Bayonetta bug 가능성과 양립한다.

## 8. Prepared f544 alias observation — NO CI YET

Branch:
`diag-bayo2-f544-depth-alias`

Base:
`fa17d834bfebd9a41c598b1b1b702000d0ff4618`

Trace script HEAD:
`389e845649a8518b3a26f7d52263c346c5bb0f4b`

File:
`tools/diagnostics/Apply-Bayonetta2F544DepthAliasTrace.py`

Baseline diff:
- trace script 1 file only
- original Cemu source not committed/modified on branch
- workflow not created
- CI not started

Planned observation markers:
- `[BAYO2_F544_REL]`
  - zero-offset relation rejection reason
  - size/pitch/tile/format/subIndex/address ranges
- `[BAYO2_F544_CREATE]`
  - aliases/relation/data-overlap counts at creation
- `[BAYO2_F544_DRAW_WRITE]`
  - actual normal render-target GPU write events and representation switches
- `[BAYO2_F544_BIND]`
  - representation switch
  - current `lastDynamicUpdate`
  - newest other same-address D24 representation event
  - `newerAlias=1/0`
  - rel/overlap/reload state
- `[BAYO2_F544_CLEAR_REQ]`
  - requested clear size/pitch/value
- `[BAYO2_F544_CLEAR_TARGET]`
  - which same-address representation actually receives propagated clear

Critical decision marker:
- small 64/256 representation receives newer draw write
- then 1280 main depth binds with `newerAlias=1`
- while `rels=0`, `sameAddrOverlaps=0`, `reloadDynamic=0`

이 조합이 나오면 **latest aliased GPU write가 main host depth representation에 전달되지 않는 runtime coherence gap**이 직접 확인된다.

반대로 main bind 전에 clear가 모든 필요한 representation을 최신화하여 `newerAlias=0`으로 유지되면 이 hypothesis를 하향한다.

## 9. 정상 depth-state 정적 확인 — 보류

Vulkan/OpenGL은 `DB_DEPTH_CONTROL`의 `Z_ENABLE / Z_WRITE_ENABLE / Z_FUNC`를 의미상 동일하게 매핑한다.

원래 다음 단계로 `f5442800` 정상 draw의 depth-state correlation trace를 준비하려 했고 빈 branch `diag-bayo2-main-depth-state`도 생성했으나, **새 multi-pitch f544 evidence가 더 직접적이므로 현재 보류한다.**

f544 alias coherence가 탈락하면 depth-state trace로 복귀한다.

## 10. 현재 후보 우선순위

1. **`f5442800` multi-pitch D24 depth alias coherence gap**
2. 정상 gameplay draw depth-state + D24 attachment correlation
3. upstream #1348 common render path
4. `f4c24000 0x1a 640x368→640x360` same-format sync — direct correlation 생길 때만 재상승

낮음/반복 금지:
- nested occlusion resume/duplicate
- native negativeOneToOne / shader Z remap
- Position Invariance
- viewport clamp
- depthBiasClamp
- LOD
- barrier/split/depthclip/pNext/auxHash
- `f4c24000` format/depth-class conversion

## 11. Tekken 1P→2P — 별도 트랙

- physical controller → Cemu player0 → VPAD0
- KPAD 0–3 disconnected
- 게임에서는 2P side
- x64에서도 동일

Bayonetta graphics와 섞지 않는다.

## 12. 작업 원칙

- source/static verification → 최소 observation/A-B → 필요한 경우에만 CI 1회
- 이미 끝난 실험 반복 금지
- 한 build에 다른 가설 혼합 금지
- 화면 관찰과 로그 fact 분리
- generic upstream 가능성이 있으면 Adreno-specific hack보다 공통 원인을 우선
- VS `DEFAULT_VAL` rollback 금지
- GitHub Actions는 새 runtime evidence가 필요할 때만 실행

# NEXT ACTION

1. `diag-bayo2-f544-depth-alias`의 observation script를 baseline source에 적용해 anchor/diff/compile-risk 정적 검증한다.
2. behavior는 절대 바꾸지 않는다. 특히 incompatible zero-offset branch에 `TrackDataOverlap`, copy, invalidation을 추가하지 않는다.
3. trace에서 다음을 동시에 확인한다:
   - 1280/256/64 D24 reps의 tile/subIndex
   - relation rejection이 실제 pitch mismatch 때문인지
   - sameAddr overlap count가 실제 0인지
   - draw-write event의 representation switch
   - clear propagation 방향
   - main depth bind 시 `newerAlias=1` 발생 여부
4. 정적 검증이 모두 통과하면 dedicated workflow를 준비한다.
5. **새 CI 실행 전에는 명시적 사용자 승인 필요.**
6. runtime에서 coherence gap이 직접 확인된 뒤에만 behavior A/B를 설계한다.
7. gap이 없으면 `diag-bayo2-main-depth-state`로 돌아가 정상 draw depth-state correlation을 진행한다.

## New-tab startup prompt

`Cemu ARM64 Bayonetta 2 flicker 분석을 이어간다. GitHub CURRENT_HANDOFF.md, TECH_BIBLE.md, DEBUG_HISTORY.md를 먼저 읽고 runtime-experiments-arm64 문서 HEAD와 code baseline fa17d83을 구분해라. 끝난 Position Invariance, viewport clamp, depthBiasClamp, LOD, barrier variants, forced split, depthclip, pNext, VS auxHash, f4c24000 conversion, native negativeOneToOne, nested occlusion resume/duplicate를 반복하지 마. 최신 log(20260828-034828).txt에서 f5442800에 1280x720 pitch1280, 256x256 pitch256, 64x64 pitch64의 D24 depth base textures가 동시에 존재하고 모두 gpuUpdated=1이며 실제 FBO depth로 교대 사용됨을 확인했다. Source상 same-start/subIndex인데 pitch가 다르면 compatible relation도 data-overlap도 등록되지 않는 공백 경로이며 normal GPU dynamic sync는 compatibleRelations만 사용하지만 depth clear는 same physAddr의 smaller-pitch representations에도 전파한다. 현재 최우선은 diag-bayo2-f544-depth-alias HEAD 389e845의 observation-only trace를 정적 검증하고, 승인 후 runtime에서 small write 뒤 main bind의 newerAlias=1 + rels=0 + overlap=0 + reload=0을 확인하는 것이다.`