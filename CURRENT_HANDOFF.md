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
- artifact: `cemu-arm64-test`
- artifact ID: `10262500252`
- artifact digest: `sha256:7fb8e3f213818d4f0cc46067bd02ff6cd1fd4be37553564e9105a111f037d8fe`

Documentation commits may advance branch HEAD beyond `fc330d1...`. Always fetch the actual branch HEAD before writing.

## IMPORTANT CORRECTION — P1 SEMANTICS

Older handoff text written after the failed build incorrectly described P1 as pairing non-GPR 64-bit `R_NAME` loads such as `SPR::LR + SPR::CTR` at `+8` offsets and cited `F940...` examples.

That description is not supported by the actual P1 implementation or the pre-P1 debug history and must not be used as source of truth.

Actual `f929fa8...` implementation:
- considers only `PPCREC_IML_TYPE_R_NAME`
- requires `I64` IML destination format
- considers only names `PPCREC_NAME_R0 .. R31`
- groups a contiguous run of `R_NAME` IML instructions
- pairs guest GPR `n` with guest GPR `n+1` when each appears exactly once in the run and destinations differ
- emits one AArch64 `LDP` to two `WReg` destinations from adjacent `PPCInterpreter_t::gpr[]` uint32 fields
- leaves unpaired GPR and all non-GPR `R_NAME` lowering unchanged

## RUNTIME VERIFY — PASS

Hotspot:
- guest entry: `0x0420CB80`
- enterable post-RA segment: `ppc=0x00000000`, `enter=0x0420CB80`

Observed pairs:
- `r3 + r4`
- `r5 + r6`
- `r24 + r25`
- `r26 + r27`
- `r28 + r29`
- `r30 + r31`

Runtime diagnostic:
- `pairs=6`
- `native_bytes_saved=24`

Static/runtime acceptance for pair formation is **PASS**:
- runtime gate active
- six pair loads emitted
- native size reduction exactly 24 bytes
- unrelated non-GPR `R_NAME` entries still emit normally
- final JUMP retained
- BOTW stable-gameplay smoke passed

## FIRST CONTROLLED A/B — CLEAR POSITIVE DIRECTION

Run order:
1. BASELINE
2. CANDIDATE

Established comparison window:
- `t=70..260s`
- 20 windows per run

| metric | BASELINE | CANDIDATE | delta |
|---|---:|---:|---:|
| avg FPS | 49.66745 | 50.76435 | **+2.2085%** |
| avg frame time | 20.13760 ms | 19.70055 ms | **-2.1703%** |
| mean p99 | 22.25870 ms | 21.52095 ms | **-3.3144%** |
| mean 1% low | 45.10415 FPS | 46.49985 FPS | **+3.0944%** |
| barriers/frame | 203.99550 | 200.17105 | -1.8748% |
| renderpasses/frame | 287.09810 | 283.18290 | -1.3637% |

Supporting evidence:
- CANDIDATE FPS is higher in 19 of 20 aligned windows
- only `t=170s` is lower
- BASELINE degrades at `t=250..260s`, but trimming those late samples does not remove the win
- `t=70..240s`: approximately **+1.7869% FPS**
- `t=70..230s`: approximately **+1.7369% FPS**

Interpretation:
- first independent A/B is meaningfully positive
- code-size reduction was already independently verified
- P1 is preserved as a **positive candidate**
- P1 is **not yet a FIX** because only BASELINE->CANDIDATE order has been measured
- one reverse-order confirmation is required before any promotion/combination decision

## TEST CONTRACT

All behavior-changing experiments happen here only.

Rules:
- change one behavior variable at a time
- static-verify the diff before CI
- do not call an experiment a FIX until CI + runtime + controlled repeat validation pass
- do not repeat rejected experiments without new evidence
- never promote the whole Test branch into Release
- `main` must not be touched

## PROTECTED / DO NOT REGRESS

- Bayonetta 2 / Star Fox Zero `vkGetQueryPoolResults` direct query readback FIX
- VS `DEFAULT_VAL` synthesize/linkage FIX
- FidelityFX FSR1 EASU + RCAS
- existing Adreno / pre-e834 verified fixes
- XCX query behavior remains separate

## PRESERVED SEPARATE CANDIDATE — ARM64 COMPARE REUSE

`arm64-compare-reuse` remains separate and must not be mixed into the P1 confirmation.

Previous controlled same-build result:
- baseline: 52.091 FPS
- compare-reuse: 52.968 FPS
- delta: +1.68%

Generated-code reduction is real, but it is still a candidate, not a FIX.

## CURRENT NEXT ACTION

Do **not** build new code.

Use the same validated artifact for a reverse-order confirmation:
1. `ARM64_RNAME_LDP_CANDIDATE.cmd`
2. close Cemu
3. `ARM64_RNAME_LDP_BASELINE.cmd`
4. same save/location/camera/weather/graphics/FPS++ settings
5. stationary player/camera
6. restart Cemu for each preset
7. collect through at least `t=260s`
8. compare `t=70..260s`

If the reverse pair is positive again with correctness intact, classify P1 as a repeatable positive candidate and reprofile before promotion consideration.

Do not enable `arm64-compare-reuse` during this confirmation. Do not start `0x02A281A0` work until P1 is resolved.
