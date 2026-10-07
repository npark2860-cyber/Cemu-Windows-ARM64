"""Generate a bounded sequence-only probe. No game-state writes or shot inference."""
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / 'SequenceRearmValidation'

def wrapper(name, body, original, continuation=None):
    lines = [name+':', 'stwu r1, -0x30(r1)', 'stw r0, 0x08(r1)']
    for reg in range(3, 8):
        lines.append(f'stw r{reg}, 0x{12+4*(reg-3):02X}(r1)')
    lines += ['mfcr r0', 'stw r0, 0x20(r1)']
    lines += body.strip().splitlines()
    lines += ['lwz r0, 0x20(r1)', 'mtcrf 255, r0']
    for reg in range(3, 8):
        lines.append(f'lwz r{reg}, 0x{12+4*(reg-3):02X}(r1)')
    lines += ['lwz r0, 0x08(r1)', 'addi r1, r1, 0x30', original]
    if continuation is not None:
        lines.append(f'b 0x{continuation:08X}')
    return '\n'.join(lines)+'\n'

ADDRESS = 'lis r3, BowProbeState@ha\naddi r3, r3, BowProbeState@l'

def main():
    OUT.mkdir(exist_ok=True)
    rules = '''[Definition]
titleIds = 00050000101C9300,00050000101C9400,00050000101C9500
name = Bow Adaptive Trigger - Sequence re-arm validation (v208)
path = "The Legend of Zelda: Breath of the Wild/Mods/Controller/Bow Trigger Validation"
description = "VALIDATION ONLY. Reissues the known raw 0x3F04 with a new sequence every 120 Player callbacks; stops after 1201 callbacks. Not the finished bow-aware pack. Enable only one R2 raw-trigger pack."
version = 8
default = false
'''
    code = '''# VALIDATION ONLY; see ../VALIDATION.md. No bow detection is claimed.
# Exact RPX SHA256: ba58da5b95ce929e005d058ceb08b9b2788d1ab2bbc8a6c189bbadca0bb34d30
# All five overwritten words verified against the supplied original RPX.
[BotwBowSequenceProbeV208]
moduleMatches = 0x6267BFD0
.origin = codecave

# u32 offsets: 00 command,04 callbackCount,08 sequence,0C publishCount,
# 10 countdown,14 pouchLoading,18 halted,1C rebuildCount,
# 20 bowValueWriteCount,24 lastPouchItem,28 lastOldValue,2C lastNewValue,
# 30 loadCount,34 lastManager,38 lastPouchType,3C reserved.
BowProbeState:
'''
    code += '\n'.join('.uint 0' for _ in range(16))+'\n\n'
    code += 'BowProbeEntry:\n'+ADDRESS+'\nli r4, 0\n'
    code += '\n'.join(f'stw r4, 0x{i:02X}(r3)' for i in range(0,64,4))
    code += '\nli r4, 1\nstw r4, 0x14(r3)\nblr\n\n'
    code += wrapper('BowProbePlayerHook', ADDRESS+'''
lwz r4, 0x14(r3)
cmpwi r4, 0
bne BowProbePlayerDone
lwz r4, 0x18(r3)
cmpwi r4, 0
bne BowProbePlayerDone
lwz r4, 0x04(r3)
addi r4, r4, 1
stw r4, 0x04(r3)
cmpwi r4, 1201
bge BowProbeStop
lwz r4, 0x10(r3)
addi r4, r4, -1
stw r4, 0x10(r3)
cmpwi r4, 0
bgt BowProbePlayerDone
lwz r4, 0x08(r3)
addi r4, r4, 1
andi. r4, r4, 0xFFFF
stw r4, 0x08(r3)
slwi r5, r4, 16
ori r5, r5, 0x3F04
stw r5, 0x00(r3)
lwz r4, 0x0C(r3)
addi r4, r4, 1
stw r4, 0x0C(r3)
li r4, 120
stw r4, 0x10(r3)
b BowProbePlayerDone
BowProbeStop:
li r4, 0
stw r4, 0x00(r3)
li r4, 1
stw r4, 0x18(r3)
BowProbePlayerDone:
''', 'lwz r0, 0x14(r1)', 0x02d67d2c)
    code += '\n'+wrapper('BowProbeLoadBeginHook', ADDRESS+'''
li r4, 0
stw r4, 0x00(r3)
stw r4, 0x04(r3)
stw r4, 0x10(r3)
stw r4, 0x18(r3)
li r4, 1
stw r4, 0x14(r3)
lwz r4, 0x30(r3)
addi r4, r4, 1
stw r4, 0x30(r3)
lwz r4, 0x0C(r1)
stw r4, 0x34(r3)
''', 'mflr r0', 0x02eb451c)
    code += '\n'+wrapper('BowProbeLoadEndHook', ADDRESS+'''
li r4, 0
stw r4, 0x14(r3)
''', 'blr')
    code += '\n'+wrapper('BowProbeRebuildHook', ADDRESS+'''
lwz r4, 0x1C(r3)
addi r4, r4, 1
stw r4, 0x1C(r3)
''', 'lwz r0, 0x14(r1)', 0x02ebf744)
    code += '\n'+wrapper('BowProbeValueHook', ADDRESS+'''
stw r30, 0x38(r3)
cmpwi r30, 1
bne BowProbeValueDone
lwz r4, 0x20(r3)
addi r4, r4, 1
stw r4, 0x20(r3)
stw r9, 0x24(r3)
lwz r4, 0x10(r9)
stw r4, 0x28(r3)
stw r29, 0x2C(r3)
stw r28, 0x34(r3)
BowProbeValueDone:
''', 'stw r29, 0x10(r9)', 0x02eb6878)
    code += '''
.callback entry BowProbeEntry
.adaptiveTriggerRaw right BowProbeState

# Post Player callback; original 80010014 = lwz r0,0x14(r1).
0x02D67D28 = b BowProbePlayerHook
# Pouch load entry/return. These are NOT a whole-world load-complete signal.
# Original 7C0802A6 = mflr r0; original 4E800020 = blr.
0x02EB4518 = b BowProbeLoadBeginHook
0x02EB4E80 = b BowProbeLoadEndHook
# Rebuild after unlock; original 80010014 = lwz r0,0x14(r1).
0x02EBF740 = b BowProbeRebuildHook
# Under existing pouch lock, original 93A90010 = stw r29,0x10(r9).
# Only record evidence; never treat a value write as a shot.
0x02EB6874 = b BowProbeValueHook
'''
    (OUT/'rules.txt').write_text(rules, encoding='utf-8')
    (OUT/'patch_bow_sequence.asm').write_text(code, encoding='utf-8')
    print('Generated sequence probe only; not a completed bow-aware pack.')

if __name__ == '__main__':
    main()
