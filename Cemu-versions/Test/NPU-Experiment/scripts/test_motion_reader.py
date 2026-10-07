"""CPU-only checks for motion-probe profiling and measured-window gates."""
import copy
import json
import tempfile
from pathlib import Path
from read_motion1080_result import verify_profile, verify_samples

passed = []
def reject(name, action):
    try:
        action()
    except (ValueError, KeyError):
        passed.append(name)
    else:
        raise AssertionError('Accepted corrupt fixture: ' + name)

event = {'cat': 'Node', 'name': 'QNN_kernel_time', 'args': {
    'provider': 'QNNExecutionProvider',
    'input_type_shape': [{'uint8': [1,1080,1920,6]}],
    'output_type_shape': [{'uint8': [1,1080,1920,3]}]}}
with tempfile.TemporaryDirectory(prefix='motion1080-reader-') as folder:
    profile = Path(folder, 'profile.json')
    profile.write_text(json.dumps([event]*8), encoding='utf-8')
    assert verify_profile(profile, 8)['qnn_only']
    passed.append('accept_four_shared_and_four_reference_inferences')
    reject('reject_missing_measurement_inferences', lambda: verify_profile(profile, 34))
    event['args']['provider'] = 'CPUExecutionProvider'
    profile.write_text(json.dumps([event]*8), encoding='utf-8')
    reject('reject_cpu_fallback', lambda: verify_profile(profile, 8))

names = ('synthetic_gpu_ms','pack_gpu_ms','compose_gpu_ms','pre_submit_ms','pre_fence_ms',
    'post_submit_ms','post_fence_ms','downsample_gpu_ms','motion_gpu_ms','lookahead_gpu_ms',
    'worker_submit_wall_ms','harness_completion_poll_ms')
samples = []
for i in range(34):
    item = {name: 0.1 for name in names}
    item.update(round=i, phase=i%4, measured=i>=4, prepare_wall_ms=1, compose_wall_ms=1,
                npu_wall_ms=20, serial_wall_ms=22.1, producer_overlap_ms=0.25)
    samples.append(item)
stats = verify_samples(samples, 'Measure')
assert stats['count'] == 30 and stats['host_call_overlap_positive_samples'] == 30
passed.append('accept_four_phase_measured_window_and_host_overlap')
for name, key, value in (
    ('reject_old_three_phase_sequence','phase',1),
    ('reject_warmup_in_measured_window','measured',False),
    ('reject_missing_motion_timing','motion_gpu_ms',0),
    ('reject_inconsistent_total','serial_wall_ms',10),
    ('reject_nan_npu_timing','npu_wall_ms',float('nan')),
    ('reject_negative_overlap','producer_overlap_ms',-0.1)):
    bad = copy.deepcopy(samples); bad[4][key] = value
    reject(name, lambda: verify_samples(bad, 'Measure'))
for sample in samples:
    sample['producer_overlap_ms'] = 0
assert verify_samples(samples, 'Measure')['host_call_overlap_positive_samples'] == 0
passed.append('accept_zero_overlap_without_claiming_parallelism')
print(json.dumps({'status':'OFFLINE_MOTION_READER_TESTS_PASSED', 'count':len(passed),
                  'tests':passed, 'device_executed':False}, indent=2))
