#include "ort_paths.h"
#include <fstream>
#include <iostream>

int wmain(int argc,wchar_t** argv) {
    try {
        if(argc!=2) throw std::runtime_error("expected workspace test directory");
        const auto root=std::filesystem::absolute(argv[1]);
        const auto directory=root/L"한글 경로";
        std::filesystem::create_directories(directory);
        std::ofstream(directory/L"QnnHtp.dll",std::ios::binary)<<"path test fixture, not a DLL";
        unsigned checks=0;
        auto expect=[&](bool ok){if(!ok) throw std::runtime_error("path regression check failed");++checks;};
        const auto qnn=directory/L"QnnHtp.dll";
        const auto wide=qnn.wstring();
        const int length=WideCharToMultiByte(CP_UTF8,0,wide.data(),int(wide.size()),nullptr,0,nullptr,nullptr);
        std::string oldPath(length,'\0');
        WideCharToMultiByte(CP_UTF8,0,wide.data(),int(wide.size()),oldPath.data(),length,nullptr,nullptr);
        bool oldThrows=false,oldRoundtrips=false;
        try {oldRoundtrips=std::filesystem::path(oldPath).wstring()==wide;}
        catch(const std::exception& e) {oldThrows=true;std::cout<<"old_path_exception="<<e.what()<<'\n';}
        std::cout<<"process_acp="<<GetACP()<<" old_path_throws="<<oldThrows<<" old_path_roundtrips="<<oldRoundtrips<<'\n';
        expect(std::filesystem::is_regular_file(qnn));
        const auto name=cemu::npu::backendName(directory,directory/L"onnxruntime.dll");
        expect(name=="QnnHtp.dll");
        // Mirror ORT's relative branch without loading any DLL or device.
        const auto resolved=directory/std::filesystem::path(name);
        expect(std::filesystem::equivalent(resolved,qnn));
        bool rejected=false;
        try {cemu::npu::backendName(directory,root/L"onnxruntime.dll");} catch(const std::exception&){rejected=true;}
        expect(rejected);
        rejected=false;
        try {cemu::npu::backendName(L"relative",directory/L"onnxruntime.dll");} catch(const std::exception&){rejected=true;}
        expect(rejected);
        rejected=false;
        try {cemu::npu::backendName(root,root/L"onnxruntime.dll");} catch(const std::exception&){rejected=true;}
        expect(rejected);
        expect(std::filesystem::equivalent(cemu::npu::modulePath(GetModuleHandleW(nullptr)),argv[0]));
        std::cout<<"ORT_PATH_TESTS_PASSED checks="<<checks<<" gpu_npu_executed=false\n";
        return 0;
    } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}
