# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> 갱신: 2026-08-31 KST  
> Repository: `npark2860-cyber/Cemu-Windows-ARM64`  
> 주 문서 브랜치: `runtime-experiments-arm64`  
> 이전 대화를 추측해서 복원하지 말고 GitHub 문서를 source of truth로 사용한다.

## 0. 새 탭에서 먼저 읽을 문서

아래 순서로 읽는다.

1. `TECH_BIBLE.md`
2. `DEBUG_HISTORY.md`
3. `DEBUG_HISTORY_20260829_QUERY_COMPARE.md`
4. `DEBUG_HISTORY_20260831_BAYO2_RESOURCE_TRACE.md`
5. `CURRENT_HANDOFF.md`
6. `QUERY_COMPARE_ANALYSIS_20260829.md`

그 다음 `runtime-experiments-arm64`의 실제 HEAD와 아래 active experiment branch/HEAD를 GitHub에서 다시 대조한다.

## 1. 현재 최우선 목표

**Bayonetta 2 JP Vulkan 원거리/배경 폴리곤 플리커링 원인 규명**

환경:
- Windows 11 ARM64
- Snapdragon X Elite / Adreno X1-85
- Vulkan 1.3
- driver `f22d572733`
- compiler `E031.50.36.00`
- driver branch `pp165`

Bayonetta 2 JP:
- title `00050000-1011B900`, v1
- distant/background objects/polygons flicker
- close geometry is relatively stable

XCX JP remains a control title only:
- title `00050000-10116100`, v48
- do not assume the same root cause or consumption path

## 2. 보호 기준점 — 절대 되돌리지 않는다

General code-changing baseline:
`fa17d834bfebd9a41c598b1b1b702000d0ff4618`

Clean ARM64:
`6129066e8bfa3ad89556756712c11d003e0ad31f`

Known-good Adreno compat:
`e14b764b55bf6a5d6f561e7bf1bde8dc17d1b600`

Never roll back:
- VS producer-side `DEFAULT_VAL` synthesize/linkage fix
- AArch64 generated-code cache / I-cache coherency fix
- known-good pre-e834 Vulkan compatibility behavior
  - swapchain loadOp LOAD
  - SIMULTANEOUS_USE command buffers
  - DrawBackbufferQuad clear restore
  - no in-renderpass clear attachments
- Runtime Diagnostics 77/77 exact coverage

## 3. 이미 확정된 Query 비교 결론

### XCX

Observation runtime HEAD:
`a9e731b1761d12eff97916108b11b19100e3b43d`

Predication observation HEAD:
`e6fac132fff290ee3d54a58d4e8e7c03f391f25e`

Confirmed:
- GPU occlusion query type2
- huge query traffic with genuine zero/nonzero completed results
- no exported CPU GET consumption
- no exported conditional-render markers
- no raw `IT_SET_PREDICATION` observed in the dedicated capture
- historical XCX end seed `0x100000` remains untouched

Therefore:
- do not implement/repair predication based on that negative capture
- do not transplant XCX workaround into Bayonetta 2

### Bayonetta 2

CPU query observation confirmed:
- CPU occlusion query type0 only
- heavy `GX2QueryGetOcclusionResult()` use
- `GET_READY_ZERO` dominates
- sampled FINISH always precedes matching GET
- CPU OCPU not-ready marker means ready-zero is a completed result, not a simple default/unready zero

**Do not globally force ready-zero visible.**

## 4. Clean Bayonetta query frame/draw correlation — confirmed runtime baseline

Observation branch:
`diag-bayo2-query-frame-draw-correlation`

Runtime HEAD:
`13c9705e99c23e30f476d3b46d21849b169b9212`

Run:
`33230812891` — SUCCESS

Clean all-Graphic-Packs-OFF runtime:
- GET 61,352
- zero 60,992 / nonzero 360
- `0->NZ` 328
- `NZ->0` 338
- `NZ->NZ` 22
- repeat 0
- missingSnapshot 0
- overwrittenUnconsumed 0
- 94 unique query pointers
- all observed GET values matched finished sample sums
- no GET_NOT_READY
- all Begin/End remained in the same frame
- draw-span median 1, p90 5, p95 7, max 18

User visual result:
- severe flicker remained the same with all Bayonetta Graphic Packs OFF

Cross-run conclusion:
- aggregate query transition density does not directly track visual flicker severity
- however the same small subset of query slots repeatedly oscillates across captures
- common-pointer transition-rate correlation was about 0.786

Persistent target set:
- target0 `0x46a92ec8`
- target1 `0x46a936c8`
- target2 `0x46a93bc8`
- target3 `0x46a93a08`
- target4 `0x46a93708`

## 5. Targeted query → draw fingerprint stage — BUILD COMPLETE

Branch chain:
`diag-bayo2-target-query-draw-fingerprint`

Automatic marker:
`[BAYO2_TARGET]`

Observation-only scope:
- target pointer/generation and GET transition/result
- frame/draw sequence
- pipeline and shader identity
- draw parameters
- clip/raster/depth/color state
- color/depth attachment identity
- no behavior/visibility/query semantic changes

CI history:
- Run `33241228167` — pre-build anchor failure
- Run `33241366205` — pre-build callsite-anchor failure
- Run `33241470467` — actual C++ build failure
- commit `b9200e2b637470cd8902379b535b7c978ce6f973` fixed the instrumentation compile/materialization issue
- Run `33244548809` — **SUCCESS**

Successful artifact:
- id `9712845853`
- `cemu-arm64-bayo2-target-query-draw-fingerprint`
- digest `sha256:80930256843efff9b230e14c2cfea568353a9c8aae1d79106f8113f6336ef4b3`

Do not restart this build stage.

## 6. Downstream draw observation stage — BUILD COMPLETE

Commits:
- `83b57aa7b89c54208f8583bbfa87e44eac9164dd` — add downstream trace
- `b1694fc46ba56de381fd5e9e6ec37bbb93ec3f48` — chain downstream trace

Run:
`33247256523` — **SUCCESS**

Artifact:
- id `9713651612`
- `cemu-arm64-bayo2-target-query-draw-fingerprint`
- digest `sha256:cfd1cdccfa21894c2091174792e602993f0cc01e6ade22aa1c4815876160833c`

Do not restart this build stage.

Important documentation rule:
- detailed runtime conclusions from the targeted/downstream captures are not reconstructed here unless an actual runtime log/document supports them
- do not invent a runtime finding from the fact that the build succeeded

## 7. CURRENT ACTIVE EXPERIMENT — target0 resource identity/content observation

Target:
`0x46a92ec8`

Active branch:
`diag-bayo2-target0-resource-identity`

Current confirmed branch HEAD:
`725aae2f63d6b3e766c37efe26c46341059dae83`

Current commits:
- `e19a3a4e92de0ad044226b248cf1e6b89f8fff9e` — `diagnostics: add Bayo2 target0 resource identity trace`
- `725aae2f63d6b3e766c37efe26c46341059dae83` — `diagnostics: chain Bayo2 target0 resource trace`

Script:
`tools/diagnostics/Apply-Bayo2Target0ResourceIdentityTrace.py`

Intended observation:
- vertex-buffer guest addresses/sizes/strides
- sampled vertex-buffer content hashes
- uniform/constant-buffer identities/content hashes
- uniform variable ranges
- target0-associated resource identity/content correlation

This experiment is observation-only.

### Latest CI — FAILED, NO ARTIFACT

Workflow:
`Cemu ARM64 Bayo2 Target Query Draw Fingerprint Trace`

Run:
`33286935862` — **FAILURE**

Job:
`99191642306`

Head:
`725aae2f63d6b3e766c37efe26c46341059dae83`

Confirmed:
- all preceding compatibility/diagnostic patch steps succeeded
- query-consumption observation-only verifier succeeded
- Bayo2 frame/draw correlation verifier succeeded
- `[BAYO2_TARGET]` verifier succeeded
- target0 resource trace validate/apply/observation-only verification succeeded
- toolchain setup succeeded
- CMake Configure succeeded
- **`Build Cemu once` failed during actual C++ compilation**
- Collect executable skipped
- Upload artifact skipped
- artifacts count = 0

**The exact compiler diagnostic text has not yet been recovered into the project handoff. Do not guess it.**

Consequently:
- current target0 resource trace is NOT build-ready
- there is NO target0 resource artifact
- there is NO target0 resource runtime result/log yet

## 8. NEXT ACTION — 다음 탭은 여기서 즉시 시작

1. GitHub Actions Run `33286935862`, Job `99191642306`의 **정확한 compiler error 원문을 회수**한다.
2. compiler가 지목한 generated resource trace line만 확인한다.
3. `Apply-Bayo2Target0ResourceIdentityTrace.py` 안의 `[BAYO2_RESOURCE]` instrumentation에 대해 **최소 compile-only correction 하나만** 한다.
4. 아래 semantics는 절대 변경하지 않는다:
   - query value/result/readiness
   - query lifetime/bookkeeping
   - visibility/culling
   - Vulkan pipeline/render state
   - resource contents
   - draw execution
   - XCX workaround
5. observation-only verifier와 target `0x46a92ec8` 유지 여부를 정적 검증한다.
6. 수정이 끝났을 때만 기존 workflow를 재실행한다.
7. Build + Collect + Upload가 전부 성공하고 artifact가 실제 존재할 때만 build-ready로 판정한다.
8. artifact 성공 후에만 사용자에게 runtime capture를 요청한다.

**현재는 behavior-changing A/B를 시작하지 않는다.**

## 9. Runtime capture 조건 — build 성공 후에만 사용

- Stop emulation → close Cemu → reopen
- Bayonetta 2 Graphic Packs all OFF
- Runtime Diagnostics OFF
- Master/Preset OFF
- launch Bayonetta 2 JP v1
- same severe-flicker scene
- camera mostly static for about 10–15 seconds while flicker is visible
- close/stop and upload full `log.txt`
- `[BAYO2_TARGET]` / `[BAYO2_RESOURCE]` logging is automatic; no checkbox needed
- user may separately report `same` / `better` / `worse`
- do not invent video↔log frame synchronization

## 10. 닫힌/하향 실험 — 반복 금지

- Position Invariance
- viewport depth-range clamp
- `depthBiasClamp`
- Force Maximum LOD / LOD general
- native `negativeOneToOne` / shader `(z+w)/2` removal
- RT simple/strong/pre-begin barriers
- forced render-pass split
- depthclip
- pipeline pNext
- VS auxHash pipeline key
- `f4c24000` 0x11↔0x1a conversion
- `f4c24000` depth↔color conversion
- nested/overlapping GX2 query resume / duplicate bookkeeping
- `f5442800` stale-main cross-pitch D24 coherence as Bayo primary cause
- old destructive f544 unseeded experiment
- seeded f544 Bayo primary-cause experiment
- XCX raw `IT_SET_PREDICATION` observation
- Bayo2 global ready-zero force-visible

## 11. 작업 규칙

- 이미 배제된 실험을 반복하지 않는다.
- 확정된 수정사항을 되돌리지 않는다.
- 새 runtime 사실은 실제 log로 확인한 뒤에만 문서화한다.
- CI/build 사실은 GitHub Actions로 확인한 경우 문서화 가능하다.
- 사용자 승인 없는 별도 리팩터링/개선/behavior A/B를 섞지 않는다.
- 현재 승인 범위의 단순 compile correction은 resource observation trace 안에서만 수행한다.
- 다른 원인을 동시에 건드리지 않는다.

## 12. 새 탭 시작 프롬프트

> Cemu Windows ARM64 / Adreno 구동분석·디버그 작업을 이어간다. GitHub 저장소 `npark2860-cyber/Cemu-Windows-ARM64`의 `TECH_BIBLE.md`, `DEBUG_HISTORY.md`, `DEBUG_HISTORY_20260829_QUERY_COMPARE.md`, `DEBUG_HISTORY_20260831_BAYO2_RESOURCE_TRACE.md`, `CURRENT_HANDOFF.md`, `QUERY_COMPARE_ANALYSIS_20260829.md`를 먼저 읽고 실제 GitHub의 `runtime-experiments-arm64` HEAD 및 active branch `diag-bayo2-target0-resource-identity` HEAD가 문서와 일치하는지 확인해라. 이전 대화를 추측해서 복원하지 말고 이 문서를 source of truth로 삼아라. 현재 active experiment는 Bayonetta 2 target0 query `0x46a92ec8` resource identity/content observation trace이며 branch HEAD는 `725aae2f63d6b3e766c37efe26c46341059dae83`이다. 최신 Run `33286935862`, Job `99191642306`은 모든 apply/observation-only 검증과 CMake Configure까지 성공했지만 실제 `Build Cemu once`에서 컴파일 실패했고 artifact는 0개다. 정확한 compiler error 원문은 아직 handoff에 회수되지 않았다. `CURRENT_HANDOFF.md`의 NEXT ACTION부터 즉시 시작해서 먼저 Job 로그의 compiler error를 회수하고, `Apply-Bayo2Target0ResourceIdentityTrace.py`의 `[BAYO2_RESOURCE]` instrumentation에 필요한 최소 compile-only correction만 해라. query/visibility/culling/render/resource semantics는 건드리지 말고 behavior-changing A/B도 시작하지 마라. 기존 targeted trace와 downstream trace build는 이미 성공했으므로 반복하지 마라.