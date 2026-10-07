"""Read-only ELF32-BE/RPX inspection; never modifies or executes guest code."""
import argparse
import hashlib
from pathlib import Path
import struct
import sys
import zlib

sys.path.insert(0, str(Path(__file__).parent / 'analysis-tools'))
from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN

def load(path):
    data = path.read_bytes()
    if data[:6] != b'\x7fELF\x01\x02':
        raise ValueError('Expected ELF32 big-endian RPX')
    hdr = struct.unpack_from('>16sHHIIIIIHHHHHH', data)
    if hdr[2] != 20:
        raise ValueError('Expected PowerPC ELF')
    shoff, shsize, shnum, shstrings = hdr[6], hdr[11], hdr[12], hdr[13]
    sections = []
    for i in range(shnum):
        raw = struct.unpack_from('>10I', data, shoff + i*shsize)
        name, kind, flags, addr, offset, size, link, info, align, entsize = raw
        payload = b'' if kind == 8 else data[offset:offset+size]
        if flags & 0x08000000:
            expected = struct.unpack_from('>I', payload)[0]
            payload = zlib.decompress(payload[4:])
            if len(payload) != expected:
                raise ValueError('RPX section size mismatch')
        sections.append(dict(index=i, nameoff=name, kind=kind, flags=flags,
                             addr=addr, payload=payload, size=len(payload),
                             crcsize=size if kind == 8 else len(payload), align=align))
    names = sections[shstrings]['payload']
    for s in sections:
        s['name'] = names[s['nameoff']:].split(b'\0')[0].decode('ascii', 'replace')
    return data, sections

def module_crc(data, sections):
    shstrings = struct.unpack_from('>H', data, 50)[0]
    sym = next((s['index'] for s in reversed(sections) if s['kind'] == 2), -1)
    strings = next((s['index'] for s in sections if s['kind'] == 3 and s['index'] != shstrings), -1)
    crc = zlib.crc32(b'\x7fRPX')
    crc = zlib.crc32(struct.pack('<4i', len(sections), sym, strings, shstrings), crc)
    for s in sections:
        crc = zlib.crc32(struct.pack('<6I', s['nameoff'], s['kind'], s['flags'], s['addr'], s['crcsize'], s['align']), crc)
        if s['kind'] != 8:
            crc = zlib.crc32(s['payload'], crc)
    return crc

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rpx', type=Path)
    ap.add_argument('--range', nargs=2, action='append', default=[], metavar=('START','END'))
    ap.add_argument('--callers', action='append', default=[])
    ap.add_argument('--pointers', action='append', default=[])
    ap.add_argument('--string-at', action='append', default=[])
    args = ap.parse_args()
    data, sections = load(args.rpx)
    print('SHA256', hashlib.sha256(data).hexdigest())
    print(f'Cemu moduleMatches CRC: 0x{module_crc(data, sections):08X}')
    print('Loaded sections:', ', '.join(f"{s['name']}@{s['addr']:08x}+{s['size']:x}" for s in sections if s['addr']))
    dis = Cs(CS_ARCH_PPC, CS_MODE_32 | CS_MODE_BIG_ENDIAN)
    for addr in args.string_at:
        addr = int(addr, 0)
        s = next(s for s in sections if s['addr'] <= addr < s['addr']+s['size'])
        print(f'STRING {addr:08x}', repr(s['payload'][addr-s['addr']:addr-s['addr']+256].split(b'\0')[0]))
    for value in args.pointers:
        value = int(value, 0)
        needle = struct.pack('>I', value)
        for s in sections:
            start = 0
            while True:
                off = s['payload'].find(needle, start)
                if off < 0:
                    break
                start = off+1
                if off % 4 == 0:
                    print(f"WORD REF {value:08x}: {s['name']} +{off:x} address={s['addr']+off:08x}")
    for first, last in args.range:
        start, end = int(first, 0), int(last, 0)
        section = next(s for s in sections if s['addr'] <= start and end <= s['addr']+s['size'])
        payload = section['payload'][start-section['addr']:end-section['addr']]
        print(f'\nRANGE {start:08x}..{end:08x}')
        # Decode each word independently so an unsupported instruction cannot
        # silently truncate the remaining evidence.
        for offset in range(0, len(payload), 4):
            word = payload[offset:offset+4]
            ins = next(dis.disasm(word, start+offset), None)
            if len(word) == 4 and int.from_bytes(word, 'big') >> 26 == 4:
                ins = None  # Espresso paired-single encodings are not AltiVec.
            print(f'{start+offset:08x}  {word.hex()}  ' + (f'{ins.mnemonic} {ins.op_str}' if ins else '.long 0x'+word.hex()))
    targets = {int(x, 0): [] for x in args.callers}
    for s in sections:
        if not s['flags'] & 4:
            continue
        for off in range(0, len(s['payload'])-3, 4):
            word = struct.unpack_from('>I', s['payload'], off)[0]
            if word >> 26 != 18:
                continue
            disp = word & 0x03fffffc
            if disp & 0x02000000:
                disp -= 0x04000000
            pc = s['addr']+off
            dest = (disp if word & 2 else pc+disp) & 0xffffffff
            if dest in targets:
                targets[dest].append((pc, word, 'call' if word & 1 else 'branch'))
    for target, refs in targets.items():
        print(f'\nDIRECT REFERENCES TO {target:08x} (does not include indirect calls)')
        for pc, word, kind in refs:
            print(f'{pc:08x} {word:08x} {kind}')

if __name__ == '__main__':
    main()
