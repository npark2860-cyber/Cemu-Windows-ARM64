"""Offline four-variant promotion, preserving the four original repositories."""
from pathlib import Path
from datetime import datetime, timezone
import difflib, hashlib, json, os, re, shutil, subprocess, sys
HERE=Path(__file__).resolve().parent
VERSIONS=HERE.parent
RC=VERSIONS/'Test/NPU-Release-RC1'
PYTHON=Path(sys.executable)
ROLES={
 'Release':('c5205ccbc8ffe41129fbe921b5420a79ff283216','final-adreno-compat-arm64.yml'),
 'Release+SE':('9c0b899eb31792353909ac7ff81ed42b2dd7f8fa','final-adreno-compat-arm64.yml'),
 'Diagnostics':('6aa13388289ed41c2f7c802c5b096b142dc1b4c8','diagnostics-arm64.yml'),
 'Diagnostics+SE':('b18d8faae5a4b2316974ef4907e0739a9e3a5c2b','enhanced-sound-cue-capture-v2-arm64.yml')}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s,encoding='utf-8',newline='\n')
def git(root,*args):return subprocess.check_output(['git','-C',str(root),*args],stderr=subprocess.PIPE).decode('utf-8').strip()
def run(cmd,cwd,log):
 with log.open('ab') as f:
  f.write(('\nCOMMAND: '+str(cmd)+'\n').encode('utf-8'))
  subprocess.run([str(x) for x in cmd],cwd=cwd,stdout=f,stderr=subprocess.STDOUT,check=True)
def clone_tree(src,dst,commit,log):
 if not (dst/'.git').exists():
  assert not dst.exists() or not any(dst.iterdir()),str(dst)
  run(['git','clone','--no-hardlinks','--no-checkout',src,dst],HERE,log)
  run(['git','checkout','--detach',commit],dst,log)
 assert git(dst,'rev-parse','HEAD')==commit
 modules=dst/'.gitmodules'
 if modules.exists():
  entries=git(dst,'config','--file','.gitmodules','--get-regexp',r'^submodule\..*\.path$')
  for entry in entries.splitlines():
   key,relative=entry.split(' ',1);name=key[len('submodule.'):-len('.path')]
   child=src/relative
   tree=git(dst,'ls-tree','HEAD',relative).split()
   # Gamepad-Core retains historical .gitmodules entries that are not gitlinks
   # at this pinned commit. Only tracked gitlinks belong to the source snapshot.
   if not tree or tree[0]!='160000':continue
   expected=tree[2]
   assert git(child,'rev-parse','HEAD')==expected
   clone_tree(child,dst/relative,expected,log)
   run(['git','config','submodule.'+name+'.url',str(child)],dst,log)
   run(['git','config','submodule.'+name+'.active','true'],dst,log)
 assert not git(dst,'status','--porcelain'),str(dst)
def steps(path):
 lines=path.read_text(encoding='utf-8-sig').splitlines();result={};name=''
 for i,line in enumerate(lines):
  if line.startswith('      - name: '):name=line.split(': ',1)[1]
  if line=='        run: |':
   body=[]
   for following in lines[i+1:]:
    if following.startswith('          '):body.append(following[10:])
    elif not following.strip():body.append('')
    else:break
   result[name]='\n'.join(body)
  elif line.startswith('        run: '):result[name]=line[len('        run: '):]
 return result
def workflow_step(src,role,name,body):
 folder=HERE/role/'evidence'; path=folder/('step-'+re.sub('[^a-z0-9]+','-',name.lower()).strip('-')+'.ps1')
 body=re.sub(r'(?m)^python (.*)$',lambda m:"& '"+str(PYTHON)+"' "+m[1],body)
 body="$ErrorActionPreference='Stop'\n$global:LASTEXITCODE=0\n$env:PYTHONIOENCODING='utf-8'\n"+body+'\nif($LASTEXITCODE -ne 0) {throw "Preprocessing step failed"}\n'
 write(path,body)
 run(['C:/Program Files/PowerShell/7/pwsh.exe','-NoProfile','-File',path],src,folder/'preprocess.log')
def main():
 manifest=json.loads((RC/'NPU-RELEASE-BUILD.json').read_text(encoding='utf-8'))
 for f in manifest['files']:assert sha(RC/f['path'])==f['sha256'],f['path']
 ev=HERE/'evidence';ev.mkdir(exist_ok=True)
 log=RC/'runtime/portable/log.txt'
 snapshot=ev/'rc1-user-720p-game.log'
 if not snapshot.exists():shutil.copy2(log,snapshot)
 if not (ev/'user-acceptance.json').exists():
  write(ev/'user-acceptance.json',json.dumps({'recorded_at':datetime.now(timezone.utc).isoformat(),'user_report':'테스트 다 해봤고 아주 잘 된 것 같아','candidate_manifest_sha256':sha(RC/'NPU-RELEASE-BUILD.json'),'candidate_executable_sha256':manifest['cemu_sha256'],'latest_log_sha256':sha(snapshot),'agent_executed_gpu_npu_cemu':False,'scope':'User reported overall RC1 success. Retained last game log independently confirms 720p model and window/fullscreen presentation. Other variants not yet game tested.'},ensure_ascii=False,indent=2)+'\n')
 common=steps(VERSIONS/'Release/source/.github/workflows/final-adreno-compat-arm64.yml')
 for role,(commit,wf) in ROLES.items():
  root=HERE/role;src=root/'source';folder=root/'evidence';folder.mkdir(parents=True,exist_ok=True)
  if (folder/'preprocessed.json').exists():continue
  assert not (folder/'preprocess.log').exists(),'Partial preprocessing exists; inspect before resuming '+role
  baseline=VERSIONS/role/'source'
  assert git(baseline,'rev-parse','HEAD')==commit and not git(baseline,'status','--porcelain')
  clone_tree(baseline,src,commit,folder/'clone.log')
  run(['git','switch','-c','codex/npu-'+role.lower().replace('+','-')],src,folder/'clone.log')
  specific=steps(src/'.github/workflows'/wf)
  used=[]
  if role=='Diagnostics+SE':
   name='Apply V2 cue-capture instrumentation';workflow_step(src,role,name,specific[name]);used.append(name)
   name='Validate diagnostic structure';workflow_step(src,role,name,specific[name]);used.append(name)
   # Bring this older renderer to the tested common FSR/Adreno presentation
   # path. Audio diagnostic code and its branch-specific features remain intact.
   for rel in ['tools/compat/Apply-PSDefaultLinkageFix.py','tools/graphics/Apply-FidelityFXFSRExperiment.py','tools/graphics/Apply-FidelityFXFSRFullExperiment.py']:
    dest=src/rel;dest.parent.mkdir(parents=True,exist_ok=True)
    assert not dest.exists();shutil.copy2(VERSIONS/'Release/source'/rel,dest)
   # The upstream FSR patch intentionally uses mixed shader indentation.
   # Match the Release branch's narrowly scoped whitespace policy before it runs.
   attribute='src/Cafe/HW/Latte/Renderer/RendererOuputShader.cpp whitespace=-space-before-tab'
   attributes=src/'.gitattributes';content=attributes.read_text(encoding='utf-8')
   if attribute not in content:write(attributes,content.rstrip()+'\n'+attribute+'\n')
  for name in ['Apply known-good pre-e834 runtime behavior','Apply permanent PS DEFAULT_VAL linkage compatibility fix','Apply AMD FidelityFX FSR1']:
   workflow_step(src,role,name,common[name] if role=='Diagnostics+SE' else specific[name]);used.append(name)
  if role=='Diagnostics':
   name='Install switchable ARM64 diagnostics';workflow_step(src,role,name,specific[name]);used.append(name)
   workflow_step(src,role,'Stamp diagnostics UI','python ./tools/diagnostics/release/Verify-ReleaseDiagnosticUIBuild.py --stage source --stamp-source')
  else:
   name='Apply Cemu ARM64 window branding';workflow_step(src,role,name,common[name]);used.append(name)
  if role in ['Release','Release+SE']:
   name='Verify release source is diagnostics-free';workflow_step(src,role,name,specific[name]);used.append(name)
  changed=git(src,'diff','--name-only').splitlines()
  for relative in changed:
   dest=root/'preprocessed-source'/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src/relative,dest)
  write(folder/'preprocessed.json',json.dumps({'role':role,'base_commit':commit,'steps':used,'workflow_sha256':sha(src/'.github/workflows'/wf),'changed':[{'path':p,'sha256':sha(src/p)} for p in changed]},indent=2)+'\n')
  print('PREPROCESSED '+role,flush=True)
 print('All baseline checkouts preserved; promotion copies prepared.',flush=True)
if __name__=='__main__':main()
