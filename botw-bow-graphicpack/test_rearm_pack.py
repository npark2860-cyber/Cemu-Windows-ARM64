"""Assemble and emulate the actual generated PPC probe; does not run Cemu."""
from pathlib import Path
import re
import struct
import sys
sys.path.insert(0, str(Path(__file__).parent/'analysis-tools'))
from keystone import Ks, KS_ARCH_PPC, KS_MODE_PPC32, KS_MODE_BIG_ENDIAN
from unicorn import Uc, UC_ARCH_PPC, UC_MODE_PPC32, UC_MODE_BIG_ENDIAN
import unicorn.ppc_const as P
from inspect_rpx import load, module_crc

ROOT=Path(__file__).parent
BASE=0x01800000
REGS=[getattr(P, f'UC_PPC_REG_{i}') for i in range(32)]
SPR=[P.UC_PPC_REG_LR,P.UC_PPC_REG_CR,P.UC_PPC_REG_CTR,P.UC_PPC_REG_XER]

def assemble(source=None):
    source = source or ROOT/'SequenceRearmValidation/patch_bow_sequence.asm'
    pack = source.parent
    assert source.is_file() and source.match('patch_*.asm'), 'Cemu modern parser requires patch_*.asm'
    assert not (pack/'patches.txt').exists(), 'Do not ship modern directives as legacy patches.txt'
    pc=BASE
    labels={}
    lines=[]
    hooks=[]
    for raw in source.read_text().splitlines():
        raw=raw.split('#')[0].strip()
        if not raw or raw.startswith('[') or raw.startswith('moduleMatches'):
            continue
        if raw.startswith(('.origin','.callback','.adaptiveTriggerRaw')):
            continue
        if raw.endswith(':'):
            labels[raw[:-1]]=pc
            continue
        if re.match(r'0x[0-9A-Fa-f]+\s*=',raw):
            addr,instruction=raw.split('=',1)
            hooks.append((int(addr.strip(),16),instruction.strip()))
            continue
        lines.append((pc,raw))
        pc+=4
    ks=Ks(KS_ARCH_PPC,KS_MODE_PPC32|KS_MODE_BIG_ENDIAN)
    def instruction(addr,line):
        if line.startswith('.uint '):
            return struct.pack('>I',int(line.split()[1],0))
        def immediate(m):
            value=labels[m[1]]
            value=((value+0x8000)>>16)&0xffff if m[2]=='ha' else value&0xffff
            return str(value if value<0x8000 else value-0x10000)
        line=re.sub(r'(\w+)@(ha|l)',immediate,line)
        for name,value in labels.items():
            line=re.sub(r'\b'+name+r'\b',hex(value),line)
        line=re.sub(r'\br(\d+)\b',r'\1',line)
        try:
            encoded,_=ks.asm(line,addr=addr)
        except Exception as error:
            raise RuntimeError(f'{addr:08x}: {line}') from error
        assert encoded is not None and len(encoded)==4,(line,encoded)
        return bytes(encoded)
    return labels,[(addr,instruction(addr,line)) for addr,line in lines+hooks]

def main():
    original,sections=load(ROOT.parent/'U-King.rpx')
    assert module_crc(original,sections)==0x6267BFD0
    expected={0x02d67d28:0x80010014,0x02eb4518:0x7c0802a6,
              0x02eb4e80:0x4e800020,0x02ebf740:0x80010014,
              0x02eb6874:0x93a90010}
    for addr,word in expected.items():
        sec=next(s for s in sections if s['addr']<=addr< s['addr']+s['size'])
        assert struct.unpack_from('>I',sec['payload'],addr-sec['addr'])[0]==word
    labels,words=assemble()
    u=Uc(UC_ARCH_PPC,UC_MODE_PPC32|UC_MODE_BIG_ENDIAN)
    u.mem_map(BASE,0x10000)
    u.mem_map(0x02000000,0x01000000)
    u.mem_map(0x10000000,0x20000)
    for addr,word in words:
        u.mem_write(addr,word)
    state=labels['BowProbeState']
    def get(off): return struct.unpack('>I',u.mem_read(state+off,4))[0]
    def put(off,value): u.mem_write(state+off,struct.pack('>I',value))
    def execute(start,end,changes=None):
        for i,reg in enumerate(REGS): u.reg_write(reg,0x12340000+i*0x101)
        u.reg_write(REGS[1],0x10008000)
        u.reg_write(REGS[9],0x10010000)
        u.reg_write(REGS[28],0x10011000)
        u.reg_write(REGS[29],37)
        u.reg_write(REGS[30],1)
        for reg,value in zip(SPR,[0x02000000,0xa55a1234,12345,0xe0000000]):u.reg_write(reg,value)
        u.mem_write(0x10008014,struct.pack('>I',0xcafebabe))
        u.mem_write(0x10010010,struct.pack('>I',40))
        if changes:
            for reg,value in changes.items(): u.reg_write(reg,value)
        before=[u.reg_read(x) for x in REGS+SPR]
        u.emu_start(start,end,count=3000)
        assert u.reg_read(P.UC_PPC_REG_PC)==end,'failed to reach continuation'
        return before,[u.reg_read(x) for x in REGS+SPR]
    def hook(addr,end,changed_r0=None,changes=None):
        before,after=execute(addr,end,changes)
        if changed_r0 is not None:before[0]=changed_r0
        assert before==after,[(i,a,b) for i,(a,b) in enumerate(zip(before,after)) if a!=b]
    execute(labels['BowProbeEntry'],0x02000000)
    assert get(0)==0 and get(0x14)==1
    hook(0x02d67d28,0x02d67d2c,0xcafebabe)
    assert get(0)==0 and get(4)==0,'must wait for pouch load'
    hook(0x02eb4518,0x02eb451c,0x02000000)
    assert get(0)==0 and get(0x14)==1 and get(0x30)==1
    hook(0x02eb4e80,0x02000000)
    assert get(0x14)==0
    for tick in range(1,1202):
        hook(0x02d67d28,0x02d67d2c,0xcafebabe)
        if tick<=1200:
            seq=(tick-1)//120+1
            assert get(0)==(seq<<16)|0x3f04,(tick,get(0),seq)
        else:
            assert get(0)==0 and get(0x18)==1
    assert get(0xc)==10
    hook(0x02d67d28,0x02d67d2c,0xcafebabe)
    assert get(4)==1201 and get(0)==0,'stop must latch'
    hook(0x02ebf740,0x02ebf744,0xcafebabe)
    assert get(0x1c)==1 and get(0)==0
    hook(0x02eb6874,0x02eb6878)
    assert [get(x) for x in [0x20,0x24,0x28,0x2c]]==[1,0x10010000,40,37]
    assert struct.unpack('>I',u.mem_read(0x10010010,4))[0]==37,'original store missing'
    hook(0x02eb6874,0x02eb6878,changes={REGS[30]:2})
    assert get(0x20)==1,'arrows must not count as bow value writes'
    hook(0x02eb4518,0x02eb451c,0x02000000)
    hook(0x02eb4e80,0x02000000)
    put(8,0xffff)
    hook(0x02d67d28,0x02d67d2c,0xcafebabe)
    assert get(0)==0x3f04,'sequence wrap must keep nonzero raw payload'
    hook(0x02eb4518,0x02eb451c,0x02000000)
    assert get(0)==0 and get(0x14)==1,'load entry must stop output'
    print('PASS: original RPX words and module CRC, assembly, all GPR/LR/CR/CTR/XER preservation')
    print('PASS: load gate, 10 sequence-only emissions, bounded off, wrap, trace-only rebuild/value hooks')
    print('NOT TESTED: Cemu GraphicPack loader, real callback frequency, hardware re-arm, BOTW event coverage')

if __name__=='__main__': main()
