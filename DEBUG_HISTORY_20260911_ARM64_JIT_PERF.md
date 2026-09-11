# DEBUG HISTORY — 2026-09-10~11 ARM64 JIT performance work

## Scope

Windows ARM64 / Snapdragon X Elite / Adreno X1-85에서 BOTW의 host/JIT 병목을 실제 측정으로 좁히고, 한 변수씩 성능 최적화 가능성을 검증한다.

Branch:
- `runtime-experiments-arm64`

## Benchmark harness

`perf-log`는 10초 window마다 다음을 남긴다.
- average FPS
- average frame time
- p99 frame time
- approximate 1% low
- Vulkan barriers/frame
- renderpasses/frame

Controlled first-pass rule:
- same save/location/camera
- static scene
- same graphics/FPS++ settings
- weather fixed
- restart Cemu per preset
- ignore startup/warmup
- compare `t=70..260s`

## Closed / non-winning first-pass directions

Do not repeat without new evidence:
- timer UDIV64
- no-extra-fence
- ARM64 serialize
- skip WAW barrier
- skip RT-load barrier
- force render-pass reuse
- ARM64 NEON texture hash
- historical `perf-arm64-jit-ab` compare/branch fusion
- historical direct dispatch

Barrier/render-pass count reductions alone are not performance proof.

## Host/PPC profiling path

Relevant commits:
- `3a97333e79f1addacc1f3865f9d5b8dec96a1145` — automated BOTW CPU sampling launcher
- `f89d814b72264013ec5a4813a9431f1a3e0cbe77` — symbolized CPU hotspot profiling build
- `1f766b2eeec243c761c8c4e1622ac3c57e27cd91` — sampled CPU stacks
- `0ac53af14598a8c549980e0a7cc18d83aaff3f16` — sample only actively RUNNING PPC thread
- `e1ec8d30d3fd09ae01b4cf5f5ddaf7ad8644f82d` — keep profiler diff scoped to sampling logic
- `aa2eba94f6ca6b7ce46b1e7dfc970f3e923fd511` — reduce outer profiler cadence to 10 ms

1 ms outer sampling materially perturbed FPS. 10 ms is the current diagnostic cadence.

Latest important RUNNING-only guest samples from the established profile:
- `0x0420CB80` — 5.56%
- `0x02A281A0` — 4.12%
- `0x03B84854` — 3.68%
- `0x0399B4DC` — 1.77%

HLE waits are observations, not automatic JIT targets.

## Native hotspot mapping

Relevant commits:
- `25f423ab9bb11139b084057546f39df39cb5a215` — map sampled guest hotspots to ARM64 JIT code
- `4c456c6b07ba3d0ef8e35a598dc2b88ca1ebe6b4` — add BOTW JIT hotspot launcher
- `09c4de42fe1b48b6d8fa656f02b9b8612eb3c7e9` — targeted ARM64 JIT root-cause tracing
- `9d649811653c5e4391e80cf8d32df45e8b5bfb26` — include IML debug declarations

### `0x03B84854`

This hotspot exposed repeated identical comparisons for separate boolean results.

With compare reuse enabled, native sequence includes:

```text
6b05009f  1a9f27ea  1a9f97eb  1a9f17ec
```

One compare feeds three conditional-result materializations instead of repeating the same compare.

### `0x02A281A0`

Mapped entry begins with:

```text
17ffff66 d503201f
```

Treat this as branch/thunk-like. Follow the first branch target before interpreting later words as a straight-line body.

## ARM64 consecutive compare reuse

Experiment:
- `arm64-compare-reuse`

Relevant commits:
- `bafc464ce0a4b88b20b74c04f66b55899185a576`
- `04b5626c77503aceed1fb712e45563bf620262fc`

Validated CI:
- run `34558962681`
- SUCCESS

Controlled same-build `t=70..260s` result:

| metric | BASELINE | ARM64_COMPARE_REUSE | delta |
|---|---:|---:|---:|
| avg FPS | 52.09095 | 52.96810 | +1.6839% |
| avg frame time | 19.1998 ms | 18.8834 ms | -1.6479% |
| mean p99 | 23.6361 ms | 22.7896 ms | -3.5814% |
| mean 1% low | 42.4818 FPS | 43.8995 FPS | +3.3372% |

Status:
- generated-code reduction confirmed
- positive candidate
- not a FIX
- keep separate from later experiments until each is independently measured

## `0x0420CB80` targeted IML/RA tracing

`Apply-ARM64JitRootCause.py` logs the target segment before/after RA move insertion and correlates post-RA IML instructions with emitted native byte ranges.

Pre-P1 repository history only established that `0x0420CB80` was load-heavy and required exact IML mapping. It did **not** contain the later handoff's claimed detailed non-GPR `LR+CTR` / `XER+temporaryFPR` proof.

## ARM64 R_NAME LDP P1 — actual implementation

Experiment:
- `arm64-rname-ldp`

Implementation commit:
- `f929fa8007d6ef17f90a3c166b5d248d2ee30e3d`
- actual message: `perf: add ARM64 R_NAME LDP experiment`

Implementation mechanism:
- build-time installer `tools/diagnostics/Apply-ARM64RNameLdp.py`
- runtime gate `arm64-rname-ldp`

Actual helper semantics:
- only `PPCREC_IML_TYPE_R_NAME`
- IML base format must be `I64`
- only names `PPCREC_NAME_R0 .. PPCREC_NAME_R0+31`
- contiguous run of `R_NAME` instructions is scanned
- each guest GPR must occur exactly once in the run
- guest GPR `n` may pair with `n+1`
- destination host registers must differ
- emits one `LDP` into two `WReg`s from `PPCInterpreter_t::gpr[]`
- unmatched GPR and all non-GPR R_NAME instructions retain normal lowering

Baseline backend source confirms integer R_NAME GPR loads normally use `ldr(WReg, ...)`, and `PPCInterpreter_t::gpr` is `uint32 gpr[32]`.

### Correction of stale handoff evidence

After the initial build failure, handoff documents incorrectly described P1 as:
- non-GPR 64-bit fields
- adjacent +8 byte state offsets
- `SPR::LR + SPR::CTR`
- `SPR::XER + temporaryFPR`
- `F940A546`, `F940A942`, `F9410146`, `F9410542`

This text conflicts with the actual `f929fa8...` implementation, the baseline `r_name()` lowering, `PPCInterpreter_t` field widths, and the pre-P1 debug-history state. It is therefore classified as a documentation error and must not be treated as captured evidence.

## P1 initial CI failure and compile-only repair

Initial P1 CI:
- run `34576700718`
- job `103190682420`
- failed during C++ compile

Recovered compiler diagnostic showed generated source lines beginning with literal `\t`, producing repeated `expected expression` errors in `BackendAArch64.cpp`.

Root cause:
- P1 helper C++ was stored in a Python raw triple-quoted string
- `\t` remained literal rather than becoming indentation

Minimal repair:
- commit `fc330d1c7c29e68042208337ac6e46eb21c69421`
- `helper_block = r'''` -> `helper_block = '''`
- no optimization-scope change

Rebuilt Test CI:
- run `34591462835`
- job `103237476096`
- result **SUCCESS**
- artifact `cemu-arm64-test`
- artifact ID `10262500252`
- digest `sha256:7fb8e3f213818d4f0cc46067bd02ff6cd1fd4be37553564e9105a111f037d8fe`

## P1 runtime VERIFY result

Launcher:
- `ARM64_RNAME_LDP_VERIFY.cmd`

Target entry:
- `0x0420CB80`

Target segment itself contains only cycle accounting/check IML and reports:
- `pairs=0`
- `native_bytes_saved=0`

Its enterable state-restore segment (`ppc=0`, `enter=0x0420CB80`) contains the R_NAME run.

Post-RA run exposes these six pairs:
- r3+r4
- r5+r6
- r24+r25
- r26+r27
- r28+r29
- r30+r31

Runtime diagnostic:

```text
[ARM64_RNAME_LDP] ppc=0x00000000 enter=0x0420cb80 pairs=6 native_bytes_saved=24
```

Interpretation:
- runtime gate active: PASS
- intended GPR pair planning active: PASS
- six pair emissions: PASS
- exact code-size saving 24 bytes: PASS
- unrelated CR/XER.SO R_NAME entries still emit normal loads: PASS
- control-flow tail retained: PASS
- BOTW stable-gameplay smoke: PASS

## P1 first controlled A/B — 2026-09-11

Run order:
1. `ARM64_RNAME_LDP_BASELINE`
2. `ARM64_RNAME_LDP_CANDIDATE`

Primary window:
- `t=70..260s`
- 20 samples per run

| metric | BASELINE | CANDIDATE | delta |
|---|---:|---:|---:|
| avg FPS | 49.66745 | 50.76435 | **+2.2085%** |
| avg frame time | 20.13760 ms | 19.70055 ms | **-2.1703%** |
| mean p99 | 22.25870 ms | 21.52095 ms | **-3.3144%** |
| mean 1% low | 45.10415 FPS | 46.49985 FPS | **+3.0944%** |
| barriers/frame | 203.99550 | 200.17105 | -1.8748% |
| renderpasses/frame | 287.09810 | 283.18290 | -1.3637% |

Aligned-window behavior:
- CANDIDATE FPS wins 19 of 20 windows
- only `t=170s` is lower by about 0.328 FPS

Drift check:
- BASELINE falls to 48.382 / 47.541 FPS at `t=250/260s`
- CANDIDATE stays at 50.998 / 50.827 FPS
- however the result does not depend on those final two windows
- `t=70..240s`: CANDIDATE avg FPS advantage about **+1.7869%**
- `t=70..230s`: advantage about **+1.7369%**

Interpretation:
- first P1 A/B is a clear positive direction
- this agrees with independently verified code-size reduction
- one pair is insufficient for FIX classification
- preserve `arm64-rname-ldp` as a positive candidate
- next required action is one reverse-order confirmation using the same artifact: CANDIDATE then BASELINE

## Current decision gate

Do not build another optimization yet.

Reverse-order confirmation only:
1. `ARM64_RNAME_LDP_CANDIDATE.cmd`
2. `ARM64_RNAME_LDP_BASELINE.cmd`
3. same scene/settings and `t=70..260s`

If positive again with correctness intact, classify P1 as a repeatable positive candidate and reprofile before promotion consideration.

Do not combine with `arm64-compare-reuse` yet. Do not move to `0x02A281A0` until P1 is resolved.
