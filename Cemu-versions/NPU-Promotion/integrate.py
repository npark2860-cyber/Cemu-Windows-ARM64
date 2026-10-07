"""Apply only the tested NPU integration over each variant's prepared base."""
from pathlib import Path
import argparse,difflib,json,re,shutil,subprocess
from prepare import HERE,VERSIONS,RC,ROLES,git,sha,write

def neutral_title(text):
 pattern=r'#ifdef CEMU_ENABLE_NPU\n[^\n]*NPU RC1 - Release - 1080p/720p[^\n]*\n#else\n([^\n]+)\n#endif'
 if 'NPU RC1 - Release - 1080p/720p' in text:
  text,count=re.subn(pattern,lambda m:m[1],text);assert count==1
 return text
def make_patch():
 manifest=json.loads((RC/'NPU-RELEASE-BUILD.json').read_text(encoding='utf-8'))
 paths=[r['path'][len('source-overlay/'):] for r in manifest['files'] if r['path'].startswith('source-overlay/')]
 patch='';changed=[]
 for relative in paths:
  baseline=HERE/'Release/preprocessed-source'/relative
  if not baseline.exists():baseline=VERSIONS/'Release/source'/relative
  before=baseline.read_text(encoding='utf-8-sig') if baseline.exists() else ''
  after=neutral_title((RC/'source-overlay'/relative).read_text(encoding='utf-8-sig'))
  if before==after:continue
  patch+=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/'+relative if before else '/dev/null',tofile='b/'+relative))
  changed.append(relative)
 path=HERE/'npu-common.patch'
 if path.exists():assert path.read_text(encoding='utf-8')==patch
 else:write(path,patch)
 return patch,changed
def main():
 p=argparse.ArgumentParser();p.add_argument('--role',choices=list(ROLES),required=True);args=p.parse_args();role=args.role
 src=HERE/role/'source';evidence=HERE/role/'evidence'
 assert (evidence/'preprocessed.json').exists()
 assert not (evidence/'integrated.json').exists(),'Already integrated; preserve checkpoint'
 patch,paths=make_patch()
 excluded=[]
 if role=='Diagnostics':
  excluded=['src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp','src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h']
 def apply(check):
  result=subprocess.run(['git','apply',*(['--check'] if check else []),*['--exclude='+p for p in excluded],'--ignore-space-change','--whitespace=nowarn','-'],input=patch.encode(),cwd=src,capture_output=True)
  (evidence/('patch-check.log' if check else 'patch-apply.log')).write_bytes(result.stdout+result.stderr)
  if result.returncode:raise RuntimeError('Patch needs review for '+role+'; see '+str(evidence/'patch-check.log'))
 apply(True);apply(False)
 if role=='Diagnostics':
  api=src/'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanAPI.h'
  code=api.read_text(encoding='utf-8');entry='VKFUNC_DEVICE(vkCmdWriteTimestamp);'
  assert code.count(entry)==2
  code=code.replace('VKFUNC_DEVICE(vkCmdResetQueryPool);\n'+entry+'\n','VKFUNC_DEVICE(vkCmdResetQueryPool);\n',1)
  assert code.count(entry)==1
  write(api,code)
 for rel in excluded:
  review=evidence/'merge-review';name=Path(rel).name
  text=(review/('merged-'+name)).read_text(encoding='utf-8')
  if name.endswith('.cpp'):
   expected=[
    '\tconst bool diagPresent = RuntimeDiagnostics::Enabled(RuntimeDiagnostics::Flag::PresentTiming);\n\tconst uint64_t diagPresentStart = diagPresent ? RuntimeDiagnostics::NowNs() : 0;\n',
    '\tif (diagPresent)\n\t\tRuntimeDiagnostics::AddAccum(RuntimeDiagnostics::g_presentTiming, RuntimeDiagnostics::NowNs() - diagPresentStart);\n']
   def combine(m):
    ours,base,theirs=m[1],m[2],m[3]
    assert not base and ours in expected and theirs.startswith('#ifdef CEMU_ENABLE_NPU\n')
    expected.remove(ours)
    return ours+theirs
   text,count=re.subn(r'(?m)^<<<<<<<[^\n]*\n(.*?)^\|\|\|\|\|\|\|[^\n]*\n(.*?)^=======\n(.*?)^>>>>>>>[^\n]*\n',combine,text,flags=re.S|re.M)
   assert count==2 and not expected
  assert '<<<<<<<' not in text and '>>>>>>>' not in text
  base=(review/('base-'+name)).read_text(encoding='utf-8').splitlines(True)
  ours=(review/('ours-'+name)).read_text(encoding='utf-8').splitlines(True)
  for tag,a,b,c,d in difflib.SequenceMatcher(None,base,ours,autojunk=False).get_opcodes():
   if tag in ['insert','replace']:
    added=''.join(ours[c:d]);assert added in text,'Diagnostic block was lost in '+name
  write(src/rel,text)
 title='Cemu ARM64 ['+role+' | NPU]'
 for rel in ['src/gui/wxgui/MainWindow.cpp','src/gui/wxgui/wxWindowSystem.cpp']:
  path=src/rel;text=path.read_text(encoding='utf-8-sig')
  if rel.endswith('/MainWindow.cpp'):
   pattern=r'(\treturn (?:BUILD_VERSION_WITH_NAME_STRING|wxASCII_STR\("Cemu ARM64[^"\n]*"\));)'
   replacement=lambda m:'#ifdef CEMU_ENABLE_NPU\n\treturn wxASCII_STR("'+title+'");\n#else\n'+m[1]+'\n#endif'
  else:
   pattern=r'(\twindowText = (?:BUILD_VERSION_WITH_NAME_STRING|"Cemu ARM64[^"\n]*");)'
   replacement=lambda m:'#ifdef CEMU_ENABLE_NPU\n\twindowText = "'+title+'";\n#else\n'+m[1]+'\n#endif'
  text,count=re.subn(pattern,replacement,text);assert count==1,(role,rel,count)
  write(path,text)
 # Standalone module source is the already-tested ABI v2 implementation. Its
 # models, shader binaries and runtime are packaged by hash from RC1.
 dest=src/'dependencies/npu-cemu';dest.mkdir(exist_ok=True)
 for name in ['npu_cemu.cpp','processing_profile.h','borrowed_support.h','gpu_resources.h','anvil_async_worker.h','buffered_timeline.h','ort_paths.h','test_processing_profile.cpp','test_buffered_timeline.cpp','test_ort_paths.cpp']:
  shutil.copy2(RC/'module-source'/name,dest/name)
 # Prove the complete tracked source matches its prepared variant plus exactly
 # the common integration and branding, without replacing SE/diagnostic files.
 before=json.loads((evidence/'preprocessed.json').read_text(encoding='utf-8'))
 prepared={x['path']:x['sha256'] for x in before['changed']}
 allowed=set(paths)|{'src/gui/wxgui/MainWindow.cpp','src/gui/wxgui/wxWindowSystem.cpp'}
 protected=[]
 for entry in git(src,'ls-files').splitlines():
  path=src/entry
  if not path.is_file() or entry in allowed:continue
  reference=HERE/role/'preprocessed-source'/entry
  if not reference.exists():reference=VERSIONS/role/'source'/entry
  assert sha(path)==sha(reference),'Unexpected change outside NPU integration: '+entry
  protected.append(entry)
 subprocess.run(['git','diff','--check'],cwd=src,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 write(evidence/'integrated.json',json.dumps({'role':role,'base_commit':ROLES[role][0],'branch':git(src,'branch','--show-current'),'title':title,'common_patch_sha256':sha(HERE/'npu-common.patch'),'common_changed_paths':paths,'unchanged_non_integration_tracked_files':len(protected),'baseline_preserved':not git(VERSIONS/role/'source','status','--porcelain'),'module_source':'RC1 ABI v2, identical','device_executed':False},indent=2)+'\n')
 print('INTEGRATED '+role+'; protected non-integration files='+str(len(protected)),flush=True)
if __name__=='__main__':main()
