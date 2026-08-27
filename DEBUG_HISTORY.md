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

Vulkan backend:

`vkCmdSetDepthBias(constant, clamp, slope)`

를 통해 Wii U `PA_SU_POLY_OFFSET_CLAMP`를 전달.

OpenGL backend와 clamp 사용 방식에 차이가 있어 Bayonetta 2의 distant flicker 후보로 검토.

### Dedicated branch

`exp/bayo2-depth-bias-clamp`

Successful experiment HEAD:
`bdb644d89d8963ab7a39d8a586f6d73ac3d73f92`

Commit:
`fix: include CafeSystem for Bayonetta depth-bias experiment`

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
- **Force Maximum LOD**
- Dynamic Shadows (Vulkan)
- Portal

Position Invariance test pack은 active list에 없음.

### `[BAYO2_DEPTH_BIAS]` observed records

현재 latest log의 기록된 128개 line (`n=0..127`)에서 모두:

- `offset=0`
- `slope=-0`
- `rawClamp=0`
- `appliedClamp=0`
- `nonZeroClampCount=0`

확인.

### User visual result

**플리커링 전혀 개선되지 않음.**

### Interpretation / conclusion

- 기록된 첫 128회에서는 원래 clamp 값 자체가 0이므로 experiment가 GPU state를 바꾸지 않았다.
- 사용자의 동일 장면 화면 판정도 **변화 없음**이었다.
- 따라서 `depthBiasClamp` 단독 가설은 현재 주원인 후보에서 크게 하향한다.
- logger 출력 제한 때문에 세션 전체에 non-zero clamp가 절대 없었다고 단정하지는 않는다.
- 동일한 depth-bias clamp A/B를 반복하지 않는다.

---

## Current Bayonetta candidate ranking after A/Bs

Higher value:

1. LOD / graphics-pack interaction, 특히 `Force Maximum LOD`
2. depth format / actual depth precision / depth attachment state
3. depth test/write/compare + non-zero depth bias draw correlation
4. surface/texture reinterpretation / swizzle correlation
5. `halfZ=0` path의 shader Z transform은 정상적인 clip-space conversion이므로 위 후보 이후에 신중히 검토

Lower priority:

- Position Invariance
- simple viewport depth-range clamp
- depthBiasClamp 단독 처리
- startup pipeline `-13` 2건
- 기존 GLSL fail 1건
- feedback-loop without direct evidence
- RT alias where previous master logs showed none

---

## Process rules confirmed by experiments

- 한 번에 한 변수만 변경
- 실패한 실험을 후속 build에 섞지 않음
- CI 전에 패치 적용 + source diff/static validation
- 사용자 화면 관찰과 로그 fact를 분리
- build 비용을 이유 없이 반복하지 않음
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
