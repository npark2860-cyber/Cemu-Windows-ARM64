# Cemu Windows ARM64 — Performance Optimization Plan

Status: active planning document for the **Test** branch only.

## 1. Fixed scope and source of truth

- Repository: `npark2860-cyber/Cemu-Windows-ARM64`
- Test branch: `runtime-experiments-arm64`
- Planning baseline HEAD before this document: `0d8d5da51374e2b79cda8b439b58e251be2067d7`
- Last validated non-document code checkpoint: `04b5626c77503aceed1fb712e45563bf620262fc`
- Do not touch `main`.
- Do not promote an experiment to Release/Diagnostics until static verification, CI, and required runtime validation establish it as a FIX.
- Change one performance variable at a time.
- Reuse the existing BOTW measurement harness and diagnostics whenever possible instead of adding parallel tooling.

Primary supporting records:

- `CURRENT_HANDOFF.md`
- `NEXT_ACTION.md`
- `DEBUG_HISTORY_20260911_ARM64_JIT_PERF.md`
- `BRANCH_POLICY.md`

## 2. Current evidence

The current BOTW campaign has already ruled out several speculative GPU/host changes as useful optimizations in the tested scene. Do not repeat these without new profile evidence:

- timer UDIV64
- `NO_EXTRA_FENCE`
- ARM64 timer serialize
- skip WAW barrier
- skip RT load barrier
- force render-pass reuse
- ARM64 NEON texture-hash
- historical compare/branch fusion
- historical direct dispatch

The strongest positive direction is currently AArch64 JIT generated-code quality.

`arm64-compare-reuse` proved native-code reduction and showed a positive controlled A/B direction:

- baseline: `52.09095 FPS`
- compare-reuse: `52.96810 FPS`
- FPS: `+1.6839%`
- average frame time: `-1.6479%`
- mean p99: `-3.5814%`
- mean 1% low: `+3.3372%`

This remains a **candidate**, not a promoted FIX. The gain is small enough that temporal/baseline drift must still be excluded by later revalidation.

Latest PPC profile at the validated code checkpoint identified important guest-code samples including:

- `0x0420CB80`: `5.56%`
- `0x02A281A0`: `4.12%`
- `0x03B84854`: `3.68%`
- `0x0399B4DC`: `1.77%`

HLE wait functions remain visible in the profile, but waits must not be treated automatically as JIT optimization targets.

## 3. Priority queue

| Priority | Work item | Evidence | Feasibility | Risk | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| P0 | Exact IML -> RA -> AArch64 diagnosis for `0x0420CB80` | 5/5 | 5/5 | 1/5 | **Do now** |
| P0 | Resolve branch/thunk target for `0x02A281A0` before interpreting native bytes | 5/5 | 5/5 | 1/5 | **Do now** |
| P1 | One evidence-derived AArch64 JIT optimization | pending P0 | 3-4/5 | 2-3/5 | **Next experiment** |
| P2 | Fresh controlled revalidation of `arm64-compare-reuse` | 4/5 | 5/5 | 1/5 | **Retain candidate** |
| P3 | Descriptor/update/bind/allocation and submit/wait profiling | 2/5 | 4/5 | 1/5 | **After JIT pass** |
| P4 | Cross-title runtime validation of proven winners | required for generalization | 5/5 | 1/5 | **Promotion gate** |
| P5 | Toolchain PGO/LTO/compiler-flag campaign | weak current attribution | 3/5 | 2/5 | **Late-stage only** |

## 4. P0 — targeted JIT root-cause diagnostics

### 4.1 Guest hotspot `0x0420CB80`

The mapped AArch64 entry is load-heavy, but no load is considered redundant until its origin is proven.

Use the existing IML debug infrastructure instead of creating a new diagnostic framework:

- identify the exact `IMLSegment` by `ppcAddress` / `enterPPCAddress`
- dump the target segment before RA with liveness information
- dump the same target after RA move insertion/register rewriting
- correlate the result with the existing native entry/native-byte dump
- record native offset so IML operations can be matched to emitted AArch64 instructions

The diagnosis must classify repeated native loads as one of:

1. guest semantic memory loads
2. `R_NAME` loads from `PPCInterpreter_t` state
3. RA spill/reload or cross-segment live-range mechanics
4. block entry/exit state synchronization
5. call/helper ABI state restoration

Success condition: identify at least one **provably redundant** emitted instruction pattern, or prove that the observed loads are required and close this hotspot as an optimization lead.

### 4.2 Guest hotspot `0x02A281A0`

The mapped entry begins with `17ffff66 d503201f`, so later raw words must not be interpreted as the straight-line body until the initial AArch64 branch is resolved.

Required diagnostic:

- decode the first `B imm26`
- resolve its actual native target
- dump at least 128 bytes from the resolved target
- then correlate that body to the guest block/IML

Success condition: obtain the actual native body and determine whether it exposes a concrete repeated code-generation cost worth testing.

## 5. P1 — choose exactly one optimization from P0 evidence

Do not implement multiple hypotheses together. Select the next experiment using this decision table:

| P0 finding | Next experiment |
| --- | --- |
| repeated `R_NAME` loads are inserted/survive through RA | investigate live-range continuity and safe redundant state-load elimination |
| IML is clean but AArch64 lowering duplicates equivalent loads | backend-local load reuse/peephole experiment |
| call boundaries dominate reload traffic | inspect exact AArch64 caller-saved/ABI pressure and test one scoped preservation/reload reduction |
| segment entry/exit mechanics cause repeated state loads | inspect live-in/live-out state policy for the exact path and test one scoped transition optimization |
| loads are required guest semantics | reject this lead and move to the next sampled hotspot |
| no concrete redundant pattern exists | do not create a speculative JIT patch |

Every P1 change must be runtime-gated or otherwise isolated as one test variable and must have an exact static/native-code expectation before runtime benchmarking.

## 6. P2 — compare-reuse promotion gate

`arm64-compare-reuse` stays preserved but disabled as a candidate until revalidated.

Revalidation requirements:

- same build family and benchmark configuration
- restart Cemu for each preset
- same save/location/camera and no movement for the first controlled pass
- same graphics/FPS++ settings and fixed weather
- ignore warmup/startup
- compare the established `t=70..260s` window
- run both orderings if practical (`baseline -> candidate` and `candidate -> baseline`) to reduce temporal drift
- compare average FPS, average frame time, p99, and 1% low

Promotion requires a repeatable positive result without correctness regression. A single small positive run is not enough.

## 7. P3 — host/Vulkan work after the JIT pass

Do not return first to barrier/render-pass speculation. If JIT work stops producing concrete leads, profile these areas instead:

- descriptor allocation/update/bind frequency and CPU cost
- command submission frequency and submit-side CPU cost
- queue/fence wait distribution
- upload/staging/memory command-path cost
- CPU-side Vulkan object/cache lookup pressure

Only create a behavior-changing GPU experiment after profiling points to one of these paths. Previously rejected WAW/RT-load/render-pass/fence experiments stay closed unless the new profile materially changes the evidence.

## 8. P4 — cross-title validation

A BOTW-only win is not enough to classify an ARM64 optimization as generally beneficial.

After a candidate survives repeated BOTW A/B validation:

- validate at least one additional CPU-heavy Wii U title
- verify no correctness regression in protected titles/paths
- reprofile after the change because hotspot distribution may move
- only combine separately proven winners after each has passed its own single-variable validation

## 9. P5 — toolchain optimization

PGO, LTO, compiler flags, and broad build-level tuning remain late-stage work. They should not be used to hide unresolved runtime/JIT costs because they make attribution weaker.

Start this phase only after the main runtime hotspots are understood and there is a stable set of verified code changes to profile.

## 10. Measurement and stop rules

Use the existing 10-second-window BOTW harness. The primary comparison window remains `t=70..260s` unless a later documented reason changes it.

For every experiment record:

- exact branch and HEAD
- experiment token/state
- benchmark preset/order
- average FPS
- average frame time
- p99
- 1% low
- correctness result
- static/native-code result when the experiment is JIT-related

Stop an optimization path when:

- the alleged redundant operation is proven semantically required
- a controlled A/B is neutral or negative and there is no new contradictory evidence
- the change increases correctness risk without a measured bottleneck
- the experiment duplicates an already closed path

## 11. Immediate execution order

1. Add report-only targeted IML/RA/native diagnostics for `0x0420CB80` using the existing `IMLDebug_DumpSegment()` path.
2. Decode/follow the initial branch for `0x02A281A0` and dump the actual native body.
3. Classify the exact source of redundant-looking native instructions.
4. If and only if a concrete redundant pattern is proven, design one P1 JIT experiment.
5. Run static verification first, then Test CI/runtime A/B only for that single variable.
6. Reprofile after any real win before selecting the next hotspot.
7. Revalidate `arm64-compare-reuse` separately before any promotion or combination.
