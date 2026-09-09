# DEBUG HISTORY — Adreno driver Vulkan query normalization

Date: 2026-09-09

## New runtime baseline

After an Adreno driver update, the previously reproduced Vulkan problems are reported resolved on the current driver baseline.

Affected historical title-specific workarounds/experiments:
- Bayonetta 2 direct query readback
- Star Fox Zero direct query readback
- XCX direct query readback experiment
- XCX forced zero-to-one occlusion visibility experiment

## Decision

These are no longer active compatibility fixes.

Release and Diagnostics are returned to the normal upstream Cemu occlusion-query behavior:

`vkCmdCopyQueryPoolResults` -> mapped query-result buffer -> normal accumulated result

No title-specific `vkGetQueryPoolResults` selection or forced query-result override is retained for Bayonetta 2, Star Fox Zero, or XCX.

Diagnostics may still observe the generic GX2/Vulkan query lifecycle and result values, but diagnostics must not alter which value is consumed.

## Historical status

Older DEBUG_HISTORY entries documenting the former Adreno driver failure remain valid historical records for the driver/runtime state in which they were captured. They are not current implementation requirements and must not be used to reintroduce the old workarounds without a newly reproduced regression on the current driver.

## Protected unrelated fixes

This normalization does not remove or reopen:
- VS DEFAULT_VAL synthesize/linkage compatibility fix
- FidelityFX FSR1 EASU + RCAS
- verified pre-e834 / other Adreno compatibility behavior unrelated to the retired query workaround

`main` remains untouched.
