# NEXT ACTION — BOTW DualSense Audio After Speaker PASS

## Do not repeat the completed proof

The following are already PASS/CLOSED unless a regression appears:

- BOTW whitelisted weapon-swing AX voice reaches DualSense speaker.
- BOTW Duplicate ARM64 CI run `35078312616` succeeded.
- native DualSense USB speaker route/volume initialization works without DSX on physical hardware.
- native speaker-init CI run `35084659609` succeeded on `exp/dualsense-gamepad-core-arm64`.

Do not spend the next cycle re-proving these.

## Immediate next action

Do **not** add more exact sound names to the C++ whitelist.

Continue the sound-source semantic work first:

1. inspect the current `diag/botw-sound-source-tracer` state and its handoff/findings;
2. continue packed-resource tracer v4 (`SARC -> embedded BARS`);
3. target `TitleBG.pack::Sound/Resource/PlayerVoice.bars` specifically;
4. prove runtime provenance for `PVxxx_xx` playback;
5. correlate the runtime voice with `SLink/GameROMPlayer` semantic events/categories where the game exposes them;
6. decide the least-hardcoded production routing key from evidence.

Preferred routing identity order:

```text
semantic SLink/event/category
> resource/path/category
> exact track fallback
```

The current `Spear_Swing*` / `LSword_Swing*` whitelist remains only as a known-good physical regression proof.

## Production routing design constraint

Do not solve hardcoding merely by moving hundreds of exact names into JSON.

The production layer should look like:

```text
semantic identity / category
-> routing policy
-> destination = TV | DualSense | both
-> gain / behavior
```

A mapping file is acceptable for policy and exceptions, but event/category classification should do most of the work.

## Native speaker integration

The one-time HID route initialization is already proven separately.

After semantic routing structure is stable, integrate this behavior into the Cemu-side DualSense connect/reconnect path:

```text
DualSense USB detected
-> speaker route + nonzero volume
-> UpdateOutput()
```

No final manual `Enable speaker` button is required.

## Optional rigorous check

The user reported that the controller-local swing is so perceptually dominant that the TV swing can feel absent. The code path intentionally leaves TV mix untouched.

Only if needed for documentation, perform one simple A/B:

- same swing with DualSense speaker enabled;
- mute/disable controller speaker only;
- confirm TV swing remains.

Do not block semantic work on this check.

## Workstream boundary

The 46 TOTK BNVIB/Haptic Explorer work remains a separate tab. Do not mix it into this audio routing task.
