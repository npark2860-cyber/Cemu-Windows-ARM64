# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> 갱신: 2026-08-28 KST  
> 목적: 새 탭이 이 문서만 읽고 이미 끝난 실험을 반복하지 않고 즉시 현재 작업을 이어가게 한다.  
> 장기 확정 사실은 `TECH_BIBLE.md`, 세부 실험 이력은 `DEBUG_HISTORY.md`를 본다.

## 1. 현재 최우선 목표

**Bayonetta 2 (JP) Vulkan 원거리 폴리곤 플리커링 원인 규명**

증상:
- 멀리 있는 폴리곤/오브젝트가 거리에서 깜빡인다.
- 가까워지면 상대적으로 안정된다.
- 현재 Bayonetta 2의 주 타겟은 crash가 아니다.

테스트 환경:
- Windows 11 ARM64
- Snapdragon X Elite / Qualcomm Adreno X1-85
- Vulkan 1.3
- Bayonetta 2 JP `00050000-1011B900`, v1
- driver build `f22d572733`
- compiler `E031.50.36.00`
- driver branch `pp165`

## 2. 저장소 / 보호 기준점

Repository:
`npark2860-cyber/Cemu-Windows-ARM64`

주 작업 브랜치:
`runtime-experiments-arm64`

현재 일반 진단/호환성 code-changing baseline:
`fa17d834bfebd9a41c598b1b1b702000d0ff4618`

Commit:
`diagnostics: require complete 77-item coverage`

문서-only `[skip ci]` commit은 이 뒤에 붙을 수 있으므로 branch HEAD와 code baseline을 구분한다.

### 절대 되돌리지 말 것

- VS producer-side `DEFAULT_VAL` synthesize / linkage compatibility fix
- AArch64 generated-code cache / I-cache coherency fix
- known-good pre-e834 Vulkan compatibility behavior
- 77/77 Runtime Diagnostics 구조

## 3. Runtime Diagnostics 상태

`fa17d83` 기준 **77/77 exact coverage**.

- `RuntimeDiagnostics::Enabled(flag)` = master + implemented + per-flag enabled
- UI selectable 여부 = `RuntimeDiagnostics::IsImplemented(flag)`
- verifier가 UI `kDiagItems[]`와 implemented set의 정확한 일치를 검사

새 Diagnostics Edition을 이유 없이 다시 만들지 않는다.

## 4. Bayonetta 2 — 이미 끝난 실험 / 반복 금지

### 확정 negative A/B

#### Position Invariance

- captured VS 113개 중 내부 all-zero shader 1개 제외
- 112개 replacement VS에 `invariant gl_Position;` 적용
- shader compile/SPIR-V 변화로 적용 확인
- 사용자 화면 결과: **플리커링 전혀 개선되지 않음**

결론: 주원인에서 크게 하향. 동일 조건 반복 금지.

#### Vulkan viewport depth range clamp

runtime에서 대량:
- `rawNear=-1`
- `rawFar=1`
- `halfZ=0`

Bayonetta 2 전용으로 Vulkan viewport depth를 `0..1`로 clamp했고 실제 대량 적용을 확인했다.

사용자 화면 결과: **플리커링 그대로**

결론: 단순 `VkViewport.minDepth/maxDepth` 처리 가설은 배제. 후속 build에 섞지 않는다.

#### Vulkan depthBiasClamp

전용 브랜치:
`exp/bayo2-depth-bias-clamp`

Successful HEAD:
`bdb644d89d8963ab7a39d8a586f6d73ac3d73f92`

Successful Run:
- #4
- ID `33056046387`

실험:
- Bayonetta 2에서만 Vulkan `depthBiasClamp=0.0f`
- offset/slope는 변경하지 않음

`log(20260827-093536).txt`의 첫 128개 `[BAYO2_DEPTH_BIAS]` 모두:
- `offset=0`
- `slope=-0`
- `rawClamp=0`
- `appliedClamp=0`
- `nonZeroClampCount=0`

사용자 화면 결과: **플리커링 전혀 개선되지 않음**

결론: depthBiasClamp 단독 가설 크게 하향. 동일 A/B 반복 금지.

### 이전 작업 기록에서 이미 배제/약화된 후보

다음은 이전 분석에서 이미 테스트되어 **배제 또는 약화**된 항목이다. 새 증거 없이 반복하지 않는다.

- `Force Maximum LOD` / LOD 일반 설정
- RT 단순 barrier
- strong barrier
- pre-begin barrier
- forced render-pass split
- depthclip
- pipeline pNext
- VS auxHash pipeline key

특히 **Force Maximum LOD OFF 테스트를 다시 요청하지 않는다.**

## 5. 현재 로그/source에서 확인된 유효 신호

대표 로그:
`log(20260827-093536).txt`

### A. main depth attachment

Bayonetta 2 구간에서 반복적으로:
- depth attachment address `f5442800`
- GX2/Latte hardware format family `0x11`
- stencil enabled
- Vulkan pipeline depth format signal `129`

소스 매핑상 `129 = VK_FORMAT_D24_UNORM_S8_UINT`.
현재 관찰 구간에서 main depth가 D32S8 fallback으로 바뀐 증거는 없다.

### B. `f4c24000` multi-representation alias

같은 guest physical address `f4c24000`에 실제로 최소 세 representation이 관찰됨:

- 1280x720, hardware format `0x11`, `isDepth=0`
- 1280x720, hardware format `0x1a`, `isDepth=0`
- 640x360, hardware format `0x11`, `isDepth=1`

따라서 이 주소에서는:
- format alias
- depth/non-depth alias

둘 다 실제로 발생한다.

또 `[SUSPICIOUS_TEXTURE] reason=swizzle addr=f4c24000 ...`가 반복된다.

### C. 중요한 texture-cache source 구조

`LatteTexture_CanTextureBeRepresentedAsView()`:
- depth/non-depth가 다르면 같은 base view로 합치지 않음
- 같은 주소라도 format이 다르면 현재 구현상 동일 base view로 합치지 않음
- 별도 base texture representation 생성 가능

`LatteTexture_GatherTextureRelations()` / `LatteTexture_TrackTextureRelation()`:
- 동일/겹치는 guest memory representation을 compatible relation으로 연결 가능
- 동일 pitch/tile/texel-size/format-view compatibility가 relation 조건

`LatteTexture_UpdateTextureFromDynamicChanges()`:
- `lastDynamicUpdate`가 더 최신인 representation에서 stale representation으로 copy
- source가 GPU updated면 destination의 `isUpdatedOnGPU`도 전달

`LatteTexture_CopySlice()`:
- depth ↔ non-depth이면 `surfaceCopy_copySurfaceWithFormatConversion()`
- 둘 다 depth 또는 둘 다 non-depth이면 `texture_copyImageSubData()`

Vulkan `texture_copyImageSubData()`:
- render pass 종료
- src/dst image barrier
- `vkCmdCopyImage`
- post-copy barrier

### D. `R24_X8_UNORM` 특이점

Vulkan mapping:
- `R24_X8_UNORM` → `VK_FORMAT_R32_SFLOAT`

RAM texture decoder:
- `TextureDecoder_R24_X8::decode()`는 현재 output texel을 0으로 채우는 구현

따라서 `f4c24000`의 `0x11` non-depth representation이 실제 유효 GPU 데이터를 가진다면 CPU/RAM decode만으로는 설명되지 않으며 GPU-side relation/synchronization 경로 확인 가치가 높다.

이 사실만으로 flicker 원인이라고 단정하지 않는다.

## 6. 현재 최소 관찰 진단

전용 브랜치:
`diag-bayo2-alias-sync`

Base:
`fa17d834bfebd9a41c598b1b1b702000d0ff4618`

Diagnostic script commit:
`4f1f56cc85fb645da17e9f95aaf8da2de0a74fd2`

Workflow HEAD:
`fd5f6376959d739cb50e5dfd79ef64716a40cb60`

Workflow:
`Cemu ARM64 Bayonetta2 Alias Sync Trace`

Successful Run:
- #1
- ID `33119155975`
- conclusion: **SUCCESS**

Artifact:
`cemu-arm64-bayo2-alias-sync-trace`

### 동작 변경 여부

**없음. observation-only logging.**

추가 marker:
- `[BAYO2_ALIAS_REL]`
  - `f4c24000`가 포함된 relation attempt/result
  - format/depth/size/pitch/tile/swizzle/GPU-updated state
- `[BAYO2_ALIAS_COPY]`
  - 실제 src → dst copy 방향
  - `path=image-copy` 또는 `path=format-conversion`
  - src/dst format/depth/size/pitch/tile/swizzle/GPU-updated state

### accidental generic run

실수로 `runtime-experiments-arm64`에 placeholder를 생성하면서 시작된 generic Run:
- ID `33118909610`
- conclusion: **CANCELLED**

전용 workflow를 같은 concurrency group으로 시작해 중복 빌드를 중단시켰다.
`runtime-experiments-arm64`의 accidental placeholder commits/files는 branch cleanup 대상이며 code baseline에는 포함하지 않는다.

## 7. 현재 살아 있는 후보 우선순위

1. **`f4c24000` surface alias synchronization 방향/경로**
2. **format alias(`0x11 non-depth ↔ 0x1a`)와 depth/color alias 간 GPU data handoff**
3. depth attachment state / precision + normal draw depth test/write/compare correlation
4. feedback-loop / attachment dependency의 아직 직접 검증되지 않은 세부 경로
5. `halfZ=0` shader Z conversion — 위 후보를 소진한 뒤에만 검토

낮은 우선순위 / 반복 금지:
- Position Invariance
- viewport depth-range clamp
- depthBiasClamp
- LOD 일반 설정 / Force Maximum LOD
- RT barrier variants / forced split
- depthclip / pipeline pNext / VS auxHash key
- startup pipeline `-13` 2건
- 오래된 GLSL failure `78a2659662685d55_0000000000000079`

## 8. Tekken 1P → 2P — 별도 트랙

확인:
- physical controller → Cemu player0 → VPAD channel0
- VPAD connected=1, player=0
- KPAD 0–3 disconnected
- 게임에서는 2P side로 동작
- 테스트한 x64 Cemu에서도 동일

ARM64 InputManager player-index misassignment는 강하게 하향.
Bayonetta graphics 분석과 섞지 않는다.

## 9. 작업 원칙

- source/static verification → 최소 A/B → 필요한 경우에만 CI 1회
- 이미 끝난 실험 반복 금지
- 한 build에 다른 가설 혼합 금지
- 화면 관찰과 로그 fact 분리
- VS `DEFAULT_VAL` synthesize rollback 금지
- 충분한 증거 전 `halfZ` 전역 변경 금지

# NEXT ACTION

1. `runtime-experiments-arm64`에서 accidental placeholder commits/files를 제거해 intended docs-only HEAD로 복구한다.
2. Successful Run `33119155975` artifact `cemu-arm64-bayo2-alias-sync-trace`를 사용한다.
3. Bayonetta 2 동일 flicker 장면을 실행한다.
4. Runtime Diagnostics Master는 기존 테스트 기준대로 유지하고 로그를 수집한다.
5. 결과 로그에서 다음 marker를 우선 판독한다:
   - `[BAYO2_ALIAS_REL]`
   - `[BAYO2_ALIAS_COPY]`
6. 특히 `f4c24000`에 대해 실제 copy가 존재하는지, 존재한다면:
   - `0x11 non-depth → 0x1a`
   - `0x1a → 0x11 non-depth`
   - depth → color
   - color → depth
   어느 방향인지 확정한다.
7. copy 시점의 `srcGPU/dstGPU`, swizzle, size를 비교한다.
8. 이 로그 결과 전에는 alias 동기화 동작을 변경하는 A/B를 만들지 않는다.

## New-tab startup prompt

`Cemu ARM64 Bayonetta 2 원거리 폴리곤 플리커링 분석을 이어간다. GitHub의 CURRENT_HANDOFF.md, TECH_BIBLE.md, DEBUG_HISTORY.md를 먼저 읽고 runtime-experiments-arm64 문서 HEAD와 code-changing baseline fa17d83을 구분해라. 이미 끝난 Position Invariance, viewport depth-range, depthBiasClamp, Force Maximum LOD/LOD, RT barrier variants, forced split, depthclip, pipeline pNext, VS auxHash 실험을 반복하지 마. 현재 전용 branch diag-bayo2-alias-sync의 successful Run 33119155975 artifact로 f4c24000의 [BAYO2_ALIAS_REL]/[BAYO2_ALIAS_COPY]를 수집·분석하는 단계다.`
