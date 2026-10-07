"""Verify and package one local promotion. Never executes Cemu or a device probe."""
from pathlib import Path
from datetime import datetime, timezone
import argparse,gettext,io,json,shutil,struct,subprocess,sys,xml.etree.ElementTree as ET
from prepare import HERE,VERSIONS,RC,ROLES,sha,write,git
from localize import MESSAGES,read_mo

EXES={'Release':'Cemu-Release-NPU.exe','Release+SE':'Cemu-Release-SE-NPU.exe',
      'Diagnostics':'Cemu-Diagnostics-NPU.exe','Diagnostics+SE':'Cemu-Diagnostics-SE-NPU.exe'}
DIAG_MARKERS=['ARM64 Diagnostics','[ADRENO_DIAG]','[CEMU_DIAG]','[GPU_QUERY_VIS]','[PS_INPUT_LINKAGE]']
def contains(data,s):return s.encode('utf-8') in data or s.encode('utf-16-le') in data
def record(path,root):return {'path':path.relative_to(root).as_posix(),'bytes':path.stat().st_size,'sha256':sha(path)}
def copy_verified(source,target,expected=None):
    if expected:assert sha(source)==expected,str(source)
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():assert sha(target)==sha(source),'Existing output differs: '+str(target)
    else:shutil.copy2(source,target)
    assert sha(target)==sha(source)

def package(role):
    root=HERE/role;src=root/'source';ev=root/'evidence';runtime=root/'runtime'
    assert not (root/'NPU-BUILD.json').exists(),'Already packaged; preserve this result'
    build_results=[(p,json.loads(p.read_text(encoding='utf-8-sig'))) for p in ev.glob('*-result.json')]
    build_results=[(p,r) for p,r in build_results if r.get('variant')==role and 'exit_code' in r]
    result_path,build_result=max(build_results,key=lambda pair:pair[1]['finished_at'])
    result_name=result_path.name
    assert build_result['exit_code']==0 and build_result['variant']==role
    baseline=VERSIONS/role/'source'
    assert git(src,'rev-parse','HEAD')==ROLES[role][0]==git(baseline,'rev-parse','HEAD')
    assert not git(baseline,'status','--porcelain'),'Original baseline changed'
    subprocess.run(['git','diff','--check'],cwd=src,check=True,capture_output=True)
    integrated=json.loads((ev/'integrated.json').read_text(encoding='utf-8'))
    allowed=set(integrated['common_changed_paths'])|{'src/gui/wxgui/MainWindow.cpp','src/gui/wxgui/wxWindowSystem.cpp'}
    protected=0
    for relative in git(src,'ls-files').splitlines():
        path=src/relative
        if not path.is_file() or relative in allowed:continue
        ref=root/'preprocessed-source'/relative
        if not ref.exists():ref=baseline/relative
        assert sha(path)==sha(ref),'Non-NPU source changed: '+relative
        protected+=1
    exe=src/'bin/Cemu_release.exe';binary=exe.read_bytes()
    pe=struct.unpack_from('<I',binary,0x3c)[0]
    assert binary[pe:pe+4]==b'PE\0\0' and struct.unpack_from('<H',binary,pe+4)[0]==0xaa64
    assert contains(binary,integrated['title']),'Wrong variant title'
    for s in ['NPU frame generation','NPU processing','720p / Performance','1080p / Standard','cemu_npu.dll']:
        assert contains(binary,s),'Missing NPU marker: '+s
    for s in ['Lossless.dll','lossless.dll','lsfg_cemu.dll','LSFG 2X']:
        assert not contains(binary,s),'Legacy LSFG marker: '+s
    cache=(root/'build/CMakeCache.txt').read_text(encoding='utf-8')
    assert 'CEMU_ENABLE_NPU:BOOL=ON' in cache and 'CMAKE_BUILD_TYPE:STRING=Release' in cache
    graph=(root/'build/build.ninja').read_text(encoding='utf-8')
    assert 'VulkanNPU.cpp.obj' in graph and 'VulkanLSFG.cpp.obj' not in graph
    assert '-DEMULATOR_HASH='+ROLES[role][0][:7] in graph,'Wrong baseline compiled'
    role_checks=[]
    if role in ['Release','Release+SE']:
        for s in DIAG_MARKERS:assert not contains(binary,s),'Release contains diagnostics: '+s
        role_checks.append('release_diagnostics_absent')
    if role=='Release+SE':
        for s in ['Enhanced Sound Experience','Haptic output: eligible USB DualSense detected','Haptic playback capacity exhausted']:
            assert contains(binary,s),'Latest SE marker absent: '+s
        role_checks.append('latest_SE_Test_PR5_audio_and_haptics_preserved')
    if role=='Diagnostics':
        verifier=src/'tools/diagnostics/release/Verify-ReleaseDiagnosticUIBuild.py'
        with (ev/'diagnostics-verification.log').open('wb') as log:
            for stage,path in [('source',None),('object',root/'build'),('binary',exe)]:
                subprocess.run([sys.executable,str(verifier),'--stage',stage,*(['--path',str(path)] if path else [])],check=True,stdout=log,stderr=subprocess.STDOUT)
        role_checks.append('diagnostics_source_object_library_binary_markers_verified')
    if role=='Diagnostics+SE':
        for s in ['Enhanced Sound Experience','enhanced_sound_cue_capture.csv','source_path,track_name,route_match']:
            assert contains(binary,s),'CueCaptureV2 marker absent: '+s
        voice=(src/'src/Cafe/OS/libs/snd_core/ax_voice.cpp').read_text(encoding='utf-8')
        assert 'EnhancedSoundCueDiagnostic::Record' in voice and 'ResolveSourceCandidates' in voice
        role_checks.append('SE_CueCaptureV2_instrumentation_preserved')
    reference=json.loads((RC/'NPU-RELEASE-BUILD.json').read_text(encoding='utf-8'))
    assert sha(RC/'NPU-RELEASE-BUILD.json')=='5981cd28313e2b702eb2e65cc6952b4d07920e4e8c40531b906f936562f7c0f9'
    # Pin each inherited file to the accepted RC1, then change only the app and Korean catalog.
    inherited=[]
    for f in reference['files']:
        rel=f['path']
        if not rel.startswith('runtime/'):continue
        if rel in ['runtime/Cemu-NPU-Release.exe','runtime/module-smoke-probe.exe','runtime/resources/ko/cemu.mo']:continue
        copy_verified(RC/rel,root/rel,f['sha256']);inherited.append(rel)
    copy_verified(exe,runtime/EXES[role])
    copy_verified(HERE/'shared-runtime/resources/ko/cemu.mo',runtime/'resources/ko/cemu.mo')
    old_catalog=read_mo((RC/'runtime/resources/ko/cemu.mo').read_bytes())
    new_catalog=read_mo((runtime/'resources/ko/cemu.mo').read_bytes())
    assert all(new_catalog[k]==v for k,v in old_catalog.items())
    translated=gettext.GNUTranslations(io.BytesIO((runtime/'resources/ko/cemu.mo').read_bytes()))
    assert all(translated.gettext(k)==v for k,v in MESSAGES.items())
    locales=[]
    for catalog in sorted((runtime/'resources').glob('*/cemu.mo')):
        gettext.GNUTranslations(io.BytesIO(catalog.read_bytes()));locales.append(catalog.parent.name)
    # Independent settings/cache copies, same saved-game path. Never copy or edit MLC.
    seed=RC/'runtime/portable';portable=runtime/'portable'
    assert not portable.exists(),'Review partial settings copy before retrying'
    portable.mkdir()
    for name in ['settings.xml','title_list_cache.xml','controllerProfiles','gameProfiles','graphicPacks','shaderCache']:
        p=seed/name;q=portable/name
        if p.is_dir():shutil.copytree(p,q)
        elif p.is_file():shutil.copy2(p,q)
    settings=ET.parse(portable/'settings.xml').getroot()
    assert settings.findtext('mlc_path')==ET.parse(seed/'settings.xml').getroot().findtext('mlc_path')
    assert not (portable/'mlc01').exists()
    if role=='Release+SE':
        from se_pack_compat import correct_pack
        correct_pack(root)
    seed_files=[record(p,portable) for p in sorted(portable.rglob('*')) if p.is_file()]
    write(ev/'portable-seed.json',json.dumps({'mutable_after_launch':True,'shared_mlc_path':settings.findtext('mlc_path'),'seeded_processing_height':settings.findtext('.//NPUProcessingHeight'),'files':seed_files},ensure_ascii=False,indent=2)+'\n')
    # Retain the precise source delta and inventory, including new module files.
    delta=subprocess.check_output(['git','diff','--binary','HEAD'],cwd=src)
    (ev/'source.patch').write_bytes(delta)
    paths=set(git(src,'diff','--name-only','HEAD').splitlines())
    paths.update(git(src,'ls-files','--others','--exclude-standard').splitlines())
    paths.update(p.relative_to(src).as_posix() for p in (src/'dependencies/npu-cemu').rglob('*') if p.is_file())
    paths.update(p.relative_to(src).as_posix() for p in (src/'i18n/npu').rglob('*') if p.is_file())
    if role=='Diagnostics+SE':
        paths.update(['tools/compat/Apply-PSDefaultLinkageFix.py','tools/graphics/Apply-FidelityFXFSRExperiment.py','tools/graphics/Apply-FidelityFXFSRFullExperiment.py','src/Cafe/OS/common/EnhancedSoundCueDiagnostic.h'])
    source_files=[record(src/p,src) for p in sorted(paths) if (src/p).is_file()]
    write(ev/'source-files.json',json.dumps(source_files,indent=2)+'\n')
    files=[record(p,root) for p in sorted(runtime.rglob('*')) if p.is_file() and portable not in p.parents]
    manifest={'created_at':datetime.now(timezone.utc).isoformat(),'status':'LOCAL_BUILD_AND_PACKAGE_VERIFIED',
        'role':role,'base_commit':ROLES[role][0],'source_branch':git(src,'branch','--show-current'),
        'title':integrated['title'],'executable':'runtime/'+EXES[role],'cemu_sha256':sha(runtime/EXES[role]),
        'source_inventory':'evidence/source-files.json','source_inventory_sha256':sha(ev/'source-files.json'),
        'source_patch_sha256':sha(ev/'source.patch'),'build_result':result_name,
        'unchanged_non_integration_tracked_files':protected,'role_checks':role_checks,
        'accepted_RC1_manifest_sha256':sha(RC/'NPU-RELEASE-BUILD.json'),
        'module_abi':2,'module_sha256':sha(runtime/'cemu_npu.dll'),'profiles':[1080,720],
        'profile_changes_apply':'next game start','enabled_by_default':False,
        'legacy_gpu_lsfg_linked':False,'lossless_dll_required':False,
        'npu_driver':reference['npu_driver'],'gpu_driver':reference['gpu_driver'],
        'inherited_runtime_files_identical_to_RC1':inherited,'available_catalogs':locales,
        'korean_added_messages':len(MESSAGES),'existing_korean_entries_preserved':len(old_catalog),
        'inherited_arabic_catalog_note':'Original filename contains directional marks and lacks a charset header; retained unchanged, excluded from canonical catalog discovery/validation.',
        'mutable_portable_seed':'evidence/portable-seed.json','shared_mlc_path':settings.findtext('mlc_path'),
        'user_accepted_RC1':True,'this_binary_game_tested':False,'agent_executed_gpu_npu_cemu':False,
        'files':files}
    write(root/'NPU-BUILD.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print('PACKAGED '+role+'; ARM64; protected='+str(protected)+'; runtime files='+str(len(files))+'; locales='+str(len(locales)),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--role',choices=list(ROLES),required=True)
    package(parser.parse_args().role)
