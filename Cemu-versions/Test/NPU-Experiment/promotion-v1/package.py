"""Assemble a separate, immutable release candidate; never launch device code."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, shutil, struct, subprocess
HERE=Path(__file__).resolve().parent
LAB=HERE.parent
TEST=LAB.parent
SOURCE=TEST/'LSFG-Release/source'
BASE=TEST/'NPU-Release-v4'
PACKAGE=TEST/'NPU-Release-RC1'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def copy(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(src,dst)
def text(path,s):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(s,encoding='utf-8',newline='\n')

def main():
    assert not PACKAGE.exists(), 'Preserve existing candidate package'
    base=json.loads((BASE/'NPU-RELEASE-BUILD.json').read_text(encoding='utf-8-sig'))
    for record in base['files']:
        assert sha(BASE/record['path'])==record['sha256'],record['path']
    tests=json.loads((LAB/'evidence/npu-cpu-tests-rc1.json').read_text(encoding='utf-8-sig'))
    assert len(tests)==4 and all(t['exit_code']==0 for t in tests)
    assets=json.loads((HERE/'asset-checks.json').read_text())
    assert assets['1080p_model_and_shaders_byte_identical_to_v4']
    cache=(TEST/'LSFG-Release/build/CMakeCache.txt').read_text(encoding='utf-8-sig')
    assert 'CEMU_ENABLE_NPU:BOOL=ON' in cache and 'CEMU_ENABLE_LSFG:' not in cache
    assert 'CMAKE_BUILD_TYPE:STRING=Release' in cache
    log=(LAB/'evidence/cemu-npu-build-rc1.log').read_text(encoding='utf-8-sig')
    assert 'FAILED:' not in log and 'Linking CXX executable' in log and 'Cemu_release.exe' in log
    executable=SOURCE/'bin/Cemu_release.exe'
    binary=executable.read_bytes(); pe=struct.unpack_from('<I',binary,60)[0]
    assert struct.unpack_from('<H',binary,pe+4)[0]==0xaa64
    assert b'NPU RC1 - Release - 1080p/720p' in binary and b'[NPU] READY/OFF' in binary
    assert b'Lossless.dll' not in binary and b'LSFG 2x frame generation' not in binary
    for forbidden in [b'ARM64 Diagnostics',b'[ADRENO_DIAG]',b'[CEMU_DIAG]',b'[GPU_QUERY_VIS]',b'[PS_INPUT_LINKAGE]']:
        assert forbidden not in binary, 'Release role marker mismatch: '+repr(forbidden)
    skip={'runtime/cemu_npu.dll','runtime/module-smoke-probe.exe','runtime/anvil-1080p-u8nhwc.onnx',base['executable']}
    for record in base['files']:
        rel=record['path']
        if not rel.startswith('runtime/') or rel in skip or rel.startswith('runtime/shaders/'): continue
        copy(BASE/rel,PACKAGE/rel)
    copy(executable,PACKAGE/'runtime/Cemu-NPU-Release.exe')
    for name in ['cemu_npu.dll','module-smoke-probe.exe']:
        copy(HERE/'build'/name,PACKAGE/'runtime'/name)
    shutil.copytree(HERE/'assets/npu',PACKAGE/'runtime/npu')
    portable=PACKAGE/'runtime/portable';portable.mkdir()
    for name in ['settings.xml','title_list_cache.xml','controllerProfiles','gameProfiles','graphicPacks']:
        source=BASE/'runtime/portable'/name
        if source.is_dir(): shutil.copytree(source,portable/name)
        elif source.is_file(): copy(source,portable/name)
    # Retain both existing model/shader and source provenance, independent of
    # future working-tree changes. Baseline binaries and saved games stay put.
    changed=subprocess.check_output(['git','diff','--name-only','-z'],cwd=SOURCE).decode().split('\0')
    changed += ['src/Cafe/HW/Latte/Renderer/Vulkan/VulkanNPU.cpp','dependencies/npu-cemu/npu_cemu.h']
    for rel in sorted(set(filter(None,changed))):
        if (SOURCE/rel).is_file(): copy(SOURCE/rel,PACKAGE/'source-overlay'/rel)
    for p in HERE.iterdir():
        if p.is_file(): copy(p,PACKAGE/'module-source'/p.name)
    shutil.copytree(HERE/'shader-sources',PACKAGE/'module-source/shader-sources')
    for name in ['npu-cpu-tests-rc1.json','npu-module-build-rc1.log','npu-probe-build-rc1.log','npu-cpu-build-rc1.log','cemu-npu-build-rc1.log']:
        copy(LAB/'evidence'/name,PACKAGE/'evidence'/name)
    copy(HERE/'asset-checks.json',PACKAGE/'evidence/asset-checks.json')
    copy(LAB/'flow-cache-v4/probe_process.ps1',PACKAGE/'probe_process.ps1')
    for name in ['README.md','verify-build.ps1','run-module-check.ps1']:
        copy(HERE/'package-files'/name,PACKAGE/name)
    files=[]
    for p in sorted(PACKAGE.rglob('*')):
        if not p.is_file() or p.is_relative_to(portable): continue
        files.append({'path':p.relative_to(PACKAGE).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)})
    manifest={'created_at':datetime.now(timezone.utc).isoformat(),'status':'BUILT_DEVICE_TEST_PENDING',
        'variant':'Release / NPU RC1 / 1080p and 720p','base_commit':base['base_commit'],
        'base_manifest_sha256':sha(BASE/'NPU-RELEASE-BUILD.json'),'base_package':'NPU-Release-v4',
        'executable':'runtime/Cemu-NPU-Release.exe','cemu_sha256':sha(PACKAGE/'runtime/Cemu-NPU-Release.exe'),
        'module_abi':2,'module_sha256':sha(PACKAGE/'runtime/cemu_npu.dll'),
        'npu_driver':base['npu_driver'],'gpu_driver':base['gpu_driver'],
        'profiles':[{'height':1080,'width':1920,'mode':'Standard'},{'height':720,'width':1280,'mode':'Performance'}],
        'profile_changes_apply':'next game start','default_profile':1080,'enabled_by_default':False,
        'legacy_gpu_lsfg_linked':False,'lossless_dll_required':False,'cpu_tests':tests,
        'shared_mlc_path':base['shared_mlc_path'],'portable_config_seed':'Independent v4 copy; existing MLC path preserved; saved games not copied or modified',
        'device_executed_by_agent':False,'new_720p_device_validated':False,'game_test_pending':True,
        'four_variant_rollout_complete':False,'files':files,
        'limitations':'New ABI/profile resource wiring requires device validation. Prior user game test was v4/1080p. 720p model uses unchanged synthetic quantization scales; no new game-quality or scanout-cadence validation. NPU ON processes both buffered real and generated frames at the chosen resolution.'}
    text(PACKAGE/'NPU-RELEASE-BUILD.json',json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'status':manifest['status'],'executable':str(PACKAGE/manifest['executable']),'sha256':manifest['cemu_sha256'],'pinned_files':len(files),'gpu_npu_executed':False},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
