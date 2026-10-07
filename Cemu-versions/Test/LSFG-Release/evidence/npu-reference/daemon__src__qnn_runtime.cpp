#include "qnn_runtime.hpp"
#include <algorithm>
#include <cmath>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <mutex>
#include <stdexcept>
#ifdef HEXSCALE_ENABLE_QNN
#include <CPU/QnnCpuCommon.h>
#include <QnnInterface.h>
#include <System/QnnSystemInterface.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <dlfcn.h>
#endif
#endif

namespace hexscale::qnn {
#ifdef HEXSCALE_ENABLE_QNN
namespace {
void *load_library(const std::string &name) {
#ifdef _WIN32
    return reinterpret_cast<void *>(
        LoadLibraryExW(std::filesystem::path(name).c_str(), nullptr,
                       LOAD_LIBRARY_SEARCH_DEFAULT_DIRS | LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR));
#else
    return dlopen(name.c_str(), RTLD_NOW | RTLD_LOCAL);
#endif
}
void unload(void *handle) {
    if (!handle)
        return;
#ifdef _WIN32
    FreeLibrary(static_cast<HMODULE>(handle));
#else
    dlclose(handle);
#endif
}
void *symbol(void *handle, const char *name) {
#ifdef _WIN32
    return reinterpret_cast<void *>(GetProcAddress(static_cast<HMODULE>(handle), name));
#else
    return dlsym(handle, name);
#endif
}
void check(Qnn_ErrorHandle_t code, const char *operation) {
    if (code != QNN_SUCCESS)
        throw std::runtime_error(std::string(operation) + " failed: QNN code " +
                                 std::to_string(code));
}
template <class F> decltype(auto) tensor(Qnn_Tensor_t &t, F f) {
    if (t.version == QNN_TENSOR_VERSION_1)
        return f(t.v1);
    if (t.version == QNN_TENSOR_VERSION_2)
        return f(t.v2);
    throw std::runtime_error("Unsupported QNN tensor version");
}
struct OwnedTensor {
    Qnn_Tensor_t value{};
    TensorSpec spec;
    std::vector<uint32_t> dims;
    std::vector<uint8_t> storage;
    explicit OwnedTensor(const Qnn_Tensor_t &source) : value(source) {
        tensor(value, [&](auto &t) {
            if (t.dataFormat != QNN_TENSOR_DATA_FORMAT_FLAT_BUFFER || t.rank == 0 || t.rank > 8 ||
                !t.dimensions)
                throw std::runtime_error("Only static flat QNN tensors of rank 1..8 are supported");
            spec.name = t.name ? t.name : "";
            dims.assign(t.dimensions, t.dimensions + t.rank);
            spec.dimensions = dims;
            spec.elements = 1;
            for (auto d : dims) {
                if (!d || spec.elements > 64 * 1024 * 1024 / d)
                    throw std::runtime_error("Invalid/oversized tensor shape");
                spec.elements *= d;
            }
            spec.data_type = t.dataType;
            size_t width = 0;
            if (t.dataType == QNN_DATATYPE_FLOAT_32)
                width = 4;
            else if (t.dataType == QNN_DATATYPE_UFIXED_POINT_8 ||
                     t.dataType == QNN_DATATYPE_SFIXED_POINT_8) {
                width = 1;
                auto &q = t.quantizeParams;
                if (q.quantizationEncoding == QNN_QUANTIZATION_ENCODING_SCALE_OFFSET) {
                    spec.scale = q.scaleOffsetEncoding.scale;
                    spec.offset = q.scaleOffsetEncoding.offset;
                } else if (q.quantizationEncoding == QNN_QUANTIZATION_ENCODING_BW_SCALE_OFFSET &&
                           q.bwScaleOffsetEncoding.bitwidth == 8) {
                    spec.scale = q.bwScaleOffsetEncoding.scale;
                    spec.offset = q.bwScaleOffsetEncoding.offset;
                } else
                    throw std::runtime_error(
                        "Only per-tensor 8-bit scale/offset IO quantization is supported");
                if (!std::isfinite(spec.scale) || spec.scale <= 0)
                    throw std::runtime_error("Invalid tensor quantization scale");
            } else
                throw std::runtime_error(
                    "Unsupported IO datatype; use float32 or per-tensor W8A8 IO");
            spec.bytes = width * spec.elements;
            storage.resize(spec.bytes);
        });
        if (value.version == QNN_TENSOR_VERSION_2) {
            if (value.v2.isDynamicDimensions)
                for (size_t i = 0; i < dims.size(); ++i)
                    if (value.v2.isDynamicDimensions[i])
                        throw std::runtime_error("Dynamic IO shapes are unsupported");
            value.v2.isDynamicDimensions = nullptr;
        }
        bind();
    }
    void bind() {
        tensor(value, [&](auto &t) {
            t.name = spec.name.c_str();
            t.dimensions = dims.data();
            t.memType = QNN_TENSORMEMTYPE_RAW;
            t.clientBuf = {storage.data(), static_cast<uint32_t>(storage.size())};
        });
    }
    void encode(std::span<const float> input) {
        if (input.size() != spec.elements)
            throw std::runtime_error("Input element count differs from context tensor");
        for (size_t i = 0; i < input.size(); ++i) {
            if (!std::isfinite(input[i]))
                throw std::runtime_error("Nonfinite model input");
            if (spec.data_type == QNN_DATATYPE_FLOAT_32)
                std::memcpy(storage.data() + i * 4, &input[i], 4);
            else {
                const float low = spec.data_type == QNN_DATATYPE_UFIXED_POINT_8 ? 0.f : -128.f;
                const float high = spec.data_type == QNN_DATATYPE_UFIXED_POINT_8 ? 255.f : 127.f;
                float q = std::clamp(
                    std::round(input[i] / spec.scale - static_cast<float>(spec.offset)), low, high);
                storage[i] = static_cast<uint8_t>(static_cast<int>(q));
            }
        }
    }
    std::vector<float> decode() const {
        std::vector<float> result(spec.elements);
        for (size_t i = 0; i < result.size(); ++i) {
            if (spec.data_type == QNN_DATATYPE_FLOAT_32)
                std::memcpy(&result[i], storage.data() + i * 4, 4);
            else {
                int q = spec.data_type == QNN_DATATYPE_UFIXED_POINT_8
                            ? storage[i]
                            : static_cast<int8_t>(storage[i]);
                result[i] = spec.scale * (static_cast<float>(q) + spec.offset);
            }
            if (!std::isfinite(result[i]))
                throw std::runtime_error("Nonfinite QNN graph output");
        }
        return result;
    }
};
} // namespace
#endif
struct Runtime::Impl {
    std::string error;
    std::vector<TensorSpec> input_specs, output_specs;
    std::mutex mutex;
#ifdef HEXSCALE_ENABLE_QNN
    void *backend_lib{}, *system_lib{};
    QnnInterface_t provider{};
    QNN_INTERFACE_VER_TYPE api{};
    QnnSystemDlc_Handle_t dlc{};
    QnnSystemContext_GraphInfo_t *dlc_graphs{};
    uint32_t dlc_count{};
    QNN_SYSTEM_INTERFACE_VER_TYPE system{};
    Qnn_BackendHandle_t backend{};
    Qnn_DeviceHandle_t device{};
    Qnn_ContextHandle_t context{};
    Qnn_GraphHandle_t graph{};
    QnnSystemContext_Handle_t system_context{};
    std::vector<std::unique_ptr<OwnedTensor>> in, out;
    // Retain metadata backing storage through context destruction.
    std::vector<char> binary;
    void clear_graph() {
        graph = nullptr;
        if (context && api.contextFree)
            api.contextFree(context, nullptr);
        context = nullptr;
        in.clear();
        out.clear();
        input_specs.clear();
        output_specs.clear();
        if (system_context && system.systemContextFree)
            system.systemContextFree(system_context);
        system_context = nullptr;
        binary.clear();
        if (dlc_graphs) {
            for (uint32_t i = 0; i < dlc_count; ++i) {
                auto &g = dlc_graphs[i].graphInfoV1;
                std::free(const_cast<char *>(g.graphName));
                std::free(g.graphInputs);
                std::free(g.graphOutputs);
            }
            std::free(dlc_graphs);
        }
        dlc_graphs = nullptr;
        dlc_count = 0;
        if (dlc && system.systemDlcFree)
            system.systemDlcFree(dlc);
        dlc = nullptr;
    }
    void clear() {
        clear_graph();
        if (device && api.deviceFree)
            api.deviceFree(device);
        if (backend && api.backendFree)
            api.backendFree(backend);
        device = nullptr;
        backend = nullptr;
        unload(system_lib);
        unload(backend_lib);
        system_lib = backend_lib = nullptr;
        api = {};
        system = {};
    }
#endif
};
Runtime::Runtime() : impl_(std::make_unique<Impl>()) {}
Runtime::~Runtime() { close(); }
void Runtime::close() {
    std::lock_guard lock(impl_->mutex);
#ifdef HEXSCALE_ENABLE_QNN
    impl_->clear();
#endif
}
bool Runtime::ready() const {
#ifdef HEXSCALE_ENABLE_QNN
    return impl_->graph != nullptr;
#else
    return false;
#endif
}
uint32_t Runtime::backend_id() const {
#ifdef HEXSCALE_ENABLE_QNN
    return impl_->backend ? impl_->provider.backendId : 0;
#else
    return 0;
#endif
}
const std::string &Runtime::error() const { return impl_->error; }
const std::vector<TensorSpec> &Runtime::inputs() const { return impl_->input_specs; }
const std::vector<TensorSpec> &Runtime::outputs() const { return impl_->output_specs; }
bool Runtime::open(const std::string &backend_library, const std::string &system_library) {
    std::lock_guard lock(impl_->mutex);
#ifndef HEXSCALE_ENABLE_QNN
    impl_->error = "Built without HEXSCALE_ENABLE_QNN; configure QNN_SDK_ROOT and rebuild";
    return false;
#else
    impl_->clear();
    impl_->error.clear();
    try {
        std::filesystem::path path(backend_library);
#ifdef _WIN32
        if (!path.is_absolute())
            path = std::filesystem::absolute(path);
        const char *sysname = "QnnSystem.dll";
#else
        const char *sysname = "libQnnSystem.so";
#endif
        auto sys = system_library.empty()
                       ? (path.has_parent_path() ? path.parent_path() / sysname
                                                 : std::filesystem::path(sysname))
                       : std::filesystem::path(system_library);
        impl_->backend_lib = load_library(path.string());
        if (!impl_->backend_lib)
            throw std::runtime_error("Cannot load QNN backend: " + path.string());
        impl_->system_lib = load_library(sys.string());
        if (!impl_->system_lib)
            throw std::runtime_error("Cannot load QNN System library: " + sys.string());
        using GetProviders = Qnn_ErrorHandle_t (*)(const QnnInterface_t ***, uint32_t *);
        using GetSystem = Qnn_ErrorHandle_t (*)(const QnnSystemInterface_t ***, uint32_t *);
        auto get =
            reinterpret_cast<GetProviders>(symbol(impl_->backend_lib, "QnnInterface_getProviders"));
        auto getsys = reinterpret_cast<GetSystem>(
            symbol(impl_->system_lib, "QnnSystemInterface_getProviders"));
        if (!get || !getsys)
            throw std::runtime_error("Missing QNN interface provider exports");
        const QnnInterface_t **providers = nullptr;
        uint32_t count = 0;
        check(get(&providers, &count), "QnnInterface_getProviders");
        for (uint32_t i = 0; i < count; ++i)
            if (providers[i] &&
                providers[i]->apiVersion.coreApiVersion.major == QNN_API_VERSION_MAJOR &&
                providers[i]->apiVersion.coreApiVersion.minor >= QNN_API_VERSION_MINOR) {
                impl_->provider = *providers[i];
                impl_->api = providers[i]->QNN_INTERFACE_VER_NAME;
                break;
            }
        const QnnSystemInterface_t **systems = nullptr;
        count = 0;
        check(getsys(&systems, &count), "QnnSystemInterface_getProviders");
        for (uint32_t i = 0; i < count; ++i)
            if (systems[i] && systems[i]->systemApiVersion.major == QNN_SYSTEM_API_VERSION_MAJOR &&
                systems[i]->systemApiVersion.minor >= QNN_SYSTEM_API_VERSION_MINOR) {
                impl_->system = systems[i]->QNN_SYSTEM_INTERFACE_VER_NAME;
                break;
            }
        auto &a = impl_->api;
        auto &s = impl_->system;
        if (!a.backendCreate || !a.backendFree || !a.contextCreateFromBinary || !a.contextFree ||
            !a.graphRetrieve || !a.graphExecute || !s.systemContextCreate ||
            !s.systemContextGetBinaryInfo || !s.systemContextFree)
            throw std::runtime_error("SDK/runtime API version mismatch or incomplete interface");
        check(a.backendCreate(nullptr, nullptr, &impl_->backend), "backendCreate");
        if (a.deviceCreate) {
            auto code = a.deviceCreate(nullptr, nullptr, &impl_->device);
            if (code != QNN_SUCCESS && code != QNN_DEVICE_ERROR_UNSUPPORTED_FEATURE)
                check(code, "deviceCreate");
        }
        return true;
    } catch (const std::exception &e) {
        impl_->error = e.what();
        impl_->clear();
        return false;
    }
#endif
}
bool Runtime::load(const std::string &path, const std::string &requested_graph) {
    std::lock_guard lock(impl_->mutex);
#ifndef HEXSCALE_ENABLE_QNN
    impl_->error = "QNN support is not compiled in";
    return false;
#else
    impl_->clear_graph();
    impl_->error.clear();
    try {
        if (!impl_->backend)
            throw std::runtime_error("QNN backend is not initialized");
        bool is_dlc = std::filesystem::path(path).extension() == ".dlc";
#ifdef _WIN32
        if (!is_dlc && impl_->provider.backendId == QNN_BACKEND_ID_CPU)
            throw std::runtime_error("Use DLC for the Windows QNN CPU backend: QAIRT 2.45 context "
                                     "deserialization crashes in the vendor runtime");
#endif
        QnnSystemContext_GraphInfo_t *graphs = nullptr;
        uint32_t count = 0;
        if (is_dlc) {
            if (!impl_->system.systemDlcCreateFromFile || !impl_->system.systemDlcComposeGraphs ||
                !impl_->api.contextCreate || !impl_->api.graphFinalize)
                throw std::runtime_error("Runtime does not support DLC composition");
            check(impl_->system.systemDlcCreateFromFile(nullptr, path.c_str(), &impl_->dlc),
                  "systemDlcCreateFromFile");
            check(impl_->api.contextCreate(impl_->backend, impl_->device, nullptr, &impl_->context),
                  "contextCreate");
            check(impl_->system.systemDlcComposeGraphs(impl_->dlc, nullptr, 0, impl_->backend,
                                                       impl_->context, impl_->provider,
                                                       QNN_SYSTEM_CONTEXT_GRAPH_INFO_VERSION_1,
                                                       &impl_->dlc_graphs, &impl_->dlc_count),
                  "systemDlcComposeGraphs");
            graphs = impl_->dlc_graphs;
            count = impl_->dlc_count;
        } else {
            std::ifstream file(path, std::ios::binary | std::ios::ate);
            auto size = file.tellg();
            if (!file || size <= 0 || size > 1024LL * 1024 * 1024)
                throw std::runtime_error("Context missing, empty or exceeds 1 GiB: " + path);
            impl_->binary.resize(static_cast<size_t>(size));
            file.seekg(0);
            if (!file.read(impl_->binary.data(), size))
                throw std::runtime_error("Failed to read complete context");
            check(impl_->system.systemContextCreate(&impl_->system_context), "systemContextCreate");
            const QnnSystemContext_BinaryInfo_t *info = nullptr;
            Qnn_ContextBinarySize_t info_size = 0;
            check(impl_->system.systemContextGetBinaryInfo(impl_->system_context,
                                                           impl_->binary.data(),
                                                           impl_->binary.size(), &info, &info_size),
                  "systemContextGetBinaryInfo");
            if (!info)
                throw std::runtime_error("No QNN context metadata");
            switch (info->version) {
            case QNN_SYSTEM_CONTEXT_BINARY_INFO_VERSION_1:
                graphs = info->contextBinaryInfoV1.graphs;
                count = info->contextBinaryInfoV1.numGraphs;
                break;
            case QNN_SYSTEM_CONTEXT_BINARY_INFO_VERSION_2:
                graphs = info->contextBinaryInfoV2.graphs;
                count = info->contextBinaryInfoV2.numGraphs;
                break;
            case QNN_SYSTEM_CONTEXT_BINARY_INFO_VERSION_3:
                graphs = info->contextBinaryInfoV3.graphs;
                count = info->contextBinaryInfoV3.numGraphs;
                break;
            default:
                throw std::runtime_error("Unsupported context metadata version");
            }
        }
        if (!graphs || !count || count > 64)
            throw std::runtime_error("Invalid graph table");
        if (requested_graph.empty() && count != 1)
            throw std::runtime_error("Multi-graph context requires an explicit graph name");
        std::string name;
        bool found = false;
        auto select = [&](const auto &g) {
            if (!g.graphName)
                return;
            if (!requested_graph.empty() && requested_graph != g.graphName)
                return;
            if (!g.numGraphInputs || !g.numGraphOutputs || g.numGraphInputs > 16 ||
                g.numGraphOutputs > 16 || !g.graphInputs || !g.graphOutputs)
                throw std::runtime_error("Invalid graph IO table");
            name = g.graphName;
            found = true;
            for (uint32_t j = 0; j < g.numGraphInputs; ++j)
                impl_->in.push_back(std::make_unique<OwnedTensor>(g.graphInputs[j]));
            for (uint32_t j = 0; j < g.numGraphOutputs; ++j)
                impl_->out.push_back(std::make_unique<OwnedTensor>(g.graphOutputs[j]));
        };
        for (uint32_t i = 0; i < count && !found; ++i)
            switch (graphs[i].version) {
            case QNN_SYSTEM_CONTEXT_GRAPH_INFO_VERSION_1:
                select(graphs[i].graphInfoV1);
                break;
            case QNN_SYSTEM_CONTEXT_GRAPH_INFO_VERSION_2:
                select(graphs[i].graphInfoV2);
                break;
            case QNN_SYSTEM_CONTEXT_GRAPH_INFO_VERSION_3:
                select(graphs[i].graphInfoV3);
                break;
            default:
                throw std::runtime_error("Unsupported graph metadata version");
            }
        if (!found)
            throw std::runtime_error("Requested graph was not found");
        if (!is_dlc)
            check(impl_->api.contextCreateFromBinary(impl_->backend, impl_->device, nullptr,
                                                     impl_->binary.data(), impl_->binary.size(),
                                                     &impl_->context, nullptr),
                  "contextCreateFromBinary");
        check(impl_->api.graphRetrieve(impl_->context, name.c_str(), &impl_->graph),
              "graphRetrieve");
        if (is_dlc)
            check(impl_->api.graphFinalize(impl_->graph, nullptr, nullptr), "graphFinalize");
        for (auto &t : impl_->in)
            impl_->input_specs.push_back(t->spec);
        for (auto &t : impl_->out)
            impl_->output_specs.push_back(t->spec);
        return true;
    } catch (const std::exception &e) {
        impl_->error = e.what();
        impl_->clear_graph();
        return false;
    }
#endif
}
bool Runtime::execute(const std::vector<std::vector<float>> &input,
                      std::vector<std::vector<float>> &output) {
    std::lock_guard lock(impl_->mutex);
    output.clear();
#ifndef HEXSCALE_ENABLE_QNN
    impl_->error = "QNN support is not compiled in";
    return false;
#else
    try {
        if (!impl_->graph || input.size() != impl_->in.size())
            throw std::runtime_error("Graph not loaded or input count mismatch");
        std::vector<Qnn_Tensor_t> inputs, outputs;
        for (size_t i = 0; i < input.size(); ++i) {
            impl_->in[i]->encode(input[i]);
            impl_->in[i]->bind();
            inputs.push_back(impl_->in[i]->value);
        }
        for (auto &t : impl_->out) {
            t->bind();
            std::fill(t->storage.begin(), t->storage.end(), 0);
            outputs.push_back(t->value);
        }
        check(impl_->api.graphExecute(impl_->graph, inputs.data(),
                                      static_cast<uint32_t>(inputs.size()), outputs.data(),
                                      static_cast<uint32_t>(outputs.size()), nullptr, nullptr),
              "graphExecute");
        for (auto &t : impl_->out)
            output.push_back(t->decode());
        impl_->error.clear();
        return true;
    } catch (const std::exception &e) {
        impl_->error = e.what();
        output.clear();
        return false;
    }
#endif
}
} // namespace hexscale::qnn
