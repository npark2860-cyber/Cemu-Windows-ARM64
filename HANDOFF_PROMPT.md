# HANDOFF PROMPT — Cemu ARM64 / BOTW DualSense Audio

Continue the BOTW DualSense audio-routing work from GitHub source of truth.

Repository:
`npark2860-cyber/Cemu-Windows-ARM64`

Active branch:
`diag/botw-dualsense-speaker-duplicate`

At the start of the new chat/tab:

1. read `CURRENT_HANDOFF.md`
2. read `NEXT_ACTION.md`
3. read `docs/BOTW_DUALSENSE_SPEAKER_DUPLICATE.md`
4. query the actual branch HEAD and compare it with the handoff snapshot
5. check existing workflow run `35078312616` / job `104735889958` before starting any new CI

Do not touch `main`.

Do not re-run or re-investigate items already marked CLOSED unless there is an actual regression.

Current task is **not** haptics. The 46 TOTK BNVIB test UI/Haptic Explorer is being developed in another tab.

Current task is the first narrow audio proof:

```text
resolved BOTW weapon swing
-> preserve TV mix
-> add DRC0 duplicate mix
-> Cemu GamePad PCM
-> DualSense USB speaker
```

Implementation is in:
- `tools/botw_speaker_duplicate_patch.py`
- `.github/workflows/botw-dualsense-speaker-duplicate-arm64.yml`

The routing whitelist is intentionally narrow and must remain limited to already runtime-confirmed pure swing cues until physical validation passes.

If CI succeeds, proceed directly to the physical Duplicate-mode test described in `NEXT_ACTION.md`. If it fails, inspect the first real compiler/patch diagnostic and make the smallest correction only.

After physical PASS, continue with packed `PlayerVoice.bars` discovery (`SARC -> embedded BARS`) and semantic Link-local audio routing.
