# NEXT ACTION — ARM64 JIT hotspot `0x02A281A0`

Repository: `npark2860-cyber/Cemu-Windows-ARM64`

Branch: `runtime-experiments-arm64`

## 0. SOURCE-OF-TRUTH CHECK

Before any write/build:
1. fetch actual `runtime-experiments-arm64` HEAD
2. read `CURRENT_HANDOFF.md`
3. read `HANDOFF_PROMPT.md`
4. read `DEBUG_HISTORY_20260911_ARM64_JIT_PERF.md`
5. read `PERFORMANCE_OPTIMIZATION_PLAN.md`
6. confirm `.github/workflows/runtime-experiments-arm64.yml`
7. do not touch `main`, Release, or Diagnostics

## 1. CLOSED P1 — `arm64-rname-ldp`

Implementation:
- `f929fa8007d6ef17f90a3c166b5d248d2ee30e3d`

Compile repair:
- `fc330d1c7c29e68042208337ac6e46eb21c69421`

Green CI:
- run `34591462835`
- artifact `10262500252`

Static/runtime VERIFY:
- PASS
- six GPR pair loads at the `0x0420CB80` enterable state-restore path
- `native_bytes_saved=24`
- BOTW stable-gameplay smoke PASS

Performance crossover result:

Pair 1, BASELINE -> CANDIDATE:
- `49.66745 -> 50.76435 FPS`
- **+2.2085%** candidate

Pair 2, CANDIDATE -> BASELINE:
- `49.90825 baseline` vs `48.12405 candidate`
- **-3.5750%** candidate

Across both orders:
- BASELINE condition mean: `49.78785 FPS`
- CANDIDATE condition mean: `49.44420 FPS`
- candidate: **-0.6902%**

Period effect:
- first run mean: `48.89575 FPS`
- second run mean: `50.33630 FPS`
- second-run advantage: **+2.9462%**

Decision:
- codegen reduction is real
- performance win is not repeatable
- **do not promote**
- **do not combine with compare-reuse**
- do not spend more runs on P1 without new evidence or an improved benchmark protocol

## 2. BENCHMARK PROTOCOL UPDATE

Small effects are vulnerable to strong order/period bias on this setup.

For future sub-3% candidates:
- do not accept a single A->B pair
- prefer a sacrificial preconditioning launch plus AB/BA, or ABBA
- at minimum test both orderings before positive classification
- continue using the fixed BOTW scene and primary `t=70..260s` window
- record run order explicitly

`arm64-compare-reuse` is still only a preserved candidate because its earlier +1.68% result was one-order only.

## 3. NEXT TARGET — `0x02A281A0`

Latest RUNNING-only guest profile share:
- about `4.12%`

Existing mapped native entry starts with:

```text
17ffff66 d503201f
```

The first instruction is branch/thunk-like and is followed by padding. Do not treat later raw words from the original entry dump as straight-line executable code until the branch destination is resolved.

## 4. REQUIRED NEXT SEQUENCE

Analysis first, no optimization code yet:
1. confirm the existing report-only branch-target diagnostic is still present/usable on the Test branch
2. decode the first AArch64 `B imm26` at `0x02A281A0`
3. log the actual native branch target
4. dump at least 128 bytes from the resolved target body
5. map the body to guest block/IML where possible
6. identify whether the cost is repeated compare/load/state movement/branch glue/ABI mechanics or required guest semantics
7. only if one concrete redundant pattern is proven, design exactly one new runtime-gated experiment

If current logging cannot answer this, add report-only diagnostics first.

## 5. EXPERIMENT RULE

For the next behavior-changing candidate:
- one variable only
- Test branch only
- static/native expectation first
- inspect diff before CI
- green Test CI
- correctness smoke
- order-balanced runtime validation
- no silent combination with `arm64-compare-reuse`

## 6. CLOSED / NON-WINNING DIRECTIONS

Do not repeat without new evidence:
- timer UDIV64
- no-extra-fence
- ARM64 timer serialize
- skip WAW barrier
- skip RT load barrier
- force render-pass reuse
- ARM64 NEON texture hash
- historical compare/branch fusion
- historical direct dispatch
- `arm64-rname-ldp` as a performance optimization
