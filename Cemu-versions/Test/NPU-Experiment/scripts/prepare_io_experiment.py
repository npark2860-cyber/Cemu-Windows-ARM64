"""Derive U8-I/O and channel-last variants of the measured 1080p QDQ model.
Only small one-thread CPU equivalence checks run here; no NPU provider is loaded.
"""
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import collections
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "quant-tools"), str(ROOT / "model-tools")]
import numpy as np
import onnx
import onnxruntime as ort
from onnx import TensorProto, numpy_helper
from onnxruntime.quantization.execution_providers.qnn.preprocess import update_io_to_channel_last
from onnxruntime.quantization.onnx_model import ONNXModel
from prepare_int8_experiment import cpu_options
from prepare_resolution_models import require, dims, sha

SOURCE_FOLDER = ROOT / "evidence/int8-prep-20260929-071500-022764"
SOURCE_SHA = "ec1abb0d5921a5117ff247bc7803287b44be38423af8e84393d8553cee84d95f"


def boundary_params(model):
    ins = [n for n in model.graph.node if "input" in n.input]
    outs = [n for n in model.graph.node if "output" in n.output]
    require(len(ins) == len(outs) == 1, "Unexpected I/O fanout")
    q, dq = ins[0], outs[0]
    require(q.op_type == "QuantizeLinear" and dq.op_type == "DequantizeLinear", "Unexpected boundary operations")
    initializers = {v.name: v for v in model.graph.initializer}
    require(initializers[q.input[2]].data_type == initializers[dq.input[2]].data_type == TensorProto.UINT8,
            "Only U8 boundaries supported")
    return q, dq, {"input_scale": float(numpy_helper.to_array(initializers[q.input[1]])),
                   "input_zero_point": int(numpy_helper.to_array(initializers[q.input[2]])),
                   "output_scale": float(numpy_helper.to_array(initializers[dq.input[1]])),
                   "output_zero_point": int(numpy_helper.to_array(initializers[dq.input[2]]))}


def u8_boundary(source):
    model = deepcopy(source)
    q, dq, params = boundary_params(model)
    quantized_input, quantized_output = q.output[0], dq.input[0]
    remove_names = {q.name, dq.name}
    nodes = [deepcopy(n) for n in model.graph.node if n.name not in remove_names]
    require(len(nodes) == len(model.graph.node) - 2, "Ambiguous boundary node names")
    for node in nodes:
        for i, name in enumerate(node.input):
            if name == quantized_input:
                node.input[i] = "input"
            elif name == quantized_output:
                node.input[i] = "output"
        for i, name in enumerate(node.output):
            if name == quantized_output:
                node.output[i] = "output"
    del model.graph.node[:]
    model.graph.node.extend(nodes)
    del model.graph.value_info[:]
    model.graph.input[0].type.tensor_type.elem_type = TensorProto.UINT8
    model.graph.output[0].type.tensor_type.elem_type = TensorProto.UINT8
    require(list(model.graph.initializer) == list(source.graph.initializer), "Weights or scales changed")
    onnx.checker.check_model(model, full_check=True)
    return onnx.shape_inference.infer_shapes(model, strict_mode=True, data_prop=True), params


def nhwc_boundary(nchw):
    model = deepcopy(nchw)
    update_io_to_channel_last(model, ["input"], ["output"])
    ONNXModel(model).topological_sort()
    onnx.checker.check_model(model, full_check=True)
    require(list(model.graph.initializer) == list(nchw.graph.initializer), "Layout transform changed weights/scales")
    # These boundary Transposes are candidates for cancellation with the NPU layout pass.
    # Their runtime elimination is an experiment, not a property guaranteed by this file.
    return onnx.shape_inference.infer_shapes(model, strict_mode=True, data_prop=True)


def cpu_session(model):
    result = ort.InferenceSession(model.SerializeToString(), cpu_options(), providers=["CPUExecutionProvider"])
    require(result.get_providers() == ["CPUExecutionProvider"], "Unexpected CPU-check provider")
    return result


def main():
    source_path = SOURCE_FOLDER / "anvil-1080p-synthetic-u8u8.onnx"
    require(sha(source_path) == SOURCE_SHA, "Measured source model changed")
    source = onnx.load(source_path)
    nchw, params = u8_boundary(source)
    require(params["input_zero_point"] == 0 and abs(params["input_scale"] - 1 / 255) < 1e-9,
            "Probe's deterministic U8 values would not match baseline input quantization")
    nhwc = nhwc_boundary(nchw)
    folder = ROOT / "evidence" / ("io-prep-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    folder.mkdir()
    models = []
    for name, model in [("U8NCHW", nchw), ("U8NHWC", nhwc)]:
        path = folder / ("anvil-1080p-" + name.lower() + ".onnx")
        onnx.save(model, path)
        models.append({"variant": name, "model": path.relative_to(ROOT).as_posix(), "sha256": sha(path),
                       "input_shape": dims(model.graph.input[0]), "output_shape": dims(model.graph.output[0]),
                       "host_dtype": "uint8", "input_bytes": 12441600, "output_bytes": 6220800,
                       "node_count": len(model.graph.node), "operators": dict(collections.Counter(n.op_type for n in model.graph.node)),
                       "weights_and_scales_unchanged": True, **params})

    # Test the exact transformations on the previously calibrated tiny proxy.
    # The full model is not evaluated during preparation.
    proxy = onnx.load(SOURCE_FOLDER / "proxy-u8u8.onnx")
    proxy_nchw, proxy_params = u8_boundary(proxy)
    require(proxy_params == params, "Proxy and full-resolution boundary quantization differ")
    proxy_nhwc = nhwc_boundary(proxy_nchw)
    ref_session, nchw_session, nhwc_session = map(cpu_session, [proxy, proxy_nchw, proxy_nhwc])
    shape = tuple(dims(proxy.graph.input[0]))
    count = int(np.prod(shape))
    rng = np.random.default_rng(20260929)
    patterns = [((np.arange(count, dtype=np.uint32) * 7 + 11) % 251).astype(np.uint8).reshape(shape),
                rng.integers(0, 256, shape, dtype=np.uint8),
                np.where(np.indices(shape)[-1] % 16 < 8, 0, 255).astype(np.uint8)]
    checks = []
    for i, x in enumerate(patterns):
        float_x = x.astype(np.float32) / np.float32(255.0)
        expected = ref_session.run(None, {"input": float_x})[0]
        a = nchw_session.run(None, {"input": x})[0]
        b = nhwc_session.run(None, {"input": np.ascontiguousarray(x.transpose(0, 2, 3, 1))})[0]
        b_nchw = b.transpose(0, 3, 1, 2)
        require(np.array_equal(a, b_nchw), "NHWC mapping changed the quantized result")
        restored = (a.astype(np.float32) - params["output_zero_point"]) * np.float32(params["output_scale"])
        max_error = float(np.max(np.abs(restored - expected)))
        require(np.all(np.isfinite(restored)) and max_error <= 1e-7, "U8 boundary changed the dequantized result")
        checks.append({"pattern": i, "u8_nchw_nhwc_bitwise_equal": True,
                       "max_abs_error_vs_existing_qdq": max_error})
    report = {"status": "IO_VARIANTS_PREPARED_NOT_NPU_TESTED", "source_model": source_path.relative_to(ROOT).as_posix(),
              "source_sha256": SOURCE_SHA, "models": models, "cpu_proxy_shape": list(shape),
              "cpu_threads": 1, "equivalence_checks": checks, "npu_executed": False,
              "full_resolution_inference_executed": False, "game_quality_validated": False,
              "note": "Original synthetic calibration/weights/scales retained. External quantization, packing, output dequantization and layout conversion are outside probe Run timing. NHWC speed benefit depends on QNN/ORT optimization and is not yet verified."}
    (folder / "preparation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
