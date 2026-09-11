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

The most promising remaining area is still AArch64 JIT generated-code quality, but small code-size reductions are not automatically useful at runtime.

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
- `0x02A281A0` was resolved from its branch/thunk into the real native body
- IML proved exact `COUNT_CYCLES -> CYCLE_CHECK` adjacency
- backend source proved the second `LDR remainingCycles` redundant for that adjacency
- runtime VERIFY reduced `CYCLE_CHECK` from 12 bytes to 8 bytes at both `0x02A281A0` and `0x0420CB80`
- BOTW correctness smoke PASS

Order-balanced performance (`t=70..260s`, B -> C -> C -> B):
- pair 1 candidate: `-2.3571%` FPS
- pair 2 candidate: `-0.5587%` FPS
- two-order baseline mean: `53.22655 FPS`
- two-order candidate mean: `52.44823 FPS`
- candidate delta: **-1.4623%**
- avg frame time: **+1.4708%** candidate
- p99: **+1.0912%** candidate
- 1% low: **-0.4124%** candidate

Decision:
- semantic/static optimization valid
- native code-size reduction real
- repeatable runtime performance gain absent
- CLOSED / DO NOT PROMOTE / DO NOT COMBINE

### Preserved candidate: `arm64-compare-reuse`

One-order result:
- baseline `52.09095 FPS`
- candidate `52.96810 FPS`
- `+1.6839%`

Generated-code simplification is real, but this result predates the strengthened order-bias protocol. It requires order-balanced revalidation before any promotion.

## 3. Priority queue

| Priority | Work item | Evidence | Feasibility | Risk | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| P0 | Order-balanced revalidation of `arm64-compare-reuse` | 4/5 | 5/5 | 1/5 | **Do now** |
| P1 | Reprofile JIT hotspots if compare-reuse fails or wins | 4/5 | 5/5 | 1/5 | **Next after P0** |
| P2 | One evidence-derived JIT optimization from a newly proven hotspot | pending profile | 3-4/5 | 2-3/5 | **Only if proven** |
| P3 | Descriptor/update/bind/allocation and submit/wait profiling | 2/5 | 4/5 | 1/5 | **After JIT pass** |
| P4 | Cross-title runtime validation of proven winners | required for generalization | 5/5 | 1/5 | **Promotion gate** |
| P5 | Toolchain PGO/LTO/compiler-flag campaign | weak current attribution | 3/5 | 2/5 | **Late-stage only** |

## 4. Immediate P0 — compare-reuse balanced revalidation

Experiment:
- `arm64-compare-reuse`

Use exactly one behavior variable.

Required order:
1. BASELINE
2. COMPARE_REUSE
3. COMPARE_REUSE
4. BASELINE

Primary window:
- `t=70..260s`
- 10-second samples

Fixed scene requirements:
- same save/location/camera
- stationary player/camera
- same graphics/FPS++ settings
- fixed weather
- restart Cemu per preset

Primary metrics:
- average FPS
- average frame time
- p99 frame time
- approximate 1% low

Supporting only:
- barriers/frame
- renderpasses/frame

Promotion condition:
- positive direction must survive both orderings
- no correctness regression
- a sub-3% gain that crosses over is not a promotion candidate

## 5. Benchmark protocol — order bias control

The primary BOTW measurement window remains `t=70..260s`.

A single BASELINE -> CANDIDATE pair is not sufficient for small effects.

The R_NAME LDP campaign demonstrated that execution order can create a false positive of several percent. The cycle-check campaign then showed the value of balanced testing: despite a structurally valid optimization, the candidate was slower in both orderings.

For future sub-3% candidates:
1. use sacrificial preconditioning when practical
2. use AB/BA or ABBA-style balancing
3. never classify from one pair only
4. record exact branch/HEAD, order, experiment token, FPS, avg frame time, p99, 1% low, and supporting counters

Barrier/render-pass reductions alone are not performance proof.

## 6. After compare-reuse

If compare-reuse passes balanced validation:
- retain it as the first independently proven JIT performance winner
- reprofile BOTW because hotspot distribution may move
- cross-title validate before promotion
- do not combine it with another candidate until that candidate independently passes

If compare-reuse fails:
- close it
- reprofile current JIT hotspots
- choose the next target only from measured evidence
- do not resurrect closed code-size-only optimizations

## 7. Host/Vulkan work after the JIT pass

If JIT analysis stops producing concrete leads, profile:
- descriptor allocation/update/bind frequency and CPU cost
- command submission frequency and submit-side CPU cost
- queue/fence wait distribution
- upload/staging/memory command-path cost
- CPU-side Vulkan object/cache lookup pressure

Do not return to barrier/render-pass speculation without new profile evidence.

## 8. Cross-title validation

A BOTW-only win is not enough for a general ARM64 optimization.

After a candidate survives repeated order-balanced BOTW validation:
- validate at least one additional CPU-heavy Wii U title
- verify protected paths/titles do not regress
- reprofile because hotspot distribution may move
- combine winners only after each has independently passed

## 9. Toolchain optimization

PGO, LTO, compiler flags, and broad build tuning remain late-stage work because they weaken attribution.

## 10. Stop rules

Stop an optimization path when:
- alleged redundancy is semantically required
- order-balanced performance is neutral/negative
- the measured gain does not survive crossover
- correctness risk increases without a measured bottleneck
- the experiment duplicates a closed path
- code-size reduction is real but runtime benefit is absent

## 11. Immediate execution order

1. Revalidate `arm64-compare-reuse` with B -> C -> C -> B.
2. If it wins, reprofile and cross-title validate before promotion.
3. If it loses, close it and reprofile current JIT hotspots.
4. Only design another behavior-changing JIT experiment after a new redundancy is proven by IML/native evidence.
5. Move to host/Vulkan profiling if the JIT pass stops yielding measured wins.
