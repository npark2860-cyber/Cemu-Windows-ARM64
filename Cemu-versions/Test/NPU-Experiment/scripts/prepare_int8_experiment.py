"""CPU-only synthetic calibration for an explicitly experimental 1080p U8 QDQ graph.

Use small fully-convolutional proxy inputs to bound preparation cost. Reusing
those ranges at 1080p is a speed/compatibility experiment, NOT quality calibration.
No NPU provider is loaded. The native ARM64 probe will test the full 1080p graph
separately, only during an approved device-use time slot.
"""
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import argparse
import collections
import hashlib
import json
import os
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "quant-tools"), str(ROOT / "model-tools")]
import numpy as np
import onnx
import onnxruntime as ort
from onnx import TensorProto, numpy_helper
from onnxruntime.quantization import CalibrationDataReader, QuantType
from onnxruntime.quantization.calibrate import MinMaxCalibrater
from onnxruntime.quantization.execution_providers.qnn import get_qnn_qdq_config
from onnxruntime.quantization.qdq_quantizer import QDQQuantizer
from onnxruntime.quantization.quant_utils import add_infer_metadata
import prepare_resolution_models as resolution


def cpu_options():
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.add_session_config_entry("session.intra_op.allow_spinning", "0")
    options.add_session_config_entry("session.inter_op.allow_spinning", "0")
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
    return options


class OneThreadMinMax(MinMaxCalibrater):
    def create_inference_session(self):
        self.infer_session = ort.InferenceSession(str(self.augmented_model_path), cpu_options(),
                                                  providers=["CPUExecutionProvider"])
        resolution.require(self.infer_session.get_providers() == ["CPUExecutionProvider"],
                           "Unexpected calibration provider")


class TileReader(CalibrationDataReader):
    def __init__(self, samples):
        self.samples = iter(samples)

    def get_next(self):
        sample = next(self.samples, None)
        return None if sample is None else {"input": sample}


def static_model(source, height, width):
    model = resolution.derive(source, height, width)
    # Original export's constant-only prefix computes exactly this pad vector.
    # Derivation/reference tests already verified that formula and reflect mode.
    del model.graph.node[:47]
    model.graph.initializer.append(numpy_helper.from_array(
        np.array([0, 0, 0, 0, 0, 0, (-height) % 16, (-width) % 16], np.int64),
        "/Cast_1_output_0"))
    onnx.checker.check_model(model, full_check=True)
    inferred = onnx.shape_inference.infer_shapes(model, strict_mode=True, data_prop=True)
    add_infer_metadata(inferred)
    return inferred


def samples(height, width):
    shape = (1, 6, height, width)
    rng = np.random.default_rng(20260929)
    y, x = np.mgrid[:height, :width]
    pattern = np.stack([x / max(width - 1, 1), y / max(height - 1, 1),
                        ((x // 8 + y // 8) % 2)], axis=0).astype(np.float32)
    pair = np.concatenate([pattern, np.roll(pattern, 3, axis=2)], axis=0)[None]
    return [np.zeros(shape, np.float32), np.ones(shape, np.float32), pair,
            rng.random(shape, dtype=np.float32)]


def quantize(model, config, ranges, target):
    quantizer = QDQQuantizer(deepcopy(model), per_channel=config.per_channel, reduce_range=False,
        weight_qType=config.weight_type, activation_qType=config.activation_type,
        tensors_range=deepcopy(ranges), nodes_to_quantize=[], nodes_to_exclude=[],
        op_types_to_quantize=config.op_types_to_quantize, extra_options=deepcopy(config.extra_options))
    quantizer.quantize_model()
    quantizer.model.save_model_to_file(str(target), use_external_data_format=False)
    result = onnx.load(target)
    onnx.checker.check_model(result, full_check=True)
    return result


def audit_qdq(model):
    producers = {out: node for node in model.graph.node for out in node.output}
    consumers = collections.defaultdict(list)
    for node in model.graph.node:
        for inp in node.input:
            consumers[inp].append(node)
    initializers = {value.name: value for value in model.graph.initializer}
    counts = collections.Counter()
    for node in model.graph.node:
        if node.op_type not in {"Conv", "ConvTranspose", "Add", "Pad", "Slice"}:
            continue
        # Data inputs must come from U8 dequantization. Bias uses INT32 accumulators.
        data_count = 2 if node.op_type in {"Conv", "ConvTranspose", "Add"} else 1
        for value in node.input[:data_count]:
            dq = producers.get(value)
            resolution.require(dq is not None and dq.op_type == "DequantizeLinear",
                               f"Unquantized data input: {node.name} / {value}")
            zp = initializers[dq.input[2]]
            resolution.require(zp.data_type == TensorProto.UINT8, "Expected U8 quantization")
            scale = numpy_helper.to_array(initializers[dq.input[1]])
            resolution.require(np.all(np.isfinite(scale)) and np.all(scale > 0), "Invalid scale")
            if node.op_type in {"Conv", "ConvTranspose"} and value == node.input[1]:
                resolution.require(initializers[dq.input[0]].data_type == TensorProto.UINT8,
                                   "Convolution weights are not U8")
        for value in node.output:
            resolution.require(any(n.op_type == "QuantizeLinear" for n in consumers[value]),
                               "Unquantized core output: " + node.name)
        counts[node.op_type] += 1
    resolution.require(counts == {"Conv": 32, "ConvTranspose": 4, "Add": 17, "Pad": 1, "Slice": 2},
                       "Unexpected quantized network coverage")
    for node in model.graph.node:
        if node.op_type in {"QuantizeLinear", "DequantizeLinear"}:
            scale = numpy_helper.to_array(initializers[node.input[1]])
            resolution.require(np.all(np.isfinite(scale)) and np.all(scale > 0), "Invalid QDQ scale")
    return dict(counts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true", help="Prepare with small, one-thread CPU inference")
    args = parser.parse_args()
    if not args.prepare:
        print("Use --prepare for CPU-only synthetic calibration. No model execution started.")
        return
    resolution.require(ort.__version__ == "1.24.4", "Unexpected tool version")
    resolution.require(resolution.sha(resolution.ORIGINAL) == resolution.SOURCE_SHA, "Original model changed")
    started = time.perf_counter()
    folder = ROOT / "evidence" / ("int8-prep-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    folder.mkdir()
    # ONNX's native infer_shapes_path has an ANSI-path issue on this Windows build.
    # Keep all of its paths relative/ASCII; chdir affects this preparation process only.
    os.chdir(folder)
    source = onnx.load(resolution.ORIGINAL)
    # Small tiles: matching pad height and the same 84 CNN operations/weights.
    height, width = 136, 240
    resolution.validate(source, resolution.derive(source, height, width), height, width)
    proxy = static_model(source, height, width)
    full = static_model(source, 1080, 1920)
    onnx.save(proxy, folder / "proxy-fp32.onnx")
    onnx.save(full, folder / "1080p-static-fp32.onnx")
    calibration_samples = samples(height, width)
    config = get_qnn_qdq_config(full, TileReader(calibration_samples),
        activation_type=QuantType.QUInt8, weight_type=QuantType.QUInt8,
        per_channel=False, calibration_providers=["CPUExecutionProvider"])
    calibrator = OneThreadMinMax(Path("proxy-fp32.onnx"),
        op_types_to_calibrate=config.op_types_to_quantize,
        augmented_model_path="proxy-augmented.onnx")
    calibrator.augment_graph()
    calibrator.create_inference_session()
    print("Calibrating four synthetic 136x240 samples on one CPU thread...", flush=True)
    calibrator.collect_data(TileReader(calibration_samples))
    ranges = calibrator.compute_data()
    serial_ranges = {name: {"min": np.asarray(data.range_value[0]).tolist(),
                             "max": np.asarray(data.range_value[1]).tolist()}
                     for name, data in ranges.items()}
    (folder / "synthetic-ranges.json").write_text(json.dumps(serial_ranges, indent=2) + "\n", encoding="utf-8")
    output_path = folder / "anvil-1080p-synthetic-u8u8.onnx"
    qdq = quantize(full, config, ranges, output_path)
    coverage = audit_qdq(qdq)
    qproxy = quantize(proxy, config, ranges, folder / "proxy-u8u8.onnx")
    audit_qdq(qproxy)
    # A held-out tiny synthetic pattern checks that quantized output is finite/nonconstant.
    # This is not a visual-quality acceptance test and does not execute the 1080p graph.
    held = np.random.default_rng(17).random((1, 6, height, width), dtype=np.float32)
    reference = ort.InferenceSession(str(folder / "proxy-fp32.onnx"), cpu_options(),
                                    providers=["CPUExecutionProvider"]).run(None, {"input": held})[0]
    candidate = ort.InferenceSession(str(folder / "proxy-u8u8.onnx"), cpu_options(),
                                    providers=["CPUExecutionProvider"]).run(None, {"input": held})[0]
    resolution.require(candidate.shape == (1, 3, height, width) and np.all(np.isfinite(candidate)),
                       "Invalid quantized proxy output")
    resolution.require(float(np.std(candidate)) > 0, "Constant quantized proxy output")
    error = candidate.astype(np.float64) - reference.astype(np.float64)
    report = {"status": "SYNTHETIC_INT8_PREPARED_NOT_NPU_TESTED", "created_at": datetime.now().astimezone().isoformat(),
        "model": output_path.relative_to(ROOT).as_posix(), "sha256": resolution.sha(output_path),
        "model_bytes": output_path.stat().st_size, "source_sha256": resolution.SOURCE_SHA,
        "input_shape": [1, 6, 1080, 1920], "output_shape": [1, 3, 1080, 1920],
        "input_bytes": 49766400, "output_bytes": 24883200,
        "weight_bits": 8, "activation_bits": 8, "storage": "UINT8, per-tensor QDQ; INT32 bias",
        "host_io": "FLOAT32 unchanged from FP16 baseline", "quantized_core_coverage": coverage,
        "quantization_tools": "ORT 1.24.4 x64 CPU, QNN config, QDQQuantizer; ONNX " + onnx.__version__,
        "calibration": {"kind": "synthetic proxy ranges for performance/compatibility only",
                        "proxy_shape": [1, 6, height, width], "samples": 4, "random_seed": 20260929,
                        "patterns": ["all-zero", "all-one", "gradient/checker pair shifted 3px", "uniform noise"],
                        "cpu_threads": 1, "tensors_calibrated": len(serial_ranges),
                        "representative_game_data": False, "full_resolution_calibrated": False},
        "tiny_proxy_validation": {"finite": True, "nonconstant": True, "max_abs_error": float(np.max(np.abs(error))),
                                  "rmse": float(np.sqrt(np.mean(error * error))), "game_quality_claim": False},
        "prepare_seconds": time.perf_counter() - started, "npu_executed": False,
        "full_1080p_inference_executed": False, "quality_validated": False,
        "limitations": "Synthetic low-resolution activation ranges reused at 1080p. May clip real activations and give poor game output. Candidate is for NPU speed/compatibility only, with no Cemu integration or GPU transfers."}
    (folder / "preparation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
