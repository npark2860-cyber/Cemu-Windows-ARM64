from pathlib import Path
import subprocess
r=Path('generic-voice-haptics')
for name in subprocess.check_output(['git','-C',str(r),'diff','--cached','--diff-filter=A','--name-only']).decode().splitlines():
 p=r/name
 if p.suffix=='.bnvib':continue
 s=p.read_text(encoding='utf-8-sig');p.write_bytes(('\n'.join(l.rstrip() for l in s.splitlines()).rstrip()+'\n').encode('utf-8'))
 subprocess.check_call(['git','-c','core.autocrlf=false','-C',str(r),'add',name])
