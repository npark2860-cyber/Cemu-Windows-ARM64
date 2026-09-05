# DEBUG HISTORY — 2026-09-05 — Bayonetta 2 target0 producer resource runtime

> Repository: `npark2860-cyber/Cemu-Windows-ARM64`  
> Handoff/docs branch: `diag-bayo2-target0-resource-identity`  
> Input: user-supplied `log (2)(1).zip` produced with Run #12 artifact  
> Scope: observation-only; no behavior workaround is inferred from this capture.

## 1. Artifact / capture validity

Run #12:

- workflow: `Cemu ARM64 Bayo2 Target Query Draw Fingerprint Trace`
- Run ID: `33939024628`
- head: `4498bfe9c80c54ea1ac4df48355f27a1bf676e95`
- conclusion: SUCCESS
- artifact ID: `9961710613`
- artifact SHA-256: `00ae9f6208ba2b592606778e980cc31e37ea7e0a25aad82a062c395bcfd1095d`

The supplied runtime log contains the required marker:

- `[BAYO2_TARGET_RESOURCE]`: 3,444 rows
- `[BAYO2_TARGET] GET`: 1,782 rows total across the five targets
- target0 completed GET generations: 573
- one final target0 producer generation (`gen=574`) has six producer-resource rows but no completed GET before capture end and is excluded from result-class comparison

Every completed target0 generation has exactly six `[BAYO2_TARGET_RESOURCE]` producer rows.

## 2. Target0 result classes in this capture

Target0:
`0x46a92ec8`

Completed generations:

- total: 573
- result ZERO: 518
- result NONZERO: 55

The producer draw span remains six draws for every completed generation.

## 3. Producer six-draw structure remains fixed

Representative recurring six-draw pipeline sequence:

1. `7e005ef7a0ebc3c5`
2. `bb71fa356a5b48ce`
3. `bb71fa356a5b48ce`
4. `000909ced0b17a78`
5. `ead20dc8febd5234`
6. `bb71fa356a5b48ce`

The same sequence exists in ZERO and NONZERO generations.

Recurring VS hashes:

- `e6fc4f385f9b0034`
- `93a12f899ed56598`

Recurring PS hashes:

- `e2b9a6e6c2a4a0f8`
- `519954498085e510`
- `902ca3422dccc182`
- `362608e302d3de4c`

## 4. Vertex resource result — ruled out as discriminator

For every one of the six producer draw positions:

- ZERO generations have exactly one VB identity
- NONZERO generations have exactly one VB identity
- the identity is the same on both result classes
- ZERO generations have exactly one VB content hash
- NONZERO generations have exactly one VB content hash
- the content hash is the same on both result classes

Representative fixed values:

- `vbCount=1`
- `vbIdentity=ac3ef01be7bb148a`
- `vbContent=32e7595ae3520075`
- first VB address `0x130b08c0`
- size `565792`
- stride `32`

Therefore:

**target0 completed ZERO/NONZERO is not explained by different guest vertex-buffer identity or the sampled vertex-buffer content captured by this trace.**

## 5. Constant-buffer result — no discriminator exists here

Across all six producer draw positions in both result classes:

- `vsCbCount=0`
- `psCbCount=0`
- `gsCbCount=0`
- CB identity/content hashes are zero

Therefore no producer constant-buffer identity/content difference exists in this path.

## 6. Remaining changing resource class — uniform-variable blocks

VS:

- both recurring VS families expose `vsVarSize=4096`
- the whole-block VS hash changes generation-to-generation
- within one generation, draws using the same VS family share the same VS hash
- for each draw position, every completed generation had a distinct VS whole-block hash in this capture
- ZERO/NONZERO whole-block VS hash sets therefore have no overlap, but this alone does not establish causality because the block also changes continuously with frame/generation

PS:

- recurring PS variable sizes are 304 or 320 bytes depending on shader
- PS hashes also change frequently
- some exact PS whole-block hashes appear in both ZERO and NONZERO classes
- therefore whole-block PS hash alone is not a sufficient result discriminator

GS:

- no active GS variable block for this producer sequence

## 7. Interpretation

Run #12 closes the producer-resource identity question as follows:

- producer draw sequence: same
- pipeline/shader/render-state fingerprint: same
- VB identity: same
- sampled VB content: same
- VS/PS/GS constant buffers: absent / same
- remaining per-generation difference visible to this instrumentation: VS/PS uniform-variable data

Do not claim that changing uniforms are already proven to be the cause. The current hashes only prove that this is the remaining observed changing input class.

## 8. Approved next observation

Next stage:
**target0 producer uniform vec4 delta trace**

Goal:

- keep the same target0 query generation correlation
- for only the two recurring VS and four recurring PS shader hashes
- suppress duplicate draws using the same shader in one generation
- compare each 16-byte vec4 slot against the previous generation for that shader
- log only changed slots, including actual float values

This keeps log volume and runtime perturbation below a full uniform dump while allowing numeric comparison at `0->NZ` and `NZ->0` transitions.

Staging branch:
`diag-bayo2-target0-uniform-delta`

Code checkpoint:
`2f5d4080082219e096bfbf593d711c69fed807ce`

New marker:
`[BAYO2_TARGET_UNIFORM]`

No behavior-changing workaround is authorized before this result.
