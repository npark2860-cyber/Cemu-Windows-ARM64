# NEXT ACTION — ARM64 JIT hotspot `0x02A281A0`

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

## `0x02A281A0` BRANCH TARGET — CAPTURED

Fresh RUNNING-only profile:
- `0x02A281A0`: `5.59%` (`185/3312` RUNNING samples)
- `0x0420CB80`: `5.40%`
- `0x03B84854`: `3.80%`

Actual direct-jump entry in this run:

```text
17ffff64 d503201f
```

Runtime branch diagnostic resolved:
- signed `imm26 = -156`
- byte displacement `-624` (`-0x270`)
- `nativeEntry = 0x00000143973bcc50`
- target body `= 0x00000143973bc9e0`

The earlier `17ffff66 / -0x268` value was from an older build/layout and must not be hardcoded. Always trust the runtime-decoded branch instruction for the current build.

## RESOLVED BODY — IMPORTANT PATTERN

The first instructions at the resolved body are:

```text
b942b3b9  ldr  w25, [x29, #0x2b0]   ; remainingCycles
51001739  sub  w25, w25, #5
b902b3b9  str  w25, [x29, #0x2b0]
b942b3b9  ldr  w25, [x29, #0x2b0]   ; same value reloaded
37f810b9  tbnz w25, #31, ...         ; cycle check
```

Source correlation confirms:
- `PPCREC_IML_MACRO_COUNT_CYCLES` emits `LDR -> SUB -> STR` through `TEMP_GPR1.WReg`
- `PPCREC_IML_TYPE_CJUMP_CYCLE_CHECK` independently reloads `remainingCycles` into the same `TEMP_GPR1.WReg` before testing bit 31

This exposes a concrete AArch64-only peephole hypothesis:
- when `COUNT_CYCLES` is immediately followed by `CYCLE_CHECK`, reuse the value already present in `TEMP_GPR1` and skip the second `LDR`
- expected static saving: one 4-byte AArch64 load for each qualifying pair
- do not implement as a performance candidate until IML/RA adjacency is captured on the target block

Other body instructions decode as normal guest semantics/state handling, including guest-memory load+endian swap, compare/CSET, CR writeback, GPR updates, conditional branch, and successor/state restore loads. They are not classified redundant yet.

## REPORT-ONLY IML/RA EXTENSION — BUILDING

Test branch diagnostic extension:
- `8017b9d9f7a44f4ba226343db1cc38c9868b4496` — add `Extend-ARM64JitRootCause02A.py`
- `5dd260c1cd6be9915085ff7b6e0553d7859b06e4` — run the extension after generic diagnostics in the Test workflow

Scope:
- report-only
- expands existing `jit-iml-ra-hotspot` coverage from `0x0420CB80` to `0x02A281A0`
- no behavior-changing code

CI:
- run `34611534661`
- job `103303192396`
- diagnostic extension step already PASS
- full build/artifact validation still required before runtime capture

## NEXT RUNTIME CAPTURE

After the new Test artifact is green, use:
- `JIT_IML_RA_HOTSPOT.cmd`

Same BOTW scene, then:
1. `Debug > View PPC threads`
2. profile `0E001800 / Default Core 1`
3. capture the `0x02A281A0` `JIT_IML_RA_PREMOVE`, `JIT_IML_RA_REWRITTEN`, `JIT_IML_RA_POSTMOVE`, `JIT_IML_NATIVE_SEG`, and `JIT_IML_NATIVE` lines
4. verify whether `MACRO COUNT_CYCLES cycles: 5` and `CYCLE_CHECK` are consecutive in the relevant segment and map to the native `LDR/SUB/STR/LDR/TBNZ` sequence

If adjacency is proven with no intervening clobber, design exactly one runtime-gated candidate to reuse `TEMP_GPR1` for the cycle check.

Do not implement another optimization in parallel. Do not touch `main`, Release, or Diagnostics.
