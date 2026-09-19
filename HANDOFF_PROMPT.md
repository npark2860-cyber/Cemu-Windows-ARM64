# HANDOFF_PROMPT

Continue the Cemu Windows ARM64 Enhanced Sound / DualSense project.

Repository:
`npark2860-cyber/Cemu-Windows-ARM64`

Active Test branch:
`test/se-fingerprint-index-v1`

GitHub is the only source of truth. Do not create a new branch.

The current Test target is a clean binary composed of:
- Release+SE
- BNVIB haptics
- raw adaptive-trigger transport only

The Cemu binary must not contain BOTW-specific addresses, bow IDs/tables, attack-to-tension formulas, aiming/firing/reload logic, or R2 polling.

Raw trigger protocol:
- GraphicPack declares `.adaptiveTriggerRaw right|left <commandSymbol>`
- command 0 = off
- bits 0..7 = raw SetBow22 StartZone byte
- bits 8..15 = raw SetBow22 SnapBack/force byte
- bits 16..31 = GraphicPack-owned event sequence
- Cemu ignores the sequence except that a changed 32-bit command causes a fresh output.

After this binary is built, all BOTW bow work is GraphicPack-only.
