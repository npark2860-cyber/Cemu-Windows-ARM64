"""Rebuild the ARM64 preview on Windows using the local Zig cross compiler."""
import os
import pathlib
import subprocess
import sys

root = pathlib.Path(__file__).resolve().parent.parent
task = root.parent.parent
zig = task / 'work/zig-tool/ziglang/zig.exe'
qnn = '--qnn' in sys.argv
out = task / ('work/arm64-qnn-build' if qnn else 'work/arm64-build')
out.mkdir(exist_ok=True)
env = os.environ.copy()
env['ZIG_GLOBAL_CACHE_DIR'] = str(task / 'work/zig-cache')
env['ZIG_LOCAL_CACHE_DIR'] = str(task / 'work/zig-local-cache')
base = [str(zig), 'c++', '-target', 'aarch64-linux-gnu.2.28', '-mcpu=generic',
        '-std=c++20', '-O2', '-pthread', '-DHEXSCALE_PREVIEW_BUILD', '-I', str(root / 'daemon/include')]
if qnn:
    base += ['-DHEXSCALE_ENABLE_QNN', '-I', str(task / 'work/qairt-sdk/qairt/2.45.0.260326/include/QNN')]
targets = {
    'hexscaled': ['daemon/src/main.cpp', 'daemon/src/qnn_backend.cpp', 'daemon/src/fastrpc_session_windows.cpp', 'daemon/src/ipc_server.cpp'],
    'hexscale-cli': ['cli/src/main.cpp', 'daemon/src/qnn_backend.cpp'],
    'hexscale-cpu-test': ['tests/cpu_output.cpp', 'daemon/src/qnn_backend.cpp'],
    'libVkLayer_hexscale.so': ['layer/src/layer_entry.cpp'],
}
targets['hexscaled'] += ['daemon/src/frame_processor.cpp']
targets['hexscale-frame-test'] = ['tests/frame_processing.cpp', 'daemon/src/frame_processor.cpp', 'daemon/src/qnn_backend.cpp']
targets['hexscale-interpolate'] = ['cli/src/interpolate.cpp', 'layer/src/motion_vulkan.cpp', 'daemon/src/frame_processor.cpp', 'daemon/src/qnn_backend.cpp']
base += ['-I', str(task / 'work/vulkan-headers/include'), '-I', str(root / 'layer/include')]
targets['hexscale-qnn-probe'] = ['tests/qnn_probe.cpp']
for name, sources in targets.items():
    if not name.endswith('.so'): sources += ['daemon/src/qnn_runtime.cpp']
    flags = []
    if name.endswith('.so'):
        flags = ['-shared', '-fPIC', '-DVK_USE_PLATFORM_WAYLAND_KHR', '-I', str(task / 'work/vulkan-headers/include')]
    command = base + flags + [str(root / s) for s in sources] + ['-ldl', '-o', str(out / name)]
    print('Compiling', name, flush=True)
    with (out / (name + '.build.log')).open('w', encoding='utf-8') as log:
        log.write(subprocess.list2cmdline(command) + '\n')
        log.flush()
        result = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        print((out / (name + '.build.log')).read_text(encoding='utf-8'))
        sys.exit(result.returncode)
    print('Built', name, (out / name).stat().st_size, 'bytes', flush=True)
