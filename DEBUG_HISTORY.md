# Cemu Windows ARM64 / Adreno DEBUG HISTORY

> 날짜별 실험 결과를 누적한다. 현재 이어서 할 일은 `CURRENT_HANDOFF.md`를 본다.

## 2026-08-16 — VS DEFAULT_VAL synthesize

### Problem

Adreno에서 producer가 PS가 요구하는 varying을 실제 export하지 않는 경우 Vulkan shader interface/pipeline 생성이 깨졌다.

### Change

producer-side `DEFAULT_VAL` fallback/synthesis 도입.

### Result

- BOTW 렌더 정상 확인
- Tekken Tag Tournament 2 렌더 정상 확인
- 관련 `VK_ERROR_UNKNOWN (-13)` 해소
- shader/interface 안정화

### Status

- **확정 수정**
- rollback 금지
- GS path는 별도 검증 대상

---

## 2026-08 — Adreno visual regression compatibility fix

### Symptoms

- giant distorted triangles/faces
- horizontal bands
- swapchain/backbuffer 계열 시각 이상

### Known-good behavior restored

- swapchain loadOp `DONT_CARE → LOAD`
- command buffer usage `ONE_TIME_SUBMIT → SIMULTANEOUS_USE` 2곳
- `DrawBackbufferQuad` pre-renderpass `ClearColorbuffer(padView)` 복원
- renderpass 내부 `vkCmdClearAttachments()` 제거

### Result

Qualcomm 테스트 환경의 해당 시각 회귀 해결.

### Status

known-good compatibility baseline. 원인을 Qualcomm driver 단독으로 단정하지 않는다.

---

## 2026-08-24 ~ 2026-08-27 — Generic Runtime Diagnostics completion

### Goal

게임별 임시 패치가 아니라 Windows ARM64 + Adreno에서 Vulkan/JIT/input 문제를 재사용 가능한 로그로 진단할 수 있는 runtime diagnostics를 구축.

### Areas connected

- ARM64/JIT lifecycle, mapping, branch patch, ReadyRE
- command buffer / fence / semaphore / submit completion
- pipeline cache/create/failure/state/hash
- VS/PS/GS/interface/compile failure
- renderpass / attachment / load-store / barrier / RAW / WAW / self-dependency
- feedback-loop related signals
- texture/cache/surface related signals
- frame timing / GPU timestamp / CPU waits
- descriptor / upload / hitch / overhead / summary
- input/controller mapping

### Final generic code checkpoint

Branch:
`runtime-experiments-arm64`

Code-changing baseline:
`fa17d834bfebd9a41c598b1b1b702000d0ff4618`

Commit:
`diagnostics: require complete 77-item coverage`

### Final architecture

- `RuntimeDiagnostics::Enabled(flag)` = master + implemented + per-flag enabled
- UI availability = `RuntimeDiagnostics::IsImplemented(flag)`
- verifier compares UI `kDiagItems[]` with implemented set
- **77/77 exact coverage required**

### Result

이전의 "다수 회색 checkbox = 미구현" 상태는 현재 generic diagnostic baseline 기준으로 폐기.

새 Diagnostics Edition을 반복 생성하기보다 현재 77/77 baseline과 source A/B를 우선한다.

---

## 2026-08-27 — Tekken 1P → 2P input boundary

### Symptom

Tekken Tag Tournament 2에서 1P로 지정한 physical controller가 실제 게임에서 2P side로 동작.

### Runtime log boundary

- physical controller → Cemu player0
- player0 → VPAD channel0
- VPAD connected=1, player=0
- KPAD 0–3 disconnected
- x64 Cemu에서도 동일 현상 관찰

### Interpretation

ARM64 InputManager player-index misassignment는 강하게 하향.

### Next direction

- GamePad/VPAD0 vs Pro Controller/KPAD
- Tekken join/side semantics

Bayonetta graphics track과 섞지 않는다.

---

## 2026-08-27 — Bayonetta 2 graphics target redefined

### Correct symptom

Bayonetta 2 현재 주 증상은 crash가 아니라:

**멀리 있는 폴리곤이 거리에서 flicker하는 현상**.

Test title:
- JP `00050000-1011B900`
- v1
- Adreno X1-85 / Vulkan 1.3
- driver build `f22d572733`

Master diagnostics에서 device loss/submit failure 없이 장시간 실행됨.

기존 startup signal:
- `PIPELINE_FAIL` 2
- `GLSL_FAIL` 1
- suspicious swizzle events

이들은 원거리 flicker와 직접 상관이 증명되지 않았으므로 별도 신호로 유지.

---

## 2026-08-27 — Bayonetta 2 Position Invariance A/B

### Why tested

Cemu Metal backend에 Bayonetta/Bayonetta 2 Position Invariance workaround 선례가 있고 Vulkan GLSL path에는 `invariant gl_Position`이 없어서 강한 후보로 평가.

### Method

- 기존 `DumpEveryShader` Bayonetta 2 capture에서 unique VS 113개 확인
- all-zero internal/generic VS 1개 제외
- 112개 VS graphics-pack replacement 생성
- 각 shader에 `invariant gl_Position;`만 추가
- Cemu 본체 rebuild 없이 pack OFF/ON 비교

### Validation

replacement shader가 실제 compile되었고 SPIR-V byte size 변화도 확인되어 A/B 자체는 유효.

### User visual result

**플리커링 전혀 개선되지 않음.**

### Conclusion

Position Invariance는 현재 distant-polygon flicker의 주원인 후보에서 크게 하향.
동일 조건 재실험 금지.

---

## 2026-08-27 — Bayonetta 2 viewport depth-range clamp A/B

### Hypothesis

Vulkan `VkViewport.minDepth/maxDepth` handling과 Wii U `-1..1` depth-range 의미 차이 가능성.

### Experiment

Bayonetta 2 전용 build에서 out-of-range viewport depth만 Vulkan legal `0..1`로 clamp하고 raw/applied 값을 기록.

### Runtime evidence

대량의 runtime call에서:

- `rawNear=-1`
- `rawFar=1`
- `halfZ=0`
- applied `0..1`

이 확인됨.

이전 집계에서는 약 888k call 수준으로 거의 세션 전반에 적용되었음.

### User visual result

**플리커링 그대로.**

### Conclusion

단순 `VkViewport.minDepth/maxDepth` `-1..1 → 0..1` handling은 현재 주원인에서 배제.
이 실험을 후속 build에 섞지 않는다.

---

## 2026-08-27 — Bayonetta 2 Vulkan depthBiasClamp A/B

### Source motivation

Vulkan backend는 `vkCmdSetDepthBias(constant, clamp, slope)`를 통해 Wii U `PA_SU_POLY_OFFSET_CLAMP`를 전달한다.
OpenGL backend와 clamp 사용 방식에 차이가 있어 distant flicker 후보로 검토했다.

### Dedicated branch

`exp/bayo2-depth-bias-clamp`

Successful experiment HEAD:
`bdb644d89d8963ab7a39d8a586f6d73ac3d73f92`

Workflow:
`Cemu ARM64 Bayonetta2 Depth Bias Experiment`

Successful Run:
- run #4
- ID `33056046387`
- result: **SUCCESS**

### Experiment behavior

Bayonetta 2 title IDs에만 Vulkan `depthBiasClamp=0.0f`를 적용하고 original values를 `[BAYO2_DEPTH_BIAS]`로 기록.

### Latest runtime log

`log(20260827-093536).txt`

Runtime confirms:
- Cemu short hash `bdb644d`
- Bayonetta 2 JP `00050000-1011B900`, v1
- Qualcomm Adreno X1-85
- Master diagnostics ON

Active packs:
- Contrasty
- Graphics 2560x1440 / High / 16x
- 60 FPS Cutscenes
- Force Maximum LOD
- Dynamic Shadows (Vulkan)
- Portal

Position Invariance test pack은 active list에 없음.

### `[BAYO2_DEPTH_BIAS]` observed records

기록된 첫 128개 line (`n=0..127`)에서 모두:

- `offset=0`
- `slope=-0`
- `rawClamp=0`
- `appliedClamp=0`
- `nonZeroClampCount=0`

### User visual result

**플리커링 전혀 개선되지 않음.**

### Interpretation / conclusion

- 기록된 첫 128회에서는 원래 clamp 값 자체가 0이므로 experiment가 GPU state를 바꾸지 않았다.
- 사용자 화면 판정도 변화 없음.
- `depthBiasClamp` 단독 가설은 주원인에서 크게 하향.
- logger 출력 제한 때문에 세션 전체에 non-zero clamp가 절대 없었다고 단정하지는 않는다.
- 동일 A/B 반복 금지.

---

## 2026-08-28 — Recovered prior Bayonetta exclusions

이전 작업 기록을 다시 대조해 최신 handoff에서 누락됐던 완료 실험을 복구했다.

이미 테스트되어 **배제 또는 약화**된 항목:

- Force Maximum LOD / LOD 일반 설정
- RT 단순 barrier
- strong barrier
- pre-begin barrier
- forced render-pass split
- depthclip
- pipeline pNext
- VS auxHash pipeline key

### Status

- 새 증거 없이 반복 금지.
- 특히 Force Maximum LOD OFF A/B를 다시 사용자에게 요청하지 않는다.
- 최신 handoff의 LOD pending 항목은 폐기했다.

---

## 2026-08-28 — Bayonetta depth/surface static re-analysis

### Existing runtime evidence

대표 로그 `log(20260827-093536).txt`에서:

- 반복되는 depth attachment: `addr=f5442800`, format `0x11`, stencil enabled
- pipeline format signal에서 depth `129`
- `f4c24000`에 반복되는 `[SUSPICIOUS_TEXTURE] reason=swizzle`
- 같은 physical address `f4c24000`가 texture lifecycle에서 hardware format family `0x11` 및 `0x1a` representation으로 존재

### Source verification

`LatteReg.h` / `LatteConst.h`:
- `0x11` = `HWFMT_8_24`
- `0x1a` = `HWFMT_8_8_8_8`
- `D24_S8_UNORM`은 `HWFMT_8_24` family
- `R8_G8_B8_A8_UNORM`은 `HWFMT_8_8_8_8` family

Vulkan depth mapping:
- `D24_S8_UNORM`은 지원 시 `VK_FORMAT_D24_UNORM_S8_UINT`
- 현재 logged depth `129`와 일치

따라서 현재 관찰 구간에서 D24S8가 D32S8 fallback으로 잘못 바뀐 증거는 없다.

`LatteTextureLegacy.cpp`:
- macro-tiled texture bind 시 guest physical address에서 swizzle을 추출
- cached `baseTexture->swizzle`과 requested swizzle 비교
- requested swizzle이 `lastRenderTargetSwizzle`과 같으면 reload 없이 base swizzle 갱신
- 다르면 `swizzleChanged=true` 후 texture reload 경로로 들어감

`LatteTexture.cpp`:
- overlapping texture memory를 검색
- `LatteTexture_CanTextureBeRepresentedAsView()`로 existing texture/view reuse 판정
- view compatibility와 texel-size compatibility를 별도로 처리
- incompatible representation이면 별도 texture representation 생성 가능

### Interpretation

`f4c24000`의 multi-format representation 자체는 Cemu texture cache 설계상 합법일 수 있어 버그로 단정하지 않는다.
다만 swizzle mismatch가 실제 reload/validity 경계와 일치하므로 현재 distant flicker와 상관관계를 추적할 가치가 높은 실제 runtime 신호다.

### Next direction at that point

- `f4c24000` mapping/relation/copy를 observation-only trace로 확인
- 실제 copy path를 확인한 뒤에만 동작 A/B 검토

---

## 2026-08-28 — Bayonetta 2 alias synchronization trace

### Goal

`f4c24000`의 multi-format/depth representation이 실제 gameplay에서 어느 방향으로 동기화되는지 확인한다.

### Branch / build

Branch:
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
- result: **SUCCESS**

Diagnostic behavior:
- observation only
- `[BAYO2_ALIAS_REL]`
- `[BAYO2_ALIAS_COPY]`
- target guest address `f4c24000`

### User log

`log(20260828-002909).txt`

Runtime:
- Cemu `fd5f637`
- Bayonetta 2 JP `00050000-1011B900`, v1
- Adreno X1-85 / Vulkan 1.3
- driver `f22d572733`
- Master diagnostics ON
- Full sync at GX2DrawDone: true

### Counts

- `[BAYO2_ALIAS_REL]` = 10
- `[BAYO2_ALIAS_COPY]` = 1024 logged records

### Relation results

1280x720 relation:
- `0x1a`, non-depth, swizzle `000d0000`, GPU=false
- ↔ `0x11`, non-depth, swizzle `00000000`, GPU=true
- result: success, then duplicate

640-class relations:
- `0x1a 640x368` non-depth ↔ `0x11 640x360` depth
- `0x1a 640x360` non-depth ↔ `0x11 640x360` depth
- `0x1a 640x360` non-depth ↔ `0x1a 640x368` non-depth
- all relevant relation attempts succeeded

### Actual copy result

**1024/1024 logged copy records were the same class:**

Source:
- addr `f4c24000`
- fmt `0x1a`
- non-depth
- 640x368
- pitch 640
- tile 4
- swizzle 0
- GPU=true

Destination:
- addr `f4c24000`
- fmt `0x1a`
- non-depth
- 640x360
- pitch 640
- tile 4
- swizzle 0

Copy:
- `640x360`
- path `image-copy`

First logged copy had dstGPU=false; subsequent records were dstGPU=true.

### Not observed

- actual `0x11 -> 0x1a` copy: 0
- actual `0x1a -> 0x11` copy: 0
- depth -> color copy: 0
- color -> depth copy: 0
- `format-conversion` copy: 0

### Conclusion

- `f4c24000` multi-representation relations are real.
- But the suspected R24_X8/D24 ↔ RGBA8 or depth/color conversion handoff did **not** execute in the captured flicker session.
- therefore the `0x11/0x1a alias conversion` hypothesis is strongly downgraded as the direct flicker cause.
- same-format `0x1a 640x368 -> 640x360` synchronization is real and frequent, but no direct flicker correlation is proven. Do not call it a bug yet.

---

## 2026-08-28 — Upstream generic Bayonetta 2 flicker boundary

### Upstream evidence

`cemu-project/Cemu` Issue #1348:
`[Bayonetta 2] images rendering erros`

Reported:
- Chapter VIII image flickering
- Windows 10
- GeForce RTX 3060 Ti
- problem existed across previous Cemu versions

Exzap asked whether graphic packs affected it.
Reporter reconfirmed:
- first Chapter VIII flicker occurs regardless of graphic-pack/default settings
- separate Chapter IX cutscene issue was related to 60 FPS Cutscenes and later solved
- first flicker remained unresolved

Issue remained open and a 2026 comment still states the first flicker is unresolved.

### Interpretation

This is strong evidence that at least a very similar Bayonetta 2 flicker exists on non-ARM64 / non-Adreno hardware.

Do **not** claim the user's exact distant-polygon scene and #1348 are proven identical yet.
Do **not** assume Qualcomm/ARM64 exclusivity.

### Scope change

Primary investigation now treats the symptom as potentially **generic Cemu Bayonetta 2 rendering behavior**, with Adreno as the current test platform rather than presumed root cause.

---

## 2026-08-28 — Vulkan shader clip-space Z path identified

### Source

Current fork and current upstream Cemu both generate Vulkan `SET_POSITION` as:

- if `DX_CLIP_SPACE_DEF=1`: `gl_Position = _v`
- if `DX_CLIP_SPACE_DEF=0`: `gl_Position = _v; gl_Position.z = (gl_Position.z + gl_Position.w) / 2.0`

OpenGL path does not use this shader-side Z remap.

### Important distinction

This is **not the same experiment** as the already-failed viewport depth-range clamp.

- previous A/B changed `VkViewport.minDepth/maxDepth`
- this path changes clip-space vertex Z in shader output before rasterization

Therefore `halfZ` / shader clip-space semantics remains alive.

### Safety constraint

Blindly deleting `(z+w)/2` is not valid evidence-based testing because Vulkan's default clip volume expects 0..w Z.
A semantics-preserving alternative such as Vulkan negative-one-to-one depth clip control must be checked first.

---

## Current Bayonetta candidate ranking

Higher value:

1. generic Cemu Bayonetta 2 clip-space/depth semantics
2. normal gameplay draw depth test/write/compare + depth attachment precision/state correlation
3. upstream #1348 common render path correlation
4. same-format `0x1a 640x368 -> 640x360` sync only if new direct evidence appears

Strongly downgraded / do not repeat without new evidence:

- Position Invariance
- simple viewport depth-range clamp
- depthBiasClamp
- Force Maximum LOD / LOD general settings
- RT simple/strong/pre-begin barriers
- forced render-pass split
- depthclip
- pipeline pNext
- VS auxHash pipeline key
- `f4c24000` 0x11/0x1a actual conversion
- `f4c24000` depth/color format conversion
- startup pipeline `-13` 2건
- old GLSL failure as an ARM64-specific explanation

---

## Process rules confirmed by experiments

- 한 번에 한 변수만 변경
- 이미 끝난 실험을 반복하지 않음
- 실패한 실험을 후속 build에 섞지 않음
- CI 전에 source/static validation 완료
- 사용자 화면 관찰과 로그 fact 분리
- build 비용을 이유 없이 반복하지 않음
- generic upstream bug evidence가 있으면 platform-specific hack보다 공통 원인을 우선
- VS `DEFAULT_VAL` synthesize rollback 금지

---

## Logging template for future experiments

```text
## YYYY-MM-DD — Experiment name

Goal:
Branch/commit:
Workflow/run:
Game/title/version:
GPU/driver:
Graphic packs/options:
Log/dump:
Runtime evidence:
User visual result:
Confirmed fact:
Ruled out / downgraded:
Still possible:
Next action:
```
