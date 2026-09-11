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

The report-only IML/RA extension then proved exact adjacency for guest `0x02A281A0`:

```text
00 MACRO COUNT_CYCLES cycles: 5
01 CYCLE_CHECK
```

This survives PREMOVE, REWRITTEN, and POSTMOVE unchanged.

Native correlation is exact:
- `COUNT_CYCLES`: `native 0x000 -> 0x00c`, 12 bytes
- `CYCLE_CHECK`: `native 0x00c -> 0x018`, 12 bytes

The same structural pair is also present at `0x0420CB80` with `COUNT_CYCLES cycles: 2` followed immediately by `CYCLE_CHECK`.

Safety observation:
- branch targets enter at the IML segment start, not directly at instruction 1
- therefore a qualifying `CYCLE_CHECK` cannot execute without its immediately preceding `COUNT_CYCLES`
- `COUNT_CYCLES` leaves the decremented value in `TEMP_GPR1.WReg` (`w25`)
- there is no generated instruction between the pair that clobbers `w25`

Conclusion: the second `LDR remainingCycles` is a concrete AArch64 backend redundancy for this exact adjacency pattern.

## NEW SINGLE-VARIABLE EXPERIMENT

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

Expected static result for each qualifying pair:
- `COUNT_CYCLES`: remains 12 bytes
- `CYCLE_CHECK`: 12 bytes -> 8 bytes
- saving: 4 bytes / one AArch64 `LDR`

Launchers:
- `ARM64_CYCLECHECK_REUSE_BASELINE.cmd`
- `ARM64_CYCLECHECK_REUSE_CANDIDATE.cmd`
- `ARM64_CYCLECHECK_REUSE_VERIFY.cmd`

Implementation/composition commits through:
- `f311e5e2644f71dea03e680819e3399ad96a37f3`

Current Test CI:
- run `34618642312`
- compile/build validation in progress
- source composition and diagnostic-diff steps already PASS

## NEXT ACTION

Do not performance-benchmark until the new Test CI is green.

Once the artifact is green, run `ARM64_CYCLECHECK_REUSE_VERIFY.cmd` first.

VERIFY acceptance for both targeted pairs where emitted:
1. `[ARM64_CYCLECHECK_REUSE]` confirms reuse
2. `COUNT_CYCLES` remains 12 bytes
3. `CYCLE_CHECK` becomes 8 bytes
4. BOTW reaches stable gameplay without regression

Only after VERIFY passes, run order-balanced performance validation using the fixed BOTW scene and established `t=70..260s` window. Because expected effect may be small, use both orderings or ABBA/preconditioning; do not classify from a single BASELINE -> CANDIDATE pair.

Do not combine this candidate with `arm64-compare-reuse` or any other behavior experiment during validation.
Do not touch `main`, Release, or Diagnostics.
