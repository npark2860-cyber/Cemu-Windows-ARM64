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
- `f5442800` guest-RAM roundtrip (`256/64 GPU readback → same guest RAM → main 1280 reload`)

## 4. 완료된 핵심 진단 요약

### f4c24000 alias sync
Branch `diag-bayo2-alias-sync`, Run `33119155975`, SUCCESS.

- actual 1024 copies 전부 `0x1a` non-depth `640x368 → 640x360`
- `0x11↔0x1a` = 0
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

## 5. `f5442800` multi-pitch D24 runtime fact

동일 guest physical start `f5442800`, 동일 D24/S8 (`0x11`), tile4에 서로 다른 세 base texture가 동시에 존재하고 실제 depth attachment로 사용된다:

- `1280x720`, pitch `1280`
- `256x256`, pitch `256`
- `64x64`, pitch `64`

세 representation 모두 GPU write를 받는다.

Source 구조:
- zero-offset + same-subIndex인데 pitch가 다르면 compatible relation 생성 안 됨
- 같은 경우 `TrackDataOverlap()`에도 내려가지 않음
- GPU dynamic sync는 `list_compatibleRelations`만 순회
- depth clear만 same physical address/smaller-pitch representation에 별도 전파

## 6. f544 observation trace — 완료

Branch:
`diag-bayo2-f544-depth-alias`

Trace HEAD:
`389e845649a8518b3a26f7d52263c346c5bb0f4b`

Workflow/runtime HEAD:
`2334cb517180dc887221b7177ef1cc190f639fb3`

Run:
`33141337691` — SUCCESS

User log:
`log(20260828-050332).txt`

Runtime result:
- 세 pair 모두 `result=untracked-zero-offset-incompatible`
- 원인은 runtime에서도 pitch mismatch 하나로 확인
- main 1280 rebind 1462회에서 전부 `newerAlias=1`
- 동시에 항상 `rels=0 / sameAddrOverlaps=0 / reloadDynamic=0`
- 직전 newest other는 64x64 depth

확정 가능한 것:
1. Cemu host texture-cache에는 same-address / multi-pitch D24 representation coherence gap이 실제 존재한다.
2. small depth passes 뒤 main representation이 더 오래된 `lastDynamicUpdate` 상태로 다시 bind된다.

**하지만 이것만으로 guest hardware가 반드시 그 small-surface 데이터를 main depth와 합성해야 한다고 단정하지 않는다.**

## 7. `f544` guest-RAM roundtrip A/B — 실행됐지만 INVALID

Branch:
`exp/bayo2-f544-guest-roundtrip`

Runtime build/HEAD:
`001df98b74e4d469ff69cd0b9c1010d7e1b07792`

Workflow Run #3:
`33145985810` — SUCCESS

User native-resolution log:
`log(20260828-063425).txt`

Native condition:
- graphics resolution pack 미활성
- guest/effective main depth `1280x720`
- safety guard 통과

Runtime counts:
- `phase=begin` = 1662
- `phase=alias-to-guest` = 3324
  - 매 cycle 256x256 1회
  - 64x64 1회
- `[BAYO2_F544_ROUNDTRIP_UPLOAD]` = 1662
- `phase=main-reload` = 1662
- `skip-resized` = 0
- roundtrip failure marker = 0
- `VK_ERROR_DEVICE_LOST` = 0
- pipeline/SPIR-V/GLSL failure = 0 in captured log

대략 27.7초 동안 1662 cycle이므로 사실상 60Hz로 매 frame roundtrip이 수행됐다.

User visual result:
- **화면이 어마어마하게 망가짐**

### Correct interpretation

이 결과를 `f544 coherence root cause confirmed`로 해석하면 안 된다.

실험은:
1. 256x256 host depth를 pitch256/tile4 layout으로 same guest RAM에 writeback
2. 64x64 host depth를 pitch64/tile4 layout으로 같은 base RAM에 다시 writeback
3. 그 RAM 전체를 main 1280x720 depth로 reload

한다.

서로 다른 pitch surface의 guest-memory 의미를 이렇게 하나의 canonical RAM image로 순차 합성하는 것이 Wii U hardware 의미와 동일하다는 검증이 없었다. 화면의 대규모 파괴는 **이 강제 canonicalization/roundtrip 방식이 유효하지 않음을 증명**한다.

따라서:
- f544 same-address/multi-pitch cache fact는 유지
- guest-RAM roundtrip 보정 방식은 폐기
- flicker 인과성은 여전히 미확정
- 해당 `001df98` build로 추가 테스트 금지

## 8. D24 transfer 관련 별도 정적 사실

roundtrip 설계 중 확인:
- Cemu 기존 tiled readback writer는 `HWFMT_8_24`를 지원하지 않았다.
- experimental path가 D24/S8 readback/writeback 및 Vulkan split depth/stencil plane 처리를 새로 추가했다.
- 이 자체가 기존 Cemu에서 충분히 검증된 경로가 아니므로 permanent fix 근거로 사용하지 않는다.

## 9. 현재 우선순위

1. **main 1280x720 depth로 복귀한 첫 draw의 실제 depth state와 사용 방식 확인**
2. 해당 first draw가 previous main depth를 읽는지, depth를 새로 덮는지 판정
3. 그 뒤에만 f544 multi-pitch coherence가 실제 gameplay semantics에 필요한지 재평가
4. upstream #1348 common render path correlation

`f544`를 강제로 RAM canonicalization하는 behavior A/B는 반복하지 않는다.

## 10. 다음 관찰 방향

이미 준비된 branch:
`diag-bayo2-main-depth-state`

현재 branch HEAD는 아직 baseline `fa17d83`; source modification 없음.

Vulkan draw path에서는 정상 draw마다 `draw_getOrCreateGraphicsPipeline()` 후 `m_state.activePipelineInfo`가 정해지고, current `DB_DEPTH_CONTROL`은 pipeline hash에도 포함된다.

다음 observation-only trace에서 main `f5442800 1280x720` depth attachment를 쓰는 draw에 대해 기록할 것:
- draw sequence / first draw after main rebind
- `Z_ENABLE`
- `Z_WRITE_ENABLE`
- `Z_FUNC`
- stencil enable
- depth-bias enable 여부
- VS / PS / GS hash
- pipeline hash
- index count / primitive mode
- main rebind 직전 small-depth pass 여부

목표:
- main return 첫 draw가 stale prior-main depth를 **실제로 depth-test input으로 읽는지** 확인
- 또는 depth test off/write-all/clear-equivalent라서 previous contents가 사실상 irrelevant한지 확인

# NEXT ACTION

**새 behavior fix 금지. 새 CI는 아직 돌리지 않는다.**

1. `diag-bayo2-main-depth-state`에 observation-only trace 설계.
2. log 폭증 방지를 위해 main rebind 직후 첫 1~몇 draw 또는 state-change fingerprint만 기록.
3. source behavior unchanged verifier를 먼저 만든다.
4. 정적 검증 후 user `ㄱㄱ` 승인 시에만 dedicated ARM64 diagnostic CI 1회.
5. 결과가 depth-test read 의존을 보이면 f544 coherence 후보를 다시 올린다.
6. first draw가 previous depth contents를 사용하지 않으면 f544 coherence를 flicker root cause에서 크게 하향하고 다른 draw/depth-state correlation으로 이동한다.

## New-tab startup prompt

`Cemu ARM64 Bayonetta 2 flicker 분석을 이어간다. GitHub CURRENT_HANDOFF.md, TECH_BIBLE.md, DEBUG_HISTORY.md를 먼저 읽고 runtime-experiments-arm64 문서 HEAD와 code-changing baseline fa17d83을 구분해라. 끝난 Position Invariance, viewport clamp, depthBiasClamp, LOD, barrier variants, forced split, depthclip, pNext, VS auxHash, f4c24000 conversion, native negativeOneToOne, nested occlusion resume/duplicate를 반복하지 마. f544 observation trace에서는 same-address 1280x720/256x256/64x64 D24 reps가 pitch mismatch 때문에 relation 없이 사용되고 main rebind가 newerAlias=1임을 확인했다. 하지만 001df98 guest-RAM roundtrip A/B는 native 720p에서 1662회 완전 실행되며 화면을 대규모로 파괴했으므로 invalid causal A/B로 폐기한다. 이 결과를 root-cause confirmation으로 해석하지 마. NEXT ACTION은 behavior를 바꾸지 않고 main f544 1280 depth로 복귀한 첫 draw의 Z_ENABLE/Z_WRITE/Z_FUNC + shader/pipeline hash를 관찰해 previous main depth contents가 실제로 사용되는지 판정하는 것이다.`