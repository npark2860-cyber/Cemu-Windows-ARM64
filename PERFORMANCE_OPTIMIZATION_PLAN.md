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
- `DEBUG_HISTORY_20260912_ARM64_CYCLECHECK_REUSE.md`
- `DEBUG_HISTORY_20260912_ARM64_COMPARE_REUSE_REVALIDATION.md`
- `BRANCH_POLICY.md`

## 2. Current evidence

Closed/non-winning directions — do not repeat without new evidence:
- timer UDIV64
- `NO_EXTRA_FENCE`
- ARM64 timer serialize
- skip WAW barrier
- skip RT load barrier
- force render-pass reuse
- ARM64 NEON texture hash
- historical compare/branch fusion
- historical direct dispatch
- `arm64-rname-ldp`
- `arm64-cyclecheck-reuse`
- `arm64-compare-reuse`

The recent AArch64 JIT campaign established an important rule: a generated-code reduction is not sufficient evidence of a runtime performance win.

### Closed: `arm64-rname-ldp`

Static/runtime VERIFY:
- six pair loads emitted at the `0x0420CB80` enterable state-restore path
- `native_bytes_saved=24`
- correctness smoke PASS

Performance:
- BASELINE -> CANDIDATE: candidate `+2.2085%`
- CANDIDATE -> BASELINE: candidate `-3.5750%`
- two-order condition mean: candidate `-0.6902%`

Decision:
- generated-code reduction valid
- repeatable performance gain not established
- CLOSED / DO NOT PROMOTE / DO NOT COMBINE

### Closed: `arm64-cyclecheck-reuse`

Evidence chain:
- exact `COUNT_CYCLES -> CYCLE_CHECK` adjacency proven in IML
- backend source proved the second `LDR remainingCycles` redundant for that adjacency
- runtime VERIFY reduced `CYCLE_CHECK` from 12 bytes to 8 bytes at both `0x02A281A0` and `0x0420CB80`
- BOTW correctness smoke PASS

Balanced performance (`t=70..260s`, B -> C -> C -> B):
- pair 1 candidate: `-2.3571%` FPS
- pair 2 candidate: `-0.5587%` FPS
- two-order candidate: `-1.4623%` FPS

Decision:
- semantic/static optimization valid
- runtime benefit absent
- CLOSED / DO NOT PROMOTE / DO NOT COMBINE

### Closed: `arm64-compare-reuse`

Previous one-order result:
- baseline `52.09095 FPS`
- candidate `52.96810 FPS`
- `+1.6839%`

Balanced revalidation (`t=70..260s`, B -> C -> C -> B):
- pair 1 candidate: `-1.6914%` FPS
- pair 2 candidate: `-1.9508%` FPS
- two-order baseline mean: `53.14998 FPS`
- two-order candidate mean: `52.18275 FPS`
- candidate delta: **-1.8198%**
- avg frame time: **+1.8700%** candidate
- p99: **+2.1586%** candidate
- 1% low: **-1.1764%** candidate
- execution-position second-run effect: only about `+0.1123%`

Decision:
- generated-code simplification remains real
- the previous `+1.6839%` one-order result is treated as a false positive under the strengthened protocol
- candidate loses in both orderings
- CLOSED / DO NOT PROMOTE / DO NOT COMBINE

## 3. Priority queue

| Priority | Work item | Evidence | Feasibility | Risk | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| P0 | Report-only reprofiling of current JIT/native hotspots | 5/5 | 5/5 | 1/5 | **Do now** |
| P1 | Correlate hottest actionable entry to native body + IML | pending P0 | 5/5 | 1/5 | **Next if JIT remains dominant** |
| P2 | One evidence-derived JIT optimization from a newly proven redundancy | pending P1 | 3-4/5 | 2-3/5 | **Only if proven** |
| P3 | Descriptor/update/bind/allocation and submit/wait profiling | 3/5 | 4/5 | 1/5 | **Fallback if JIT stalls** |
| P4 | Cross-title runtime validation of proven winners | required for generalization | 5/5 | 1/5 | **Promotion gate** |
| P5 | Toolchain PGO/LTO/compiler-flag campaign | weak current attribution | 3/5 | 2/5 | **Late-stage only** |

## 4. Immediate P0 — report-only reprofiling

Do not start another behavior-changing optimization yet.

Use the fixed BOTW benchmark scene and current Test baseline to answer:
- which guest/native JIT entries are actually hottest now?
- do the previous `0x0420CB80`, `0x02A281A0`, `0x03B84854` entries still dominate?
- is the dominant cost still inside generated PPC code, or has host/Vulkan work become more important?

For the hottest actionable JIT entry:
1. resolve any entry branch/thunk to the actual native body
2. dump enough native code to classify the hot sequence
3. correlate to guest block/IML
4. identify only provably redundant work before considering a new experiment

Report-only diagnostics first.

## 5. Benchmark protocol — order bias control

The primary BOTW measurement window remains `t=70..260s`.

A single BASELINE -> CANDIDATE pair is not sufficient for small effects.

The recent campaign showed three distinct failure modes:
- R_NAME LDP: large run-order crossover
- cycle-check reuse: valid code reduction but slower in both orders
- compare-reuse: earlier +1.68% one-order result invalidated by balanced testing

For future sub-3% candidates:
1. use sacrificial preconditioning when practical
2. use AB/BA or ABBA-style balancing
3. never classify from one pair only
4. record exact branch/HEAD, order, experiment token, FPS, avg frame time, p99, 1% low, and supporting counters

Barrier/render-pass reductions alone are not performance proof.

## 6. Host/Vulkan fallback

If JIT reprofiling stops producing concrete, high-confidence leads, profile:
- descriptor allocation/update/bind frequency and CPU cost
- command submission frequency and submit-side CPU cost
- queue/fence wait distribution
- upload/staging/memory command-path cost
- CPU-side Vulkan object/cache lookup pressure

Do not return to barrier/render-pass speculation without new profile evidence.

## 7. Cross-title validation

A BOTW-only win is not enough for a general ARM64 optimization.

After a candidate survives repeated order-balanced BOTW validation:
- validate at least one additional CPU-heavy Wii U title
- verify protected paths/titles do not regress
- reprofile because hotspot distribution may move
- combine winners only after each has independently passed

## 8. Toolchain optimization

PGO, LTO, compiler flags, and broad build tuning remain late-stage work because they weaken attribution.

## 9. Stop rules

Stop an optimization path when:
- alleged redundancy is semantically required
- order-balanced performance is neutral/negative
- the measured gain does not survive crossover
- correctness risk increases without a measured bottleneck
- the experiment duplicates a closed path
- code-size reduction is real but runtime benefit is absent

## 10. Immediate execution order

1. Reprofile current JIT/native hotspots using report-only diagnostics.
2. Correlate the hottest actionable entry to real native code and IML.
3. Only if a new redundancy is proven, design one behavior-changing JIT experiment.
4. Validate any sub-3% claim with order-balanced testing.
5. If JIT profiling yields no convincing lead, move to host/Vulkan CPU-side profiling.
6. Cross-title validate only after a genuine winner survives BOTW.
