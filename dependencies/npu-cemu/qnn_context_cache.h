#pragma once
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <system_error>
#include <vector>

// Compiled QNN context cache, without ORT/Windows dependencies. A context binary
// is valid only for the source model, the QNN options, and the runtime and
// driver that produced it. The file name hashes all of them, so any change
// selects a new file. A file that still fails to load is removed by the caller
// and regenerated. Every cache failure falls back to the uncached path.
namespace cemu::npu {
class ContextCacheKey {
public:
    ContextCacheKey& add(std::string_view text) {
        mix(text.data(), text.size());
        constexpr char separator = '\0';
        mix(&separator, 1);
        return *this;
    }
    ContextCacheKey& add(const std::vector<char>& bytes) { return add(std::string_view(bytes.data(), bytes.size())); }
    // Runtime files are identified by name, size and write time; a missing file
    // is part of the identity too.
    ContextCacheKey& addFile(const std::filesystem::path& path) {
        std::error_code error;
        const auto size = std::filesystem::file_size(path, error);
        if (error) return add(path.filename().string()).add("missing");
        const auto time = std::filesystem::last_write_time(path, error);
        const auto ticks = error ? 0 : int64_t(time.time_since_epoch().count());
        return add(path.filename().string()).add(std::to_string(size)).add(std::to_string(ticks));
    }
    std::string hex() const {
        char text[17]{};
        std::snprintf(text, sizeof(text), "%016llx", static_cast<unsigned long long>(hash_));
        return text;
    }
private:
    void mix(const char* data, size_t size) {
        for (size_t i = 0; i < size; ++i) { hash_ ^= uint8_t(data[i]); hash_ *= 0x100000001b3ull; }
    }
    uint64_t hash_{0xcbf29ce484222325ull};
};

// Every file this cache writes starts with ContextPrefix.
inline constexpr std::string_view ContextPrefix = "anvil-u8nhwc-";
inline std::filesystem::path contextFileName(const ContextCacheKey& key) {
    return std::filesystem::path(std::string(ContextPrefix) + key.hex() + ".ctx.onnx");
}
// Marks a key that stays uncached on this machine. Written before compiling and
// removed once the context is saved, so it remains after a failed or
// interrupted compile, or when the folder cannot be written.
inline std::filesystem::path disabledMarker(std::filesystem::path context) { return context += ".disabled"; }

inline std::vector<char> readFile(const std::filesystem::path& path) {
    std::ifstream in(path, std::ios::binary | std::ios::ate);
    if (!in) throw std::runtime_error("Cannot open " + path.filename().string());
    const auto end = in.tellg();
    if (end <= 0) throw std::runtime_error("Empty " + path.filename().string());
    std::vector<char> bytes(static_cast<size_t>(end));
    in.seekg(0);
    if (!in.read(bytes.data(), std::streamsize(bytes.size()))) throw std::runtime_error("Cannot read " + path.filename().string());
    return bytes;
}

// Writes beside the target and renames, so a crash never leaves a truncated
// context under the final name. Returns false instead of throwing.
inline bool writeFileReplacing(const std::filesystem::path& path, const void* data, size_t size) noexcept {
    std::error_code error;
    auto partial = path;
    partial += ".partial";
    try {
        std::filesystem::create_directories(path.parent_path(), error);
        if (error) return false;
        {
            std::ofstream out(partial, std::ios::binary | std::ios::trunc);
            if (!out.write(static_cast<const char*>(data), std::streamsize(size))) throw std::runtime_error("write");
            out.close();
            if (!out) throw std::runtime_error("close");
        }
        std::filesystem::rename(partial, path, error);
        if (error) throw std::runtime_error("rename");
        return true;
    } catch (...) {
        std::filesystem::remove(partial, error);
        return false;
    }
}

// Removes every cache file except keep: other keys' contexts and markers, the
// marker of keep's key, and interrupted writes.
inline void removeStaleContexts(const std::filesystem::path& directory, const std::filesystem::path& keep) noexcept {
    try {
        std::error_code error;
        std::vector<std::filesystem::path> stale;
        for (std::filesystem::directory_iterator it(directory, error), end; !error && it != end; it.increment(error)) {
            const auto name = it->path().filename();
            if (name != keep && name.string().rfind(ContextPrefix, 0) == 0) stale.push_back(it->path());
        }
        for (const auto& path : stale) std::filesystem::remove(path, error);
    } catch (...) {}
}
}
