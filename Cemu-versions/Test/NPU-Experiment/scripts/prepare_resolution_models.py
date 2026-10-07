"""Derive fixed-resolution ANVIL graphs. CPU-only; no device runtime imported.

Retain the network and its weights byte for byte. Validate the exported padding
and cropping subgraphs separately with ONNX's reference evaluator; infer the CNN
shapes on a temporary copy with the validated constant padding folded.
"""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "model-tools"))
import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper
from onnx.reference import ReferenceEvaluator

ORIGINAL = ROOT / "models/anvil-small-1080p-fp32.onnx"
SOURCE_SHA = "65e871aed25b331e3a3747cf9019942121a94af71997476f5804a24b768cd0d8"
CONSTANTS = {"/Constant": (1080, "height"), "/Constant_4": (1920, "width"),
             "/Constant_22": ([1080], "height"), "/Constant_26": ([1920], "width")}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dims(value_info):
    return [d.dim_value if d.HasField("dim_value") else d.dim_param
            for d in value_info.type.tensor_type.shape.dim]


def set_dims(value_info, shape):
    value_info.type.tensor_type.shape.ClearField("dim")
    for value in shape:
        value_info.type.tensor_type.shape.dim.add().dim_value = value


def derive(source, height, width):
    require(16 <= height <= 2160 and 16 <= width <= 3840, "Unsupported dimensions")
    model = deepcopy(source)
    found = set()
    for node in model.graph.node:
        if node.name not in CONSTANTS:
            continue
        old, axis = CONSTANTS[node.name]
        require(node.op_type == "Constant" and len(node.attribute) == 1,
                "Unexpected export constant")
        tensor = node.attribute[0].t
        before = numpy_helper.to_array(tensor)
        require(np.array_equal(before, np.asarray(old)), "Unexpected source dimensions")
        value = height if axis == "height" else width
        tensor.CopyFrom(numpy_helper.from_array(np.full(before.shape, value, before.dtype)))
        found.add(node.name)
    require(found == CONSTANTS.keys(), "Missing dimension constants")
    set_dims(model.graph.input[0], [1, 6, height, width])
    set_dims(model.graph.output[0], [1, 3, height, width])
    return model


def validate(source, candidate, height, width):
    require(len(source.graph.node) == len(candidate.graph.node) == 142, "Node count changed")
    require(list(source.graph.initializer) == list(candidate.graph.initializer), "Weights changed")
    require(source.opset_import == candidate.opset_import, "Opset changed")
    changed_nodes = []
    for before, after in zip(source.graph.node, candidate.graph.node):
        if before.SerializeToString() != after.SerializeToString():
            require(before.name in CONSTANTS, "Network operation changed: " + before.name)
            restored = deepcopy(after)
            restored.attribute[0].CopyFrom(before.attribute[0])
            require(restored == before, "Non-value part of dimension constant changed")
            changed_nodes.append(before.name)
    require(dims(candidate.graph.input[0]) == [1, 6, height, width], "Input shape mismatch")
    require(dims(candidate.graph.output[0]) == [1, 3, height, width], "Output shape mismatch")

    # This exporter computes the pads using constants, not the image tensor.
    prefix = helper.make_graph(list(candidate.graph.node[:47]), "constant_padding", [],
        [helper.make_tensor_value_info("/Cast_1_output_0", TensorProto.INT64, [8])])
    prefix_model = helper.make_model(prefix, ir_version=8, opset_imports=list(candidate.opset_import))
    pads = ReferenceEvaluator(prefix_model).run(None, {})[0]
    pad_h, pad_w = (-height) % 16, (-width) % 16
    expected_pads = [0, 0, 0, 0, 0, 0, pad_h, pad_w]
    require(pads.tolist() == expected_pads, "Exported padding does not match target resolution")

    # Numerically check reflection orientation on a tiny image, without CNN inference.
    pad_node = candidate.graph.node[47]
    require(pad_node.op_type == "Pad" and list(pad_node.input) == ["input", "/Cast_1_output_0"],
            "Unexpected padding boundary")
    pad_graph = helper.make_graph([pad_node], "reflect_check",
        [helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 1, 17, 19])],
        [helper.make_tensor_value_info(pad_node.output[0], TensorProto.FLOAT,
                                       [1, 1, 17 + pad_h, 19 + pad_w])],
        [numpy_helper.from_array(pads, "/Cast_1_output_0")])
    tile = np.arange(17 * 19, dtype=np.float32).reshape(1, 1, 17, 19)
    padded = ReferenceEvaluator(helper.make_model(pad_graph, ir_version=8,
        opset_imports=list(candidate.opset_import))).run(None, {"input": tile})[0]
    require(np.array_equal(padded, np.pad(tile, ((0, 0), (0, 0), (0, pad_h), (0, pad_w)),
                                        mode="reflect")), "Reflection mismatch")

    # Resolve every CNN tensor statically using the independently checked pad vector.
    folded = deepcopy(candidate)
    del folded.graph.node[:47]
    folded.graph.initializer.append(numpy_helper.from_array(pads, "/Cast_1_output_0"))
    # Infer the output independently rather than trusting our output annotation.
    folded.graph.output[0].type.tensor_type.shape.ClearField("dim")
    for _ in range(4):
        folded.graph.output[0].type.tensor_type.shape.dim.add()
    inferred = onnx.shape_inference.infer_shapes(folded, strict_mode=True, data_prop=True)
    shapes = {v.name: dims(v) for v in [*inferred.graph.input, *inferred.graph.value_info,
                                      *inferred.graph.output]}
    require(shapes["output"] == [1, 3, height, width], "Inferred output differs from target")
    checked_ops = 0
    for node in inferred.graph.node:
        if node.op_type in {"Conv", "ConvTranspose", "Relu", "Add"}:
            for output in node.output:
                require(output in shapes and all(isinstance(x, int) and x > 0 for x in shapes[output]),
                        "Unresolved network shape: " + output)
            if node.op_type == "Add":
                require(shapes[node.input[0]] == shapes[node.input[1]], "Skip connection mismatch")
            checked_ops += 1

    # Check the original crop nodes against a spatial ramp. Broadcast channels cost no extra memory.
    padded_h, padded_w = height + pad_h, width + pad_w
    ramp = np.arange(padded_h * padded_w, dtype=np.float32).reshape(1, 1, padded_h, padded_w)
    tensor = np.broadcast_to(ramp, (1, 3, padded_h, padded_w))
    crop_graph = helper.make_graph(list(candidate.graph.node[132:]), "crop_check",
        [helper.make_tensor_value_info("/out_conv/Conv_output_0", TensorProto.FLOAT,
                                       [1, 3, padded_h, padded_w])],
        [helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, 3, height, width])])
    cropped = ReferenceEvaluator(helper.make_model(crop_graph, ir_version=8,
        opset_imports=list(candidate.opset_import))).run(None, {"/out_conv/Conv_output_0": tensor})[0]
    require(np.array_equal(cropped, tensor[:, :, :height, :width]), "Crop mismatch")
    onnx.checker.check_model(candidate, full_check=True)
    return {"changed_nodes": changed_nodes, "weights_unchanged": True,
            "initializer_count": len(candidate.graph.initializer), "network_ops_shape_checked": checked_ops,
            "pads": pads.tolist(), "padded_spatial_shape": [padded_h, padded_w],
            "input_shape": [1, 6, height, width], "output_shape": [1, 3, height, width],
            "input_bytes": 1 * 6 * height * width * 4, "output_bytes": 1 * 3 * height * width * 4,
            "reflection_and_crop_reference_checked": True, "onnx_checker": "PASS"}


def save_immutable(path, content):
    if path.exists():
        require(path.read_bytes() == content, "Refusing to overwrite different model: " + str(path))
    else:
        path.write_bytes(content)


def main():
    require(sha(ORIGINAL) == SOURCE_SHA, "Unexpected source model hash")
    original = onnx.load(ORIGINAL)
    records = []
    for label, height, width in [("1080p", 1080, 1920), ("720p", 720, 1280), ("540p", 540, 960)]:
        candidate = derive(original, height, width)
        report = validate(original, candidate, height, width)
        if label == "1080p":
            # Baseline executable still uses the untouched original with symbolic output metadata.
            path = ORIGINAL
        else:
            path = ROOT / ("models/anvil-small-" + label + "-fp32.onnx")
            save_immutable(path, candidate.SerializeToString())
        records.append({"resolution": label, "path": path.relative_to(ROOT).as_posix(),
                        "sha256": sha(path), **report})
    # Regression: changing only input/output shapes must be rejected (old 1080p padding remains).
    broken = deepcopy(original)
    set_dims(broken.graph.input[0], [1, 6, 720, 1280])
    set_dims(broken.graph.output[0], [1, 3, 720, 1280])
    try:
        validate(original, broken, 720, 1280)
    except ValueError as error:
        require("padding" in str(error), "Negative test failed for an unrelated reason")
    else:
        raise ValueError("Shape-only edit was incorrectly accepted")
    output = {"status": "OFFLINE_CHECKS_PASSED_NOT_DEVICE_TESTED", "source_sha256": SOURCE_SHA,
              "onnx_version": onnx.__version__, "models": records,
              "shape_only_edit_rejected": True, "full_cnn_numerical_equivalence_tested": False,
              "quality_validated": False, "device_executed": False,
              "precision": "FP32 ONNX weights and host I/O; existing probe requests HTP FP16",
              "limitations": "Static tensor shapes, unchanged weights/operators, and padding/cropping verified. No full CNN inference, quantization, NPU execution, frame alignment or image-quality validation."}
    (ROOT / "evidence/resolution-models.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
