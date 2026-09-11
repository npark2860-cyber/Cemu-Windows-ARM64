# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> Canonical policy: `BRANCH_POLICY.md`
> Active-role manifest: `ACTIVE_BRANCH_ROLES.md`
> Before every write/build, fetch the actual Test branch HEAD/workflow/source from GitHub.

## ROLE

**[Test]**

Repository:
- `npark2860-cyber/Cemu-Windows-ARM64`

Branch:
- `runtime-experiments-arm64`

Workflow:
- `.github/workflows/runtime-experiments-arm64.yml`
- display name: `[Test] Cemu Windows ARM64`

Artifact identity:
- `cemu-arm64-test`
- executable: `Cemu-Test.exe`

Do not modify `main`, Release, or Diagnostics in this stage.

## CLOSED P1 — ARM64 R_NAME GPR LDP

Experiment:
- `arm64-rname-ldp`

Implementation:
- `f929fa8007d6ef17f90a3c166b5d248d2ee30e3d`

Compile-only repair:
- `fc330d1c7c29e68042208337ac6e46eb21c69421`

Validated CI/artifact:
- run `34591462835`
- SUCCESS
- artifact ID `10262500252`

Static/runtime result:
- six GPR pair loads verified at the `0x0420CB80` enterable state-restore path
- `native_bytes_saved=24`
- correctness smoke PASS

Performance result after both run orders:
- BASELINE condition mean `49.78785 FPS`
- CANDIDATE condition mean `49.44420 FPS`
- candidate `-0.6902%`
- second run of each pair was about `+2.9462%` faster than the first regardless of preset

Final classification:
- codegen reduction: REAL
- repeatable performance gain: NOT CONFIRMED
- `arm64-rname-ldp`: CLOSED / NON-WINNING for performance
- DO NOT PROMOTE
- DO NOT COMBINE with `arm64-compare-reuse`

Future sub-3% candidates require order-balanced validation.

## PRESERVED SEPARATE CANDIDATE — ARM64 COMPARE REUSE

`arm64-compare-reuse` remains only a candidate.

Previous one-order result:
- baseline `52.09095 FPS`
- candidate `52.96810 FPS`
- `+1.6839%`

Because the P1 campaign exposed strong order bias, compare-reuse also needs fresh order-balanced validation before promotion.

## CURRENT TARGET — `0x02A281A0`

RUNNING-only guest profile share:
- about `4.12%`

Previously mapped native entry begins:

```text
17ffff66 d503201f
```

Static AArch64 decode of `0x17ffff66`:
- unconditional `B imm26`
- signed imm26 = `-154`
- byte displacement = `-616` = `-0x268`
- actual body target = `nativeEntry - 0x268`

Therefore the raw words after the original entry are not the straight-line body and must not be analyzed as such.

## EXISTING REPORT-ONLY DIAGNOSTIC — CONFIRMED

`tools/diagnostics/Apply-ARM64JitRootCause.py` already contains the exact `0x02A281A0` branch-follow path:
- detect first `B imm26`
- sign-extend immediate
- resolve target
- log `JIT_HOTSPOT_BRANCH`
- dump 128 bytes as `JIT_HOTSPOT_TARGET`

This exact code is present at the validated artifact build commit `fc330d1...`.

Existing launcher in that artifact:
- `JIT_HOTSPOT_NATIVE.cmd`
- enables `jit-hotspot-native,perf-log`

No new build is required for the next capture.

## CURRENT NEXT ACTION

Using validated artifact `10262500252`:
1. run `JIT_HOTSPOT_NATIVE.cmd`
2. load the same BOTW scene
3. open `Debug > View PPC threads`
4. profile `0E001800 / Default Core 1` for about 60 seconds
5. close Cemu after output is written
6. upload the generated log

Expected `0x02A281A0` evidence:
- `JIT_HOTSPOT_MAP`
- `JIT_HOTSPOT_CODE`
- `JIT_HOTSPOT_BRANCH` with `imm26=-154`, `byte_off=-616`
- 128 bytes of `JIT_HOTSPOT_TARGET`

After capture:
- decode actual target body
- correlate to guest block/IML where possible
- classify repeated compare/load/state movement/branch glue/ABI mechanics versus required guest semantics
- only then design one behavior-changing experiment if a concrete redundant pattern is proven

Do not start a new optimization patch before this capture.
