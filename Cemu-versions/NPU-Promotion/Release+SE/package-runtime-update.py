"""Package the SE update in place and prepare a reviewed external install plan."""
from pathlib import Path
from datetime import datetime, timezone
import json, shutil, struct, subprocess, sys
ROOT = Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent))
from prepare import sha, git, write
from package import record, contains, DIAG_MARKERS


def main():
    ev=ROOT/'evidence/npu-runtime-20261005';before=ev/'before';src=ROOT/'source'
    release=ROOT.parent/'Release';target=Path('C:/Emulators/Cemu_arm64')
    old=json.loads((before/'NPU-BUILD.json').read_text(encoding='utf-8'))
    prepared=json.loads((ev/'prepared.json').read_text(encoding='utf-8'))
    ref=json.loads((release/'NPU-BUILD.json').read_text(encoding='utf-8'))
    assert sha(ROOT/'NPU-BUILD.json')==prepared['parent_manifest_sha256']
    assert sha(release/'NPU-BUILD.json')==prepared['release_reference_manifest_sha256']
    assert json.loads((ROOT/'evidence/npu-runtime-20261005-result.json').read_text(encoding='utf-8-sig'))['exit_code']==0
    assert git(src,'rev-parse','HEAD')==old['base_commit']
    subprocess.run(['git','diff','--check'],cwd=src,check=True,capture_output=True)
    inventory=json.loads((before/old['source_inventory']).read_text(encoding='utf-8'))
    allowed={c['path']:c for c in prepared['changes']}
    for f in inventory:
        expected=allowed[f['path']]['after_sha256'] if f['path'] in allowed else f['sha256']
        assert sha(src/f['path'])==expected,f['path']
    for c in prepared['changes']:assert sha(src/c['path'])==c['after_sha256'],c['path']
    # Byte-identical module sources and native-image host already passed the
    # Release CPU contracts. The SE-specific audio fix matches accepted Fix1.
    for p in (release/'source/dependencies/npu-cemu').iterdir():
        if p.is_file():assert sha(src/'dependencies/npu-cemu'/p.name)==sha(p),p.name
    host='src/Cafe/HW/Latte/Renderer/Vulkan/VulkanNPU.cpp'
    assert sha(src/host)==sha(release/'source'/host)
    voice='src/Cafe/OS/libs/snd_core/ax_voice.cpp'
    assert sha(src/voice)==sha(ROOT.parent/'Release+SE-Fix1/source'/voice)
    binary=(src/'bin/Cemu_release.exe').read_bytes();pe=struct.unpack_from('<I',binary,0x3c)[0]
    assert binary[pe:pe+4]==b'PE\0\0' and struct.unpack_from('<H',binary,pe+4)[0]==0xaa64
    for marker in [old['title'],'Enhanced Sound Experience','Haptic output: eligible USB DualSense detected',
                   'Haptic playback capacity exhausted','native-resolution originals','Adaptive 1-3 frame buffering']:
        assert contains(binary,marker),marker
    for marker in DIAG_MARKERS+['Lossless.dll','LSFG 2X']:assert not contains(binary,marker),marker
    graph=(ROOT/'build/build.ninja').read_text(encoding='utf-8')
    assert '-DEMULATOR_HASH='+old['base_commit'][:7] in graph
    assert 'VulkanNPU.cpp.obj' in graph and 'VulkanLSFG.cpp.obj' not in graph
    running=subprocess.check_output(['powershell.exe','-NoProfile','-Command',
        "Get-Process -Name '*Cemu*' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Path"],text=True).splitlines()
    assert all(Path(p).parent!=ROOT/'runtime' for p in running if p.strip()),'Close the workspace SE package before local replacement'
    for f in old['files']:assert sha(ROOT/f['path'])==f['sha256'],f['path']
    for f in ref['files']:assert sha(release/f['path'])==f['sha256'],f['path']
    changes={old['executable']:src/'bin/Cemu_release.exe',
        'runtime/cemu_npu.dll':release/'runtime/cemu_npu.dll',
        'runtime/resources/ko/cemu.mo':release/'runtime/resources/ko/cemu.mo'}
    for rel,p in changes.items():shutil.copy2(p,ROOT/rel);assert sha(ROOT/rel)==sha(p)
    for f in old['files']:
        if f['path'] not in changes:assert sha(ROOT/f['path'])==f['sha256'],f['path']
    paths={f['path'] for f in inventory}|set(allowed)
    write(ROOT/old['source_inventory'],json.dumps([record(src/p,src) for p in sorted(paths)],indent=2)+'\n')
    (ROOT/'evidence/source.patch').write_bytes(subprocess.check_output(['git','diff','--binary','HEAD'],cwd=src))
    manifest=dict(old);bugfix=dict(ref['in_place_bugfix'])
    bugfix.update({'evidence':'evidence/npu-runtime-20261005','before_manifest_sha256':sha(before/'NPU-BUILD.json'),
        'before_executable_sha256':old['cemu_sha256'],'before_module_sha256':old['module_sha256'],
        'unicode_haptic_path_fix':True,'verification_reused_from_byte_identical_sources':True,'game_test_pending':True})
    manifest.update({'created_at':datetime.now(timezone.utc).isoformat(),'module_abi':3,
        'cemu_sha256':sha(ROOT/old['executable']),'module_sha256':sha(ROOT/'runtime/cemu_npu.dll'),
        'source_inventory_sha256':sha(ROOT/old['source_inventory']),'source_patch_sha256':sha(ROOT/'evidence/source.patch'),
        'build_result':'npu-runtime-20261005-result.json','in_place_bugfix':bugfix,'this_binary_game_tested':False,
        'inherited_runtime_files_identical_to_RC1':[p for p in old['inherited_runtime_files_identical_to_RC1'] if p not in changes],
        'files':[record(ROOT/f['path'],ROOT) for f in old['files']]})
    manifest['role_checks']=old['role_checks']+['paired_ABI3_host_and_module','accepted_UTF8_haptic_fix_preserved','NPU_sources_identical_to_Release']
    write(ROOT/'NPU-BUILD.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    index_path=ROOT.parent/'NPU-PROMOTION.json';shutil.copy2(index_path,before/'NPU-PROMOTION.json')
    index=json.loads(index_path.read_text(encoding='utf-8'))
    for variant in index['variants']:
        if variant['role']=='Release+SE':
            variant.update({'manifest_sha256':sha(ROOT/'NPU-BUILD.json'),'cemu_sha256':manifest['cemu_sha256'],
                'game_tested':False,'game_test_result':'2026-10-05 rebuild includes the accepted Fix1 audio correction and Release ABI3 NPU; game retest pending.',
                'in_place_bugfix':bugfix})
            variant['historical_fix_candidate']=variant.pop('fix_candidate',None)
    index['provenance']='Release and Release+SE use matching ABI3 NPU; SE includes the accepted UTF-8 haptic path fix. Models, shaders and QNN runtime remain pinned to RC1. Diagnostic variants retain ABI2.'
    write(index_path,json.dumps(index,ensure_ascii=False,indent=2)+'\n')
    assert sha(target/'Cemu-Release-NPU.exe')==ref['cemu_sha256']
    assert sha(target/'Cemu-Release-SE-NPU.exe')==old['cemu_sha256']
    files=[]
    for f in manifest['files']:
        rel=Path(f['path']).relative_to('runtime').as_posix();dst=target/rel
        assert not rel.startswith('portable/')
        existing=sha(dst) if dst.is_file() else None
        assert existing in (None,f['sha256']) or (rel=='Cemu-Release-SE-NPU.exe' and existing==old['cemu_sha256']),rel
        files.append({'relative_path':rel,'source':str(ROOT/f['path']),'sha256':f['sha256'],'bytes':f['bytes'],'before_sha256':existing})
    protected=[{'relative_path':p.name,'sha256':sha(p)} for p in target.glob('*.exe') if p.name!='Cemu-Release-SE-NPU.exe']
    plan={'target_root':str(target),'source_manifest':str(ROOT/'NPU-BUILD.json'),
        'source_manifest_sha256':sha(ROOT/'NPU-BUILD.json'),'backup_root':str(ev/'installed-before'),
        'receipt':str(ev/'installed-result.json'),'files':files,'protected_executables':protected,
        'module_abi':3,'portable_mode_created':False,'cemu_or_devices_executed':False}
    write(ev/'install-plan.json',json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'SE_ABI3_PACKAGE_VERIFIED_INSTALL_PLAN_READY','files':len(files),
        'bytes':sum(f['bytes'] for f in files),'cemu_sha256':manifest['cemu_sha256'],
        'module_sha256':manifest['module_sha256'],'target':str(target)},ensure_ascii=False))


if __name__=='__main__':main()
