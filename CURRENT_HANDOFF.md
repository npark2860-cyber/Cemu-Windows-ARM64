# CURRENT HANDOFF — [Release+SE]

Canonical policy:
- `BRANCH_POLICY.md`
- `ACTIVE_BRANCH_ROLES.md`

GitHub is the only source of truth. Fetch the actual branch HEAD before every write/build.

## Role

Branch:
`Release+SE`

Purpose:
- production Enhanced Sound line
- verified SE features only
- promotion target for runtime-verified SE/haptic changes

Do not confuse this branch with stock `final-adreno-compat-arm64`.

## Current implementation baseline

Implementation HEAD before policy-document-only commits:
`f2a5ad15b191d30eb2c870db7626518628cd90a2`

That commit promoted the indexed Enhanced Sound fingerprint lookup.

The later branch-policy commits are documentation-only. Fetch the actual current HEAD from GitHub before work.

## Fingerprint optimization

`BotWSoundFingerprintCatalog::FindMatches()` no longer scans the entire bounded fingerprint catalog for every lookup.

The promoted implementation:
- keeps `s_entries` as source of truth;
- uses a lookup-only `unordered_map` keyed by `(hashA, hashB)`;
- preserves expectedPath filtering;
- preserves duplicate path+track suppression;
- preserves multiple-candidate/ambiguity behavior;
- preserves catalog eviction semantics.

Test validation source:
- branch `test/se-fingerprint-index-v1`
- validated test implementation/build HEAD `9263604feff7d92cbe517cd75246ac97d15d853d`
- run `35425264365` SUCCESS

## DualSense SE

Keep the current USB DualSense headset detection/auto-routing behavior.

The temporary TV `g_tvAudio->Play()` workaround was reverted after the user determined the TV output was already normal. Do not reintroduce it without new evidence.

## Promotion rule

New haptic behavior must be developed on:
`test/se-fingerprint-index-v1`

Do not add new haptic experiments directly here.

Promote to Release+SE only after user runtime validation and explicit approval.

## Build note

`build/release-se-once` is a build carrier only, never source of truth.

Before any build:
- verify Release+SE HEAD;
- check active/queued once;
- start one build only;
- preserve CPU/Vulkan behavior.
