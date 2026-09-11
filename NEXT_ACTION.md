# NEXT ACTION — ARM64 cycle-check TEMP_GPR1 reuse

Repository: `npark2860-cyber/Cemu-Windows-ARM64`

Branch: `runtime-experiments-arm64`

## CLOSED P1 — `arm64-rname-ldp`

P1 remains closed as a non-winning performance direction.

- static/correctness: PASS
- native code-size reduction: REAL
- repeatable performance gain: NOT CONFIRMED
- promotion: DO NOT PROMOTE
- do not combine with `arm64-compare-reuse`

Future sub-3% candidates require order-balanced validation because the P1 crossover exposed a strong second-run bias.

## `0x02A281A0` ROOT CAUSE — PROVEN

Fresh diagnostic run from Test build `5dd260c1...` captured:
- `0x02A281A0`: `5.59%` (`185/3312` RUNNING samples)
- actual entry first word: `17ffff64`
- runtime-decoded branch: `imm26=-156`, `byte_off=-624` (`-0x270`)
- resolved target: `0x00000143973bc9e0`

Resolved target begins:

```text
ldr  w25, [x29, #remainingCycles]
sub  w25, w25, #5
str  w25, [x29, #remainingCycles]
ldr  w25, [x29, #remainingCycles]
tbnz w25, #31, ...
```

The report-only IML/RA extension proved exact adjacency for guest `0x02A281A0`:

```text
00 MACRO COUNT_CYCLES cycles: 5
01 CYCLE_CHECK
```

This survives PREMOVE, REWRITTEN, and POSTMOVE unchanged.

The same structural pair is present at `0x0420CB80` with `COUNT_CYCLES cycles: 2` followed immediately by `CYCLE_CHECK`.

Safety observation:
- branch targets enter at the IML segment start, not directly at instruction 1
- therefore a qualifying `CYCLE_CHECK` cannot execute without its immediately preceding `COUNT_CYCLES`
- `COUNT_CYCLES` leaves the decremented value in `TEMP_GPR1.WReg` (`w25`)
- there is no generated instruction between the pair that clobbers `w25`

Conclusion: the second `LDR remainingCycles` is a concrete AArch64 backend redundancy for this exact adjacency pattern.

## SINGLE-VARIABLE EXPERIMENT — `arm64-cyclecheck-reuse`

Experiment token:
- `arm64-cyclecheck-reuse`

Implementation installer:
- `tools/diagnostics/Apply-ARM64CycleCheckReuse.py`

Implementation rule:
- only for `PPCREC_IML_TYPE_CJUMP_CYCLE_CHECK`
- only when the immediately preceding IML in the same segment is `PPCREC_IML_TYPE_MACRO / PPCREC_IML_MACRO_COUNT_CYCLES`
- candidate skips the cycle-check reload and directly uses `TEMP_GPR1.WReg`
- all other cycle checks keep the existing `conditionalJumpCycleCheck()` path unchanged
- token absent => baseline behavior unchanged

Implementation/composition commit:
- `f311e5e2644f71dea03e680819e3399ad96a37f3`

Validated Test CI:
- run `34618642312`
- job `103326770490`
- conclusion: SUCCESS
- artifact `cemu-arm64-test`
- artifact ID `10273002162`
- artifact digest `sha256:9378dbac17b2457aa2f1e0f76bdf301c4c6fb4ae65f3785af9a52a3eb2284da9`

## VERIFY — PASS

Runtime VERIFY used build `f311e5e` with:

```text
[EXPERIMENT] Active: arm64-cyclecheck-reuse,jit-iml-ra-hotspot,perf-log
[PERF_META] preset=ARM64_CYCLECHECK_REUSE_VERIFY
```

Target `0x0420CB80`:

```text
[JIT_IML_NATIVE] ... iml=0 native=0x000->0x00c bytes=12 MACRO COUNT_CYCLES cycles: 2
[ARM64_CYCLECHECK_REUSE] ppc=0x0420cb80 iml=1 reuse=TEMP_GPR1
[JIT_IML_NATIVE] ... iml=1 native=0x00c->0x014 bytes=8 CYCLE_CHECK
```

Target `0x02A281A0`:

```text
[JIT_IML_NATIVE] ... iml=0 native=0x000->0x00c bytes=12 MACRO COUNT_CYCLES cycles: 5
[ARM64_CYCLECHECK_REUSE] ppc=0x02a281a0 iml=1 reuse=TEMP_GPR1
[JIT_IML_NATIVE] ... iml=1 native=0x00c->0x014 bytes=8 CYCLE_CHECK
```

VERIFY result:
- reuse marker: PASS on both targeted pairs
- `COUNT_CYCLES`: unchanged at 12 bytes
- `CYCLE_CHECK`: 12 bytes -> 8 bytes
- static saving: exactly 4 bytes / one AArch64 `LDR` per qualifying pair
- BOTW reaches gameplay under the candidate without an observed correctness regression in the VERIFY run

The optimization hypothesis is therefore validated structurally and by runtime generated-code inspection. It is now eligible for performance validation, but it is not yet a promoted optimization.

## NEXT ACTION — ORDER-BALANCED PERFORMANCE VALIDATION

Run only the fixed BOTW benchmark scene. Keep player/camera/settings/weather identical and restart Cemu for every preset.

Use:
- `ARM64_CYCLECHECK_REUSE_BASELINE.cmd`
- `ARM64_CYCLECHECK_REUSE_CANDIDATE.cmd`

Primary comparison window:
- `t=70..260s`

Required ordering because the previous P1 test exposed a strong order/period effect:
1. first pair: BASELINE -> CANDIDATE
2. second pair: CANDIDATE -> BASELINE

Prefer a sacrificial warm-up/preconditioning run before the measured pairs if practical. Do not classify from one pair only.

Primary decision metrics:
- average FPS
- average frame time
- p99 frame time
- approximate 1% low

Supporting only:
- barriers/frame
- renderpasses/frame

Promotion rule:
- correctness must remain clean
- candidate must show a repeatable advantage after both orderings, not merely a second-run advantage
- if gain is sub-3%, treat it as noise-sensitive and require especially consistent direction across the balanced runs

Do not combine `arm64-cyclecheck-reuse` with `arm64-compare-reuse` or any other behavior experiment during this validation.
Do not touch `main`, Release, or Diagnostics.
