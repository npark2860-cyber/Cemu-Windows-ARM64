"""Generate v208-only adaptive trigger pack. Does not modify Cemu or the RPX."""
from pathlib import Path
import csv

ROOT = Path(__file__).parent
OUT = ROOT/'BowAdaptiveTriggerV208'
# All addresses/words are checked against the supplied RPX by test_bow_pack.py.
HOOKS = [
    (0x02D67D28, 0x80010014, 'BowTick', 'lwz r0, 0x14(r1)', 0x02D67D2C),
    (0x02EB4518, 0x7C0802A6, 'BowLoadBegin', 'mflr r0', 0x02EB451C),
    (0x02EB4E80, 0x4E800020, 'BowLoadEnd', 'blr', None),
    (0x0252826C, 0x83A1001C, 'BowReleaseA', 'lwz r29, 0x1C(r1)', 0x02528270),
    (0x0252852C, 0x83A1001C, 'BowReleaseB', 'lwz r29, 0x1C(r1)', 0x02528530),
    (0x02528684, 0x8001006C, 'BowReleaseC', 'lwz r0, 0x6C(r1)', 0x02528688),
    (0x024A29C4, 0x3C601047, 'BowLifeSync', 'lis r3, 0x1047', 0x024A29C8),
    (0x0378A374, 0x7C0802A6, 'BowDelete', 'mflr r0', 0x0378A378),
    (0x02D6F0CC, 0x7C0802A6, 'BowDetach', 'mflr r0', 0x02D6F0D0),
]

def ptr(reg, fail):
    # Guest mapped data range; this is a range guard, not a lifetime guarantee.
    return f'''lis r11, 0x1000
cmplw r{reg}, r11
blt {fail}
lis r11, -0x2000
cmplw r{reg}, r11
bge {fail}
andi. r11, r{reg}, 3
bne {fail}
'''

def wrapper(name, body, original, continuation):
    lines=[name+':', 'stwu r1, -0x60(r1)', 'stw r0, 0x08(r1)']
    for r in range(3,13): lines.append(f'stw r{r}, 0x{12+(r-3)*4:X}(r1)')
    for op,off in [('mfcr',0x38),('mflr',0x3c),('mfctr',0x40)]:
        lines += [f'{op} r0',f'stw r0, 0x{off:X}(r1)']
    lines += ['lis r12, BowState@ha','addi r12, r12, BowState@l',
              'addi r11, r12, 0x7C',name+'Lock:', 'lwarx r10, 0, r11',
              'cmpwi r10, 0','bne '+name+'Lock','li r10, 1',
              'stwcx. r10, 0, r11','bne '+name+'Lock','isync']
    lines += body.strip().splitlines()
    lines += [name+'Done:', '.uint 0x7C0004AC','li r10, 0','stw r10, 0x7C(r12)']
    for op,off in [('mtctr',0x40),('mtlr',0x3c)]:
        lines += [f'lwz r0, 0x{off:X}(r1)',f'{op} r0']
    lines += ['lwz r0, 0x38(r1)','mtcrf 255, r0']
    for r in range(3,13): lines.append(f'lwz r{r}, 0x{12+(r-3)*4:X}(r1)')
    lines += ['lwz r0, 0x08(r1)','addi r1, r1, 0x60',original]
    if continuation is not None: lines.append(f'b 0x{continuation:08X}')
    return '\n'.join(lines)+'\n'

def main():
    OUT.mkdir(exist_ok=True)
    rows=list(csv.DictReader((ROOT/'bow_db.csv').open(encoding='utf-8')))
    db={int(r['bow_id'][-3:]):(int(r['normalized_tension']),int(r['proposed_raw16'],0)) for r in rows}
    assert len(db)==26
    for tension, raw in db.values():
        q=max(1,min(8,1+(7*tension+50)//100))
        assert raw==(((q-1)|((q-1)<<3))<<8)|4
    (OUT/'bow_db.csv').write_bytes((ROOT/'bow_db.csv').read_bytes())
    out=['''# Wii U BOTW v208 ONLY. See README.md and HOOKS.md.
# No R2 polling, periodic re-arm, arrow attack, or Cemu modifications.
[BotwBowAdaptiveTriggerV208]
moduleMatches = 0x6267BFD0
.origin = codecave
BowState:
''', '\n'.join('.uint 0' for _ in range(32)), '''
BowTable:
''', '\n'.join(f'.uint 0x{((db.get(i,(0,0))[0]<<16)|db.get(i,(0,0))[1]):08X}' for i in range(73)), '''
BowEntry:
lis r3, BowState@ha
addi r3, r3, BowState@l
li r4, 0
''', '\n'.join(f'stw r4, 0x{i:X}(r3)' for i in range(0,128,4)), '''
li r4, 1
stw r4, 0x08(r3)
blr

# Helpers run only while the private GP lock is held. No game/OS calls.
# Off clears observation, not the Bow-ID tension cache.
BowOff:
lwz r4, 0x00(r12)
cmpwi r4, 0
beq BowOffClear
lwz r4, 0x48(r12)
addi r4, r4, 1
stw r4, 0x48(r12)
BowOffClear:
li r4, 0
stw r4, 0x00(r12)
stw r4, 0x18(r12)
stw r4, 0x1C(r12)
stw r4, 0x2C(r12)
lwz r4, 0x70(r12)
stw r4, 0x74(r12)
blr

BowPublish:
lwz r4, 0x24(r12)
cmpwi r4, 0
beqlr
lwz r5, 0x04(r12)
addi r5, r5, 1
andi. r5, r5, 0xFFFF
stw r5, 0x04(r12)
slwi r5, r5, 16
or r4, r4, r5
stw r4, 0x00(r12)
lwz r4, 0x38(r12)
addi r4, r4, 1
stw r4, 0x38(r12)
blr
''']
    tick='''lwz r4, 0x34(r12)
addi r4, r4, 1
stw r4, 0x34(r12)
lwz r4, 0x08(r12)
cmpwi r4, 0
bne BowTickOff
mr r3, r31
'''+ptr(3,'BowTickOff')+'''
lbz r4, 0x54(r3)
cmpwi r4, 1
bne BowTickOff
lwz r4, 0x64(r3)
andi. r4, r4, 1
bne BowTickOff
lwz r4, 0xE8(r3)
'''+ptr(4,'BowTickOff')+'''
# Reject a different Player layout: vtable+314 must be the verified getter.
lwz r4, 0x314(r4)
lis r5, 0x02D8
addi r5, r5, -0x6650
cmplw r4, r5
bne BowTickOff
lwz r5, 0x50(r3)
lwz r4, 0x5C(r12)
cmplw r3, r4
bne BowTickPlayerIdentity
lwz r4, 0x68(r12)
cmplw r4, r5
beq BowTickOff
BowTickPlayerIdentity:
lwz r4, 0x10(r12)
cmplw r3, r4
bne BowTickNewPlayer
lwz r4, 0x14(r12)
cmplw r4, r5
beq BowTickHandle
BowTickNewPlayer:
bl BowOff
stw r3, 0x10(r12)
stw r5, 0x14(r12)
lwz r4, 0x0C(r12)
addi r4, r4, 1
stw r4, 0x0C(r12)
li r4, 0
stw r4, 0x54(r12)
stw r4, 0x58(r12)
BowTickHandle:
# Player+7CC is EquipMgr; bow slot 2 is a 16-byte ProcLink at +7EC.
lwz r6, 0x7EC(r3)
lwz r7, 0x7F0(r3)
cmpwi r7, -1
beq BowTickOff
'''+ptr(6,'BowTickOff')+'''
lwz r4, 0x3C(r6)
cmplw r4, r7
bne BowTickOff
lwz r8, 0x40(r6)
'''+ptr(8,'BowTickOff')+'''
lbz r4, 0x54(r8)
cmpwi r4, 1
bne BowTickOff
lwz r4, 0x64(r8)
andi. r4, r4, 1
bne BowTickOff
lwz r4, 0x50(r8)
cmplw r4, r7
bne BowTickOff
# Recheck the link generation after reading the resolved object.
lwz r4, 0x3C(r6)
cmplw r4, r7
bne BowTickOff
lwz r4, 0x7F0(r3)
cmplw r4, r7
bne BowTickOff
lwz r4, 0x54(r12)
cmplw r4, r8
bne BowTickIdentity
lwz r4, 0x58(r12)
cmplw r4, r7
beq BowTickOff
BowTickIdentity:
lwz r4, 0x18(r12)
cmplw r4, r8
bne BowTickNewBow
lwz r4, 0x1C(r12)
cmplw r4, r7
bne BowTickNewBow
# Stable instance: no name parsing or DB access. Consume releases once/tick.
lwz r4, 0x70(r12)
lwz r5, 0x74(r12)
cmplw r4, r5
beq BowTickDone
stw r4, 0x74(r12)
li r4, 3
stw r4, 0x50(r12)
bl BowPublish
b BowTickDone
BowTickNewBow:
lwz r6, 0x04(r8)
'''
    # A char buffer need not be aligned. Validate range without alignment.
    tick+='''lis r11, 0x1000
cmplw r6, r11
blt BowTickOff
lis r11, -0x2000
addi r11, r11, -16
cmplw r6, r11
bge BowTickOff
'''
    for i,c in enumerate(b'Weapon_Bow_'):
        tick+=f'lbz r4, {i}(r6)\ncmpwi r4, {c}\nbne BowTickOff\n'
    tick+='li r9, 0\n'
    for i in range(11,14):
        tick+=f'lbz r4, {i}(r6)\naddi r4, r4, -48\ncmplwi r4, 9\nbgt BowTickOff\nmulli r9, r9, 10\nadd r9, r9, r4\n'
    tick+='''lbz r4, 14(r6)
cmpwi r4, 0
bne BowTickOff
cmplwi r9, 72
bgt BowTickOff
cmpwi r9, 0
beq BowTickOff
lwz r4, 0x20(r12)
cmplw r4, r9
bne BowTickDB
lwz r4, 0x44(r12)
addi r4, r4, 1
stw r4, 0x44(r12)
b BowTickCacheReady
BowTickDB:
lis r4, BowTable@ha
addi r4, r4, BowTable@l
slwi r5, r9, 2
lwzx r4, r4, r5
srwi r5, r4, 16
stw r5, 0x6C(r12)
andi. r4, r4, 0xFFFF
stw r4, 0x24(r12)
stw r9, 0x20(r12)
lwz r4, 0x40(r12)
addi r4, r4, 1
stw r4, 0x40(r12)
BowTickCacheReady:
stw r8, 0x18(r12)
stw r7, 0x1C(r12)
li r4, 0
stw r4, 0x2C(r12)
lwz r4, 0x70(r12)
stw r4, 0x74(r12)
lwz r4, 0x30(r12)
addi r4, r4, 1
stw r4, 0x30(r12)
li r4, 2
stw r4, 0x50(r12)
lwz r4, 0x24(r12)
cmpwi r4, 0
bne BowTickArm
li r4, 0
stw r4, 0x00(r12)
b BowTickDone
BowTickArm:
bl BowPublish
b BowTickDone
BowTickOff:
li r4, 1
stw r4, 0x50(r12)
bl BowOff
'''
    bodies={'BowTick':tick,
      'BowLoadBegin':'''bl BowOff
li r4, 1
stw r4, 0x08(r12)
lwz r4, 0x0C(r12)
addi r4, r4, 1
stw r4, 0x0C(r12)
lwz r4, 0x4C(r12)
addi r4, r4, 1
stw r4, 0x4C(r12)
li r4, 0
stw r4, 0x10(r12)
stw r4, 0x14(r12)
stw r4, 0x54(r12)
stw r4, 0x58(r12)
stw r4, 0x5C(r12)
stw r4, 0x68(r12)
''',
      'BowLoadEnd':'''li r4, 0
stw r4, 0x08(r12)
'''}
    for name,reg in [('BowReleaseA',29),('BowReleaseB',29),('BowReleaseC',30)]:
        bodies[name]=f'''lwz r3, 0(r{reg})
lwz r4, 0x18(r12)
cmpwi r4, 0
beq {name}Done
cmplw r3, r4
bne {name}Reject
lwz r4, 0x1C(r12)
lwz r5, 0x50(r3)
cmplw r4, r5
bne {name}Reject
lwz r4, 0x08(r12)
cmpwi r4, 0
bne {name}Reject
lwz r4, 0x70(r12)
addi r4, r4, 1
stw r4, 0x70(r12)
lwz r4, 0x3C(r12)
addi r4, r4, 1
stw r4, 0x3C(r12)
b {name}Done
{name}Reject:
lwz r4, 0x64(r12)
addi r4, r4, 1
stw r4, 0x64(r12)
'''
    bodies['BowLifeSync']='''cmpwi r31, 1
bne BowLifeSyncDone
lwz r4, 0x18(r12)
cmplw r4, r30
bne BowLifeSyncDone
lwz r4, 0x1C(r12)
lwz r5, 0x50(r30)
cmplw r4, r5
bne BowLifeSyncDone
lwz r4, 0x10(r1)
stw r4, 0x28(r12)
li r6, 1
stw r6, 0x2C(r12)
lwz r6, 0x60(r12)
addi r6, r6, 1
stw r6, 0x60(r12)
cmpwi r4, 0
bgt BowLifeSyncDone
stw r30, 0x54(r12)
stw r5, 0x58(r12)
bl BowOff
'''
    bodies['BowDelete']='''lwz r3, 0x0C(r1)
lwz r4, 0x10(r12)
cmplw r3, r4
bne BowDeleteCheckBow
stw r3, 0x5C(r12)
lwz r4, 0x50(r3)
stw r4, 0x68(r12)
bl BowOff
li r4, 0
stw r4, 0x10(r12)
stw r4, 0x14(r12)
lwz r4, 0x0C(r12)
addi r4, r4, 1
stw r4, 0x0C(r12)
b BowDeleteDone
BowDeleteCheckBow:
lwz r4, 0x18(r12)
cmpwi r4, 0
beq BowDeleteDone
cmplw r3, r4
bne BowDeleteDone
stw r3, 0x54(r12)
lwz r4, 0x50(r3)
stw r4, 0x58(r12)
bl BowOff
'''
    bodies['BowDetach']='''lwz r4, 0x10(r1)
cmpwi r4, 2
bne BowDetachDone
lwz r3, 0x0C(r1)
lwz r4, 0x10(r12)
cmplw r3, r4
bne BowDetachDone
bl BowOff
'''
    for addr,word,name,original,cont in HOOKS:
        out.append(wrapper(name,bodies[name],original,cont))
    out+=['.callback entry BowEntry\n.adaptiveTriggerRaw right BowState\n']
    out += [f'# Original {word:08X}: {original}\n0x{addr:08X} = b {name}\n' for addr,word,name,original,cont in HOOKS]
    (OUT/'patch_bow.asm').write_text('\n'.join(out),encoding='utf-8')
    (OUT/'rules.txt').write_text('''[Definition]
titleIds = 00050000101C9300,00050000101C9400,00050000101C9500
name = BOTW Bow Adaptive Trigger v208 - event driven RC1
path = "The Legend of Zelda: Breath of the Wild/Mods/Controller/Bow Adaptive Trigger"
description = "Bow-ID tension cache and release-event re-arm. Wii U v208 only. Disable all other raw R2 packs. RC1: gameplay event coverage still requires hardware validation."
version = 8
default = false
''',encoding='utf-8')
    print('Generated BowAdaptiveTriggerV208 RC1; hardware gameplay acceptance is still required.')

if __name__=='__main__': main()
