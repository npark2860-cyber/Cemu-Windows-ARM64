# Cemu Windows ARM64 — Performance Optimization Plan

Status: active planning document for the **Test** branch only.

## 1. Fixed scope and source of truth

- Repository: `npark2860-cyber/Cemu-Windows-ARM64`
- Test branch: `runtime-experiments-arm64`
- Do not touch `main`.
- Do not promote an experiment to Release/Diagnostics until static verification, CI, correctness/runtime validation, and order-balanced performance validation establish it as a real winner.
- Change one performance variable at a time.
- Reuse the existing BOTW measurement harness and diagnostics whenever possible.

Primary records:
- `CURRENT_HANDOFF.md`
- `NEXT_ACTION.md`
- `DEBUG_HISTORY_20260911_ARM64_JIT_PERF.md`
- `BRANCH_POLICY.md`

## 2. Current evidence

Previously closed/non-winning directions:
- timer UDIV64
- `NO_EXTRA_FENCE`
- ARM64 timer serialize
- skip WAW barrier
- skip RT load barrier
- force render-pass reuse
- ARM64 NEON texture hash
- historical compare/branch fusion
- historical direct dispatch
- `arm64-rname-ldp` as a performance optimization

The most promising area remains AArch64 JIT generated-code quality, but small wins are vulnerable to run-order bias.

### Preserved candidate: `arm64-compare-reuse`

One-order result:
- baseline `52.09095 FPS`
- candidate `52.96810 FPS`
- `+1.6839%`

Generated-code reduction is real, but the result is still only a candidate because later crossover testing exposed a strong second-run advantage. Revalidate compare-reuse with order-balanced testing before promotion.

### Closed P1: `arm64-rname-ldp`

Static/runtime VERIFY:
- six pair loads emitted at the `0x0420CB80` enterable state-restore path
- `native_bytes_saved=24`
- correctness smoke PASS

Performance:
- BASELINE -> CANDIDATE: candidate `+2.2085%`
- CANDIDATE -> BASELINE: candidate `-3.5750%`
- two-order condition mean: candidate `-0.6902%`
- second-run period advantage: about `+2.9462%`

Decision:
- codegen reduction is valid
- repeatable performance gain is not established
- do not promote or combine

## 3. Priority queue

| Priority | Work item | Evidence | Feasibility | Risk | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| P0 | Resolve branch/thunk target for `0x02A281A0` | 5/5 | 5/5 | 1/5 | **Do now** |
| P1 | One evidence-derived AArch64 JIT optimization from resolved target | pending P0 | 3-4/5 | 2-3/5 | **Next experiment only if proven** |
| P2 | Order-balanced revalidation of `arm64-compare-reuse` | 4/5 | 5/5 | 1/5 | **Retain candidate** |
| P3 | Descriptor/update/bind/allocation and submit/wait profiling | 2/5 | 4/5 | 1/5 | **After JIT pass** |
| P4 | Cross-title runtime validation of proven winners | required for generalization | 5/5 | 1/5 | **Promotion gate** |
| P5 | Toolchain PGO/LTO/compiler-flag campaign | weak current attribution | 3/5 | 2/5 | **Late-stage only** |

## 4. P0 — `0x02A281A0` branch-target resolution

The mapped native entry begins with:

```text
17ffff66 d503201f
```

Do not interpret later raw words as the straight-line body until the initial branch is resolved.

Required diagnostic:
- decode the first AArch64 `B imm26`
- resolve the actual native target
- dump at least 128 bytes from that target
- correlate the target body to the guest block/IML
- classify repeated work as compare/load/state movement/branch glue/ABI mechanics/required guest semantics

Success condition:
- identify one provably redundant generated-code pattern, or prove the target has no actionable redundancy and close it.

Use report-only diagnostics first.

## 5. P1 — exactly one optimization from P0 evidence

Do not bundle hypotheses.

Possible next experiments only after proof:
- equivalent load reuse/peephole
- redundant compare elimination
- scoped branch glue reduction
- state restore/load reduction with proven liveness safety
- ABI-preservation/reload reduction when exact call-boundary evidence supports it

Every P1 experiment must:
- remain Test-branch only
- be one behavior variable
- have an exact static/native expectation
- be runtime-gated or otherwise isolated
- be diff-inspected before CI
- pass Test CI and correctness smoke before performance testing

## 6. Benchmark protocol — order bias control

The primary BOTW measurement window remains:
- `t=70..260s`
- 10-second windows

Fixed scene requirements:
- same save/location/camera
- stationary player/camera
- same graphics/FPS++ settings
- fixed weather
- restart Cemu per preset

### New requirement from P1 crossover

A single BASELINE -> CANDIDATE result is **not sufficient** for small effects.

Observed on P1:
- first run mean across two sequences: `48.89575 FPS`
- second run mean across two sequences: `50.33630 FPS`
- second-run advantage: about `+2.9462%`

This is large enough to create a false positive for a ~1-3% optimization.

For future sub-3% candidates, use one of these:
1. sacrificial preconditioning launch, then measured AB and BA
2. ABBA sequence
3. at minimum both AB and BA orders before positive classification

Always record:
- exact branch/HEAD
- preset/order
- experiment token
- average FPS
- average frame time
- p99
- 1% low
- barriers/frame and renderpasses/frame as supporting data only
- correctness result
- static/native-code result for JIT experiments

Do not interpret lower barrier/render-pass counts by themselves as a performance win.

## 7. P2 — compare-reuse promotion gate

`arm64-compare-reuse` remains disabled by default and preserved as a candidate.

Before any promotion:
- use the strengthened order-balanced benchmark protocol
- verify the candidate remains positive across orderings
- verify no correctness regression
- reprofile after any confirmed win

A single +1.68% one-order result is not enough after the P1 order-bias finding.

## 8. P3 — host/Vulkan work after JIT

If JIT analysis stops producing concrete leads, profile:
- descriptor allocation/update/bind frequency and CPU cost
- command submission frequency and submit-side CPU cost
- queue/fence wait distribution
- upload/staging/memory command-path cost
- CPU-side Vulkan object/cache lookup pressure

Do not return to barrier/render-pass speculation without new profile evidence.

## 9. P4 — cross-title validation

A BOTW-only win is not enough for a general ARM64 optimization.

After a candidate survives repeated order-balanced BOTW validation:
- validate at least one additional CPU-heavy Wii U title
- verify protected paths/titles do not regress
- reprofile because hotspot distribution may move
- combine winners only after each has independently passed

## 10. P5 — toolchain optimization

PGO, LTO, compiler flags, and broad build tuning remain late-stage work because they weaken attribution.

## 11. Stop rules

Stop an optimization path when:
- alleged redundancy is proven semantically required
- order-balanced performance is neutral/negative
- the measured gain is smaller than uncontrolled period bias and does not survive crossover
- correctness risk increases without a measured bottleneck
- the experiment duplicates a closed path

## 12. Immediate execution order

1. Resolve/follow the initial branch for `0x02A281A0` with report-only diagnostics.
2. Dump/correlate the actual target body.
3. Classify any redundant-looking code.
4. If and only if one redundant pattern is proven, design one new JIT experiment.
5. Static verify -> diff inspect -> Test CI -> correctness smoke.
6. Performance test with order-balanced protocol.
7. Reprofile after any real win.
8. Revalidate `arm64-compare-reuse` separately before promotion/combination.
