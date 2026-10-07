"""Package the Release+SE UTF-8 path fix; file checks only, no device execution."""
from pathlib import Path
from datetime import datetime, timezone
import difflib
import json
import shutil
import struct
import subprocess
import xml.etree.ElementTree as ET
from prepare import sha, git, write
from package import contains, copy_verified, record, DIAG_MARKERS

HERE = Path(__file__).resolve().parent
PARENT = HERE / 'Release+SE'
ROOT = HERE / 'Release+SE-Fix1'
TITLE = 'Cemu ARM64 [Release+SE | NPU | Fix 1]'


def main():
    manifest_path = ROOT / 'NPU-BUILD.json'
    assert not manifest_path.exists(), 'Preserve the packaged result'
    ev, src = ROOT / 'evidence', ROOT / 'source'
    prepared = json.loads((ev / 'prepared.json').read_text(encoding='utf-8-sig'))
    parent = json.loads((PARENT / 'NPU-BUILD.json').read_text(encoding='utf-8'))
    assert sha(PARENT / 'NPU-BUILD.json') == prepared['parent_manifest_sha256']
    result = json.loads((ev / 'build-result.json').read_text(encoding='utf-8-sig'))
    assert result['exit_code'] == 0 and result['variant'] == ROOT.name
    assert git(src, 'rev-parse', 'HEAD') == parent['base_commit'] == prepared['base_commit']
    subprocess.run(['git', 'diff', '--check'], cwd=src, check=True, capture_output=True)

    changed = {f['path']: f for f in prepared['changes']}
    inherited_inventory = json.loads((PARENT / parent['source_inventory']).read_text(encoding='utf-8'))
    assert sha(PARENT / parent['source_inventory']) == parent['source_inventory_sha256']
    for f in inherited_inventory:
        assert sha(PARENT / 'source' / f['path']) == f['sha256'], f['path']
    paths = set(git(src, 'ls-files').splitlines())
    paths.update(f['path'] for f in inherited_inventory)
    paths.update(changed)
    unchanged = 0
    delta = []
    for rel in sorted(paths):
        before, after = PARENT / 'source' / rel, src / rel
        if not before.is_file():
            continue  # gitlinks are verified by the prepared offline clone.
        assert after.is_file(), rel
        if rel in changed:
            assert sha(before) == changed[rel]['before_sha256'], rel
            assert sha(after) == changed[rel]['after_sha256'], rel
            delta.extend(difflib.unified_diff(
                before.read_text(encoding='utf-8').splitlines(keepends=True),
                after.read_text(encoding='utf-8').splitlines(keepends=True),
                fromfile='parent/' + rel, tofile='fix1/' + rel))
        else:
            assert sha(before) == sha(after), 'Unexpected source difference: ' + rel
            unchanged += 1
    assert unchanged == prepared['unchanged_source_files']
    write(ev / 'fix1-vs-parent.patch', ''.join(delta))
    (ev / 'source.patch').write_bytes(subprocess.check_output(['git', 'diff', '--binary', 'HEAD'], cwd=src))
    inventory_paths = {f['path'] for f in inherited_inventory} | set(changed)
    source_files = [record(src / p, src) for p in sorted(inventory_paths)]
    write(ev / 'source-files.json', json.dumps(source_files, indent=2) + '\n')

    exe = src / 'bin/Cemu_release.exe'
    binary = exe.read_bytes()
    offset = struct.unpack_from('<I', binary, 0x3c)[0]
    assert binary[offset:offset+4] == b'PE\0\0'
    assert struct.unpack_from('<H', binary, offset+4)[0] == 0xaa64
    for marker in [TITLE, 'NPU frame generation', 'NPU processing', '720p / Performance',
                   '1080p / Standard', 'cemu_npu.dll', 'Enhanced Sound Experience',
                   'Haptic output: eligible USB DualSense detected', 'Haptic playback capacity exhausted']:
        assert contains(binary, marker), marker
    for marker in DIAG_MARKERS + ['Lossless.dll', 'lossless.dll', 'lsfg_cemu.dll', 'LSFG 2X']:
        assert not contains(binary, marker), marker
    cache = (ROOT / 'build/CMakeCache.txt').read_text(encoding='utf-8')
    graph = (ROOT / 'build/build.ninja').read_text(encoding='utf-8')
    assert 'CEMU_ENABLE_NPU:BOOL=ON' in cache and 'CMAKE_BUILD_TYPE:STRING=Release' in cache
    assert 'VulkanNPU.cpp.obj' in graph and 'VulkanLSFG.cpp.obj' not in graph
    assert '-DEMULATOR_HASH=' + parent['base_commit'][:7] in graph

    runtime = ROOT / 'runtime'
    inherited = []
    for f in parent['files']:
        assert sha(PARENT / f['path']) == f['sha256'], f['path']
        if f['path'] == parent['executable']:
            continue
        assert f['path'].startswith('runtime/') and '/portable/' not in f['path']
        copy_verified(PARENT / f['path'], ROOT / f['path'], f['sha256'])
        inherited.append(f['path'])
    executable = 'runtime/Cemu-Release-SE-NPU-Fix1.exe'
    copy_verified(exe, ROOT / executable)

    # Use the user's CURRENT settings, not the original RC1 package seed.
    seed, portable = PARENT / 'runtime/portable', runtime / 'portable'
    assert not portable.exists(), 'Review partial settings copy before retrying'
    portable.mkdir()
    seed_records = []
    for name in ['settings.xml', 'title_list_cache.xml', 'controllerProfiles',
                 'gameProfiles', 'graphicPacks', 'shaderCache']:
        p, q = seed / name, portable / name
        if p.is_dir():
            assert not p.is_symlink() and not p.is_junction(), p
            for child in p.rglob('*'):
                assert not child.is_symlink() and not child.is_junction(), child
            shutil.copytree(p, q)
        elif p.is_file():
            shutil.copy2(p, q)
        copied = [q] if q.is_file() else [f for f in q.rglob('*') if f.is_file()]
        for file in copied:
            rel = file.relative_to(portable)
            assert sha(file) == sha(seed / rel), 'Settings changed during copy: ' + str(rel)
            seed_records.append(record(file, portable))
    settings = ET.parse(portable / 'settings.xml').getroot()
    mlc = settings.findtext('mlc_path')
    assert mlc == ET.parse(seed / 'settings.xml').getroot().findtext('mlc_path')
    assert mlc and not (portable / 'mlc01').exists()
    rules = portable / 'graphicPacks/downloadedGraphicPacks/BreathOfTheWild/DualSenseExperience/rules.txt'
    assert sha(rules) == '7a932d759586dfd8cf0be113a358c52af3e1123d38e7d3c7cf5be14bf9e606df'
    write(ev / 'portable-seed.json', json.dumps({
        'copied_from': str(seed), 'mutable_after_launch': True,
        'shared_mlc_path': mlc, 'mlc_copied_or_modified': False,
        'files': seed_records}, ensure_ascii=False, indent=2) + '\n')

    freeze = 'freeze-20260929-191547'
    shutil.copytree(PARENT / 'evidence' / freeze, ev / freeze)
    cpu_result = (ev / freeze / 'cpu-probe/result.txt').read_text(encoding='utf-8')
    assert 'files=12 old_throws=12 old_failed=12 checks=3386' in cpu_result
    manifest = {
        'created_at': datetime.now(timezone.utc).isoformat(),
        'status': 'CPU_REGRESSION_AND_LOCAL_PACKAGE_VERIFIED_GAME_TEST_PENDING',
        'role': 'Release+SE', 'candidate': 'Fix1', 'title': TITLE,
        'base_commit': parent['base_commit'], 'source_branch': git(src, 'branch', '--show-current'),
        'parent_manifest': '../Release+SE/NPU-BUILD.json',
        'parent_manifest_sha256': prepared['parent_manifest_sha256'],
        'parent_executable_sha256': parent['cemu_sha256'],
        'executable': executable, 'cemu_sha256': sha(ROOT / executable),
        'source_inventory': 'evidence/source-files.json',
        'source_inventory_sha256': sha(ev / 'source-files.json'),
        'source_patch_sha256': sha(ev / 'source.patch'),
        'source_changes_from_parent': prepared['changes'], 'unchanged_source_files': unchanged,
        'build_result': 'evidence/build-result.json', 'architecture': 'ARM64',
        'fix': 'Explicit UTF-8 to filesystem path conversion for SE BNVIB haptic routes.',
        'cpu_regression_result': cpu_result.strip(),
        'module_abi': parent['module_abi'], 'module_sha256': parent['module_sha256'],
        'profiles': parent['profiles'], 'enabled_by_default': False,
        'lossless_dll_required': False, 'legacy_gpu_lsfg_linked': False,
        'inherited_runtime_files_identical_to_parent': inherited,
        'shared_mlc_path': mlc, 'mlc_copied_or_modified': False,
        'this_binary_game_tested': False, 'agent_executed_gpu_npu_cemu_controller': False,
        'files': [record(p, ROOT) for p in sorted(runtime.rglob('*'))
                  if p.is_file() and portable not in p.parents]
    }
    write(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': manifest['status'], 'executable': str(ROOT / executable),
                      'sha256': manifest['cemu_sha256'], 'unchanged_source_files': unchanged,
                      'runtime_files': len(manifest['files']), 'mlc_path': mlc}, ensure_ascii=False))


if __name__ == '__main__':
    main()
