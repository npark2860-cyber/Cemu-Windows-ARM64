# Active branch roles

This repository currently has exactly five active source-of-truth roles.

| Role | Branch | Purpose |
| --- | --- | --- |
| [Release] | `final-adreno-compat-arm64` | Stock final ARM64/Adreno production baseline |
| [Diagnostics] | `fix/arm64-diagnostics-ui-artifact-gate` | Stock diagnostic/instrumentation line |
| [Release+SE] | `Release+SE` | Production Enhanced Sound line |
| [Diagnostics+SE] | `feat/enhanced-sound-experience-v1` | Enhanced Sound diagnostics, including CueCaptureV2 |
| [Test] | `test/se-fingerprint-index-v1` | Current SE/haptic experiment line |

## Current build identities

- [Release]: `.github/workflows/final-adreno-compat-arm64.yml` -> `cemu-arm64-release`.
- [Diagnostics]: `.github/workflows/diagnostics-arm64.yml` -> `cemu-arm64-diagnostics`.
- [Release+SE]: source of truth is `Release+SE`; `build/release-se-once` is an ephemeral build carrier only when needed.
- [Diagnostics+SE]: CueCaptureV2 workflow is `.github/workflows/enhanced-sound-cue-capture-v2-arm64.yml`; verify actual workflow/HEAD before each diagnostic build.
- [Test]: current dedicated workflow is stored at `.github/workflows/final-adreno-compat-arm64.yml` on the Test branch with display name `[Test] Cemu ARM64 SE Fingerprint Index`; current artifact identity is `cemu-arm64-test-se-fingerprint-index-v1`. This branch remains the haptic laboratory even if the workflow/artifact name is later updated for haptic testing.

## Not active source of truth

`Final+SE`, `test-haptic`, `runtime-experiments-arm64`, historical diagnostic/experiment branches, build helpers, archives, bisects, temporary branches, and `main` are not active work branches unless the user explicitly changes the policy.

Before any write/build, read `BRANCH_POLICY.md`, identify the role, and verify the actual branch HEAD.
