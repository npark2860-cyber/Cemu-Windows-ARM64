#include <onnxruntime_cxx_api.h>
#include <windows.h>
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;
using Clock = std::chrono::steady_clock;
double milliseconds(Clock::time_point start) { return std::chrono::duration<double, std::milli>(Clock::now() - start).count(); }

std::string escaped(const std::string& value) {
    std::ostringstream out;
    for (unsigned char c : value) {
        if (c == '"' || c == '\\') out << '\\' << c;
        else if (c < 32) out << "\\u" << std::hex << std::setw(4) << std::setfill('0') << unsigned(c);
        else out << c;
    }
    return out.str();
}

std::string utf8(const std::wstring& value) {
    int size = WideCharToMultiByte(CP_UTF8, 0, value.data(), int(value.size()), nullptr, 0, nullptr, nullptr);
    std::string result(size, '\0');
    WideCharToMultiByte(CP_UTF8, 0, value.data(), int(value.size()), result.data(), size, nullptr, nullptr);
    return result;
}

struct Arguments {
    fs::path model, directory;
    int runs = 20, warmup = 3;
    bool runHtp = false, expectAverage = false;
};

Arguments arguments(int argc, wchar_t** argv) {
    Arguments result;
    for (int i = 1; i < argc; ++i) {
        std::wstring arg(argv[i]);
        if (arg == L"--run-htp") result.runHtp = true;
        else if (arg == L"--expect-average") result.expectAverage = true;
        else if ((arg == L"--model" || arg == L"--out" || arg == L"--runs" || arg == L"--warmup") && i + 1 < argc) {
            std::wstring value(argv[++i]);
            if (arg == L"--model") result.model = value;
            else if (arg == L"--out") result.directory = value;
            else {
                size_t consumed{};
                int count = std::stoi(value, &consumed);
                if (consumed != value.size()) throw std::runtime_error("Invalid iteration count");
                if (arg == L"--runs") result.runs = count; else result.warmup = count;
            }
        } else throw std::runtime_error("Unknown or incomplete argument");
    }
    if (!result.runHtp || result.model.empty() || result.directory.empty() || result.runs < 1 || result.runs > 200 || result.warmup < 0 || result.warmup > 10)
        throw std::runtime_error("Explicit --run-htp --model PATH --out NEW_DIRECTORY required; runs 1..200, warmup 0..10. No inference was started.");
    return result;
}

size_t elements(const std::vector<int64_t>& shape) {
    size_t count = 1;
    for (int64_t dim : shape) {
        if (dim < 1 || dim > 8192 || count > 100000000 / size_t(dim)) throw std::runtime_error("Invalid or oversized tensor shape");
        count *= size_t(dim);
    }
    return count;
}

double percentile(const std::vector<double>& sorted, double fraction) {
    return sorted[std::min(sorted.size() - 1, size_t(std::ceil(fraction * sorted.size())) - 1)];
}

int wmain(int argc, wchar_t** argv) {
    fs::path outputDirectory;
    try {
        const auto args = arguments(argc, argv);
        if (!fs::is_regular_file(args.model)) throw std::runtime_error("Model missing");
        // The runner supplies an unused run directory. Never overwrite evidence.
        if (!fs::create_directory(args.directory)) throw std::runtime_error("Output directory already exists or cannot be created");
        outputDirectory = args.directory;
        const fs::path backend = L"QnnHtp.dll";
        if (!fs::is_regular_file(backend)) throw std::runtime_error("Run from the prepared ARM64 runtime directory");
        std::cout << "QNN HTP only; CPU fallback disabled. Creating session..." << std::endl;
        Ort::Env env(ORT_LOGGING_LEVEL_INFO, "cemu-npu-probe");
        Ort::SessionOptions options;
        options.SetIntraOpNumThreads(1);
        options.SetInterOpNumThreads(1);
        options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
        options.AddConfigEntry("session.disable_cpu_ep_fallback", "1");
        const auto profilePrefix = args.directory / L"ort-profile";
        options.EnableProfiling(profilePrefix.c_str());
        // HTP is explicit. Do not register QNN CPU/GPU backends or permit ORT CPU fallback.
        options.AppendExecutionProvider("QNN", {
            {"backend_path", "QnnHtp.dll"},
            {"offload_graph_io_quantization", "0"},
            {"enable_htp_fp16_precision", "1"},
            {"htp_performance_mode", "balanced"},
            {"profiling_level", "detailed"},
            {"profiling_file_path", utf8((args.directory / L"qnn-profile.csv").wstring())},
        });
        const auto sessionStart = Clock::now();
        Ort::Session session(env, args.model.c_str(), options);
        const double sessionMs = milliseconds(sessionStart);
        if (session.GetInputCount() != 1 || session.GetOutputCount() != 1) throw std::runtime_error("Probe requires one input and one output");
        Ort::AllocatorWithDefaultOptions allocator;
        auto inputName = session.GetInputNameAllocated(0, allocator);
        auto outputName = session.GetOutputNameAllocated(0, allocator);
        const std::array<const char*, 1> inputNames{inputName.get()}, outputNames{outputName.get()};
        auto inputTypeInfo = session.GetInputTypeInfo(0);
        auto inputInfo = inputTypeInfo.GetTensorTypeAndShapeInfo();
        auto shape = inputInfo.GetShape();
        const size_t count = elements(shape);
        const auto dtype = inputInfo.GetElementType();
        if (dtype != ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT && dtype != ONNX_TENSOR_ELEMENT_DATA_TYPE_UINT8)
            throw std::runtime_error("Only FLOAT and UINT8 input supported");
        if (args.expectAverage && shape != std::vector<int64_t>{1, 6, 32, 32}) throw std::runtime_error("Average oracle is only valid for the supplied 32x32 fixture");
        const auto prepareStart = Clock::now();
        std::vector<float> floatInput(dtype == ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT ? count : 0);
        std::vector<uint8_t> byteInput(dtype == ONNX_TENSOR_ELEMENT_DATA_TYPE_UINT8 ? count : 0);
        for (size_t i = 0; i < count; ++i) {
            const auto value = uint8_t((i * 7 + 11) % 251);
            if (dtype == ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT) floatInput[i] = float(value) / 255.0f;
            else byteInput[i] = value;
        }
        auto memory = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
        auto input = dtype == ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT
            ? Ort::Value::CreateTensor<float>(memory, floatInput.data(), count, shape.data(), shape.size())
            : Ort::Value::CreateTensor<uint8_t>(memory, byteInput.data(), count, shape.data(), shape.size());
        const double prepareMs = milliseconds(prepareStart);
        const auto invoke = [&] { return session.Run(Ort::RunOptions{nullptr}, inputNames.data(), &input, 1, outputNames.data(), 1); };
        const auto firstStart = Clock::now();
        auto outputs = invoke();
        const double firstMs = milliseconds(firstStart);
        for (int i = 0; i < args.warmup; ++i) outputs = invoke();
        std::vector<double> times;
        for (int i = 0; i < args.runs; ++i) {
            const auto start = Clock::now();
            outputs = invoke();
            times.push_back(milliseconds(start));
        }
        const auto validationStart = Clock::now();
        const auto outputInfo = outputs[0].GetTensorTypeAndShapeInfo();
        const auto outputShape = outputInfo.GetShape();
        const auto outputType = outputInfo.GetElementType();
        const auto outputCount = elements(outputShape);
        if (args.expectAverage && outputShape != std::vector<int64_t>{1, 3, 32, 32}) throw std::runtime_error("Unexpected smoke output shape");
        double checksum{}, maximumError{};
        for (size_t i = 0; i < outputCount; ++i) {
            double actual{};
            if (outputType == ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT) actual = outputs[0].GetTensorData<float>()[i];
            else if (outputType == ONNX_TENSOR_ELEMENT_DATA_TYPE_UINT8) actual = outputs[0].GetTensorData<uint8_t>()[i];
            else throw std::runtime_error("Unsupported output type");
            if (!std::isfinite(actual)) throw std::runtime_error("Non-finite output");
            checksum += actual;
            if (args.expectAverage) {
                const double a = dtype == ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT ? double(floatInput[i]) : double(byteInput[i]);
                const double b = dtype == ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT ? double(floatInput[i + 3072]) : double(byteInput[i + 3072]);
                maximumError = std::max(maximumError, std::abs(actual - (a + b) * 0.5));
            }
        }
        const double validationMs = milliseconds(validationStart);
        if (args.expectAverage && maximumError > (dtype == ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT ? 0.002 : 1.0))
            throw std::runtime_error("Smoke output differs from independent arithmetic oracle");
        auto profile = session.EndProfilingAllocated(allocator);
        std::sort(times.begin(), times.end());
        const double mean = std::accumulate(times.begin(), times.end(), 0.0) / times.size();
        const size_t outputBytes = outputCount * (outputType == ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT ? sizeof(float) : sizeof(uint8_t));
        std::ofstream raw(args.directory / L"output.bin", std::ios::binary);
        raw.write(static_cast<const char*>(outputs[0].GetTensorRawData()), std::streamsize(outputBytes));
        if (!raw) throw std::runtime_error("Could not save output tensor");
        std::ofstream report(args.directory / L"result.json");
        report << std::setprecision(12)
            << "{\n  \"status\": \"inference_completed_profile_verification_pending\","
            << "\n  \"ort_version\": \"" << escaped(OrtGetApiBase()->GetVersionString()) << "\","
            << "\n  \"backend\": \"QnnHtp.dll\", \"cpu_fallback_disabled\": true,"
            << "\n  \"synthetic_input\": true, \"frame_interpolation_quality_validated\": false,"
            << "\n  \"model\": \"" << escaped(utf8(args.model.wstring())) << "\","
            << "\n  \"profile\": \"" << escaped(profile.get()) << "\","
            << "\n  \"session_create_ms\": " << sessionMs << ", \"input_prepare_ms\": " << prepareMs << ","
            << "\n  \"first_run_ms\": " << firstMs << ", \"warmup_runs\": " << args.warmup << ", \"measured_runs\": " << args.runs << ","
            << "\n  \"run_mean_ms\": " << mean << ", \"run_p50_ms\": " << percentile(times, 0.5) << ", \"run_p95_ms\": " << percentile(times, 0.95) << ","
            << "\n  \"run_min_ms\": " << times.front() << ", \"run_max_ms\": " << times.back() << ","
            << "\n  \"input_bytes\": " << count * (dtype == ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT ? 4 : 1) << ", \"output_bytes\": " << outputBytes << ","
            << "\n  \"output_validation_ms\": " << validationMs << ", \"checksum\": " << checksum << ","
            << "\n  \"average_oracle_checked\": " << (args.expectAverage ? "true" : "false") << ", \"maximum_oracle_error\": " << maximumError << ","
            << "\n  \"timing_scope\": \"ORT Run wall time including output allocation, host transfers/RPC and detailed profiling; excludes Vulkan transfers, motion estimation and present\"\n}\n";
        if (!report) throw std::runtime_error("Could not save result");
        std::cout << "Completed. Mean " << mean << " ms, p95 " << percentile(times, 0.95)
                  << " ms. Check execution providers in ORT profile before declaring HTP success." << std::endl;
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAILED: " << error.what() << std::endl;
        if (!outputDirectory.empty()) {
            std::ofstream file(outputDirectory / L"failure.json");
            file << "{\"status\":\"failed\",\"error\":\"" << escaped(error.what()) << "\"}\n";
        }
        return 1;
    }
}
