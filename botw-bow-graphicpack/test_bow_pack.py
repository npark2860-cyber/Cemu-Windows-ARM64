"""Execute RC1's actual PPC, with synthetic guest objects; no Cemu build/run."""
from pathlib import Path
import struct
import csv
from test_rearm_pack import assemble, load, module_crc, Uc, UC_ARCH_PPC, UC_MODE_PPC32, UC_MODE_BIG_ENDIAN, P, REGS, SPR, BASE, ROOT
from generate_bow_pack import HOOKS

def main():
    raw, sections=load(ROOT.parent/'U-King.rpx')
    assert module_crc(raw,sections)==0x6267BFD0
    def original(a):
        s=next(s for s in sections if s['addr']<=a<s['addr']+s['size'])
        return struct.unpack_from('>I',s['payload'],a-s['addr'])[0]
    for a,w,*_ in HOOKS: assert original(a)==w,(hex(a),hex(original(a)))
    for a,w in {0x02d799b0:0x386307cc,0x02d799b4:0x4e800020,
                0x101e6310:0x02d799b0,0x02d8d0e4:0x38600002,
                0x0378d93c:0x801e0050,0x0378d940:0x901f003c,
                0x0378d938:0x93df0040,0x02528268:0x4bffe5a5,
                0x02528528:0x4bffe2e5,0x02528680:0x4bffe18d}.items():
        assert original(a)==w,hex(a)
    labels, words=assemble(ROOT/'BowAdaptiveTriggerV208/patch_bow.asm')
    u=Uc(UC_ARCH_PPC,UC_MODE_PPC32|UC_MODE_BIG_ENDIAN)
    u.mem_map(BASE,0x10000)
    u.mem_map(0x02000000,0x02000000)
    u.mem_map(0x10000000,0x200000)
    for a,w in words:u.mem_write(a,w)
    state=labels['BowState']
    def w(a,v):u.mem_write(a,struct.pack('>I',v&0xffffffff))
    def r(a):return struct.unpack('>I',u.mem_read(a,4))[0]
    def get(o):return r(state+o)
    def put(o,v):w(state+o,v)
    player,link,bow,bow2,vt,name,comp=0x10010000,0x10020000,0x10030000,0x10040000,0x10050000,0x10060001,0x10070000
    sp=0x10180000
    def hook(a,changes=None):
        _,_,label,ins,end=next(x for x in HOOKS if x[0]==a)
        for i,reg in enumerate(REGS):u.reg_write(reg,0x98700000+17*i)
        u.reg_write(REGS[1],sp)
        u.reg_write(REGS[31],player)
        for reg,val in zip(SPR,[0x02000000,0xa55a1234,0x12345678,0xe0000000]):u.reg_write(reg,val)
        w(sp+0x14,0xcafebabe);w(sp+0x1c,0x13579bdf);w(sp+0x6c,0x2468ace0)
        for reg,val in (changes or {}).items():u.reg_write(REGS[reg],val)
        before=[u.reg_read(reg) for reg in REGS+SPR]
        expected=before[:]
        if ins=='lwz r0, 0x14(r1)':expected[0]=0xcafebabe
        elif ins=='lwz r0, 0x6C(r1)':expected[0]=0x2468ace0
        elif ins=='lwz r29, 0x1C(r1)':expected[29]=0x13579bdf
        elif ins=='mflr r0':expected[0]=0x02000000
        elif ins=='lis r3, 0x1047':expected[3]=0x10470000
        end=end or 0x02000000
        u.emu_start(a,end,count=20000)
        assert u.reg_read(P.UC_PPC_REG_PC)==end,(label,'did not finish')
        after=[u.reg_read(reg) for reg in REGS+SPR]
        assert expected==after,(label,[(i,a,b) for i,(a,b) in enumerate(zip(expected,after)) if a!=b])
        assert get(0x7c)==0,'lock leak'
    tick=lambda:hook(0x02d67d28)
    def equip(actor=bow,ident=11,bowid=1):
        w(player+0xe8,vt);w(vt+0x314,0x02d799b0)
        w(player+0x50,1);u.mem_write(player+0x54,b'\x01');w(player+0x64,0)
        w(player+0x7ec,link);w(player+0x7f0,ident)
        w(link+0x3c,ident);w(link+0x40,actor)
        w(actor+0x50,ident);u.mem_write(actor+0x54,b'\x01');w(actor+0x64,0)
        w(actor+4,name);u.mem_write(name,f'Weapon_Bow_{bowid:03d}\0'.encode())
        w(comp,actor)
    def release(a=0x0252826c):hook(a,{29:comp,30:comp})
    def life(value,typ=1):hook(0x024a29c4,{30:bow,31:typ,4:value})
    u.reg_write(REGS[1],sp);u.reg_write(P.UC_PPC_REG_LR,0x02000000)
    u.emu_start(labels['BowEntry'],0x02000000,count=1000)
    equip();tick();assert get(0)==0,'entry must not imply load complete'
    hook(0x02eb4518,{3:0x10080000});hook(0x02eb4e80)
    tick();assert get(0)==0x00011b04 and get(0x40)==1
    for _ in range(200):tick()
    assert get(4)==1 and get(0x40)==1,'no periodic publish or repeated lookup'
    life(80);life(79);tick();assert get(4)==1,'durability loss is not a release'
    life(0,2);tick();assert get(4)==1,'arrows must not affect tension/off'
    for a in (0x0252826c,0x0252852c,0x02528684):
        before=get(4);release(a);tick();assert get(4)==before+1
        assert get(0)&0xffff==0x1b04
    release();release();before=get(4);tick();assert get(4)==before+1,'same tick release coalescing'
    before=get(4);lookups=get(0x40);releases=get(0x3c)
    equip(bow2,12,1);tick()
    assert get(4)==before+1 and get(0x40)==lookups and get(0x44)==1
    assert get(0x3c)==releases and get(0x2c)==0,'instance swap must reset baseline without shot'
    w(comp,bow);release();tick();assert get(0x3c)==releases,'old actor release rejected'
    equip(bow2,13,33);tick();assert get(0)&0xffff==0x3604,'same pointer new generation'
    assert get(0x40)==lookups+1
    equip(bow,14,2);tick();release();life(0);tick()
    assert get(0)==0,'break/off must beat pending release'
    tick();assert get(0)==0,'broken instance must remain blocked'
    equip(bow,15,2);tick();assert get(0)&0xffff==0x2404,'new generation may arm'
    put(4,0xffff);release();tick();assert get(0)==0x2404,'sequence wrap retains raw'
    w(player+0x7f0,0xffffffff);tick();assert get(0)==0,'unequip off'
    equip(bow,16,2);tick();hook(0x02d6f0cc,{3:player,4:2});assert get(0)==0
    tick();hook(0x0378a374,{3:bow});tick();assert get(0)==0,'delete bow blocks stale handle'
    equip(bow2,17,3);tick();hook(0x02eb4518,{3:0x10080000});assert get(0)==0
    release();tick();assert get(0)==0,'no arm during load'
    hook(0x02eb4e80);tick();assert get(0)&0xffff==0x1b04
    hook(0x0378a374,{3:player});assert get(0)==0,'player destruction off'
    tick();assert get(0)==0,'a late callback on the deleted player must remain off'
    hook(0x02eb4518,{3:0x10080000});hook(0x02eb4e80)
    for bowid in (0,5,999):
        equip(bow,100+bowid,bowid);tick();assert get(0)==0,'unknown ID fail closed'
    equip(bow,30,1);u.mem_write(name,b'Weapon_Bow_001_extra\0');tick();assert get(0)==0
    equip(bow,31,1);w(link+0x3c,32);tick();assert get(0)==0,'torn handle generation'
    equip(bow,33,1);w(vt+0x314,0xdeadbeef);tick();assert get(0)==0,'layout guard'
    for row in csv.DictReader((ROOT/'bow_db.csv').open()):
        bowid=int(row['bow_id'][-3:]);equip(bow,1000+bowid,bowid);tick()
        assert get(0)&0xffff==int(row['proposed_raw16'],0)
        assert get(0x6c)==int(row['normalized_tension'])
    print('PASS: all 9 hook words, getter/handle cross-checks, actual generated PPC assembly')
    print('PASS: GPR/LR/CR/CTR/XER preservation and private-lock release on all exercised hooks')
    print('PASS: initial load, stable cache, 26 DB rows, same-ID instance swap, pointer reuse, release coalescing')
    print('PASS: durability is not SHOT, arrow exclusion, break priority, detach/delete/load off, sequence wrap')
    print('NOT TESTED: Cemu assembler/loader, multicore interleavings, real gameplay event coverage, force calibration')

if __name__=='__main__':main()
