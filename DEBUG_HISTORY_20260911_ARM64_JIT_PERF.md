# DEBUG HISTORY — 2026-09-10~11 ARM64 JIT performance profiling / compare reuse

## Scope

Windows ARM64 / Snapdragon X Elite / Adreno X1-85에서 BOTW의 host/JIT 병목을 실제 측정으로 좁히고, 한 변수씩 성능 최적화 가능성을 검증한다.

Branch:
- `runtime-experiments-arm64`

Last validated non-documentation code checkpoint:
- `04b5626c77503aceed1fb712e45563bf620262fc`

## Benchmark harness

`perf-log`는 10초 window마다 다음을 남긴다.
- average FPS
- average frame time
- p99 frame time
- approximate 1% low
- Vulkan barriers/frame
- renderpasses/frame

현재 1차 비교 규칙:
- 같은 save/location/camera
- 정지 scene
- 같은 graphics/FPS++ settings
- weather fixed
- Cemu 재시작
- startup/warmup 제외
- `t=70..260s`를 비교 구간으로 사용

## Closed / non-winning first-pass experiments

다음 방향은 현재 BOTW 정지 scene에서 승자가 아니었다.
- timer UDIV64
- no-extra-fence
- ARM64 serialize
- skip WAW barrier
- skip RT-load barrier
- force render-pass reuse
- ARM64 NEON texture hash

Barrier 수나 render-pass 수 자체를 크게 줄여도 FPS가 개선되지 않은 경우가 있었으므로, 숫자 감소를 곧바로 성능 향상으로 해석하지 않는다.

Historical branch `perf-arm64-jit-ab`의 compare/branch fusion 및 direct-dispatch variants도 baseline과 비슷하거나 불리하여 종료했다. 동일 실험을 새 근거 없이 반복하지 않는다.

## Host/PPC profiling path

CPU sampling/WPR launcher와 symbolized build를 추가했고, 이후 guest PPC execution을 직접 좁히기 위해 `Debug -> View PPC threads -> Profile thread` 경로를 사용했다.

Relevant commits:
- `3a97333e79f1addacc1f3865f9d5b8dec96a1145` — automated BOTW CPU sampling launcher
- `f89d814b72264013ec5a4813a9431f1a3e0cbe77` — symbolized CPU hotspot profiling build
- `1f766b2eeec243c761c8c4e1622ac3c57e27cd91` — sampled CPU stacks
- `0ac53af14598a8c549980e0a7cc18d83aaff3f16` — sample only actively RUNNING PPC thread
- `e1ec8d30d3fd09ae01b4cf5f5ddaf7ad8644f82d` — keep profiler diff scoped to sampling logic
- `aa2eba94f6ca6b7ce46b1e7dfc970f3e923fd511` — reduce outer profiler cadence to 10 ms

### Profiler perturbation finding

1 ms outer sampling repeatedly suspended/resumed the guest thread and materially reduced FPS during profiling.

The outer cadence was changed to 10 ms while keeping 1 ms polling only for suspend completion. This preserved thousands of RUNNING samples while removing the large profiler-induced FPS drop seen with the 1 ms version.

Profiler percentages are therefore diagnostic execution-sample distributions, not final FPS measurements.

## Latest RUNNING-only guest profile

Build: `04b5626`

Selected thread:
- `0E001800 / Default Core 1`

State counts:
- observations: 5058
- RUNNING: 3564 (70.46%)
- READY: 31 (0.61%)
- WAITING: 1463 (28.92%)

Top entries:
- `coreinit.OSWaitEvent` — 12.93%
- `0x0420CB80` — 5.56%
- `0x02A281A0` — 4.12%
- `gx2.GX2SetAlphaToMaskReg` — 3.73%
- `0x03B84854` — 3.68%
- `coreinit.OSWaitSemaphore` — 3.17%
- `coreinit.OSFastMutex_Lock` — 2.02%
- `0x0399B4DC` — 1.77%

HLE waits are not automatically JIT optimization targets.

## Native hotspot mapping

Relevant commits:
- `25f423ab9bb11139b084057546f39df39cb5a215` — map sampled guest hotspots to ARM64 JIT code
- `4c456c6b07ba3d0ef8e35a598dc2b88ca1ebe6b4` — add BOTW JIT hotspot launcher

The mapper logs direct jump-table entrypoints for selected guest PCs and dumps 128 bytes of native code.

### `0x03B84854`

This hotspot exposed a concrete redundant-code pattern: identical comparisons were being emitted repeatedly for separate boolean results.

With compare reuse enabled, the relevant native sequence includes:

```text
6b05009f  1a9f27ea  1a9f97eb  1a9f17ec
```

Interpretation:
- one `CMP`
- three condition-result materializations (`CSET`-family)

The prior behavior repeated the same compare for each result. This is a real generated-code reduction, not only a benchmark correlation.

### `0x0420CB80`

Current mapped code is dominated by loads before a branch. It is not yet known whether these loads are:
- required guest semantics
- register allocator spill/reload
- state restore
- block-entry/exit mechanics

No optimization should be written until exact IML/basic-block mapping identifies redundancy.

### `0x02A281A0`

Current mapped entry begins with:

```text
17ffff66 d503201f
```

The first instruction is branch-like and is followed by padding. Later words in the raw 128-byte dump may not be straight-line executable code. The next diagnostic should resolve/follow the branch destination before drawing conclusions from those bytes.

## ARM64 consecutive compare reuse experiment

Experiment token:
- `arm64-compare-reuse`

Relevant commits:
- `bafc464ce0a4b88b20b74c04f66b55899185a576` — implement flag reuse
- `04b5626c77503aceed1fb712e45563bf620262fc` — fix patch ordering against existing diagnostic instrumentation

### CI history

Run #55 failed **before compile** while applying Diagnostic Edition:
- `Apply-ARM64CompareReuse.py` expected an exact function-body anchor
- the base diagnostic performance patch had already inserted `RuntimeDiagnostics::ScopedJitCompile`
- result: `expected 1 anchor, found 0`

Fix:
- stop anchoring on the whole untouched function prefix
- patch around stable signature/context locations compatible with existing instrumentation

Run #56:
- ID `34558962681`
- result: **SUCCESS**
- artifact `cemu-arm64-test`
- artifact ID `10184443139`
- artifact digest `sha256:7294b62139b1f53aa56205a5a060dbd54d6dea62963a710125dbf03aa22efb82`

## Controlled same-build A/B result

Comparison window: `t=70..260s`, 20 samples each.

| metric | BASELINE | ARM64_COMPARE_REUSE | delta |
|---|---:|---:|---:|
| avg FPS | 52.09095 | 52.96810 | +1.6839% |
| avg frame time | 19.1998 ms | 18.8834 ms | -1.6479% |
| mean p99 | 23.6361 ms | 22.7896 ms | -3.5814% |
| mean 1% low | 42.4818 FPS | 43.8995 FPS | +3.3372% |
| barriers/frame | 200.0892 | 201.2699 | +0.5901% |
| renderpasses/frame | 283.2197 | 284.3660 | +0.4047% |

### Interpretation

Confirmed:
- generated ARM64 code is smaller for the proven identical-compare pattern
- same-build benchmark direction is positive
- this is the first clearly positive optimization candidate in the current performance campaign

Not confirmed:
- it is **not yet a FIX**
- magnitude is small and may not be visually obvious
- the baseline run trends down late (`t=240..260s`), so part of the observed gap could be temporal drift
- no Release/Diagnostics promotion yet

Status:
- **PRESERVE AS POSITIVE CANDIDATE**
- continue looking for larger JIT wins
- if promotion is considered later, repeat controlled A/B (preferably with reversed order / another fresh pair) first

## Next action

See `NEXT_ACTION.md`.

Priority:
1. exact IML/native analysis of `0x0420CB80`
2. branch-target resolution for `0x02A281A0`
3. only then create one new single-variable JIT experiment
