"""Read imported symbols without executing or altering the game module."""
import json
import struct
import sys
import zlib
from pathlib import Path

p = Path(sys.argv[1])
b = p.read_bytes()
assert b[:6] == b'\x7fELF\x01\x02', 'Expected 32-bit big-endian ELF'
shoff = struct.unpack_from('>I', b, 32)[0]
shsize, shnum = struct.unpack_from('>HH', b, 46)
assert shsize == 40
sections = [struct.unpack_from('>10I', b, shoff + i * shsize) for i in range(shnum)]

def contents(i):
    _, typ, flags, _, offset, size, *_ = sections[i]
    if typ == 8:
        return b''
    data = b[offset:offset + size]
    if flags & 0x08000000:
        expected = struct.unpack_from('>I', data)[0]
        data = zlib.decompress(data[4:])
        assert len(data) == expected
    return data

imports = []
for i, section in enumerate(sections):
    _, typ, _, _, _, _, link, _, _, entsize = section
    if typ != 2:
        continue
    data = contents(i)
    strings = contents(link)
    assert entsize == 16
    for off in range(0, len(data), entsize):
        name, value, size, info, other, index = struct.unpack_from('>IIIBBH', data, off)
        if index < len(sections) and sections[index][1] == 0x80000002:
            end = strings.find(b'\0', name)
            symbol = strings[name:end].decode('ascii', errors='replace')
            imports.append(symbol)
result = {'path': str(p), 'import_count': len(imports),
          'memory_and_gpu_imports': sorted(set(s for s in imports if s.startswith(('DC', 'GX2'))))}
out = p.with_suffix('.imports.json')
out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(result, indent=2, ensure_ascii=True))
