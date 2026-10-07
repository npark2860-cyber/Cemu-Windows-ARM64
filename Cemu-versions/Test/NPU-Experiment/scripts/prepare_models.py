"""Offline graph validation/generation only. Does not import a device runtime."""
from pathlib import Path
import collections
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "model-tools"))
import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper


def save_checked(model, name):
    onnx.checker.check_model(model, full_check=True)
    path = ROOT / "models" / name
    onnx.save(model, path)
    return {"path": "models/" + name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def average_model(quantized):
    shape_in, shape_out = [1, 6, 32, 32], [1, 3, 32, 32]
    weights = np.zeros([3, 6, 1, 1], dtype=np.float32)
    for channel in range(3):
        weights[channel, channel, 0, 0] = 0.5
        weights[channel, channel + 3, 0, 0] = 0.5
    if quantized:
        initializers = [
            numpy_helper.from_array(np.array(1 / 255, np.float32), "scale"),
            numpy_helper.from_array(np.array(0, np.uint8), "zero"),
            numpy_helper.from_array((weights * 2).astype(np.uint8), "weights_q"),
            numpy_helper.from_array(np.array(0.5, np.float32), "weight_scale"),
        ]
        nodes = [
            helper.make_node("DequantizeLinear", ["input", "scale", "zero"], ["x"]),
            helper.make_node("DequantizeLinear", ["weights_q", "weight_scale", "zero"], ["w"]),
            helper.make_node("Conv", ["x", "w"], ["y"], kernel_shape=[1, 1]),
            helper.make_node("QuantizeLinear", ["y", "scale", "zero"], ["output"]),
        ]
        dtype = TensorProto.UINT8
    else:
        initializers = [numpy_helper.from_array(weights, "weights")]
        nodes = [helper.make_node("Conv", ["input", "weights"], ["output"], kernel_shape=[1, 1])]
        dtype = TensorProto.FLOAT
    graph = helper.make_graph(nodes, "NPU_connection_probe_not_frame_interpolation",
                              [helper.make_tensor_value_info("input", dtype, shape_in)],
                              [helper.make_tensor_value_info("output", dtype, shape_out)], initializers)
    return helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)], ir_version=8,
                             producer_name="Cemu NPU standalone experiment")


def main():
    records = [save_checked(average_model(True), "smoke-average-qdq-u8.onnx"),
               save_checked(average_model(False), "smoke-average-fp32.onnx")]
    path = ROOT / "models/anvil-small-1080p-fp32.onnx"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == "65e871aed25b331e3a3747cf9019942121a94af71997476f5804a24b768cd0d8"
    model = onnx.load(path)
    onnx.checker.check_model(model, full_check=True)
    report = {
        "mode": "offline structure validation only; no inference",
        "onnx_version": onnx.__version__, "fixtures": records,
        "anvil": {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "ir_version": model.ir_version,
            "operators": dict(collections.Counter(n.op_type for n in model.graph.node)),
            "inputs": [{"name": x.name, "shape": [d.dim_value or d.dim_param for d in x.type.tensor_type.shape.dim]} for x in model.graph.input],
            "outputs": [{"name": x.name, "shape": [d.dim_value or d.dim_param for d in x.type.tensor_type.shape.dim]} for x in model.graph.output],
            "note": "Fixed input; exported output metadata has symbolic axes. ORT must resolve its shape/pad/crop graph. HTP support not yet tested.",
        },
    }
    (ROOT / "evidence/model-preparation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
