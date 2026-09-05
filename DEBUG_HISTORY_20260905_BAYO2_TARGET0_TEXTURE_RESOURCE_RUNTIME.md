# DEBUG HISTORY — 2026-09-05 — Bayo2 target0 sampled texture resource runtime

## Scope

Observation-only runtime analysis of Run #16 / commit `552b8d4b500bdd959b6b3b4bb5eb2fcba157b4b6` for Bayonetta 2 JP target0 CPU occlusion query `0x46a92ec8`.

Input capture: `log (2)(2).zip`.

Do not reinterpret the 4 KiB guest-memory hashes as full GPU texture-content hashes.

## Capture validity

- `[BAYO2_TARGET_TEXTURE]`: 15,599 rows
- texture generations observed: 821
- exactly 19 texture rows per generation
- completed target0 GET generations: 820
- final gen 821 incomplete and excluded
- completed ZERO: 767
- completed NONZERO: 53
- transitions: FIRST 1, `0->0` 717, `0->NZ` 49, `NZ->0` 49, `NZ->NZ` 4
- NONZERO episodes: 49 total; 46 single-generation, 2 two-generation, 1 three-generation

## Exact sampled-texture resource result

Across all 820 completed generations, the complete logged texture signature has **exactly one unique value**.

The signature includes, for every recurring producer shader and every referenced texture unit:

- shader/stage and referenced unit set
- all seven guest texture resource words
- raw guest image and mip addresses
- 4 KiB guest-memory prefix hashes when the helper can read the address
- sampler assignment
- depth-compare flag

Therefore the logged resource/register identity and readable 4 KiB prefixes do not distinguish ZERO from NONZERO.

Recurring shader texture-unit sets are fixed:

- VS `e6fc4f385f9b0034`: no textures
- VS `93a12f899ed56598`: no textures
- PS `e2b9a6e6c2a4a0f8`: units 0,2,3,11
- PS `519954498085e510`: units 0,1,2,11
- PS `902ca3422dccc182`: units 0,2,3,11
- PS `362608e302d3de4c`: units 0,1,2,3,11

## Critical unresolved unit 11

All four recurring PS shaders sample unit 11 with `depthCompare=1`.

The resource identity is constant:

- `word0=1ff87f21`
- `word1=440007ff`
- `word2=00f57c80`
- `word3=00f57c80`
- `word4=00008000`
- `word5=00000000`
- `word6=800000f0`
- image/mip raw address `0xf57c8000`

The logged `image4kHash`/`mip4kHash` is always zero **because the existing guest-memory hash helper intentionally returns 0 for addresses >= `0x50000000`**. It is not evidence that the texture contains zeros or remains unchanged.

The same capture independently shows:

- `[TEXTURE_LIFECYCLE] CREATE addr=f57c8000 ... size=1024x2048x1 ... format=0x11 ... isDepth=1`
- `[TEXTURE_VIEW] CREATE ... addr=f57c8000`
- repeated `[TEXTURE_CACHE] ... stage=1 unit=11 addr=f57c8000 ... format=0x11`
- `[ATTACHMENT_USE] ... kind=depth ... addr=f57c8000 ... format=0x11 ... stencil=1`
- delete-time texture state reports `gpuUpdated=1`

Thus `0xf57c8000` is a GPU-updated depth texture that is both used as a depth attachment and sampled with depth compare by every target0 producer PS family.

## Conclusion

The broad sampled-texture register/address layer is closed:

**ZERO/NONZERO is not explained by different sampled-texture unit selection, resource words, guest image/mip identity, sampler assignment, or readable 4 KiB guest-prefix content.**

However, the GPU-produced depth-compare texture `0xf57c8000` remains a real observation gap. Its GPU content was not read by Run #16, and the zero guest hash is only a helper-range sentinel.

Do not jump directly to occlusion-query backend semantics until the already-bound `0xf57c8000` texture object's write/update history is correlated to target0 results.

## Next experiment

Observation-only PS unit11 depth-compare texture history trace:

- marker `[BAYO2_TARGET_DEPTHCOMPARE]`
- once per target0 generation
- use the already-bound PS unit11 texture view; no lookup/creation
- record physical identity, isDepth/stencil/format/tile/swizzle/view
- record `isUpdatedOnGPU`, readback flag, dynamic reload flag
- record `lastWriteEventCounter`, `lastUpdateEventCounter`, update/data-update frame counters, reload count, last access frame, last unflushed RT draw and `texDataHash2`
- no GPU readback
- no texture mutation
- no query/render behavior change

If that history also fails to distinguish ZERO/NONZERO, the case for a Vulkan/driver visibility-query or GPU synchronization semantic issue becomes substantially stronger.
