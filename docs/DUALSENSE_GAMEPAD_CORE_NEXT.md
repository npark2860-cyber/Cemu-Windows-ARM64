Status update: native DualSense USB speaker-route initialization is physically PASS/CLOSED on ARM64 at commit `638d19309f94acde70e9a0496c5a3bbe3027c25d` (CI run `35084659609` PASS). DSX is no longer required for the target USB speaker-init design.

Next action for the sound path: integrate the proven one-time Gamepad-Core speaker route/volume initialization into Cemu's DualSense connect/reconnect path, while preserving Cemu as the PCM owner. Then combine it with the BOTW semantic AX voice Duplicate proof: keep TV mix intact and add DRC/DualSense routing for already-confirmed weapon swing tracks first. Do not repeat the basic native speaker-enable experiment unless a regression appears.

Haptic/BVNIB library exploration is handled separately and must not block this speaker/audio integration path.
