"""Verify and replace this Release package in place. Does not launch Cemu/devices."""
from pathlib import Path
from datetime import datetime, timezone
import difflib
import json
import os
import shutil
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from prepare import sha, git, write
from package import record, contains, DIAG_MARKERS


def main():
    ev = ROOT / 'evidence/cadence-native-20261001'
    before = ev / 'before'
    old = json.loads((before / 'NPU-BUILD.json').read_text(encoding='utf-8'))
    assert sha(ROOT / 'NPU-BUILD.json') == sha(before / 'NPU-BUILD.json'), 'Package already changed; review before retry'
    for name in ['evidence/cadence-native-ui-result.json',
                 'evidence/cadence-native-20261001/module-build-final-result.json']:
        assert json.loads((ROOT / name).read_text(encoding='utf-8-sig'))['exit_code'] == 0
    cpu = (ev / 'module-build-final.log').read_text(encoding='utf-8-sig')
    assert '"checks":4385' in cpu and 'checks=7' in cpu and 'checks=27' in cpu
    assert 'PASSED checks=72' in (ev / 'native-contract.log').read_text(encoding='utf-8-sig')
    src = ROOT / 'source'
    subprocess.run(['git', 'diff', '--check'], cwd=src, check=True, capture_output=True)
    assert git(src, 'rev-parse', 'HEAD') == old['base_commit']
    updates = {
        old['executable']: ROOT / 'source/bin/Cemu_release.exe',
        'runtime/cemu_npu.dll': ROOT / 'build/npu-module/cemu_npu.dll',
        'runtime/resources/ko/cemu.mo': ROOT / 'build/npu-module/cemu-ko.mo',
    }
    for rel, path in updates.items():
        if not rel.endswith(('.exe', '.dll')):
            continue
        binary = path.read_bytes(); offset = struct.unpack_from('<I', binary, 0x3c)[0]
        assert binary[offset:offset+4] == b'PE\0\0' and struct.unpack_from('<H', binary, offset+4)[0] == 0xaa64, rel
        assert sha(path) != next(f['sha256'] for f in old['files'] if f['path'] == rel)
    binary = updates[old['executable']].read_bytes()
    for marker in [old['title'], 'native-resolution originals', 'Adaptive 1-3 frame buffering',
                   'Original frames retain their output resolution.', '720p / Performance', 'cemu_npu.dll']:
        assert contains(binary, marker), marker
    for marker in DIAG_MARKERS + ['LSFG 2X', 'Lossless.dll', 'lossless.dll']:
        assert not contains(binary, marker), marker
    graph = (ROOT / 'build/build.ninja').read_text(encoding='utf-8')
    assert 'VulkanNPU.cpp.obj' in graph and 'VulkanLSFG.cpp.obj' not in graph
    assert '-DEMULATOR_HASH=' + old['base_commit'][:7] in graph
    # Validate every old fixed asset before the first replacement.
    for f in old['files']:
        assert sha(ROOT / f['path']) == f['sha256'], f['path']
    inventory = json.loads((before / 'evidence/source-files.json').read_text(encoding='utf-8'))
    expected = {
        'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanNPU.cpp', 'src/gui/wxgui/GeneralSettings2.cpp',
        'dependencies/npu-cemu/buffered_timeline.h', 'dependencies/npu-cemu/npu_cemu.h',
        'dependencies/npu-cemu/npu_cemu.cpp', 'dependencies/npu-cemu/test_buffered_timeline.cpp',
        'i18n/npu/npu.pot', 'i18n/npu/ko.po'}
    actual = {f['path'] for f in inventory if sha(src / f['path']) != f['sha256']}
    assert actual == expected, actual ^ expected
    new_source = 'dependencies/npu-cemu/frame_contract.h'
    patch = []
    for rel in sorted(actual):
        a, b = before / 'source' / rel, src / rel
        patch.extend(difflib.unified_diff(a.read_text(encoding='utf-8').splitlines(keepends=True),
            b.read_text(encoding='utf-8').splitlines(keepends=True), fromfile='before/' + rel, tofile='after/' + rel))
    patch.extend(difflib.unified_diff([], (src / new_source).read_text(encoding='utf-8').splitlines(keepends=True),
        fromfile='/dev/null', tofile='after/' + new_source))
    write(ev / 'patch-vs-deployed-source.diff', ''.join(patch))
    # Avoid replacing a running emulator or its loaded module. Never terminate it.
    processes = subprocess.check_output(['powershell.exe', '-NoProfile', '-Command',
        "@(Get-Process -Name '*Cemu*' -ErrorAction SilentlyContinue).Count"], text=True).strip()
    assert processes == '0', 'Close Cemu before replacing this package'
    staged = ROOT / 'build/npu-module/deploy'
    staged.mkdir(exist_ok=True)
    for rel, path in updates.items():
        shutil.copy2(path, staged / Path(rel).name)
    # Install the host last. Either ABI mismatch rejects FG and keeps originals.
    for rel in ['runtime/cemu_npu.dll', 'runtime/resources/ko/cemu.mo', old['executable']]:
        os.replace(staged / Path(rel).name, ROOT / rel)
        assert sha(ROOT / rel) == sha(updates[rel]), rel
    for f in old['files']:
        if f['path'] not in updates:
            assert sha(ROOT / f['path']) == f['sha256'], f['path']

    paths = {f['path'] for f in inventory} | {new_source}
    write(ROOT / old['source_inventory'], json.dumps([record(src / p, src) for p in sorted(paths)], indent=2) + '\n')
    (ROOT / 'evidence/source.patch').write_bytes(subprocess.check_output(['git', 'diff', '--binary', 'HEAD'], cwd=src))
    manifest = dict(old)
    manifest.update({
        'created_at': datetime.now(timezone.utc).isoformat(),
        'cemu_sha256': sha(ROOT / old['executable']), 'module_sha256': sha(ROOT / 'runtime/cemu_npu.dll'),
        'module_abi': 3, 'build_result': 'cadence-native-ui-result.json',
        'source_inventory_sha256': sha(ROOT / old['source_inventory']),
        'source_patch_sha256': sha(ROOT / 'evidence/source.patch'),
        'this_binary_game_tested': False, 'agent_executed_gpu_npu_cemu': False,
        'in_place_bugfix': {
            'name': 'native-originals-and-bounded-GPU-lag-buffering',
            'evidence': 'evidence/cadence-native-20261001',
            'before_manifest_sha256': sha(before / 'NPU-BUILD.json'),
            'before_executable_sha256': old['cemu_sha256'], 'before_module_sha256': old['module_sha256'],
            'original_resolution_preserved': True, 'buffered_source_frames': [1, 3],
            'buffer_reduction': 'resets on toggle, resize, or capture gap; no mid-session frame skipping',
            'native_history_images': 4, 'job_slots': 5, 'cpu_checks': 4491,
            'cpu_native_copy_check_uses_mocked_Vulkan': True, 'game_test_pending': True,
            'same_executable_path': True, 'portable_settings_and_saves_modified': False,
        },
        'inherited_runtime_files_identical_to_RC1': [p for p in old['inherited_runtime_files_identical_to_RC1'] if p not in updates],
        'files': [record(ROOT / f['path'], ROOT) for f in old['files']],
    })
    manifest['role_checks'] = old['role_checks'] + ['native_original_copy_and_adaptive_timeline_CPU_contracts_verified', 'paired_ABI3_host_and_module']
    write(ROOT / 'NPU-BUILD.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    index_path = ROOT.parent / 'NPU-PROMOTION.json'
    shutil.copy2(index_path, before / 'NPU-PROMOTION.json')
    index = json.loads(index_path.read_text(encoding='utf-8'))
    for variant in index['variants']:
        if variant['role'] == 'Release':
            variant.update({'manifest_sha256': sha(ROOT / 'NPU-BUILD.json'),
                'cemu_sha256': manifest['cemu_sha256'], 'game_tested': False,
                'in_place_bugfix': manifest['in_place_bugfix']})
    index['release_in_place_bugfix_game_test_pending'] = True
    write(index_path, json.dumps(index, ensure_ascii=False, indent=2) + '\n')
    result = {'status': 'RELEASE_PATCHED_IN_PLACE_GAME_TEST_PENDING',
        'executable': str(ROOT / old['executable']), 'cemu_sha256': manifest['cemu_sha256'],
        'module_sha256': manifest['module_sha256'], 'cpu_checks': 4491,
        'unchanged_other_runtime_files': len(old['files']) - len(updates),
        'cemu_gpu_npu_executed': False}
    write(ev / 'deployed.json', json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
