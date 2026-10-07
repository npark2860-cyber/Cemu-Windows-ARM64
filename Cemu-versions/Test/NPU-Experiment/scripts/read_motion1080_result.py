"""CPU-only evidence reader. It never loads Vulkan, ORT, or a QNN DLL."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import numpy as np

PIXELS = 1920 * 1080
INPUT_BYTES, OUTPUT_BYTES, RGBA_BYTES = PIXELS * 6, PIXELS * 3, PIXELS * 4
MEMHANDLE = 'Setting Qnn_Tensor_t memHandle to ORT tensor shared memory.'
RAW = 'Setting Qnn_Tensor_t clientBuf to ORT tensor memory.'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


from motion_oracle import verify_motion_bytes as verify_bytes


def verify_profile(profile, expected_count):
    events = json.loads(Path(profile).read_text(encoding='utf-8-sig'))
    kernels = [e for e in events if e.get('cat') == 'Node' and e.get('name', '').endswith('kernel_time')]
    require(len(kernels) == expected_count, 'Unexpected number of QNN kernels')
    require(all(e.get('args', {}).get('provider') == 'QNNExecutionProvider' for e in kernels), 'CPU fallback or unknown provider')
    nodes = [e for e in events if e.get('cat') == 'Node' and e.get('args', {}).get('provider')]
    require(all(e['args']['provider'] == 'QNNExecutionProvider' for e in nodes), 'Non-QNN node in profile')
    for event in kernels:
        inputs = event['args'].get('input_type_shape', [])
        outputs = event['args'].get('output_type_shape', [])
        require(inputs and inputs[0].get('uint8') == [1, 1080, 1920, 6] and
                len(outputs) == 1 and outputs[0].get('uint8') == [1, 1080, 1920, 3], 'Profile I/O mismatch')
    return {'qnn_only': True, 'kernel_events': len(kernels)}


def verify_samples(samples, mode):
    count = 4 if mode == 'Verify' else 34
    require(len(samples) == count, 'Missing chronological samples')
    names = ('synthetic_gpu_ms', 'pack_gpu_ms', 'compose_gpu_ms', 'prepare_wall_ms', 'npu_wall_ms',
             'compose_wall_ms', 'serial_wall_ms', 'pre_submit_ms', 'pre_fence_ms', 'post_submit_ms', 'post_fence_ms', 'downsample_gpu_ms', 'motion_gpu_ms', 'lookahead_gpu_ms', 'worker_submit_wall_ms', 'harness_completion_poll_ms')
    for i, sample in enumerate(samples):
        require(sample.get('round') == i and sample.get('phase') == i % 4 and
                sample.get('measured') is (mode == 'Measure' and i >= 4), 'Invalid round/phase/warmup sequence')
        require(all(isinstance(sample.get(k), (int, float)) and math.isfinite(sample[k]) and sample[k] > 0 for k in names), 'Invalid timing sample')
        component_sum = sum(sample[k] for k in ('prepare_wall_ms', 'npu_wall_ms', 'compose_wall_ms'))
        require(sample['serial_wall_ms'] + 0.001 >= component_sum, 'Wall total is smaller than sequential components')
        require(sample['prepare_wall_ms'] + 0.001 >= sample['pre_submit_ms'] + sample['pre_fence_ms'] and
                sample['compose_wall_ms'] + 0.001 >= sample['post_submit_ms'] + sample['post_fence_ms'], 'Invalid nested submit/fence timings')
    require(all(math.isfinite(s.get('producer_overlap_ms',float('nan'))) and s['producer_overlap_ms'] >= 0 for s in samples), 'Invalid overlap metric')
    if mode == 'Verify':
        return None
    measured = samples[4:]
    result = {}
    for key in names:
        values = sorted(float(s[key]) for s in measured)
        result[key] = {'mean': sum(values) / len(values), 'p50': values[14], 'p95': values[28], 'min': values[0], 'max': values[-1]}
    return {'count': 30, 'metrics': result, 'serial_under_33_333_ms': sum(s['serial_wall_ms'] < 1000 / 30 for s in measured),
            'gpu_metrics_nested_within_wall_metrics': True, 'cemu_costs_excluded': True, 'host_call_overlap_mean_ms': sum(s['producer_overlap_ms'] for s in measured)/30, 'host_call_overlap_positive_samples': sum(s['producer_overlap_ms']>0 for s in measured)}


def read_result(run_directory, manifest, exit_code, verification_directory=None):
    root = Path(run_directory).resolve()
    result = json.loads((root / 'result.json').read_text(encoding='utf-8-sig'))
    require(exit_code == 0 and result.get('status') == 'MOTION1080_COMPLETED_VERIFICATION_PENDING', 'Native probe failed: ' + result.get('reason', 'incomplete'))
    model = manifest['model']
    mode = result.get('mode')
    require(mode in ('Verify', 'Measure'), 'Unexpected mode')
    require(result.get('model') == '../' + model['model'] and result.get('rpc_library') == manifest['driver']['rpc_library'], 'Model or RPC identity mismatch')
    require(result.get('backend') == 'QnnHtp.dll' and result.get('ort_version') == '1.24.4' and result.get('cpu_fallback_disabled') is True,
            'Unexpected backend or fallback policy')
    for name, expected in {'input_shape': [1,1080,1920,6], 'output_shape': [1,1080,1920,3], 'dtype': 'uint8',
        'input_bytes': INPUT_BYTES, 'output_bytes': OUTPUT_BYTES, 'qnn_profiling_level': 'off', 'performance_mode': 'balanced',
        'ort_profiling_enabled': True, 'input_allocator': 'QnnHtpShared', 'output_allocator': 'QnnHtpShared',
        'invocation': 'direct_preallocated_run', 'gpu_texture_input_and_compose': True, 'diagnostic_readback_outside_timing': True,
        'application_cpu_writes_to_shared_payload': False, 'application_copy_free_gpu_npu_handoff': True,
        'cemu_executed': False, 'full_framegen_validated': False, 'external_memory_host': True,
        'async_worker': True, 'motion_alignment': True, 'phase_cycle': 4, 'gpu_vendor_id': 0x5143, 'matching_adreno_devices': 1}.items():
        require(result.get(name) == expected, 'Unexpected evidence field: ' + name)
    require(result.get('verbose_logging') is (mode == 'Verify'), 'Unexpected logging mode')
    require(result.get('completed_rounds') == (4 if mode == 'Verify' else 34), 'Incomplete execution')
    require((result.get('first_runs'), result.get('warmup_runs'), result.get('measured_runs')) == ((0,0,0) if mode == 'Verify' else (1,3,30)), 'Invalid iteration configuration')
    for name in ('input_memory_flags', 'output_memory_flags'):
        require(isinstance(result.get(name), int) and result[name] & 6 == 6, 'Non-coherent memory evidence')
    profile = (Path(__file__).resolve().parents[1] / 'runtime' / result['ort_profile']).resolve()
    require(profile.parent == root, 'Unexpected profile path')
    providers = verify_profile(profile, 8 if mode == 'Verify' else 34)
    timing = verify_samples(result['samples'], mode)
    console = Path(str(root) + '-console.log').read_text(encoding='utf-8-sig', errors='replace')
    checks = []
    if mode == 'Verify':
        require(console.count(MEMHANDLE) == 8 and console.count(RAW) == 8, 'Expected shared and ordinary-memory I/O bindings for four paired reference runs')
        for phase in range(4):
            reference = (root / f'reference-{phase}.bin').read_bytes()
            checks.append(verify_bytes((root / f'diagnostic-{phase}.bin').read_bytes(), reference, phase, scale=model['output_scale']))
        require(len({c['input_sha256'] for c in checks}) == 4 and len({c['output_sha256'] for c in checks}) == 4, 'Expected four distinct motion fixtures and outputs')
    else:
        require(verification_directory is not None, 'Measurement needs prior verification')
        prior = Path(verification_directory).resolve()
        # Re-read original evidence instead of trusting a mutable success label.
        read_result(prior, manifest, 0)
        reference = (prior / 'reference-1.bin').read_bytes()
        checks.append(verify_bytes((root / 'diagnostic-final.bin').read_bytes(), reference, 1, scale=model['output_scale']))
    return {'status': 'MOTION1080_PIPELINE_VERIFIED', 'mode': mode, 'profile': providers, 'checks': checks, 'timing': timing,
            'timing_scope': result['timing_scope'], 'physical_zero_copy_proven': False, 'full_framegen_validated': False,
            'real_game_quality_validated': False, 'application_copy_free_gpu_npu_handoff': True,
            'performance_validation_scope': 'Four static/translation/cut fixtures. All four audited in Verify; final phase one audited after 34 Measure rounds. No per-round readback in the measured loop.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-directory', required=True)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--exit-code', type=int, required=True)
    parser.add_argument('--verification-directory')
    args = parser.parse_args()
    try:
        manifest = json.loads(Path(args.manifest).read_text(encoding='utf-8-sig'))
        result = read_result(args.run_directory, manifest, args.exit_code, args.verification_directory)
    except Exception as error:
        result = {'status': 'VERIFICATION_FAILED', 'error': str(error)}
    Path(args.run_directory, 'verification.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result['status'] == 'MOTION1080_PIPELINE_VERIFIED' else 1)


if __name__ == '__main__':
    main()
