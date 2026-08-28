# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> 갱신: 2026-08-28 KST  
> 목적: 새 탭이 이 문서만 읽고 이미 끝난 실험을 반복하지 않고 즉시 현재 작업을 이어가게 한다.  
> 장기 확정 사실은 `TECH_BIBLE.md`, 세부 실험 이력은 `DEBUG_HISTORY.md`를 본다.

## 1. 현재 최우선 목표

**Bayonetta 2 (JP) Vulkan 원거리/배경 폴리곤 플리커링 원인 규명**

사용자 증상:
- 멀리 있는 폴리곤/오브젝트가 거리에서 깜빡인다.
- 가까워지면 상대적으로 안정된다.
- 현재 주 타겟은 crash가 아니다.

테스트 환경:
- Windows 11 ARM64
- Snapdragon X Elite / Qualcomm Adreno X1-85
- Vulkan 1.3
- Bayonetta 2 JP `00050000-1011B900`, v1
- driver build `f22d572733`
- compiler `E031.50.36.00`
- driver branch `pp165`

### 중요한 범위 재정의

upstream `cemu-project/Cemu` Issue #1348에 Bayonetta 2 Chapter VIII image flickering이 공개되어 있다.
해당 보고 환경은 Windows 10 + GeForce RTX 3060 Ti이며, reporter는 graphic packs를 모두 꺼도 첫 번째 flicker가 항상 발생한다고 재확인했다.
2026-04-22 기준 첫 flicker는 여전히 unresolved로 보고되어 있다.

따라서 현재 사용자 증상을 **ARM64/Adreno 전용 버그라고 전제하지 않는다.**
정확히 같은 장면/근본원인인지 아직 증명되지는 않았지만, Cemu 공통 Bayonetta 2 rendering bug일 가능성을 우선 고려한다.

## 2. 저장소 / 보호 기준점

Repository:
`npark2860-cyber/Cemu-Windows-ARM64`

주 문서/진단 브랜치:
`runtime-experiments-arm64`

일반 진단/호환성 code-changing baseline:
`fa17d834bfebd9a41c598b1b1b702000d0ff4618`

Commit:
`diagnostics: require complete 77-item coverage`

문서-only `[skip ci]` commit은 이 뒤에 붙으므로 branch HEAD와 code baseline을 구분한다.

### 절대 되돌리지 말 것

- VS producer-side `DEFAULT_VAL` synthesize / linkage compatibility fix
- AArch64 generated-code cache / I-cache coherency fix
- known-good pre-e834 Vulkan compatibility behavior
- 77/77 Runtime Diagnostics 구조

## 3. 이미 끝난 Bayonetta 2 실험 — 반복 금지

### 확정 negative A/B

- Position Invariance (`invariant gl_Position`): **개선 0**
- Vulkan viewport depth-range `-1..1 -> 0..1` clamp: **개선 0**
- Vulkan `depthBiasClamp=0`: **개선 0**
- Force Maximum LOD / LOD 일반 설정: 이미 테스트, 유의미한 개선 없음

### 이전 기록에서 이미 배제/약화

- RT simple barrier
- strong barrier
- pre-begin barrier
- forced render-pass split
- depthclip
- pipeline pNext
- VS auxHash pipeline key

새 증거 없이 반복하지 않는다.

## 4. Bayonetta 2 alias-sync trace — 완료

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

Run:
- ID `33119155975`
- **SUCCESS**

User runtime log:
`log(20260828-002909).txt`

### Trace counts

- `[BAYO2_ALIAS_REL]`: 10 lines
- `[BAYO2_ALIAS_COPY]`: 1024 logged lines

### Relation facts

`f4c24000`에서 다음 compatible relation은 실제 생성됨.

1. 1280x720:
   - `fmt=0x1a`, non-depth, swizzle `000d0000`, GPU=false
   - ↔ `fmt=0x11`, non-depth, swizzle `00000000`, GPU=true

2. 640x360/368 계열:
   - `0x1a` color ↔ `0x11` depth relation 생성
   - `0x1a 640x360` ↔ `0x1a 640x368` relation 생성

### Actual copy facts

로그된 **1024/1024 copy가 모두 동일 계열**:

- path: `image-copy`
- src: `f4c24000`, `fmt=0x1a`, non-depth, `640x368`, pitch 640, tile 4, swizzle 0, GPU=true
- dst: `f4c24000`, `fmt=0x1a`, non-depth, `640x360`, pitch 640, tile 4, swizzle 0
- copy: `640x360`

첫 copy에서 dstGPU=false, 이후 기록에서는 dstGPU=true.

### 관찰되지 않은 것

- `0x11 -> 0x1a` actual copy: **0회**
- `0x1a -> 0x11` actual copy: **0회**
- depth -> color copy: **0회**
- color -> depth copy: **0회**
- `path=format-conversion`: **0회**

### 결론

`f4c24000` multi-representation relation 자체는 실제다.
그러나 이번 flicker 세션에서 의심했던 `R24_X8/D24 <-> RGBA8` 또는 depth/color format-conversion handoff는 실행되지 않았다.

따라서 **0x11/0x1a alias conversion을 flicker 직접 원인으로 보는 가설은 크게 하향**한다.

반면 `0x1a 640x368 -> 640x360` same-format copy가 지속적으로 발생한 것은 fact로 유지한다. 이것이 버그/중복 copy인지, 정상 동기화인지 아직 단정하지 않는다.

## 5. texture-cache source fact

`LatteTexture_UpdateTextureFromDynamicChanges()`에는:

> 한 slice/mip에 여러 overlapping texture가 동시에 updated인 경우 현재 구현은 한 source를 가정하며, 최신 timestamp를 개별 merge해야 한다는 취지의 TODO

가 있다.

하지만 현재 trace만으로 이 TODO가 실제 flicker를 일으킨다고 증명되지 않았다.

`LatteTexture_CopySlice()`:
- depth/non-depth mismatch -> `surfaceCopy_copySurfaceWithFormatConversion()`
- 동일 depth class -> `texture_copyImageSubData()`

이번 실제 copy는 전부 두 번째 경로였다.

## 6. shader clip-space Z / halfZ — 현재 A/B 진행 중

Vulkan GLSL emitter는 `PA_CL_CLIP_CNTL.DX_CLIP_SPACE_DEF == 0`일 때:

```text
gl_Position = _v;
gl_Position.z = (gl_Position.z + gl_Position.w) / 2.0
```

을 VS/GS output에 삽입한다.

OpenGL path는 이 shader-side Z 변환을 하지 않는다.

이 후보는 이미 실패한 **VkViewport minDepth/maxDepth clamp와 다른 단계**다.
viewport A/B는 rasterizer viewport state를 바꿨고, 이쪽은 clip-space vertex Z 자체를 shader에서 변환한다.

현재 capture 세션에서 game geometry shader 생성/사용 신호는 0이었다.
VS base hash에는 `DX_CLIP_SPACE_DEF`가 이미 포함되어 있어 VS shader-cache state 혼선은 아니다.

### 의미 보존형 native A/B

Blind하게 `(z+w)/2`를 삭제하지 않는다.
`VK_EXT_depth_clip_control`의 `negativeOneToOne=VK_TRUE`를 사용할 수 있을 때만 Vulkan native `[-1,1]` NDC semantics로 대체한다.

수학적 목표 depth mapping은 기존 경로와 동일하고, 비교 변수는 **shader-side Z FP remap을 제거하고 native viewport clip control로 옮기는 것**이다.

## 7. native negativeOneToOne 실험 — 현재 상태

전용 브랜치:
`exp/vk-native-negative-one-to-one`

Base:
`fa17d834bfebd9a41c598b1b1b702000d0ff4618`

Patch script commit:
`601eac82108db1626254c025aaff1efc83a0ccc5`

Workflow HEAD:
`66ab7c76af02f7bff76747ea6dcbb6f28b6a6c13`

Workflow:
`Cemu ARM64 Bayonetta2 Native Depth Clip Control`

Run:
- ID `33131685028`
- 현재 상태: **IN PROGRESS**
- patch 적용 step: **SUCCESS**
- patch verify / `git diff --check`: **SUCCESS**
- generic 77/77 diagnostics와 함께 적용되는 단계까지 충돌 없음
- 현재 기록 시점에는 CMake configure/build가 아직 완료되지 않음

### 정확한 적용 범위

동작 변경은 다음 조건을 모두 만족할 때만 허용:

- Vulkan
- Bayonetta 2 USA/EUR/JPN title ID
- Vertex shader
- game GS 없음
- `RECTS` 아님 (내부 rect-emulation GS 경로도 제외)
- `DX_CLIP_SPACE_DEF=0`
- `VK_EXT_depth_clip_control` extension 지원
- `VkPhysicalDeviceDepthClipControlFeaturesEXT.depthClipControl == VK_TRUE`

지원하지 않으면 기존 shader `(z+w)/2` 경로를 그대로 유지한다.

### Runtime markers

지원 판정:

`[BAYO2_NATIVE_DEPTH_CLIP] VK_EXT_depth_clip_control: supported`

또는:
- `unsupported`
- `unavailable in Vulkan headers`

실제 A/B 활성화:

`[BAYO2_NATIVE_DEPTH_CLIP] negativeOneToOne=1 shaderZRemap=0`

두 번째 marker가 없으면 native A/B가 실제 draw에 적용됐다고 판정하지 않는다.

## 8. upstream generic Bayonetta 2 flicker evidence

`cemu-project/Cemu` Issue #1348:
- title: `[Bayonetta 2] images rendering erros`
- open
- Chapter VIII image flickering
- Windows 10 + GeForce RTX 3060 Ti
- reporter 재확인: graphic packs 설정과 무관하게 첫 flicker 항상 발생
- 별도의 Chapter IX cutscene bug는 60 FPS Cutscenes와 연관되어 이후 해결됨
- 첫 flicker는 별개이며 이후에도 unresolved라고 보고

이 증거 때문에:
- Qualcomm driver 단독 원인 전제 금지
- ARM64 단독 원인 전제 금지
- Adreno-only workaround를 먼저 만들지 않는다.

## 9. 현재 후보 우선순위

1. **Cemu 공통 Bayonetta 2 clip-space/depth semantics**
   - 현재 native `negativeOneToOne` A/B 진행 중
2. **정상 gameplay draw의 depth test/write/compare + attachment precision/state correlation**
3. **upstream #1348과 현재 사용자 장면의 공통 render path 식별**
4. `f4c24000`의 active same-format `0x1a 640x368 -> 640x360` sync
   - direct correlation이 생길 때만 재상승

크게 하향:
- `0x11 <-> 0x1a` actual alias conversion
- depth/color format-conversion at `f4c24000`
- Position Invariance
- simple viewport clamp
- depthBiasClamp
- LOD
- 이전 barrier/split/depthclip/pNext/auxHash A/B

## 10. Tekken 1P -> 2P — 별도 트랙

확인:
- physical controller -> Cemu player0 -> VPAD channel0
- VPAD connected=1, player=0
- KPAD 0-3 disconnected
- 게임에서는 2P side로 동작
- 테스트한 x64 Cemu에서도 동일

ARM64 InputManager player-index misassignment는 강하게 하향.
Bayonetta graphics 분석과 섞지 않는다.

## 11. 작업 원칙

- source/static verification -> 최소 A/B -> 필요한 경우에만 CI 1회
- 이미 끝난 실험 반복 금지
- 한 build에 다른 가설 혼합 금지
- 화면 관찰과 로그 fact 분리
- generic upstream bug 가능성이 있으면 Adreno-specific hack보다 공통 원인을 우선
- VS `DEFAULT_VAL` synthesize rollback 금지

# NEXT ACTION

1. Run `33131685028`의 최종 build 결과를 확인한다.
2. 실패하면 완료 job log에서 정확한 compile/configure 오류만 수정하고 다른 가설을 섞지 않는다.
3. 성공하면 artifact `cemu-arm64-bayo2-native-depth-clip-control`을 사용한다.
4. Bayonetta 2 JP의 **동일 flicker 장면 / 동일 camera distance / 동일 graphics-pack 조건**으로 테스트한다.
5. 로그에서 먼저 다음을 확인한다:
   - extension/feature가 `supported`인지
   - `negativeOneToOne=1 shaderZRemap=0` marker가 실제 발생했는지
6. 실제 activation marker가 있는 경우에만 화면 A/B를 유효 판정한다:
   - flicker 개선
   - 동일
   - 악화
7. extension/feature 미지원이면 이 build는 동작상 기존 경로와 같으므로 negative 결과로 기록하지 않는다. 바로 normal gameplay draw depth-state correlation으로 이동한다.
8. activation됐는데 화면이 동일이면 shader-side `(z+w)/2` FP remap을 주원인에서 크게 하향하고 normal gameplay draw depth-state correlation으로 이동한다.
9. `f4c24000` alias conversion 추적은 새 직접 증거 전까지 반복하지 않는다.

## New-tab startup prompt

`Cemu ARM64 Bayonetta 2 flicker 분석을 이어간다. GitHub의 CURRENT_HANDOFF.md, TECH_BIBLE.md, DEBUG_HISTORY.md를 먼저 읽고 runtime-experiments-arm64 문서 HEAD와 code-changing baseline fa17d83을 구분해라. 이미 끝난 Position Invariance, viewport clamp, depthBiasClamp, Force Maximum LOD/LOD, RT barrier variants, forced split, depthclip, pipeline pNext, VS auxHash, f4c24000 0x11/0x1a alias-conversion 추적을 반복하지 마. alias trace log(20260828-002909).txt에서 actual copy 1024/1024가 0x1a 640x368->640x360 image-copy였고 format-conversion은 0회였다. 현재 exp/vk-native-negative-one-to-one branch, workflow HEAD 66ab7c7, Run 33131685028에서 VK_EXT_depth_clip_control negativeOneToOne을 이용해 shader (z+w)/2 remap을 의미 보존형으로 대체하는 단일 A/B를 진행 중이다. CURRENT_HANDOFF의 NEXT ACTION부터 계속해.`