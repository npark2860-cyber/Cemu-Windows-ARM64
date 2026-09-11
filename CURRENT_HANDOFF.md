# CURRENT HANDOFF — Cemu Windows ARM64 / Adreno

> Canonical policy: `BRANCH_POLICY.md`
> Active-role manifest: `ACTIVE_BRANCH_ROLES.md`
> Do **not** trust a hardcoded branch HEAD in a handoff. Before every write/build, fetch the actual branch HEAD/workflow/source from GitHub.

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

`main`, Release, and Diagnostics are not to be modified in this stage.

## CURRENT VALIDATED CODE CHECKPOINT

Current behavior-changing experiment:
- token: `arm64-rname-ldp`
- implementation commit: `f929fa8007d6ef17f90a3c166b5d248d2ee30e3d`
- actual commit message: `perf: add ARM64 R_NAME LDP experiment`
- implementation is applied at Test build time by `tools/diagnostics/Apply-ARM64RNameLdp.py`
- launchers: `ARM64_RNAME_LDP_BASELINE.cmd`, `ARM64_RNAME_LDP_CANDIDATE.cmd`, `ARM64_RNAME_LDP_VERIFY.cmd`

Compile-only repair:
- `fc330d1c7c29e68042208337ac6e46eb21c69421`
- `fix: decode ARM64 R_NAME LDP helper indentation`
- root cause was a Python raw triple-quoted helper string preserving literal `\t` in generated C++
- repair only removed the raw-string prefix; optimization scope was unchanged

Validated Test CI:
- run ID: `34591462835`
- job ID: `103237476096`
- result: **SUCCESS**
- `Build Cemu once`: SUCCESS
- artifact: `cemu-arm64-test`
- artifact ID: `10262500252`
- artifact digest: `sha256:7fb8e3f213818d4f0cc46067bd02ff6cd1fd4be37553564e9105a111f037d8fe`

Documentation commits may advance branch HEAD beyond `fc330d1...`. Always fetch the actual branch HEAD before writing.

## IMPORTANT CORRECTION — P1 SEMANTICS

Older handoff text written after the failed build incorrectly described P1 as pairing non-GPR 64-bit `R_NAME` loads such as `SPR::LR + SPR::CTR` at `+8` offsets and cited `F940...` examples.

That description is **not supported by the actual P1 implementation or the pre-P1 debug history** and must not be used as source of truth.

Actual `f929fa8...` implementation:
- considers only `PPCREC_IML_TYPE_R_NAME`
- requires `I64` IML destination format
- considers only names `PPCREC_NAME_R0 .. R31`
- groups a contiguous run of `R_NAME` IML instructions
- pairs guest GPR `n` with guest GPR `n+1` when each appears exactly once in the run and destinations differ
- emits one AArch64 `LDP` to two `WReg` destinations from adjacent `PPCInterpreter_t::gpr[]` uint32 fields
- leaves unpaired GPR and all non-GPR `R_NAME` lowering unchanged

This matches the actual baseline AArch64 backend, where integer `R_NAME` values are loaded into `WReg`; `PPCInterpreter_t::gpr[]` is a `uint32[32]` array.

The stale claims about non-GPR +8-byte pairs, `LR+CTR`, `XER+temporaryFPR`, and the cited `F940...` sequence must not be resurrected unless new independently captured evidence proves them.

## RUNTIME VERIFY — PASS

User runtime verification used `ARM64_RNAME_LDP_VERIFY.cmd` on the successful `fc330d1...` artifact.

Hotspot:
- guest entry: `0x0420CB80`
- enterable post-RA segment: `ppc=0x00000000`, `enter=0x0420CB80`

Observed post-RA GPR `R_NAME` set allowed six adjacent guest-GPR pairs:
- `r3 + r4`
- `r5 + r6`
- `r24 + r25`
- `r26 + r27`
- `r28 + r29`
- `r30 + r31`

Runtime diagnostic:
- `[ARM64_RNAME_LDP] ... pairs=6 native_bytes_saved=24`

The six partner IML instructions show `bytes=0`, exactly matching six pair emissions replacing twelve individual 4-byte GPR loads with six 4-byte pair loads.

The actual `0x0420CB80` cycle-check segment itself reports `pairs=0`; the optimization acts on its enterable state-restore segment. The final `JUMP` remains present and is still 8 bytes in the IML/native correlation log.

Static/runtime acceptance for pair formation is therefore **PASS**:
- runtime gate is active
- expected GPR pair planning occurs
- six pair loads are emitted
- native size reduction is exactly 24 bytes
- unrelated non-GPR `R_NAME` entries still emit normally
- no branch/control-flow removal is indicated
- BOTW reaches stable gameplay without correctness failure in the verify smoke

Do not use the VERIFY run's early FPS samples as a performance result; it was a correctness/static verification run, not the controlled `t=70..260s` A/B.

## TEST CONTRACT

All behavior-changing experiments happen here only.

Rules:
- change one behavior variable at a time
- static-verify the diff before CI
- do not call an experiment a FIX until CI + runtime + controlled A/B validation pass
- do not repeat rejected experiments without new evidence
- never promote the whole Test branch into Release
- `main` must not be touched

## PROTECTED / DO NOT REGRESS

- Bayonetta 2 / Star Fox Zero `vkGetQueryPoolResults` direct query readback FIX
- VS `DEFAULT_VAL` synthesize/linkage FIX
- FidelityFX FSR1 EASU + RCAS
- existing Adreno / pre-e834 verified fixes
- XCX query behavior remains separate

## PRESERVED POSITIVE CANDIDATE — ARM64 COMPARE REUSE

`arm64-compare-reuse` remains separate and must not be mixed into the first R_NAME LDP A/B.

Previous controlled same-build result:
- baseline: 52.091 FPS
- compare-reuse: 52.968 FPS
- delta: +1.68%

Generated-code reduction is real, but it is still a candidate, not a FIX.

## CURRENT NEXT ACTION

P1 build and verify gates are cleared.

Next action is one controlled same-build BOTW A/B pair using the existing artifact:
1. `ARM64_RNAME_LDP_BASELINE.cmd`
2. `ARM64_RNAME_LDP_CANDIDATE.cmd`
3. same save/location/camera/weather/graphics/FPS++ settings
4. keep player/camera still
5. restart Cemu for each preset
6. collect through at least `t=260s`
7. compare established `t=70..260s` window
8. upload both PERF logs for analysis

First pass should be BASELINE then CANDIDATE. If the first pair is meaningfully positive, repeat in reverse order before treating it as repeatable.

Do not enable `arm64-compare-reuse` during this measurement. Do not start `0x02A281A0` work until this P1 experiment is validated or rejected.
