BOTW DualSense Experience - UI + Sheikah Slate Haptics v2

Purpose
-------
Graphics-pack-only implementation. No Cemu source/binary modification.

Tuning
------
General UI:
- Pouch cursor: 0.40
- Equip shortcut change: 0.45
- Decide: 0.40~0.45
- Back: 0.35
- Invalid/error: PresetPiton 0.40

Sheikah Slate:
- Open: 1.00
- Close: 0.90
- Page slide: 1.00
- Home/app tool/map interactions: 0.85~0.90
- Sheikah Sensor: 0.90
- Camera shutter: 1.00
- Camera save/detect: 0.85~0.90
- Camera zoom/selfie/moveback: 0.75

Important
---------
EnhancedSoundRouter uses first-match routing.
For cues that already had an SE audio route, this pack repeats the same
mode/gain on the specific haptic rule so the existing audio routing is preserved.

Bow adaptive-trigger tension is intentionally NOT included here.
Master Cycle audio-haptics is intentionally NOT included here.


v3 spatial routing correction
-----------------------------
NPC/enemy weapon swing and footstep cues can share the same sound sources.
To preserve the game's original distance/spatial attenuation, the following
routes now use spatial_drc, matching the RemoteBomb distance-routing policy:

Weapon basic swing:
- SpearSwing
- LongSwordSwing
- SwordSwingPlayer
- SwordSwingShort
- SwordSwingFourth

Footsteps:
- PlayerFootstepMove
- PlayerFootstepJump
- PlayerFootstepLand

Gain remains 0x8000.
Charge/spin/special weapon effects are unchanged.
