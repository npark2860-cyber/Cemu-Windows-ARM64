"""Read-only BARS/FWAV metadata using the pinned Cemu catalog layout."""
from pathlib import Path
import struct, json, argparse

def tracks(path):
    d=path.read_bytes()
    assert d[:4]==b'BARS'
    e='>' if d[8:10]==b'\xfe\xff' else '<'
    u32=lambda a:struct.unpack_from(e+'I',d,a)[0]
    u16=lambda a:struct.unpack_from(e+'H',d,a)[0]
    assert u32(4)==len(d)
    n=u32(12)
    assert 16+n*12<=len(d)
    for i in range(n):
        a,w=struct.unpack_from(e+'II',d,16+n*4+i*8)
        assert d[a:a+4]==b'AMTA'
        ae='>' if d[a+4:a+6]==b'\xfe\xff' else '<'
        au=lambda o:struct.unpack_from(ae+'I',d,a+o)[0]
        ver=struct.unpack_from(ae+'H',d,a+6)[0]
        dr,sr=au(12),au(20 if ver==0x100 else 24)
        assert d[a+dr:a+dr+4]==b'DATA' and d[a+sr:a+sr+4]==b'STRG'
        no=au(dr+8)
        name=d[a+sr+8+no:].split(b'\0',1)[0].decode()
        typ=d[w:w+4].decode('ascii')
        row={'bars':path.name,'track':name,'format':typ,'offset':w}
        if typ=='FWAV':
            fe='>' if d[w+4:w+6]==b'\xfe\xff' else '<'
            fu=lambda o:struct.unpack_from(fe+'I',d,w+o)[0]
            nc=struct.unpack_from(fe+'H',d,w+16)[0]
            blocks={struct.unpack_from(fe+'H',d,w+20+j*12)[0]:fu(24+j*12) for j in range(nc)}
            info=w+blocks[0x7000]; data=w+blocks[0x7001]
            iu=lambda o:struct.unpack_from(fe+'I',d,info+o)[0]
            row.update(codec=d[info+8],loop=bool(d[info+9]),rate=iu(12),loop_start=iu(16),samples=iu(20),channels=iu(28),info=info,data=data,endian=fe)
            row['seconds']=round(row['samples']/row['rate'],4)
            row['channel_info']=[info+28+iu(36+j*8) for j in range(row['channels'])]
        yield row

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('--out',type=Path)
    args=ap.parse_args()
    rows=[r for f in sorted(args.root.glob('*GameROMMotorcycle*.bars')) for r in tracks(f)]
    if args.out:args.out.write_text(json.dumps(rows,indent=2),encoding='utf-8')
    print(json.dumps(rows,indent=2))
