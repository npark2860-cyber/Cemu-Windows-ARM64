# NEXT ACTION — ARM64 JIT hotspot optimization

Repository: `npark2860-cyber/Cemu-Windows-ARM64`

Branch: `runtime-experiments-arm64`

## 0. SOURCE-OF-TRUTH CHECK

Before any write or build:
1. fetch actual `runtime-experiments-arm64` HEAD
2. read `CURRENT_HANDOFF.md`
3. read `DEBUG_HISTORY_20260911_ARM64_JIT_PERF.md`
4. confirm `.github/workflows/runtime-experiments-arm64.yml`
5. confirm no requested change touches `main`, Release, or Diagnostics

Last validated non-documentation checkpoint is `04b5626c77503aceed1fb712e45563bf620262fc`, but documentation may have advanced branch HEAD.

## 1. DO NOT PROMOTE COMPARE-REUSE YET

`arm64-compare-reuse` is the first clearly positive candidate, but not a FIX.

Same-build controlled BOTW A/B (`t=70..260s`):
- baseline: 52.091 FPS
- compare-reuse: 52.968 FPS
- delta: +1.68%

Generated-code simplification is confirmed, but effect size is small and baseline shows some late-run drift. Preserve the candidate; do not merge it into Release/Diagnostics yet.

## 2. NEXT TARGET: `0x0420CB80`

Current sampled share: about 5.56% of RUNNING-only samples in the latest profile.

The current native dump is load-heavy. Do **not** assume the loads are redundant.

Required analysis before code changes:
- map the exact guest basic block / IML corresponding to `0x0420CB80`
- identify whether the loads are guest semantics, register allocator spill/reload, state restore, or block-entry/exit mechanics
- compare repeated register/state loads within the exact block
- look for a concrete redundant instruction pattern that can be removed without changing guest semantics

If current logging cannot answer this, add report-only diagnostics first.

## 3. SECOND TARGET: `0x02A281A0`

Current sampled share: about 4.12%.

Mapped native entry begins with:
- `17ffff66`
- `d503201f`

This looks like a branch/thunk followed by padding. The later 32-bit words in the 128-byte dump must **not** be treated as a straight-line instruction stream until the branch destination is resolved.

Preferred next diagnostic if needed:
- decode/follow the first branch target
- log another 128 bytes from the actual target
- keep this report-only and runtime-gated

## 4. EXPERIMENT RULE

When one new optimization candidate is proven:
- add exactly one runtime token
- keep default behavior unchanged
- make one behavior variable change
- static-verify source diff
- build Test branch only
- runtime smoke BOTW first
- same-build BASELINE vs candidate benchmark using the controlled static scene
- compare `t=70..260s`

Do not enable `arm64-compare-reuse` automatically while measuring a different candidate. Measure each candidate independently first; combinations come only after individual wins.

## 5. CLOSED DIRECTIONS

Do not re-run without new evidence:
- timer UDIV64
- no-extra-fence
- ARM64 timer serialize
- skip WAW barrier
- skip RT load barrier
- force render-pass reuse
- ARM64 NEON texture hash
- historical compare/branch fusion
- historical direct dispatch

## 6. DECISION POINT

The next tab should **not start by writing optimization code**.

First deliverable is an evidence-based answer to:

> What exactly is expensive/redundant in the native JIT path for `0x0420CB80` (or, if that is not actionable, the resolved branch target of `0x02A281A0`)?

Only then choose the next single-variable experiment.
