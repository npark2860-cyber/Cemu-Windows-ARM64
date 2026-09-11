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

The two-order BOTW result showed a strong second-run bias, so future sub-3% candidates require order-balanced validation.

## CURRENT TARGET — `0x02A281A0`

Latest RUNNING-only guest profile share:
- about `4.12%`

Existing native entry begins:

```text
17ffff66 d503201f
```

The first word is an AArch64 unconditional `B imm26`.

Static decode:
- signed imm26: `-154`
- byte displacement: `-616` (`-0x268`)
- resolved body is therefore at `nativeEntry - 0x268`

Do not interpret the words after the original entry as the straight-line body.

## EXISTING DIAGNOSTIC — READY

No new code or build is required for the next capture.

`tools/diagnostics/Apply-ARM64JitRootCause.py` already contains the report-only `0x02A281A0` branch-target follow logic and dumps 128 bytes from the resolved target.

The Test build receives it through the existing diagnostic composition path, and the current validated artifact already contains it.

Existing launcher:
- `JIT_HOTSPOT_NATIVE.cmd`
- experiments: `jit-hotspot-native,perf-log`

## NEXT RUNTIME CAPTURE

Using the existing validated artifact:
1. run `JIT_HOTSPOT_NATIVE.cmd`
2. load the same BOTW scene
3. open `Debug > View PPC threads`
4. profile `0E001800 / Default Core 1` for about 60 seconds
5. close Cemu after the profiler output is written
6. upload the generated log

Expected log families for `0x02A281A0`:
- `JIT_HOTSPOT_MAP`
- `JIT_HOTSPOT_CODE`
- `JIT_HOTSPOT_BRANCH` with `imm26=-154` and `byte_off=-616`
- `JIT_HOTSPOT_TARGET` covering 128 bytes

After the log arrives:
1. decode the resolved target body
2. correlate it to guest block/IML where possible
3. classify repeated compare/load/state movement/branch glue/ABI mechanics versus required guest semantics
4. only if one concrete redundant pattern is proven, design exactly one new runtime-gated experiment

Do not write a behavior-changing optimization before this capture.
Do not touch `main`, Release, or Diagnostics.
