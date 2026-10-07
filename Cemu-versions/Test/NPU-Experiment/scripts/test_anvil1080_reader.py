"""Offline oracle rejection tests, not a device test."""
import json
import tempfile
from pathlib import Path
import numpy as np
from read_anvil1080_result import verify_bytes, verify_profile, verify_samples

passed = []


def reject(name, action):
    try:
        action()
    except (ValueError, KeyError):
        passed.append(name)
    else:
        raise AssertionError('Accepted corrupt fixture: ' + name)


# Hand-computed 2-pixel NHWC fixture. Zero residual (q=128) produces mean RGB.
inputs = bytes([11,25,39,53,67,81,18,32,46,60,74,88])
reference = bytes([128] * 6)
rgba = bytes([32,46,60,255,39,53,67,255])
valid = inputs + reference + rgba
assert verify_bytes(valid, reference, 0, pixels=2)['max_compose_error'] == 0
passed.append('accept_hand_computed_nhwc_and_compose')
bad = bytearray(valid); bad[0] += 1
reject('reject_input_layout_corruption', lambda: verify_bytes(bad, reference, 0, pixels=2))
reject('reject_stale_input_phase', lambda: verify_bytes(valid, reference, 1, pixels=2))
bad = bytearray(valid); bad[12] = 253
reject('reject_output_poison', lambda: verify_bytes(bad, reference, 0, pixels=2))
bad = bytearray(valid); bad[18] += 4
reject('reject_bad_residual_consumption', lambda: verify_bytes(bad, reference, 0, pixels=2))
bad = bytearray(valid); bad[-1] = 0
reject('reject_bad_alpha', lambda: verify_bytes(bad, reference, 0, pixels=2))
reject('reject_truncated_diagnostic', lambda: verify_bytes(valid[:-1], reference, 0, pixels=2))

# Nonzero, distinct residual bytes cross the uint boundary in the second RGB pixel.
crossing = bytes([115,116,117,123,124,125])
correct_rgba = bytes([21,36,51,255,35,50,64,255])
assert verify_bytes(inputs + crossing + correct_rgba, crossing, 0, pixels=2)['max_compose_error'] == 0
passed.append('accept_rgb_uint_boundary_with_distinct_residuals')
wrong_reused_word = bytes([21,36,51,255,35,42,57,255])
reject('reject_first_word_reuse_across_rgb_boundary', lambda: verify_bytes(inputs + crossing + wrong_reused_word, crossing, 0, pixels=2))

event = {'cat':'Node', 'name':'QNN_kernel_time', 'args':{'provider':'QNNExecutionProvider',
    'input_type_shape':[{'uint8':[1,1080,1920,6]}], 'output_type_shape':[{'uint8':[1,1080,1920,3]}]}}
with tempfile.TemporaryDirectory(prefix='anvil1080-reader-') as folder:
    profile = Path(folder, 'profile.json')
    profile.write_text(json.dumps([event] * 6), encoding='utf-8')
    assert verify_profile(profile, 6)['qnn_only']
    passed.append('accept_complete_qnn_profile')
    reject('reject_missing_inferences', lambda: verify_profile(profile, 34))
    event['args']['provider'] = 'CPUExecutionProvider'
    profile.write_text(json.dumps([event] * 6), encoding='utf-8')
    reject('reject_cpu_fallback', lambda: verify_profile(profile, 6))

names = ('synthetic_gpu_ms','pack_gpu_ms','compose_gpu_ms','prepare_wall_ms','npu_wall_ms','compose_wall_ms',
         'serial_wall_ms','pre_submit_ms','pre_fence_ms','post_submit_ms','post_fence_ms')
samples = []
for i in range(34):
    item = {name: 0.1 for name in names}
    item.update(round=i, phase=i%3, measured=i>=4, prepare_wall_ms=1, compose_wall_ms=1, npu_wall_ms=20, serial_wall_ms=22.1)
    samples.append(item)
assert verify_samples(samples,'Measure')['serial_under_33_333_ms'] == 30
passed.append('accept_separate_measured_window')
samples[4]['measured'] = False
reject('reject_warmup_in_measured_window', lambda: verify_samples(samples,'Measure'))
samples[4]['measured'] = True; samples[4]['serial_wall_ms'] = 10
reject('reject_inconsistent_nested_timings', lambda: verify_samples(samples,'Measure'))
samples[4]['serial_wall_ms'] = float('nan')
reject('reject_nonfinite_timing', lambda: verify_samples(samples,'Measure'))
print(json.dumps({'status':'OFFLINE_READER_TESTS_PASSED', 'count':len(passed), 'tests':passed, 'device_executed':False}, indent=2))
