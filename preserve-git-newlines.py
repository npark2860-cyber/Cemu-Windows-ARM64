from pathlib import Path
import subprocess,difflib
r=Path('generic-voice-haptics')
paths=subprocess.check_output(['git','-c','core.autocrlf=false','-C',str(r),'diff','--name-only']).decode().splitlines()
for name in paths:
 p=r/name
 if p.is_dir():continue
 raw=subprocess.check_output(['git','-C',str(r),'show','HEAD:'+name])
 if name.startswith('.github/'):
  p.write_bytes(raw);continue
 original=raw.decode('utf-8');new=p.read_text(encoding='utf-8-sig')
 old=original.splitlines(keepends=True);cur=new.splitlines(keepends=True)
 out=[]
 for op,a,b,c,d in difflib.SequenceMatcher(None,[s.rstrip('\r\n') for s in old],[s.rstrip('\r\n') for s in cur],autojunk=False).get_opcodes():
  out.extend(old[a:b] if op=='equal' else [s.rstrip('\r\n')+'\n' for s in cur[c:d]])
 p.write_bytes(''.join(out).encode())

