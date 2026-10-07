#pragma once
#include <windows.h>
#include <filesystem>
#include <stdexcept>
#include <string>

namespace cemu::npu {
inline std::filesystem::path modulePath(HMODULE module) {
    if(!module) throw std::runtime_error("ORT runtime module is not loaded");
    wchar_t path[32768]{};
    const DWORD size=GetModuleFileNameW(module,path,DWORD(std::size(path)));
    if(!size || size>=std::size(path)) throw std::runtime_error("Cannot resolve loaded ORT runtime path");
    return std::filesystem::path(std::wstring(path,size));
}
inline std::string backendName(const std::filesystem::path& directory,const std::filesystem::path& ortLibrary) {
    if(!directory.is_absolute() || !ortLibrary.is_absolute() ||
       !std::filesystem::equivalent(directory,ortLibrary.parent_path()))
        throw std::runtime_error("ORT must be loaded from this experiment's runtime directory");
    if(!std::filesystem::is_regular_file(directory/L"QnnHtp.dll"))
        throw std::runtime_error("QnnHtp.dll is missing beside the ORT runtime");
    // ORT 1.24.4 QNN Windows DlOpen sends absolute narrow paths through
    // std::filesystem::path(char*) and LoadLibraryExA. A UTF-8 absolute path
    // is invalid on a non-UTF-8 system code page. An ASCII basename instead
    // resolves relative to the loaded ORT module, then uses LoadLibraryExW.
    // Verify that directory above; do not depend on or change process CWD/PATH.
    return "QnnHtp.dll";
}
}
