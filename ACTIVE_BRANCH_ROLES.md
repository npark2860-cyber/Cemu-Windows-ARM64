# Active branch roles

This repository has exactly three active work roles.

| Role | Branch | Active workflow | Artifact |
| --- | --- | --- | --- |
| Release | `final-adreno-compat-arm64` | `.github/workflows/final-adreno-compat-arm64.yml` | `cemu-arm64-release` |
| Diagnostics | `fix/arm64-diagnostics-ui-artifact-gate` | `.github/workflows/diagnostics-arm64.yml` | `cemu-arm64-diagnostics` |
| Test | `runtime-experiments-arm64` | `.github/workflows/runtime-experiments-arm64.yml` | `cemu-arm64-test` |

All other branches/workflows are historical and must not be used for new work.

Before any write, build, or artifact handoff, verify the requested role against this table and `BRANCH_POLICY.md`.
