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

upstream `cemu-project/Cemu` Issue #1348에는 RTX 3060 Ti에서도 유사한 Bayonetta 2 flicker가 남아 있다. 사용자 exact scene과 동일 근본원인은 미확정이지만 ARM64/Adreno 전용이라고 전제하지 않는다.

## 2. 저장소 / 보호 기준점

Repository:
`npark2860-cyber/Cemu-Windows-ARM64`

주 문서 브랜치:
`runtime-experiments-arm64`

일반 진단/호환성 code-changing baseline:
`fa17d834bfebd9a41c598b1b1b702000d0ff4618`

문서-only `[skip ci]` commit은 baseline 뒤에 붙을 수 있으므로 branch HEAD와 code baseline을 구분한다.

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
- RT simple/strong/pre-begin barriers
- forced render-pass split
- depthclip
- pipeline pNext
- VS auxHash pipeline key
- `f4c24000` `0x11↔0x1a` actual alias conversion
- `f4c24000` depth↔color format conversion
- nested/overlapping GX2 occlusion-query resume/duplicate 경로

새 직접 증거 없이 반복하지 않는다.

## 4. 완료된 핵심 진단 요약

### f4c24000 alias sync
Branch `diag-bayo2-alias-sync`, Run `33119155975`, SUCCESS.

- `[BAYO2_ALIAS_COPY]` 1024/1024 = `0x1a` non-depth `640x368 → 640x360`, image-copy
- actual `0x11↔0x1a` = 0
- depth↔color = 0
- format-conversion = 0

R24/D24↔RGBA8/depth-color conversion direct-cause 가설은 강하게 하향.

### native negativeOneToOne
Branch `exp/vk-native-negative-one-to-one`, Run `33131685028`, SUCCESS.

- `VK_EXT_depth_clip_control` supported
- `negativeOneToOne=1 shaderZRemap=0`
- 실제 VS GLSL에서 `(z+w)/2` 제거 확인
- 사용자 화면: **개선 0**

shader-side clip-space Z remap은 강하게 하향.

### occlusion query
Branch `diag-bayo2-occlusion-query`, Run `33137618598`, SUCCESS.

최소 78,000 GX2 query BEGIN/END pair가 있었지만:
- `NESTED_RESUME=0`
- `ACTIVE_INSERT=0`
- `ACTIVE_IN_FLIGHT=0`
- `DUPLICATE_APPEND=0`

의심했던 nested-live-query bookkeeping 경로는 문제 장면에서 실행되지 않았다.

## 5. 현재 최강 증거 — `f5442800` multi-pitch D24 alias coherence gap

동일 guest physical start `f5442800`, 동일 D24/S8 (`0x11`), tile4에 서로 다른 세 base texture가 동시에 존재하고 실제 depth attachment로 사용된다:

- `1280x720`, pitch `1280`
- `256x256`, pitch `256`
- `64x64`, pitch `64`

세 representation 모두 GPU write를 받는다.

### Source 구조

`LatteTexture_GatherTextureRelations()`에서 zero-offset + same-subIndex인데 pitch가 다르면:
- compatible relation 생성 안 됨
- `TrackDataOverlap()`에도 내려가지 않음

GPU dynamic sync는 `list_compatibleRelations`만 순회한다.

Depth clear만 별도로 same physical address texture를 조회해 same/smaller pitch에 clear를 전파한다.

따라서 구조적으로:
- clear에는 partial multi-pitch coherence가 있음
- normal render write에는 relation 없는 multi-pitch alias coherence가 없음

## 6. f544 dedicated runtime trace — 완료

Branch:
`diag-bayo2-f544-depth-alias`

Base:
`fa17d834bfebd9a41c598b1b1b702000d0ff4618`

Trace script:
`389e845649a8518b3a26f7d52263c346c5bb0f4b`

Workflow/runtime HEAD:
`2334cb517180dc887221b7177ef1cc190f639fb3`

Workflow:
`Cemu ARM64 Bayonetta2 F544 Depth Alias Trace`

Run:
`33141337691` — **SUCCESS**

User log:
`log(20260828-050332).txt`

Active graphics:
- 2560x1440
- Extreme
- 16x
- Contrasty
- 60 FPS Cutscenes
- Force Maximum LOD
- Dynamic Shadows (Vulkan)
- Portal

### Relation creation — runtime confirmed

세 pair 모두:
`result=untracked-zero-offset-incompatible`

공통:
- same start `f5442800`
- same subIndex `0`
- `tileMatch=1`
- `texelCompat=1`
- `formatCompat=1`
- **`pitchMatch=0`**

Creation state:
- 1280x720: aliases=1, rels=0, overlaps=0
- 256x256: aliases=2, rels=0, overlaps=0
- 64x64: aliases=3, rels=0, overlaps=0

즉 relation이 없는 이유가 runtime에서도 **pitch mismatch 하나로 직접 확인**됐다.

### Bind chronology — decisive runtime evidence

전체 `[BAYO2_F544_BIND]` switch markers: 4387.

- 256x256 bind: 1462회, 모두 `newerAlias=0`
- 64x64 bind: 1462회, 모두 `newerAlias=0`
- 1280x720 main bind:
  - 최초 1회 `newerAlias=0`
  - 이후 **1462회 `newerAlias=1`**

그 1462회 모두 동시에:
- `rels=0`
- `sameAddrOverlaps=0`
- `reloadDynamic=0`

그리고 newest other는 항상 `64x64 pitch=64`.

대표 실제 순서:
1. main 1280 clear/write state event `666198`
2. 256x256 clear/bind/write → `666204+`
3. 64x64 clear/bind/write → `666210+`
4. main 1280 rebind:
   - `selfEvent=666198`
   - `newestOtherEvent=666211`
   - `newerAlias=1`
   - `rels=0`
   - `sameAddrOverlaps=0`
   - `reloadDynamic=0`
5. 그 뒤 main에 새 write `666212`

1462 stale-main rebind 중 1461회는 직전에 256 및 64 write가 둘 다 직접 확인됐다. 나머지 1회도 두 small write가 있었고 좁은 correlation window만 벗어났다.

주 event gap `newestOther - self`:
- +13: 1448회
- +16: 13회
- +31: 1회

### 확정 사실

이제 다음은 추측이 아니다:

1. 같은 guest physical memory가 서로 다른 pitch의 독립 host D24 image 3개로 존재한다.
2. Cemu는 이 셋의 relation을 오직 pitch mismatch 때문에 거부한다.
3. zero-offset case에서 same-address data-overlap tracking도 없다.
4. small depth passes가 더 최신 GPU write를 만든다.
5. 그 직후 main 1280 depth는 **더 오래된 상태로 재bind된다.**
6. 그 순간 Cemu에는 relation/overlap/reload mechanism이 활성화되어 있지 않다.

따라서 **실제 runtime texture-cache/depth-alias coherence gap은 확인됐다.**

### 아직 확정하면 안 되는 것

- 이 coherence gap이 flicker의 최종 root cause라는 것
- 64/256 host image를 1280 image에 단순 image-copy하면 된다는 것
- guest memory alias를 무조건 direct GPU copy로 표현할 수 있다는 것
- Adreno driver bug라는 것

최종 인과성은 behavior A/B 1회가 필요하다.

## 7. 다음 A/B 설계 시 주의 — resolution overwrite

현재 graphics pack은 2560x1440이므로 main 1280x720 guest surface가 host에서는 확대된다.

`LatteTextureReadback_Initate()`는 resolution-overwritten texture readback을 명시적으로 지원하지 않는다.

Vulkan direct readback 자체는 D24/S8을 지원하지만 transfer region은 baseTexture original width/height를 사용한다.

따라서 현재 설정에서 억지로:
- GPU readback → guest RAM writeback → 다른 pitch texture reload

를 하는 실험은 첫 선택으로 쓰지 않는다. resolution scaling 의미가 섞이기 때문이다.

Cemu의 기존 dynamic relation sync가 사용하는 `LatteTexture_SyncSlice()`가 different-size/pitch alias에 재사용 가능한지 먼저 정적으로 검증해야 한다.

## 8. 정상 depth-state trace — 보류

Vulkan/OpenGL은 `DB_DEPTH_CONTROL`의 `Z_ENABLE / Z_WRITE_ENABLE / Z_FUNC`를 의미상 동일하게 매핑한다.

`diag-bayo2-main-depth-state` branch는 준비돼 있지만, f544 coherence가 훨씬 직접적인 증거를 냈으므로 보류한다.

## 9. 현재 후보 우선순위

1. **`f5442800` multi-pitch D24 depth alias coherence gap의 flicker 인과성**
2. normal gameplay draw depth-state + D24 attachment correlation
3. upstream #1348 common render path
4. `f4c24000 0x1a 640x368→640x360` — 새 direct correlation이 생길 때만 재상승

## 10. 작업 원칙

- source/static verification → 최소 A/B → 필요한 경우에만 CI 1회
- 한 build에 한 가설
- 이미 끝난 실험 반복 금지
- observation fact와 visual result 분리
- generic Cemu bug 가능성을 우선하고 Adreno-specific hack 남발 금지
- VS `DEFAULT_VAL` rollback 금지
- resolution overwrite를 무시한 readback/reload hack 금지

# NEXT ACTION

**새 CI를 돌리지 않는다.**

1. baseline `fa17d83`의 `LatteTexture_SyncSlice()` 전체 구현을 읽는다.
2. 다음을 정적으로 판정한다:
   - src/dst guest width/height가 다를 때 copy size를 어떻게 정하는가
   - overwrite/effective resolution을 어떻게 처리하는가
   - 서로 다른 pitch지만 same-format/tile D24의 GPU-side sync가 안전한가
   - 64/256 → 1280 또는 반대 방향에서 guest-memory 의미를 보존할 수 있는가
3. 재사용이 안전하면 Bayonetta 2 JP `f5442800`에만 한정한 **단일 behavior A/B**를 설계한다.
4. 가능하면 기존 relation machinery를 최소 확장해 stale main bind 전에 최신 alias data를 동기화하는 방식으로 한다.
5. `SyncSlice`가 이 경우에 부적합하면 억지로 사용하지 않는다. native-resolution 전용 readback/reload A/B 등 다른 semantics-preserving 방법을 설계한다.
6. **code modification / 새 workflow / CI는 사용자 승인 후에만 실행한다.**

## New-tab startup prompt

`Cemu ARM64 Bayonetta 2 flicker 분석을 이어간다. GitHub CURRENT_HANDOFF.md, TECH_BIBLE.md, DEBUG_HISTORY.md를 먼저 읽고 runtime-experiments-arm64 문서 HEAD와 code-changing baseline fa17d83을 구분해라. 끝난 Position Invariance, viewport clamp, depthBiasClamp, LOD, barrier variants, forced split, depthclip, pNext, VS auxHash, f4c24000 conversion, native negativeOneToOne, nested occlusion resume/duplicate를 반복하지 마. 최신 f544 trace build 2334cb5 / Run 33141337691 / log(20260828-050332).txt에서 f5442800의 1280x720 pitch1280, 256x256 pitch256, 64x64 pitch64 D24 reps가 pitch mismatch만으로 untracked-zero-offset-incompatible 처리되고, main 1280 rebind 1462회가 모두 newerAlias=1이면서 rels=0 / sameAddrOverlaps=0 / reloadDynamic=0임을 확인했다. 실제 runtime multi-pitch depth alias coherence gap은 확정됐지만 flicker 인과성은 아직 미확정이다. NEXT ACTION은 새 CI 없이 LatteTexture_SyncSlice 전체 구현을 정적으로 분석해 의미 보존형 단일 A/B를 설계하는 것이다.`