"""Remove a mathematically empty reflect Pad rejected by QNN at 720p.
Preserve the first candidate and its metadata for the failed run's audit trail.
"""
from copy import deepcopy
import json
import prepare_resolution_models as prep
from onnx import checker, shape_inference

root = prep.ROOT
metadata_path = root / 'evidence/resolution-models.json'
original_metadata = root / 'evidence/resolution-models-v1.json'
if not original_metadata.exists():
    original_metadata.write_bytes(metadata_path.read_bytes())
metadata = json.loads(original_metadata.read_text(encoding='utf-8-sig'))
record = next(x for x in metadata['models'] if x['resolution'] == '720p')
source = prep.onnx.load(prep.ORIGINAL)
before = prep.onnx.load(root / record['path'])
prep.require(prep.sha(root / record['path']) == record['sha256'], 'Candidate hash mismatch')
checks = prep.validate(source, before, 720, 1280)
prep.require(checks['pads'] == [0] * 8, 'Only a zero-width pad may be removed')
after = deepcopy(before)
del after.graph.node[:48]
prep.require(after.graph.node[0].input[0] == '/Pad_output_0', 'Unexpected graph boundary')
after.graph.node[0].input[0] = 'input'
restored = deepcopy(after.graph.node[0])
restored.input[0] = '/Pad_output_0'
prep.require(restored == before.graph.node[48], 'First Conv changed beyond its input name')
prep.require(list(after.graph.node[1:]) == list(before.graph.node[49:]), 'CNN or crop changed')
prep.require(list(after.graph.initializer) == list(before.graph.initializer), 'Weights changed')
checker.check_model(after, full_check=True)
inferred = shape_inference.infer_shapes(after, strict_mode=True, data_prop=True)
prep.require(prep.dims(inferred.graph.output[0]) == [1, 3, 720, 1280], 'Wrong output shape')
new_path = root / 'models/anvil-small-720p-fp32-nopad.onnx'
prep.save_immutable(new_path, after.SerializeToString())
record.update(path=new_path.relative_to(root).as_posix(), sha256=prep.sha(new_path),
              no_op_pad_removed=True, node_count=len(after.graph.node),
              equivalent_to='models/anvil-small-720p-fp32.onnx',
              change_reason='QNN rejects reflect Pad when every pad width is zero; bypass exact identity operation')
metadata['revision'] = 2
metadata_path.write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
(root / 'evidence/720p-zero-pad-repair.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print(json.dumps(record, indent=2))
