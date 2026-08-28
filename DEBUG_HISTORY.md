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
Branch: `runtime-experiments-arm64`

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
현재 주 증상은 crash가 아니라 **멀리 있는 폴리곤/오브젝트가 거리에서 flicker하는 현상**.

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
- 기존 `DumpEveryShader` capture에서 unique VS 113개 확인
- all-zero internal/generic VS 1개 제외
- 112개 VS graphics-pack replacement 생성
- 각 shader에 `invariant gl_Position;`만 추가
- Cemu 본체 rebuild 없이 pack OFF/ON 비교

### Validation
replacement shader가 실제 compile되었고 SPIR-V byte size 변화도 확인되어 A/B 자체는 유효.

### User visual result
**플리커링 전혀 개선되지 않음.**

### Conclusion
Position Invariance는 현재 distant-polygon flicker의 주원인 후보에서 크게 하향. 동일 조건 재실험 금지.

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

이전 집계에서는 약 888k call 수준으로 거의 세션 전반에 적용됨.

### User visual result
**플리커링 그대로.**

### Conclusion
단순 `VkViewport.minDepth/maxDepth` `-1..1 → 0..1` handling은 현재 주원인에서 배제. 후속 build에 섞지 않는다.

---

## 2026-08-27 — Bayonetta 2 Vulkan depthBiasClamp A/B

### Source motivation
Vulkan backend는 `vkCmdSetDepthBias(constant, clamp, slope)`를 통해 Wii U `PA_SU_POLY_OFFSET_CLAMP`를 전달한다. OpenGL backend와 clamp 사용 방식 차이를 후보로 검토.

### Dedicated branch/build
Branch: `exp/bayo2-depth-bias-clamp`

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

### Runtime log
`log(20260827-093536).txt`

Runtime:
- Cemu `bdb644d`
- JP `00050000-1011B900`, v1
- Adreno X1-85
- Master diagnostics ON

Active packs:
- Contrasty
- Graphics 2560x1440 / High / 16x
- 60 FPS Cutscenes
- Force Maximum LOD
- Dynamic Shadows (Vulkan)
- Portal

첫 128개 `[BAYO2_DEPTH_BIAS]` record 모두:
- `offset=0`
- `slope=-0`
- `rawClamp=0`
- `appliedClamp=0`
- `nonZeroClampCount=0`

### User visual result
**플리커링 전혀 개선되지 않음.**

### Conclusion
기록된 구간에서는 원래 clamp 자체가 0이라 experiment가 GPU state를 바꾸지 않았고 화면도 변화 없음. `depthBiasClamp` 단독 가설은 크게 하향. logger 제한 때문에 세션 전체 non-zero 절대 부재까지는 단정하지 않음. 동일 A/B 반복 금지.

---

## 2026-08-28 — Recovered prior Bayonetta exclusions

이전 작업 기록을 대조해 최신 handoff에서 누락됐던 완료 실험을 복구.

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
- 과거 handoff의 LOD pending 항목은 폐기.

---

## 2026-08-28 — Bayonetta depth/surface static re-analysis

### Existing runtime evidence
대표 로그 `log(20260827-093536).txt`에서:
- 반복 depth attachment `addr=f5442800`, format `0x11`, stencil enabled
- pipeline depth format signal `129`
- `f4c24000` 반복 `[SUSPICIOUS_TEXTURE] reason=swizzle`
- 같은 physical address `f4c24000`가 hardware format `0x11` 및 `0x1a` representation으로 존재

### Source verification
`0x11 = HWFMT_8_24`, `0x1a = HWFMT_8_8_8_8`.
`D24_S8_UNORM`은 지원 시 `VK_FORMAT_D24_UNORM_S8_UINT`로 매핑되고 observed depth format 129와 일치.

현재 관찰 구간에서 D24S8가 D32S8 fallback으로 잘못 바뀐 증거는 없음.

`LatteTextureLegacy.cpp`에서 macro-tiled texture swizzle mismatch는 실제 reload/validity 결정 경계에 있음.
`LatteTexture.cpp`는 overlapping incompatible representation을 별도 base texture로 만들 수 있음.

### Interpretation
`f4c24000` multi-format representation 자체는 합법일 수 있어 버그로 단정하지 않음. 실제 copy path를 observation-only trace로 확인하기로 함.

---

## 2026-08-28 — Bayonetta 2 alias synchronization trace

### Goal
`f4c24000` multi-format/depth representation이 gameplay에서 어느 방향으로 동기화되는지 확인.

### Branch / build
Branch: `diag-bayo2-alias-sync`

Base:
`fa17d834bfebd9a41c598b1b1b702000d0ff4618`

Diagnostic script commit:
`4f1f56cc85fb645da17e9f95aaf8da2de0a74fd2`

Workflow HEAD:
`fd5f6376959d739cb50e5dfd79ef64716a40cb60`

Run:
- ID `33119155975`
- **SUCCESS**

User log:
`log(20260828-002909).txt`

Runtime:
- Cemu `fd5f637`
- JP `00050000-1011B900`, v1
- Adreno X1-85 / Vulkan 1.3
- driver `f22d572733`
- Master diagnostics ON
- Full sync at GX2DrawDone: true

### Counts
- `[BAYO2_ALIAS_REL]` = 10
- `[BAYO2_ALIAS_COPY]` = 1024

### Relation results
1280x720:
- `0x1a`, non-depth, swizzle `000d0000`, GPU=false
- ↔ `0x11`, non-depth, swizzle `00000000`, GPU=true

640-class:
- `0x1a 640x368` non-depth ↔ `0x11 640x360` depth
- `0x1a 640x360` non-depth ↔ `0x11 640x360` depth
- `0x1a 640x360` non-depth ↔ `0x1a 640x368` non-depth

### Actual copy result
**1024/1024 logged copy records 동일 class:**
- src `f4c24000`, fmt `0x1a`, non-depth, 640x368, pitch 640, tile 4, swizzle 0, GPU=true
- dst `f4c24000`, fmt `0x1a`, non-depth, 640x360, pitch 640, tile 4, swizzle 0
- copy `640x360`
- path `image-copy`

Not observed:
- `0x11→0x1a` = 0
- `0x1a→0x11` = 0
- depth→color = 0
- color→depth = 0
- `format-conversion` = 0

### Conclusion
`f4c24000` multi-representation relations are real, but suspected R24/D24↔RGBA8 or depth/color conversion handoff did **not** execute in captured flicker session. `0x11/0x1a alias conversion` direct-cause hypothesis strongly downgraded. Same-format `0x1a 640x368→640x360` sync remains a fact only; bug correlation unproven.

---

## 2026-08-28 — Upstream generic Bayonetta 2 flicker boundary

### Upstream evidence
`cemu-project/Cemu` Issue #1348, `[Bayonetta 2] images rendering erros`:
- Chapter VIII image flickering
- Windows 10 + GeForce RTX 3060 Ti
- previous Cemu versions에도 존재
- graphic-pack/default settings와 무관하게 첫 flicker 발생
- 별도 Chapter IX cutscene issue는 60 FPS Cutscenes와 연관되어 해결됐지만 첫 flicker는 별개로 unresolved
- 2026 comment에서도 첫 flicker unresolved

### Interpretation
적어도 매우 유사한 Bayonetta 2 flicker가 non-ARM64 / non-Adreno에서 존재한다는 강한 증거. 사용자 exact scene과 #1348 동일 근본원인은 미확정. Qualcomm/ARM64 exclusivity를 전제하지 않는다.

---

## 2026-08-28 — Vulkan shader clip-space Z path identified

Current fork와 upstream Cemu는 Vulkan `SET_POSITION`을:
- `DX_CLIP_SPACE_DEF=1`: `gl_Position = _v`
- `DX_CLIP_SPACE_DEF=0`: `gl_Position = _v; gl_Position.z = (gl_Position.z + gl_Position.w) / 2.0`

으로 생성. OpenGL path는 shader-side Z remap을 하지 않음.

이는 이미 실패한 `VkViewport.minDepth/maxDepth` clamp와 다른 단계이므로 의미 보존형 native clip-control A/B를 설계함. Blind Z-remap removal은 금지.

---

## 2026-08-28 — Native Vulkan negativeOneToOne A/B

### Goal
`VK_EXT_depth_clip_control`의 `negativeOneToOne`으로 Wii U/OpenGL식 `[-1,1]` clip-space 의미를 Vulkan native path에서 보존하면서 shader-side `(z+w)/2` FP remap만 제거하여 비교.

### Branch / build
Branch:
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
- **SUCCESS**

User runtime log:
`log(20260828-014616).txt`

### Runtime validity
- Cemu `66ab7c7`
- `[BAYO2_NATIVE_DEPTH_CLIP] VK_EXT_depth_clip_control: supported`
- `[BAYO2_NATIVE_DEPTH_CLIP] negativeOneToOne=1 shaderZRemap=0`
- same VS hashes versus previous build show GLSL consistently 55 bytes shorter; actual Z-remap source removal confirmed
- no new SPIR-V failure/device-lost regression
- startup pipeline `-13` 2건과 GLSL failure 1건은 기존과 동일한 pre-existing startup anomalies

### User visual result
**플리커링 그대로 / 개선 0.**

### Conclusion
이 결과는 extension 미지원 fallback이 아니라 실제 native path가 활성화된 유효 negative A/B다. Shader-side `(z+w)/2` FP remap / clip-space conversion 자체를 distant flicker의 주원인 후보에서 **강하게 하향**한다. 동일 실험 반복 금지.

---

## 2026-08-28 — Normal depth-state static comparison

Vulkan `InitDepthStencilState()`와 OpenGL depth-state path를 비교.

둘 다 Wii U `DB_DEPTH_CONTROL`의:
- `Z_ENABLE`
- `Z_WRITE_ENABLE`
- `Z_FUNC`

를 사용하며 compare mapping도 `NEVER, LESS, EQUAL, LEQUAL, GREATER, NOTEQUAL, GEQUAL, ALWAYS`로 의미상 동일.

따라서 단순 depth test/write/compare API mapping 차이는 source상 확인되지 않는다.

현재 generic pipeline-state snapshot은 pipeline **failure**에서만 `depthTest/depthWrite/depthCompare`와 RT format을 상세 기록한다. 성공한 normal gameplay draw에는 해당 snapshot이 없어 runtime correlation은 아직 필요.

Vulkan source에는 `depthBoundsTestEnable = false; // todo`가 있으나 GX2/Bayonetta가 실제 depth-bounds를 사용하는 증거는 아직 없어 강한 후보로 승격하지 않음.

---

## 2026-08-28 — Nested occlusion-query bookkeeping anomaly identified

### Why inspected
증상이 먼 거리에서 오브젝트/폴리곤이 나타났다 사라지고 가까워지면 안정되는 형태라 depth precision 외에 occlusion/visibility query 축을 검토.

### Source fact
Core `src/Cafe/HW/Latte/Core/LatteQuery.cpp`의 `LatteQuery_EndOcclusionQuery()`에서, 하나의 GX2 query 종료 후 다른 GX2 query가 아직 active이면:

1. 새 renderer query 생성
2. `LatteQuery_begin(queryObject, currentEventId)`로 active 시작
3. **즉시 `list_queriesInFlight.emplace_back(queryObject)` 수행**
4. 동시에 `_currentlyActiveRendererQuery = queryObject`

`list_queriesInFlight`는 `LatteQuery_UpdateFinishedQueries()`에서 종료된 renderer query 결과를 회수하고 destroy/cache하는 완료 대기열이다. 여기 들어간 active query는 `queryEnded==false`라 skip된다.

같은 query가 나중에 실제 종료되면 `LatteQuery_endActiveRendererQuery()`가 `_currentlyActiveRendererQuery`를 다시 `list_queriesInFlight`에 append하므로 **동일 pointer가 대기열에 중복 삽입될 수 있는 코드 흐름**이다.

Potential consequences if executed:
- 동일 query result 이중 처리/누적
- 동일 query object 중복 cache 반환
- debug ordering assert (`latestQueryFinishedEventId < queryEventEnd`) 충돌 가능성

### Upstream comparison
최신 `cemu-project/Cemu`의 `LatteQuery.cpp`에도 동일 코드가 그대로 존재한다. 따라서 generic Cemu bug 가능성과 양립하며 Adreno-specific explanation이 아니다.

### Important limit
이 구조가 이상하다는 사실과 Bayonetta 2 flicker 원인이라는 것은 별개다. **Bayonetta 문제 장면에서 nested/overlapping GX2 query resume path가 실제 실행되는지는 아직 미확정.**

따라서 suspicious append를 지금 제거하지 않는다. 먼저 observation-only runtime trace로 hit 여부를 확인한다.

### Prepared observation branch — no CI
Branch:
`diag-bayo2-occlusion-query`

Base:
`fa17d834bfebd9a41c598b1b1b702000d0ff4618`

Trace script commit:
`1c39f202f286f2ad953accbca4f3ae5825f778e7`

Added file only:
`tools/diagnostics/Apply-Bayonetta2OcclusionQueryTrace.py`

Baseline compare:
- 1 commit ahead
- only the trace script added
- repository source behavior unchanged
- workflow/CI not created or started

Planned markers:
- `[BAYO2_OCCLUSION] GX2_BEGIN`
- `[BAYO2_OCCLUSION] GX2_END`
- `[BAYO2_OCCLUSION] NESTED_RESUME`
- `[BAYO2_OCCLUSION] ACTIVE_INSERT`
- `[BAYO2_OCCLUSION] ACTIVE_IN_FLIGHT`
- `[BAYO2_OCCLUSION] DUPLICATE_APPEND`

Script is JP Bayonetta 2 scoped, observation-only, and intentionally verifies that the suspicious original nested append remains present so it cannot silently become a behavior fix.

### Next decision
- nested/resume = 0 → occlusion candidate immediately downgraded; move to normal gameplay draw depth-state correlation
- nested/resume occurs but no duplicate anomaly → inspect query segmentation/result timing only
- nested/resume + duplicate pointer/active-in-flight observed → design a **single bookkeeping change A/B**; only then remove/fix the premature append

---

## Current Bayonetta candidate ranking

Higher value:
1. nested/overlapping GX2 occlusion-query runtime usage and bookkeeping
2. normal gameplay draw depth test/write/compare + D24 attachment correlation
3. upstream #1348 common render path correlation
4. same-format `0x1a 640x368→640x360` sync only if new direct evidence appears

Strongly downgraded / do not repeat without new evidence:
- native negativeOneToOne / shader `(z+w)/2` remap
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
- suspected occlusion bookkeeping line은 runtime hit 확인 전 behavior fix 금지

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
